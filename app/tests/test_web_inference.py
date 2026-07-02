"""Tests for structured-input model inference helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.symptom_vocabulary import FROZEN_SYMPTOM_ORDER
from app.web.inference import (
    InferenceConfig,
    UrgencyModifiers,
    compute_rule_based_urgency,
    infer_from_structured_symptoms,
    load_model_runtime,
)

DISCLAIMER = "Test disclaimer"


def test_runtime_feature_order_matches_frozen_artifact() -> None:
    """Runtime should reject any model bundle with mismatched feature order."""
    runtime = load_model_runtime()
    assert runtime.feature_order == tuple(FROZEN_SYMPTOM_ORDER)


def test_inference_uses_frozen_one_hot_order_for_predict_proba() -> None:
    """Result confidence should match frozen-order manual one-hot scoring."""
    runtime = load_model_runtime()
    selected_symptoms = ["itching", "cough", "fatigue"]

    result = infer_from_structured_symptoms(
        runtime=runtime,
        selected_symptoms=selected_symptoms,
        disclaimer_text=DISCLAIMER,
        config=InferenceConfig(),
    )

    vector = np.zeros((1, len(runtime.feature_order)), dtype=int)
    for symptom_name in selected_symptoms:
        index = runtime.feature_order.index(symptom_name)
        vector[0, index] = 1
    frame = pd.DataFrame(vector, columns=runtime.feature_order)
    manual_confidence = float(runtime.model.predict_proba(frame)[0].max())

    assert result["model_confidence"] == round(manual_confidence, 6)


def test_inference_returns_safe_discussion_phrasing_only() -> None:
    """Areas to discuss should be category-level safe phrasing, not labels."""
    runtime = load_model_runtime()
    result = infer_from_structured_symptoms(
        runtime=runtime,
        selected_symptoms=["chest_pain", "palpitations", "sweating"],
        disclaimer_text=DISCLAIMER,
        config=InferenceConfig(),
    )

    assert result["areas_to_discuss"]
    assert (
        "Heart and circulation-related concerns" in result["areas_to_discuss"]
    )
    assert "Heart Attack" not in " ".join(result["areas_to_discuss"])


def test_empty_or_unknown_symptoms_route_to_uncertainty() -> None:
    """Nothing-recognised inputs should route straight to uncertainty."""
    runtime = load_model_runtime()
    result = infer_from_structured_symptoms(
        runtime=runtime,
        selected_symptoms=["", "not_a_real_symptom"],
        disclaimer_text=DISCLAIMER,
        config=InferenceConfig(),
    )

    assert result["urgency"] == "moderate"
    assert result["point_of_care"] == "General Physician"
    assert result["areas_to_discuss"] == []
    assert result["low_confidence"] is True
    assert result["model_confidence"] is None


def test_below_threshold_prediction_routes_to_uncertainty() -> None:
    """Recognised but low-confidence predictions should route uncertainty."""
    runtime = load_model_runtime()
    result = infer_from_structured_symptoms(
        runtime=runtime,
        selected_symptoms=["foul_smell_of_urine"],
        disclaimer_text=DISCLAIMER,
        config=InferenceConfig(),
    )

    assert result["urgency"] == "moderate"
    assert result["point_of_care"] == "General Physician"
    assert result["areas_to_discuss"] == []
    assert result["low_confidence"] is True
    assert result["model_confidence"] is not None
    assert result["model_confidence"] < 0.60


def test_rule_based_urgency_table_cells() -> None:
    """Urgency should follow the frozen §13.12 step-table behavior."""
    assert (
        compute_rule_based_urgency(
            severity_tier="Tier 1",
            modifiers=UrgencyModifiers(
                duration_band=None,
                self_severity=None,
                combination_flag="none",
            ),
        )
        == "low"
    )
    assert (
        compute_rule_based_urgency(
            severity_tier="Tier 1",
            modifiers=UrgencyModifiers(
                duration_band="prolonged",
                self_severity="severe",
                combination_flag="none",
            ),
        )
        == "moderate"
    )
    assert (
        compute_rule_based_urgency(
            severity_tier="Tier 1",
            modifiers=UrgencyModifiers(
                duration_band=None,
                self_severity="mild",
                combination_flag="concerning",
            ),
        )
        == "moderate"
    )
    assert (
        compute_rule_based_urgency(
            severity_tier="Tier 2",
            modifiers=UrgencyModifiers(
                duration_band="prolonged",
                self_severity=None,
                combination_flag="none",
            ),
        )
        == "moderate"
    )
    assert (
        compute_rule_based_urgency(
            severity_tier="Tier 3",
            modifiers=UrgencyModifiers(
                duration_band="prolonged",
                self_severity="severe",
                combination_flag="none",
            ),
        )
        == "high"
    )
    assert (
        compute_rule_based_urgency(
            severity_tier="Tier 4",
            modifiers=UrgencyModifiers(
                duration_band=None,
                self_severity=None,
                combination_flag="none",
            ),
        )
        == "high"
    )
