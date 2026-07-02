"""Flask app routes for structured-symptom triage inference."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

from flask import (
    Flask,
    abort,
    jsonify,
    make_response,
    render_template,
    request,
    session,
)

from app.data.load_curated import (
    load_body_system_groups,
    load_category_lookup,
    load_condition_category_mapping,
)
from app.data.symptom_vocabulary import FROZEN_SYMPTOM_ORDER
from app.nlp import NlpRuntime, load_nlp_runtime, run_nlp_cascade
from app.web.inference import (
    InferenceConfig,
    ModelRuntime,
    infer_from_structured_symptoms,
    load_model_runtime,
)
from app.web.safety import (
    SafetyRuntime,
    build_emergency_result,
    evaluate_safety_gate,
    load_safety_runtime,
)
from app.web.storage import ScreeningStore, resolve_db_path

DISCLAIMER_TEXT = (
    "This tool does not provide a medical diagnosis. It suggests how soon, "
    "and which kind of care, may be appropriate based on the symptoms you "
    "described. It can be wrong, and it cannot see your full history. "
    "Always rely on a qualified healthcare professional for diagnosis and "
    "treatment, and seek emergency care directly if your symptoms suddenly "
    "worsen or you are worried."
)
DISCLAIMER_VERSION = "b9-v1"
SESSION_HISTORY_KEY = "held_screening_session_ids"
MAX_HELD_HISTORY = 50
ADMIN_TOKEN_ENV_NAME = "TRIAGE_ADMIN_TOKEN"
SECRET_KEY_ENV_NAME = "FLASK_SECRET_KEY"

RESULT_FIELD_ORDER = (
    "urgency",
    "urgency_message",
    "point_of_care",
    "point_of_care_note",
    "symptoms_understood",
    "areas_to_discuss",
    "seek_sooner_if",
    "low_confidence",
    "emergency_routed",
    "disclaimer",
)

INFERENCE_CONFIG = InferenceConfig(
    areas_count_cap=3,
    areas_probability_floor=0.10,
)

RISK_QUESTION_PROMPTS = {
    "history_of_alcohol_consumption": ("Do you regularly consume alcohol?"),
    "receiving_blood_transfusion": (
        "Have you received a blood transfusion in the past?"
    ),
    "receiving_unsterile_injections": (
        "Have you had injections in a non-clinical or unsterile setting "
        "recently?"
    ),
    "family_history": (
        "Do you have a family history of similar or chronic illness?"
    ),
}

RISK_OPTION_VALUES = {"yes", "no", "prefer_not_to_say"}
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_]+$")
ACRONYM_OVERRIDES = {
    "aids": "AIDS",
    "ct": "CT",
    "ecg": "ECG",
    "ent": "ENT",
    "gi": "GI",
    "hiv": "HIV",
    "icu": "ICU",
    "id": "ID",
    "iv": "IV",
    "mri": "MRI",
    "uti": "UTI",
}


@lru_cache(maxsize=1)
def get_runtime() -> ModelRuntime:
    """Load the bundled inference runtime once per process."""
    return load_model_runtime()


@lru_cache(maxsize=1)
def get_safety_runtime() -> SafetyRuntime:
    """Load deterministic safety rules once per process."""
    return load_safety_runtime()


@lru_cache(maxsize=1)
def get_nlp_runtime() -> NlpRuntime:
    """Load NLP cascade resources once per process."""
    return load_nlp_runtime()


@lru_cache(maxsize=8)
def get_screening_store(db_path_override: str | None) -> ScreeningStore:
    """Load a SQLite screening store for the configured path."""
    store = ScreeningStore(db_path=resolve_db_path(db_path_override))
    store.initialize()
    return store


def create_app() -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get(
        SECRET_KEY_ENV_NAME
    )
    app.config["SCREENING_DB_PATH"] = os.environ.get("TRIAGE_DB_PATH")
    app.jinja_env.filters["humanize_label"] = humanize_label
    get_screening_store(app.config["SCREENING_DB_PATH"])

    def _store() -> ScreeningStore:
        return get_screening_store(app.config["SCREENING_DB_PATH"])

    def _build_result_object(
        selected_symptoms: list[str],
        risk_factor_features: list[str],
        raw_text: str,
        duration_days: str,
        self_severity_1_10: str,
    ) -> dict[str, Any]:
        """Build a terminal result for emergency/non-emergency paths."""
        safety = evaluate_safety_gate(
            runtime=get_safety_runtime(),
            selected_symptoms=selected_symptoms,
            raw_text=raw_text,
        )
        if safety.emergency_routed:
            return build_emergency_result(
                disclaimer_text=DISCLAIMER_TEXT,
                use_crisis_message=safety.use_crisis_message,
            )
        inference_features = _merge_symptom_lists(
            selected_symptoms,
            risk_factor_features,
        )
        return infer_from_structured_symptoms(
            runtime=get_runtime(),
            selected_symptoms=inference_features,
            disclaimer_text=DISCLAIMER_TEXT,
            config=INFERENCE_CONFIG,
            duration_days_raw=duration_days,
            self_severity_raw=self_severity_1_10,
        )

    def _persist_terminal_result(
        *,
        result_object: dict[str, Any],
        entered_structured_symptoms: list[str],
        entered_free_text_symptoms: list[str],
        understood_confirmed_symptoms: list[str],
        understood_unsure_symptoms: list[str],
        risk_answers: dict[str, str],
        unmatched_tokens: list[str],
    ) -> str:
        """Persist one completed screening and append it to held history."""
        screening_session_id = _store().persist_screening(
            entered_structured_symptoms=entered_structured_symptoms,
            entered_free_text_symptoms=entered_free_text_symptoms,
            understood_confirmed_symptoms=understood_confirmed_symptoms,
            understood_unsure_symptoms=understood_unsure_symptoms,
            risk_answers=risk_answers,
            result_object=result_object,
            unmatched_tokens=unmatched_tokens,
            disclaimer_version=DISCLAIMER_VERSION,
        )
        _append_history_session_id(screening_session_id)
        return screening_session_id

    @app.get("/")
    def index() -> str:
        """Render structured symptom intake for real model inference."""
        body_system_groups = load_body_system_groups()
        grouped_symptom_names = {
            symptom_name
            for symptoms in body_system_groups.values()
            for symptom_name in symptoms
        }
        searchable_symptoms = [
            symptom_name
            for symptom_name in FROZEN_SYMPTOM_ORDER
            if symptom_name in grouped_symptom_names
        ]
        return render_template(
            "intake.html",
            symptom_options=searchable_symptoms,
            body_system_groups=body_system_groups,
            risk_question_prompts=RISK_QUESTION_PROMPTS,
        )

    @app.post("/screen")
    def screen() -> str:
        """Run safety-first screen flow and show confirmation when needed."""
        selected_symptoms = _canonicalize_posted_symptoms(
            request.form.getlist("selected_symptoms")
        )
        risk_answers = _extract_risk_answers(request.form)
        risk_factor_features = _risk_features_from_answers(risk_answers)
        raw_text = _coerce_form_text(request.form.get("raw_text", ""))
        duration_days = _coerce_form_text(
            request.form.get("duration_days", "")
        )
        self_severity_1_10 = _coerce_form_text(
            request.form.get("self_severity_1_10", "")
        )

        safety = evaluate_safety_gate(
            runtime=get_safety_runtime(),
            selected_symptoms=selected_symptoms,
            raw_text=raw_text,
        )
        if safety.emergency_routed:
            result_object = build_emergency_result(
                disclaimer_text=DISCLAIMER_TEXT,
                use_crisis_message=safety.use_crisis_message,
            )
            screening_session_id = _persist_terminal_result(
                result_object=result_object,
                entered_structured_symptoms=selected_symptoms,
                entered_free_text_symptoms=[],
                understood_confirmed_symptoms=selected_symptoms,
                understood_unsure_symptoms=[],
                risk_answers=risk_answers,
                unmatched_tokens=[],
            )
            return render_template(
                "result.html",
                result=result_object,
                field_order=RESULT_FIELD_ORDER,
                screening_session_id=screening_session_id,
            )

        cascade = run_nlp_cascade(
            runtime=get_nlp_runtime(),
            raw_text=raw_text,
        )
        understood_candidates = _merge_symptom_lists(
            selected_symptoms,
            cascade.understood_symptoms,
        )
        unsure_candidate_symptoms = _extract_unsure_candidate_symptoms(
            cascade.unsure_candidates
        )

        recheck = evaluate_safety_gate(
            runtime=get_safety_runtime(),
            selected_symptoms=understood_candidates,
            raw_text="",
        )
        if recheck.emergency_routed:
            result_object = build_emergency_result(
                disclaimer_text=DISCLAIMER_TEXT,
                use_crisis_message=recheck.use_crisis_message,
            )
            screening_session_id = _persist_terminal_result(
                result_object=result_object,
                entered_structured_symptoms=selected_symptoms,
                entered_free_text_symptoms=cascade.understood_symptoms,
                understood_confirmed_symptoms=understood_candidates,
                understood_unsure_symptoms=unsure_candidate_symptoms,
                risk_answers=risk_answers,
                unmatched_tokens=cascade.unmatched_tokens,
            )
            return render_template(
                "result.html",
                result=result_object,
                field_order=RESULT_FIELD_ORDER,
                screening_session_id=screening_session_id,
            )

        resolved_duration_days = _resolve_modifier_value(
            explicit_value=duration_days,
            extracted_value=cascade.extracted_duration_days,
        )
        resolved_self_severity = _resolve_modifier_value(
            explicit_value=self_severity_1_10,
            extracted_value=cascade.extracted_self_severity,
        )

        has_raw_text = bool(raw_text.strip())
        no_confirmation_payload = (
            not understood_candidates
            and not cascade.unsure_candidates
            and not cascade.unmatched_tokens
        )
        if not has_raw_text or no_confirmation_payload:
            result_object = _build_result_object(
                selected_symptoms=understood_candidates,
                risk_factor_features=risk_factor_features,
                raw_text=raw_text,
                duration_days=resolved_duration_days,
                self_severity_1_10=resolved_self_severity,
            )
            screening_session_id = _persist_terminal_result(
                result_object=result_object,
                entered_structured_symptoms=selected_symptoms,
                entered_free_text_symptoms=cascade.understood_symptoms,
                understood_confirmed_symptoms=understood_candidates,
                understood_unsure_symptoms=unsure_candidate_symptoms,
                risk_answers=risk_answers,
                unmatched_tokens=cascade.unmatched_tokens,
            )
            return render_template(
                "result.html",
                result=result_object,
                field_order=RESULT_FIELD_ORDER,
                screening_session_id=screening_session_id,
            )

        return render_template(
            "confirm.html",
            understood_symptoms=understood_candidates,
            unsure_candidates=cascade.unsure_candidates,
            unmatched_tokens=cascade.unmatched_tokens,
            raw_text=raw_text,
            duration_days=resolved_duration_days,
            self_severity_1_10=resolved_self_severity,
            risk_answers=risk_answers,
            risk_question_prompts=RISK_QUESTION_PROMPTS,
            entered_structured_symptoms=selected_symptoms,
            entered_free_text_symptoms=cascade.understood_symptoms,
            unsure_candidate_symptoms=unsure_candidate_symptoms,
        )

    @app.post("/result")
    def result() -> str:
        """Render terminal result after deterministic safety and inference."""
        selected_symptoms = _canonicalize_posted_symptoms(
            request.form.getlist("selected_symptoms")
        )
        risk_answers = _extract_risk_answers(request.form)
        risk_factor_features = _risk_features_from_answers(risk_answers)
        raw_text = _coerce_form_text(request.form.get("raw_text", ""))
        duration_days = _coerce_form_text(
            request.form.get("duration_days", "")
        )
        self_severity_1_10 = _coerce_form_text(
            request.form.get("self_severity_1_10", "")
        )

        entered_structured_symptoms = _canonicalize_posted_symptoms(
            request.form.getlist("entered_structured_symptoms")
        )
        if not entered_structured_symptoms:
            entered_structured_symptoms = selected_symptoms
        entered_free_text_symptoms = _canonicalize_posted_symptoms(
            request.form.getlist("entered_free_text_symptoms")
        )
        unsure_candidate_symptoms = _canonicalize_posted_symptoms(
            request.form.getlist("unsure_candidate_symptoms")
        )
        unmatched_tokens = _normalize_unmatched_tokens(
            request.form.getlist("unmatched_tokens")
        )

        result_object = _build_result_object(
            selected_symptoms=selected_symptoms,
            risk_factor_features=risk_factor_features,
            raw_text=raw_text,
            duration_days=duration_days,
            self_severity_1_10=self_severity_1_10,
        )
        screening_session_id = _persist_terminal_result(
            result_object=result_object,
            entered_structured_symptoms=entered_structured_symptoms,
            entered_free_text_symptoms=entered_free_text_symptoms,
            understood_confirmed_symptoms=selected_symptoms,
            understood_unsure_symptoms=unsure_candidate_symptoms,
            risk_answers=risk_answers,
            unmatched_tokens=unmatched_tokens,
        )
        return render_template(
            "result.html",
            result=result_object,
            field_order=RESULT_FIELD_ORDER,
            screening_session_id=screening_session_id,
        )

    @app.get("/history")
    def history() -> str:
        """Render per-held-session screening history with no PII fields."""
        held_session_ids = _get_history_session_ids()
        sessions = _store().list_history(held_session_ids)
        return render_template("history.html", sessions=sessions)

    @app.get("/summary/<session_id>")
    def summary(session_id: str) -> str:
        """Render or download a printable summary from persisted data."""
        held_session_ids = set(_get_history_session_ids())
        if session_id not in held_session_ids:
            abort(404)

        payload = _store().get_result_view(
            session_id=session_id,
            disclaimer_text=DISCLAIMER_TEXT,
        )
        if payload is None:
            abort(404)

        rendered = render_template(
            "summary.html",
            result=payload["result"],
            field_order=RESULT_FIELD_ORDER,
            screening_session_id=session_id,
            created_at=payload["created_at"],
        )
        if request.args.get("download") == "1":
            response = make_response(rendered)
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            response.headers["Content-Disposition"] = (
                f'attachment; filename="triage-summary-{session_id}.html"'
            )
            return response
        return rendered

    @app.get("/admin/analytics")
    def admin_analytics() -> str:
        """Render the access-gated aggregate admin analytics dashboard."""
        _require_admin_token()
        analytics = _store().get_admin_analytics(
            selected_model_name=get_runtime().selected_model_name
        )
        return render_template(
            "admin_analytics.html",
            analytics=analytics,
        )

    @app.get("/api/admin/analytics")
    def admin_analytics_api() -> tuple[Any, int]:
        """Expose admin analytics as aggregate-only JSON."""
        _require_admin_token()
        analytics = _store().get_admin_analytics(
            selected_model_name=get_runtime().selected_model_name
        )
        return jsonify(analytics), 200

    @app.get("/health")
    def health() -> tuple[str, int]:
        """Expose scaffold health and curated artifact loading status."""
        lookup_rows = len(load_category_lookup())
        mapping_rows = len(load_condition_category_mapping())
        runtime = get_runtime()
        payload = {
            "status": "ok",
            "frozen_symptom_columns": len(FROZEN_SYMPTOM_ORDER),
            "lookup_rows": lookup_rows,
            "category_mapping_rows": mapping_rows,
            "bundle_feature_order_verified": (
                tuple(FROZEN_SYMPTOM_ORDER) == runtime.feature_order
            ),
            "selected_model_name": runtime.selected_model_name,
            "uncertainty_threshold": INFERENCE_CONFIG.uncertainty_threshold,
            "safety_solo_trigger_count": len(
                get_safety_runtime().solo_triggers
            ),
            "nlp_lexicon_entries": len(get_nlp_runtime().lexicon_entries),
            "nlp_embeddings_enabled": get_nlp_runtime().embeddings_enabled,
        }
        return jsonify(payload), 200

    return app


def _canonicalize_posted_symptoms(raw_symptoms: list[str]) -> list[str]:
    """Keep only canonical symptom names, preserving frozen order."""
    valid_names = set(FROZEN_SYMPTOM_ORDER)
    selected_set: set[str] = set()
    for item in raw_symptoms:
        symptom_name = str(item or "").strip()
        if symptom_name in valid_names:
            selected_set.add(symptom_name)
    return [
        symptom_name
        for symptom_name in FROZEN_SYMPTOM_ORDER
        if symptom_name in selected_set
    ]


def _merge_symptom_lists(
    base_symptoms: list[str],
    mapped_symptoms: list[str],
) -> list[str]:
    """Merge two symptom lists into one deduplicated frozen-order list."""
    merged_set = set(base_symptoms) | set(mapped_symptoms)
    return [
        symptom_name
        for symptom_name in FROZEN_SYMPTOM_ORDER
        if symptom_name in merged_set
    ]


def _resolve_modifier_value(
    explicit_value: Any,
    extracted_value: int | None,
) -> str:
    """Prefer explicit form input; fall back to extracted free-text value."""
    explicit_text = _coerce_form_text(explicit_value)
    if explicit_text:
        return explicit_text
    if extracted_value is None:
        return ""
    return str(extracted_value)


def _extract_risk_answers(form_data: Any) -> dict[str, str]:
    """Normalize optional risk-factor answers to frozen value options."""
    answers: dict[str, str] = {}
    for feature_name in RISK_QUESTION_PROMPTS:
        raw_value = str(
            form_data.get(f"risk_{feature_name}", "prefer_not_to_say")
        ).strip()
        if raw_value in RISK_OPTION_VALUES:
            answers[feature_name] = raw_value
        else:
            answers[feature_name] = "prefer_not_to_say"
    return answers


def _risk_features_from_answers(risk_answers: dict[str, str]) -> list[str]:
    """Return `H` features that are explicitly marked yes."""
    return [
        feature_name
        for feature_name, answer in risk_answers.items()
        if answer == "yes"
    ]


def _extract_unsure_candidate_symptoms(
    unsure_candidates: list[Any],
) -> list[str]:
    """Flatten unsure candidate targets to canonical symptom names."""
    raw_values: list[str] = []
    for item in unsure_candidates:
        if isinstance(item, dict):
            raw_values.extend(item.get("canonical_targets", []))
            continue
        raw_values.extend(getattr(item, "canonical_targets", []))
    return _canonicalize_posted_symptoms(raw_values)


def _normalize_unmatched_tokens(raw_tokens: list[str]) -> list[str]:
    """Normalize unmatched token payloads for aggregate-only persistence."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_token in raw_tokens:
        token = str(raw_token or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def _coerce_form_text(raw_value: Any) -> str:
    """Normalize form inputs to safe stripped text for route processing."""
    return str(raw_value or "").strip()


def _append_history_session_id(session_id: str) -> None:
    """Track persisted session ids in held browser session history."""
    existing = _get_history_session_ids()
    if session_id in existing:
        return
    updated = [session_id, *existing]
    session[SESSION_HISTORY_KEY] = updated[:MAX_HELD_HISTORY]


def _get_history_session_ids() -> list[str]:
    """Return normalized held session ids from the user cookie session."""
    raw_history = session.get(SESSION_HISTORY_KEY, [])
    if not isinstance(raw_history, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_history:
        session_id = str(item).strip()
        if not session_id or session_id in seen:
            continue
        seen.add(session_id)
        normalized.append(session_id)

    trimmed = normalized[:MAX_HELD_HISTORY]
    session[SESSION_HISTORY_KEY] = trimmed
    return trimmed


def _require_admin_token() -> None:
    """Enforce token-based access control for admin analytics routes."""
    expected_token = os.environ.get(ADMIN_TOKEN_ENV_NAME, "").strip()
    if not expected_token:
        abort(
            503,
            description=(
                f"Set {ADMIN_TOKEN_ENV_NAME} to enable admin analytics."
            ),
        )

    provided_token = request.headers.get("X-Admin-Token", "").strip()
    if not provided_token:
        provided_token = request.args.get("token", "").strip()
    if provided_token != expected_token:
        abort(403)


def humanize_label(raw_value: Any) -> str:
    """Render canonical identifiers as human-readable labels for display."""
    value = str(raw_value).strip()
    if not value:
        return ""
    if not IDENTIFIER_PATTERN.fullmatch(value):
        return value

    tokens = value.replace("_", " ").split()
    normalized_tokens = [
        ACRONYM_OVERRIDES.get(token.lower(), token.lower()) for token in tokens
    ]
    sentence = " ".join(normalized_tokens)
    if not sentence:
        return value
    return sentence[0].upper() + sentence[1:]


if __name__ == "__main__":
    create_app().run()
