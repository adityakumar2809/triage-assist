"""Model-inference helpers for the structured-input web flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.data.load_curated import load_body_system_groups
from app.data.symptom_vocabulary import FROZEN_SYMPTOM_ORDER

MODEL_BUNDLE_PATH = Path(__file__).resolve().parents[1] / "model"
MODEL_BUNDLE_PATH = MODEL_BUNDLE_PATH / "triage_model_bundle.joblib"

URGENCY_MESSAGE_BY_LEVEL: dict[str, str] = {
    "low": (
        "A routine visit with the suggested point of care is a "
        "reasonable next step. See them sooner if your symptoms worsen "
        "or concern you."
    ),
    "moderate": (
        "It's worth arranging to see the suggested point of care in the "
        "next few days. Go sooner if your symptoms worsen."
    ),
    "high": (
        "Please arrange to see the suggested point of care today. If your "
        "symptoms suddenly worsen, seek emergency care."
    ),
}

SEEK_SOONER_IF_BY_URGENCY: dict[str, list[str]] = {
    "low": [
        "Symptoms persist longer than expected",
        "Symptoms worsen or concern you",
    ],
    "moderate": [
        "Symptoms worsen before your appointment",
        "You develop new severe pain or breathing trouble",
    ],
    "high": [
        "You cannot access same-day care",
        "Symptoms suddenly worsen",
    ],
}

UNCERTAINTY_MESSAGE = (
    "This tool couldn't assess your symptoms reliably enough to suggest a "
    "specific next step. Please see a general physician, who can take a "
    "fuller history and examine you."
)

UNCERTAINTY_SEEK_SOONER_IF = [
    "Symptoms worsen before you can be seen",
    "You develop severe pain, breathing trouble, or fainting",
]


@dataclass(frozen=True)
class InferenceConfig:
    """Frozen B6 inference and urgency-rule parameters."""

    uncertainty_threshold: float = 0.60
    areas_count_cap: int = 3
    areas_probability_floor: float = 0.10
    prolonged_duration_min_days: int = 14
    acute_short_duration_max_days: int = 2
    mild_severity_max: int = 3
    moderate_severity_max: int = 6
    combination_min_symptom_count: int = 2
    combination_min_body_system_count: int = 2


@dataclass(frozen=True)
class UrgencyModifiers:
    """Derived modifier values consumed by deterministic urgency rules."""

    duration_band: str | None
    self_severity: str | None
    combination_flag: str


@dataclass(frozen=True)
class ModelRuntime:
    """Loaded model runtime resources for one prediction request."""

    model: Any
    selected_model_name: str
    feature_order: tuple[str, ...]
    lookup_by_category: dict[str, dict[str, str]]
    symptom_to_body_system: dict[str, str]


def load_model_runtime(bundle_path: Path = MODEL_BUNDLE_PATH) -> ModelRuntime:
    """Load and validate the bundled model + lookup resources."""
    payload: dict[str, Any] = joblib.load(bundle_path)
    feature_order = tuple(str(name) for name in payload["feature_order"])
    if feature_order != tuple(FROZEN_SYMPTOM_ORDER):
        raise ValueError(
            "Model feature order does not match frozen symptom order."
        )

    lookup_rows = payload["lookup_table"]
    lookup_by_category = {
        str(row["condition_category"]): dict(row) for row in lookup_rows
    }
    if not lookup_by_category:
        raise ValueError("Lookup table is empty in model bundle.")

    model = payload["model"]
    if not hasattr(model, "predict_proba"):
        raise ValueError("Bundled model must expose predict_proba.")

    symptom_to_body_system: dict[str, str] = {}
    for body_system, symptoms in load_body_system_groups().items():
        for symptom in symptoms:
            symptom_to_body_system[symptom] = body_system

    return ModelRuntime(
        model=model,
        selected_model_name=str(payload.get("selected_model_name", "")),
        feature_order=feature_order,
        lookup_by_category=lookup_by_category,
        symptom_to_body_system=symptom_to_body_system,
    )


def infer_from_structured_symptoms(
    runtime: ModelRuntime,
    selected_symptoms: list[str],
    disclaimer_text: str,
    config: InferenceConfig,
    duration_days_raw: str | None = None,
    self_severity_raw: str | None = None,
) -> dict[str, Any]:
    """Run B6 structured-input inference and build the result object."""
    canonical_symptoms = _canonicalize_selected_symptoms(
        selected_symptoms,
        runtime.feature_order,
    )
    if not canonical_symptoms:
        return _build_uncertainty_result(
            symptoms_understood=[],
            disclaimer_text=disclaimer_text,
            model_confidence=None,
        )

    feature_frame = _build_feature_frame(
        canonical_symptoms,
        runtime.feature_order,
    )

    probabilities = runtime.model.predict_proba(feature_frame)[0]
    ranked = sorted(
        [
            (str(category), float(probability))
            for category, probability in zip(
                runtime.model.classes_,
                probabilities,
            )
        ],
        key=lambda item: item[1],
        reverse=True,
    )

    top1_category, top1_probability = ranked[0]
    top_ranked_for_storage = ranked[: config.areas_count_cap]
    if top1_probability < config.uncertainty_threshold:
        return _build_uncertainty_result(
            symptoms_understood=canonical_symptoms,
            disclaimer_text=disclaimer_text,
            model_confidence=top1_probability,
            predicted_categories=_serialize_predicted_categories(
                top_ranked_for_storage
            ),
        )

    area_categories = _select_area_categories(
        ranked_categories=ranked,
        config=config,
    )

    top_lookup = runtime.lookup_by_category[top1_category]
    modifiers = _derive_urgency_modifiers(
        canonical_symptoms=canonical_symptoms,
        runtime=runtime,
        config=config,
        duration_days_raw=duration_days_raw,
        self_severity_raw=self_severity_raw,
    )
    urgency = compute_rule_based_urgency(
        severity_tier=top_lookup["severity_tier"],
        modifiers=modifiers,
    )

    return {
        "urgency": urgency,
        "urgency_message": URGENCY_MESSAGE_BY_LEVEL[urgency],
        "point_of_care": top_lookup["point_of_care"],
        "point_of_care_note": top_lookup["point_of_care_note"],
        "symptoms_understood": canonical_symptoms,
        "areas_to_discuss": [
            runtime.lookup_by_category[category]["safe_display_phrasing"]
            for category, _ in area_categories
        ],
        "seek_sooner_if": SEEK_SOONER_IF_BY_URGENCY[urgency],
        "model_confidence": round(top1_probability, 6),
        "low_confidence": False,
        "emergency_routed": False,
        "disclaimer": disclaimer_text,
        "primary_category": top1_category,
        "predicted_categories": _serialize_predicted_categories(
            top_ranked_for_storage
        ),
    }


def compute_rule_based_urgency(
    severity_tier: str,
    modifiers: UrgencyModifiers,
) -> str:
    """Compute urgency using the frozen deterministic §13.12 step table."""
    if severity_tier == "Tier 4":
        return "high"

    steps = _compute_urgency_steps(
        severity_tier=severity_tier,
        modifiers=modifiers,
    )
    if severity_tier == "Tier 1":
        if steps <= 1:
            return "low"
        if steps == 2:
            return "moderate"
        return "high"
    if severity_tier in {"Tier 2", "Tier 3"}:
        if steps <= 1:
            return "moderate"
        return "high"

    raise ValueError(f"Unknown severity tier: {severity_tier}")


def _build_uncertainty_result(
    symptoms_understood: list[str],
    disclaimer_text: str,
    model_confidence: float | None,
    predicted_categories: list[dict[str, float | int | str]] | None = None,
) -> dict[str, Any]:
    """Build the frozen uncertainty-path result object."""
    if predicted_categories is None:
        predicted_categories = []
    return {
        "urgency": "moderate",
        "urgency_message": UNCERTAINTY_MESSAGE,
        "point_of_care": "General Physician",
        "point_of_care_note": "",
        "symptoms_understood": symptoms_understood,
        "areas_to_discuss": [],
        "seek_sooner_if": UNCERTAINTY_SEEK_SOONER_IF,
        "model_confidence": (
            None if model_confidence is None else round(model_confidence, 6)
        ),
        "low_confidence": True,
        "emergency_routed": False,
        "disclaimer": disclaimer_text,
        "primary_category": None,
        "predicted_categories": predicted_categories,
    }


def _derive_urgency_modifiers(
    canonical_symptoms: list[str],
    runtime: ModelRuntime,
    config: InferenceConfig,
    duration_days_raw: str | None,
    self_severity_raw: str | None,
) -> UrgencyModifiers:
    """Derive duration, self-severity, and combination modifiers."""
    duration_days = _parse_optional_int(duration_days_raw)
    severity_score = _parse_optional_int(self_severity_raw)

    return UrgencyModifiers(
        duration_band=_derive_duration_band(
            duration_days=duration_days,
            config=config,
        ),
        self_severity=_derive_self_severity_band(
            self_severity_score=severity_score,
            config=config,
        ),
        combination_flag=_derive_combination_flag(
            canonical_symptoms=canonical_symptoms,
            runtime=runtime,
            config=config,
        ),
    )


def _parse_optional_int(raw_value: str | None) -> int | None:
    """Parse optional integer form input; return None when missing/invalid."""
    if raw_value is None:
        return None
    text = raw_value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _derive_duration_band(
    duration_days: int | None,
    config: InferenceConfig,
) -> str | None:
    """Map day count to the frozen duration-band encoding."""
    if duration_days is None or duration_days < 0:
        return None
    if duration_days >= config.prolonged_duration_min_days:
        return "prolonged"
    if duration_days <= config.acute_short_duration_max_days:
        return "acute_short"
    return "sub_acute"


def _derive_self_severity_band(
    self_severity_score: int | None,
    config: InferenceConfig,
) -> str | None:
    """Map 1–10 self severity to mild/moderate/severe bins."""
    if self_severity_score is None:
        return None
    if not 1 <= self_severity_score <= 10:
        return None
    if self_severity_score <= config.mild_severity_max:
        return "mild"
    if self_severity_score <= config.moderate_severity_max:
        return "moderate"
    return "severe"


def _derive_combination_flag(
    canonical_symptoms: list[str],
    runtime: ModelRuntime,
    config: InferenceConfig,
) -> str:
    """Mark concerning when input spans multiple recognized body systems."""
    if len(canonical_symptoms) < config.combination_min_symptom_count:
        return "none"

    systems = {
        runtime.symptom_to_body_system[symptom]
        for symptom in canonical_symptoms
        if symptom in runtime.symptom_to_body_system
    }
    if len(systems) >= config.combination_min_body_system_count:
        return "concerning"
    return "none"


def _compute_urgency_steps(
    severity_tier: str,
    modifiers: UrgencyModifiers,
) -> int:
    """Compute escalation-step count from duration, severity, combination."""
    steps = 0
    if modifiers.duration_band == "prolonged":
        steps += 1
    if modifiers.self_severity == "severe":
        steps += 1
    if modifiers.combination_flag == "concerning":
        if severity_tier == "Tier 1":
            steps += 2
        else:
            steps += 1
    return steps


def _canonicalize_selected_symptoms(
    raw_selected: list[str],
    feature_order: tuple[str, ...],
) -> list[str]:
    """Normalize posted symptom names and keep only known canonical names."""
    valid_names = set(feature_order)
    selected_set = {
        symptom.strip()
        for symptom in raw_selected
        if symptom.strip() in valid_names
    }
    return [symptom for symptom in feature_order if symptom in selected_set]


def _build_feature_frame(
    selected_symptoms: list[str],
    feature_order: tuple[str, ...],
) -> pd.DataFrame:
    """Build one-hot inference frame in the exact frozen column order."""
    vector = np.zeros((1, len(feature_order)), dtype=int)
    index_by_feature = {
        feature_name: index for index, feature_name in enumerate(feature_order)
    }
    for symptom in selected_symptoms:
        vector[0, index_by_feature[symptom]] = 1
    return pd.DataFrame(vector, columns=feature_order)


def _select_area_categories(
    ranked_categories: list[tuple[str, float]],
    config: InferenceConfig,
) -> list[tuple[str, float]]:
    """Apply top-k, floor, and minimum-list rule to category probabilities."""
    top_ranked = ranked_categories[: config.areas_count_cap]
    above_floor = [
        item
        for item in top_ranked
        if item[1] >= config.areas_probability_floor
    ]

    if len(above_floor) >= 2:
        return above_floor
    if len(top_ranked) >= 2:
        return top_ranked[:2]
    return top_ranked[:1]


def _serialize_predicted_categories(
    ranked_categories: list[tuple[str, float]],
) -> list[dict[str, float | int | str]]:
    """Serialize ranked categories for persistence-only storage."""
    return [
        {
            "category": category_name,
            "probability": round(probability, 6),
            "rank": rank,
        }
        for rank, (category_name, probability) in enumerate(
            ranked_categories,
            start=1,
        )
    ]
