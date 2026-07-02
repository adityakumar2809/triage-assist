"""QA triage vignette suite — curated scenarios with expected outcomes.

Each vignette has a PROVENANCE tag:
  - INDEPENDENT: genuinely composed from lay knowledge, not derived from
    the training dataset.
  - DATASET_DERIVED: symptoms taken from training data rows; partly
    circular (reports separately).

Tests run through the inference pipeline with real model + safety layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.web.inference import (
    InferenceConfig,
    ModelRuntime,
    infer_from_structured_symptoms,
)
from app.web.safety import SafetyRuntime, evaluate_safety_gate


@dataclass
class Vignette:
    """One curated test scenario."""

    id: str
    description: str
    provenance: str  # INDEPENDENT | DATASET_DERIVED
    symptoms: list[str]
    expected_urgency: str | None  # None means "any non-emergency"
    expected_emergency: bool
    expected_point_of_care: str | None  # None = don't assert specific
    expected_areas_substring: str | None  # substring in areas list


# ---------------------------------------------------------------------------
# INDEPENDENT vignettes — genuinely lay-composed, NOT from dataset rows
# ---------------------------------------------------------------------------

INDEPENDENT_VIGNETTES = [
    Vignette(
        id="V-IND-01",
        description="Mild skin itch with rash — routine dermatology",
        provenance="INDEPENDENT",
        symptoms=["itching", "skin_rash"],
        expected_urgency="low",
        expected_emergency=False,
        expected_point_of_care="Dermatology",
        expected_areas_substring="skin",
    ),
    Vignette(
        id="V-IND-02",
        description="Joint pain and stiffness — routine ortho",
        provenance="INDEPENDENT",
        symptoms=["joint_pain", "movement_stiffness"],
        expected_urgency=None,  # could be low or moderate
        expected_emergency=False,
        expected_point_of_care="Orthopaedics",
        expected_areas_substring=None,
    ),
    Vignette(
        id="V-IND-03",
        description="Emergency: chest pain (solo red flag)",
        provenance="INDEPENDENT",
        symptoms=["chest_pain"],
        expected_urgency="emergency",
        expected_emergency=True,
        expected_point_of_care="Emergency Department",
        expected_areas_substring=None,
    ),
    Vignette(
        id="V-IND-04",
        description="Sparse input: single vague symptom (fatigue only)",
        provenance="INDEPENDENT",
        symptoms=["fatigue"],
        expected_urgency=None,
        expected_emergency=False,
        expected_point_of_care=None,  # likely uncertainty → GP
        expected_areas_substring=None,
    ),
    Vignette(
        id="V-IND-05",
        description="Cough + mild fever — common respiratory, non-emergency",
        provenance="INDEPENDENT",
        symptoms=["cough", "mild_fever"],
        expected_urgency=None,
        expected_emergency=False,
        expected_point_of_care=None,
        expected_areas_substring=None,
    ),
    Vignette(
        id="V-IND-06",
        description="Headache + nausea — non-specific",
        provenance="INDEPENDENT",
        symptoms=["headache", "nausea"],
        expected_urgency=None,
        expected_emergency=False,
        expected_point_of_care=None,
        expected_areas_substring=None,
    ),
    Vignette(
        id="V-IND-07",
        description="Emergency: stiff neck + high fever (meningitis cluster)",
        provenance="INDEPENDENT",
        symptoms=["stiff_neck", "high_fever"],
        expected_urgency="emergency",
        expected_emergency=True,
        expected_point_of_care="Emergency Department",
        expected_areas_substring=None,
    ),
]

# ---------------------------------------------------------------------------
# DATASET-DERIVED vignettes — symptoms from actual training rows
# ---------------------------------------------------------------------------

DATASET_DERIVED_VIGNETTES = [
    Vignette(
        id="V-DD-01",
        description="Classic skin allergy profile",
        provenance="DATASET_DERIVED",
        symptoms=["itching", "skin_rash", "nodal_skin_eruptions"],
        expected_urgency="low",
        expected_emergency=False,
        expected_point_of_care="Dermatology",
        expected_areas_substring="skin",
    ),
    Vignette(
        id="V-DD-02",
        description="GI profile: stomach pain, vomiting, indigestion",
        provenance="DATASET_DERIVED",
        symptoms=["stomach_pain", "vomiting", "indigestion"],
        expected_urgency=None,
        expected_emergency=False,
        expected_point_of_care="Gastroenterology",
        expected_areas_substring="digestive",
    ),
    Vignette(
        id="V-DD-03",
        description="Liver profile: yellowish skin, dark urine, nausea",
        provenance="DATASET_DERIVED",
        symptoms=["yellowish_skin", "dark_urine", "nausea", "loss_of_appetite"],
        expected_urgency=None,
        expected_emergency=False,
        expected_point_of_care="Hepatology",
        expected_areas_substring="liver",
    ),
    Vignette(
        id="V-DD-04",
        description="Respiratory: cough, high fever, phlegm, breathlessness",
        provenance="DATASET_DERIVED",
        symptoms=["cough", "high_fever", "phlegm", "breathlessness"],
        expected_urgency="emergency",  # breathlessness is solo trigger
        expected_emergency=True,
        expected_point_of_care="Emergency Department",
        expected_areas_substring=None,
    ),
    Vignette(
        id="V-DD-05",
        description="Urological: burning micturition, bladder discomfort",
        provenance="DATASET_DERIVED",
        symptoms=["burning_micturition", "bladder_discomfort",
                  "foul_smell_of_urine"],
        expected_urgency=None,
        expected_emergency=False,
        expected_point_of_care="Urology",
        expected_areas_substring="urinary",
    ),
]

ALL_VIGNETTES = INDEPENDENT_VIGNETTES + DATASET_DERIVED_VIGNETTES

DISCLAIMER_TEXT = (
    "This tool does not provide a medical diagnosis. It suggests how soon, "
    "and which kind of care, may be appropriate based on the symptoms you "
    "described. It can be wrong, and it cannot see your full history. "
    "Always rely on a qualified healthcare professional for diagnosis and "
    "treatment, and seek emergency care directly if your symptoms suddenly "
    "worsen or you are worried."
)


class TestTriageVignettes:
    """Run curated vignettes through the real safety + inference pipeline."""

    @pytest.mark.parametrize(
        "vignette",
        ALL_VIGNETTES,
        ids=[v.id for v in ALL_VIGNETTES],
    )
    def test_vignette(
        self,
        vignette: Vignette,
        safety_runtime: SafetyRuntime,
        model_runtime: ModelRuntime,
        inference_config: InferenceConfig,
    ):
        # Step 1: Safety gate
        safety_decision = evaluate_safety_gate(
            runtime=safety_runtime,
            selected_symptoms=vignette.symptoms,
            raw_text="",
        )

        if vignette.expected_emergency:
            assert safety_decision.emergency_routed, (
                f"{vignette.id}: Expected emergency but safety did not fire!"
            )
            return  # Emergency path — no further assertions needed

        # Non-emergency path: run inference
        if safety_decision.emergency_routed:
            pytest.fail(
                f"{vignette.id}: Did NOT expect emergency but safety fired! "
                f"Symptoms: {vignette.symptoms}"
            )

        result = infer_from_structured_symptoms(
            runtime=model_runtime,
            selected_symptoms=vignette.symptoms,
            disclaimer_text=DISCLAIMER_TEXT,
            config=inference_config,
        )

        # Check urgency if specified
        if vignette.expected_urgency is not None:
            assert result["urgency"] == vignette.expected_urgency, (
                f"{vignette.id}: Expected urgency={vignette.expected_urgency}, "
                f"got {result['urgency']}"
            )

        # Emergency must never come from inference
        assert result["urgency"] != "emergency"
        assert result["emergency_routed"] is False

        # Point of care
        if vignette.expected_point_of_care is not None:
            assert result["point_of_care"] == vignette.expected_point_of_care, (
                f"{vignette.id}: Expected PoC={vignette.expected_point_of_care},"
                f" got {result['point_of_care']}"
            )

        # Areas substring
        if (
            vignette.expected_areas_substring is not None
            and not result["low_confidence"]
        ):
            areas_text = " ".join(result["areas_to_discuss"]).lower()
            assert vignette.expected_areas_substring.lower() in areas_text, (
                f"{vignette.id}: Expected '{vignette.expected_areas_substring}'"
                f" in areas, got: {result['areas_to_discuss']}"
            )

        # Disclaimer always present
        assert result["disclaimer"] == DISCLAIMER_TEXT


class TestVignetteProvenance:
    """Validate provenance metadata is complete for report honesty."""

    def test_all_vignettes_have_provenance(self):
        for v in ALL_VIGNETTES:
            assert v.provenance in ("INDEPENDENT", "DATASET_DERIVED")

    def test_independent_count(self):
        independent = [v for v in ALL_VIGNETTES if v.provenance == "INDEPENDENT"]
        assert len(independent) >= 5, "Need ≥5 independent vignettes"

    def test_dataset_derived_count(self):
        derived = [v for v in ALL_VIGNETTES if v.provenance == "DATASET_DERIVED"]
        assert len(derived) >= 3, "Need ≥3 dataset-derived vignettes"
