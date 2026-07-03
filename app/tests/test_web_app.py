"""Tests for local structured-input web inference flow."""

from __future__ import annotations

import re
import sqlite3

from app.web.app import (
    _canonicalize_posted_symptoms,
    _normalize_unmatched_tokens,
    create_app,
    humanize_label,
)


def test_index_renders_intake_form() -> None:
    """The root route serves structured-symptom input controls."""
    client = create_app().test_client()
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Symptom search and autocomplete" in body
    assert "Grouped symptom checklist" in body
    assert 'name="selected_symptoms"' in body
    assert 'id="symptom_suggestions"' in body
    assert "General &amp; whole-body" in body
    assert 'name="raw_text"' in body
    assert 'name="duration_days"' in body
    assert 'name="self_severity_1_10"' in body
    assert 'name="risk_history_of_alcohol_consumption"' in body
    assert 'name="risk_receiving_blood_transfusion"' in body
    assert 'name="risk_receiving_unsterile_injections"' in body
    assert 'name="risk_family_history"' in body
    assert "extra_marital_contacts" not in body
    assert "you might also have" not in body
    assert 'action="/screen"' in body


def test_health_reports_curated_artifacts() -> None:
    """The health endpoint verifies data artifacts and model bundle load."""
    client = create_app().test_client()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["frozen_symptom_columns"] == 131
    assert payload["lookup_rows"] == 10
    assert payload["category_mapping_rows"] == 41
    assert payload["bundle_feature_order_verified"] is True
    assert payload["selected_model_name"] == "BernoulliNB"
    assert payload["uncertainty_threshold"] == 0.60
    assert payload["safety_solo_trigger_count"] == 11
    assert payload["nlp_lexicon_entries"] == 35
    assert payload["nlp_embeddings_enabled"] is False


def test_result_round_trip_renders_full_result_shape() -> None:
    """Posting structured symptoms returns inferred safe routing output."""
    client = create_app().test_client()
    response = client.post(
        "/result",
        data={
            "selected_symptoms": [
                "itching",
                "skin_rash",
                "nodal_skin_eruptions",
            ]
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "itching" in body
    assert "skin_rash" in body
    assert "nodal_skin_eruptions" in body
    assert "Skin or allergy-related concerns" in body
    assert "Dermatology" in body
    assert "Heart Attack" not in body
    assert "<strong>urgency</strong>" in body
    assert "<strong>urgency_message</strong>" in body
    assert "<strong>point_of_care</strong>" in body
    assert "<strong>point_of_care_note</strong>" in body
    assert "<strong>symptoms_understood</strong>" in body
    assert "<strong>areas_to_discuss</strong>" in body
    assert "<strong>seek_sooner_if</strong>" in body
    assert "<strong>model_confidence</strong>" not in body
    assert "<strong>low_confidence</strong>" in body
    assert "<strong>emergency_routed</strong>" in body
    assert "<strong>disclaimer</strong>" in body


def test_empty_selection_routes_to_uncertainty_path() -> None:
    """Posting no recognised symptoms should return uncertainty output."""
    client = create_app().test_client()
    response = client.post("/result", data={})

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Please see a general physician" in body
    assert "General Physician" in body
    assert "<strong>low_confidence</strong>" in body
    assert "True" in body
    assert "Heart and circulation-related concerns" not in body
    assert "This tool does not provide a medical diagnosis." in body


def test_invalid_inputs_degrade_to_uncertainty_without_errors() -> None:
    """Malformed modifiers and unknown symptoms should not crash routes."""
    client = create_app().test_client()
    response = client.post(
        "/result",
        data={
            "selected_symptoms": ["not_a_real_symptom", "  "],
            "duration_days": "abc",
            "self_severity_1_10": "NaN",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Please see a general physician" in body
    assert "General Physician" in body
    assert "Emergency Department" not in body


def test_screen_handles_invalid_risk_values_gracefully() -> None:
    """Unexpected risk values should safely default and still complete flow."""
    client = create_app().test_client()
    response = client.post(
        "/screen",
        data={
            "raw_text": "   ",
            "risk_family_history": "invalid_option",
            "risk_receiving_unsterile_injections": "__proto__",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Please see a general physician" in body
    assert "General Physician" in body
    assert "Emergency Department" not in body


def test_input_normalizers_tolerate_non_string_payloads() -> None:
    """Canonicalization should ignore None/object payloads safely."""
    canonical = _canonicalize_posted_symptoms(
        [None, " itching ", 123, "not_a_real_symptom"]  # type: ignore[list-item]
    )
    assert canonical == ["itching"]

    unmatched = _normalize_unmatched_tokens(
        [None, " UnknownToken ", 7, "unknowntoken"]  # type: ignore[list-item]
    )
    assert unmatched == ["unknowntoken", "7"]


def test_humanize_label_formats_identifiers_for_ui_display() -> None:
    """Canonical identifiers should be shown as human-readable labels."""
    assert humanize_label("chest_pain") == "Chest pain"
    assert humanize_label("icu_transfer") == "ICU transfer"
    assert humanize_label("already Pretty") == "already Pretty"


def test_structured_red_flag_routes_to_emergency() -> None:
    """Structured red-flag symptoms should short-circuit to emergency."""
    client = create_app().test_client()
    response = client.post(
        "/result",
        data={"selected_symptoms": ["chest_pain"]},
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Emergency Department" in body
    assert "Your symptoms may need emergency care now." in body
    assert "Heart and circulation-related concerns" not in body
    assert "<strong>emergency_routed</strong>" in body
    assert "True" in body
    assert "This tool does not provide a medical diagnosis." in body


def test_danger_phrase_routes_to_emergency() -> None:
    """Danger phrases in raw text should fire emergency routing."""
    client = create_app().test_client()
    response = client.post(
        "/result",
        data={"raw_text": "I have crushing chest pain right now"},
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Emergency Department" in body
    assert "Your symptoms may need emergency care now." in body
    assert "<strong>areas_to_discuss</strong>" in body
    assert "Heart and circulation-related concerns" not in body


def test_negated_red_flag_does_not_trigger_emergency() -> None:
    """Explicit local negation should suppress that red-flag phrase."""
    client = create_app().test_client()
    response = client.post(
        "/result",
        data={
            "selected_symptoms": ["itching"],
            "raw_text": "no chest pain today",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Emergency Department" not in body
    assert "Your symptoms may need emergency care now." not in body


def test_emergency_short_circuits_before_model(monkeypatch) -> None:
    """Safety emergency decision must happen before any model inference."""

    def fail_inference(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("Inference must not run on emergency input.")

    monkeypatch.setattr(
        "app.web.app.infer_from_structured_symptoms",
        fail_inference,
    )

    client = create_app().test_client()
    response = client.post(
        "/result",
        data={"selected_symptoms": ["chest_pain"]},
    )

    assert response.status_code == 200
    assert "Emergency Department" in response.get_data(as_text=True)


def test_urgency_escalates_with_duration_and_severity_modifiers() -> None:
    """Tier-2 route with two modifiers should escalate to high urgency."""
    client = create_app().test_client()
    response = client.post(
        "/result",
        data={
            "selected_symptoms": [
                "acidity",
                "abdominal_pain",
                "indigestion",
            ],
            "duration_days": "14",
            "self_severity_1_10": "8",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "<strong>urgency</strong>" in body
    assert re.search(
        r"<strong>urgency</strong>.*?high",
        body,
        flags=re.DOTALL,
    )
    assert "Please arrange to see the suggested point of care today." in body


def test_screen_shows_confirmation_understood_unsure_unmatched() -> None:
    """Free-text screen should surface understood/unsure/unmatched sets."""
    client = create_app().test_client()
    response = client.post(
        "/screen",
        data={
            "raw_text": "bad cough and stuffy nose flibbertigibbet",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Confirm what we understood" in body
    assert "cough" in body
    assert "runny_nose" in body
    assert "congestion" in body
    assert "flibbertigibbet" in body


def test_screen_preserves_risk_questionnaire_choices() -> None:
    """Confirmation screen should carry optional risk answers forward."""
    client = create_app().test_client()
    response = client.post(
        "/screen",
        data={
            "raw_text": "bad cough",
            "risk_family_history": "yes",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="risk_family_history"' in body
    assert re.search(
        r'name="risk_family_history".*?value="yes".*?selected',
        body,
        flags=re.DOTALL,
    )


def test_screen_extracts_duration_and_severity_for_result_flow() -> None:
    """Free-text extraction should prefill urgency modifiers."""
    client = create_app().test_client()
    response = client.post(
        "/screen",
        data={
            "selected_symptoms": [
                "acidity",
                "abdominal_pain",
                "indigestion",
            ],
            "raw_text": "for two weeks now severe discomfort",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="duration_days"' in body
    assert 'value="14"' in body
    assert 'name="self_severity_1_10"' in body
    assert 'value="8"' in body

    follow_up = client.post(
        "/result",
        data={
            "selected_symptoms": [
                "acidity",
                "abdominal_pain",
                "indigestion",
            ],
            "raw_text": "for two weeks now severe discomfort",
            "duration_days": "14",
            "self_severity_1_10": "8",
        },
    )
    assert follow_up.status_code == 200
    follow_up_body = follow_up.get_data(as_text=True)
    assert "Please arrange to see the suggested point of care today." in (
        follow_up_body
    )


def test_danger_phrase_short_circuits_before_cascade(monkeypatch) -> None:
    """Danger-phrase emergency must fire without depending on NLP mapping."""

    def fail_cascade(*args: object, **kwargs: object) -> object:
        raise AssertionError("NLP cascade should not run on safety emergency.")

    monkeypatch.setattr("app.web.app.run_nlp_cascade", fail_cascade)

    client = create_app().test_client()
    response = client.post(
        "/screen",
        data={"raw_text": "I have crushing chest pain right now"},
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Emergency Department" in body
    assert "Your symptoms may need emergency care now." in body


def test_risk_factor_yes_is_mapped_and_sensitive_field_ignored(
    monkeypatch,
) -> None:
    """Only explicit yes risk answers should map to model input features."""
    captured: dict[str, object] = {}

    def fake_inference(*args: object, **kwargs: object) -> dict[str, object]:
        captured["selected_symptoms"] = kwargs["selected_symptoms"]
        return {
            "urgency": "low",
            "urgency_message": "Test urgency message",
            "point_of_care": "Dermatology",
            "point_of_care_note": "",
            "symptoms_understood": [],
            "areas_to_discuss": [],
            "seek_sooner_if": [],
            "model_confidence": 0.99,
            "low_confidence": False,
            "emergency_routed": False,
            "disclaimer": "Test disclaimer",
        }

    monkeypatch.setattr(
        "app.web.app.infer_from_structured_symptoms",
        fake_inference,
    )

    client = create_app().test_client()
    response = client.post(
        "/result",
        data={
            "selected_symptoms": ["itching"],
            "risk_history_of_alcohol_consumption": "yes",
            "risk_receiving_blood_transfusion": "prefer_not_to_say",
            "risk_receiving_unsterile_injections": "no",
            "risk_extra_marital_contacts": "yes",
        },
    )

    assert response.status_code == 200
    selected = captured["selected_symptoms"]
    assert isinstance(selected, list)
    assert "itching" in selected
    assert "history_of_alcohol_consumption" in selected
    assert "receiving_blood_transfusion" not in selected
    assert "receiving_unsterile_injections" not in selected
    assert "family_history" not in selected
    assert "extra_marital_contacts" not in selected


def test_result_persists_screening_and_history_view(
    monkeypatch,
    tmp_path,
) -> None:
    """Completed screenings persist to SQLite without raw free-text columns."""
    db_path = tmp_path / "triage-b9.sqlite3"
    monkeypatch.setenv("TRIAGE_DB_PATH", str(db_path))
    client = create_app().test_client()

    response = client.post(
        "/result",
        data={
            "selected_symptoms": ["itching", "skin_rash"],
            "raw_text": "I am John and feel itchy",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    match = re.search(r"/summary/([0-9a-f\\-]+)", body)
    assert match is not None
    screening_session_id = match.group(1)

    history_response = client.get("/history")
    assert history_response.status_code == 200
    history_body = history_response.get_data(as_text=True)
    assert screening_session_id in history_body
    assert "low" in history_body
    assert 'class="data-table-scroll"' in history_body

    with sqlite3.connect(db_path) as connection:
        screening_count = connection.execute(
            "SELECT COUNT(*) FROM screening_session"
        ).fetchone()[0]
        triage_count = connection.execute(
            "SELECT COUNT(*) FROM triage_result"
        ).fetchone()[0]
        assert screening_count == 1
        assert triage_count == 1

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(screening_session)"
            ).fetchall()
        }
        assert "raw_text" not in columns
        assert "free_text" not in columns


def test_printable_summary_renders_and_downloads(
    monkeypatch,
    tmp_path,
) -> None:
    """Printable summary route supports both browser and download modes."""
    db_path = tmp_path / "triage-b9-summary.sqlite3"
    monkeypatch.setenv("TRIAGE_DB_PATH", str(db_path))
    client = create_app().test_client()

    result_response = client.post(
        "/result",
        data={"selected_symptoms": ["itching", "skin_rash"]},
    )
    assert result_response.status_code == 200
    result_body = result_response.get_data(as_text=True)
    match = re.search(r"/summary/([0-9a-f\\-]+)", result_body)
    assert match is not None
    screening_session_id = match.group(1)

    summary_response = client.get(f"/summary/{screening_session_id}")
    assert summary_response.status_code == 200
    summary_body = summary_response.get_data(as_text=True)
    assert "Printable screening summary" in summary_body
    assert "<strong>model_confidence</strong>" not in summary_body
    assert "This tool does not provide a medical diagnosis." in summary_body

    download_response = client.get(
        f"/summary/{screening_session_id}?download=1"
    )
    assert download_response.status_code == 200
    disposition = download_response.headers.get(
        "Content-Disposition",
        "",
    )
    assert "attachment;" in disposition
    assert screening_session_id in disposition


def test_admin_analytics_requires_token_and_returns_aggregates(
    monkeypatch,
    tmp_path,
) -> None:
    """Admin analytics must be token-gated and aggregate-only."""
    db_path = tmp_path / "triage-b9-admin.sqlite3"
    monkeypatch.setenv("TRIAGE_DB_PATH", str(db_path))
    monkeypatch.setenv("TRIAGE_ADMIN_TOKEN", "admin-token")
    client = create_app().test_client()

    first_result = client.post(
        "/result",
        data={"selected_symptoms": ["itching", "skin_rash"]},
    )
    second_result = client.post(
        "/result",
        data={"selected_symptoms": ["acidity", "abdominal_pain"]},
    )
    assert first_result.status_code == 200
    assert second_result.status_code == 200

    denied = client.get("/admin/analytics")
    assert denied.status_code == 403

    allowed = client.get("/admin/analytics?token=admin-token")
    assert allowed.status_code == 200
    allowed_body = allowed.get_data(as_text=True)
    assert "Admin analytics dashboard" in allowed_body
    assert "Urgency distribution" in allowed_body
    assert "Common symptoms" in allowed_body
    assert "Frequent categories" in allowed_body
    assert "Model-performance summary" in allowed_body

    api_response = client.get(
        "/api/admin/analytics",
        headers={"X-Admin-Token": "admin-token"},
    )
    assert api_response.status_code == 200
    payload = api_response.get_json()
    assert payload["total_screenings"] == 2
    assert "session_id" not in str(payload)
