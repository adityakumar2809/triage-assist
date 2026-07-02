"""QA uncertainty-path and sparse-input tests.

Verifies:
- Sparse (1–2 symptom) inputs with low confidence → uncertainty path.
- Empty/unrecognised input → uncertainty path (never crash/guess).
- Uncertainty result: urgency=moderate, point_of_care=General Physician,
  areas_to_discuss=[], low_confidence=True, disclaimer present.
- tau=0.60 threshold behaviour.
"""

from __future__ import annotations

import pytest

from app.web.inference import (
    InferenceConfig,
    ModelRuntime,
    infer_from_structured_symptoms,
)
from app.web.safety import SafetyRuntime, evaluate_safety_gate

DISCLAIMER_TEXT = (
    "This tool does not provide a medical diagnosis. It suggests how soon, "
    "and which kind of care, may be appropriate based on the symptoms you "
    "described. It can be wrong, and it cannot see your full history. "
    "Always rely on a qualified healthcare professional for diagnosis and "
    "treatment, and seek emergency care directly if your symptoms suddenly "
    "worsen or you are worried."
)


def _run_inference_no_emergency(
    symptoms: list[str],
    safety_runtime: SafetyRuntime,
    model_runtime: ModelRuntime,
    config: InferenceConfig,
) -> dict:
    """Run safety + inference, asserting no emergency fires."""
    safety = evaluate_safety_gate(
        runtime=safety_runtime,
        selected_symptoms=symptoms,
        raw_text="",
    )
    assert not safety.emergency_routed, (
        f"Unexpected emergency for {symptoms}"
    )
    return infer_from_structured_symptoms(
        runtime=model_runtime,
        selected_symptoms=symptoms,
        disclaimer_text=DISCLAIMER_TEXT,
        config=config,
    )


class TestUncertaintyPathEmpty:
    """Empty or no-valid input must produce uncertainty terminal."""

    def test_empty_symptom_list(
        self, safety_runtime, model_runtime, inference_config
    ):
        result = _run_inference_no_emergency(
            [], safety_runtime, model_runtime, inference_config
        )
        assert result["low_confidence"] is True
        assert result["point_of_care"] == "General Physician"
        assert result["areas_to_discuss"] == []
        assert result["urgency"] == "moderate"
        assert result["disclaimer"] == DISCLAIMER_TEXT
        assert result["emergency_routed"] is False

    def test_invalid_symptom_names(
        self, safety_runtime, model_runtime, inference_config
    ):
        """Completely unrecognised symptom names → uncertainty."""
        result = _run_inference_no_emergency(
            ["not_a_real_symptom", "xyz_foo_bar"],
            safety_runtime,
            model_runtime,
            inference_config,
        )
        assert result["low_confidence"] is True
        assert result["point_of_care"] == "General Physician"
        assert result["areas_to_discuss"] == []


class TestUncertaintyPathSparse:
    """Sparse realistic input that produces low confidence."""

    SPARSE_INPUTS = [
        # Single vague symptoms unlikely to produce high confidence
        ["fatigue"],
        ["headache"],
        ["nausea"],
        ["weight_loss"],
        ["lethargy"],
    ]

    @pytest.mark.parametrize("symptoms", SPARSE_INPUTS)
    def test_sparse_single_symptom_behaviour(
        self, symptoms, safety_runtime, model_runtime, inference_config
    ):
        """Single vague symptom should yield low confidence or modest result
        — never a confidently-wrong emergency-level response."""
        result = _run_inference_no_emergency(
            symptoms, safety_runtime, model_runtime, inference_config
        )
        # Must never fabricate an emergency from sparse input
        assert result["urgency"] != "emergency"
        assert result["emergency_routed"] is False
        # If low confidence, verify uncertainty contract
        if result["low_confidence"]:
            assert result["point_of_care"] == "General Physician"
            assert result["areas_to_discuss"] == []
        # Disclaimer always present
        assert result["disclaimer"] == DISCLAIMER_TEXT


class TestThresholdBehaviour:
    """Verify tau=0.60 threshold is correctly applied."""

    def test_config_uncertainty_threshold(self, inference_config):
        assert inference_config.uncertainty_threshold == 0.60

    def test_high_confidence_not_uncertain(
        self, safety_runtime, model_runtime, inference_config
    ):
        """A profile with many matching symptoms should be above threshold."""
        # Classic skin profile — highly correlated in dataset
        symptoms = ["itching", "skin_rash", "nodal_skin_eruptions"]
        result = _run_inference_no_emergency(
            symptoms, safety_runtime, model_runtime, inference_config
        )
        assert result["low_confidence"] is False
        assert result["model_confidence"] is not None
        assert result["model_confidence"] >= 0.60


class TestUncertaintyResultContract:
    """Uncertainty result object must match §18 frozen contract."""

    def test_uncertainty_result_fields(
        self, safety_runtime, model_runtime, inference_config
    ):
        result = _run_inference_no_emergency(
            [], safety_runtime, model_runtime, inference_config
        )
        required_keys = {
            "urgency",
            "urgency_message",
            "point_of_care",
            "point_of_care_note",
            "symptoms_understood",
            "areas_to_discuss",
            "seek_sooner_if",
            "model_confidence",
            "low_confidence",
            "emergency_routed",
            "disclaimer",
        }
        assert required_keys.issubset(result.keys())
        # Specific uncertainty values
        assert result["urgency"] == "moderate"
        assert "could not assess" in result["urgency_message"].lower() or (
            "couldn't assess" in result["urgency_message"].lower()
        )
