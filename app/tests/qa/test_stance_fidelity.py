"""QA stance-fidelity and label-safety tests.

Verifies:
- Condition categories appear ONLY as "areas to discuss", never as a verdict.
- Alarming labels (heart attack, AIDS, brain hemorrhage, etc.) NEVER surface.
- The not-a-diagnosis disclaimer is present on result/emergency/uncertainty.
- model_confidence is never rendered to the user.
- The system never asserts the absence of a problem.
"""

from __future__ import annotations

import pytest

from app.web.inference import (
    InferenceConfig,
    ModelRuntime,
    infer_from_structured_symptoms,
)
from app.web.safety import SafetyRuntime, evaluate_safety_gate, build_emergency_result
from app.data.load_curated import load_category_lookup

DISCLAIMER_TEXT = (
    "This tool does not provide a medical diagnosis. It suggests how soon, "
    "and which kind of care, may be appropriate based on the symptoms you "
    "described. It can be wrong, and it cannot see your full history. "
    "Always rely on a qualified healthcare professional for diagnosis and "
    "treatment, and seek emergency care directly if your symptoms suddenly "
    "worsen or you are worried."
)

ALARMING_LABELS = [
    "heart attack",
    "myocardial infarction",
    "stroke",
    "AIDS",
    "HIV",
    "cancer",
    "tumor",
    "brain hemorrhage",
    "meningitis",
    "sepsis",
    "aneurysm",
    "pulmonary embolism",
    "cardiac arrest",
]


class TestNoAlarmingLabels:
    """NFR-S5: No alarming disease label surfaces to the user."""

    def test_lookup_table_safe_phrasing(self):
        """All safe_display_phrasing entries avoid alarming labels."""
        lookup = load_category_lookup()
        for row in lookup:
            phrasing = str(row.get("safe_display_phrasing", "")).lower()
            for label in ALARMING_LABELS:
                assert label.lower() not in phrasing, (
                    f"Alarming label '{label}' found in safe_display_phrasing: "
                    f"'{row['safe_display_phrasing']}'"
                )

    def test_normal_result_no_alarming_labels(
        self, model_runtime, inference_config
    ):
        """A normal-path result never contains alarming labels."""
        # Use a profile that will produce a confident result
        symptoms = ["itching", "skin_rash", "nodal_skin_eruptions"]
        result = infer_from_structured_symptoms(
            runtime=model_runtime,
            selected_symptoms=symptoms,
            disclaimer_text=DISCLAIMER_TEXT,
            config=inference_config,
        )
        result_text = str(result).lower()
        for label in ALARMING_LABELS:
            assert label.lower() not in result_text, (
                f"Alarming label '{label}' found in result!"
            )

    def test_emergency_no_alarming_labels(self):
        """Emergency result never contains alarming labels."""
        result = build_emergency_result(
            disclaimer_text=DISCLAIMER_TEXT, use_crisis_message=False
        )
        result_text = str(result).lower()
        for label in ALARMING_LABELS:
            assert label.lower() not in result_text


class TestDisclaimerPresence:
    """NFR-U2: Disclaimer on every result path."""

    def test_disclaimer_on_normal_result(self, model_runtime, inference_config):
        symptoms = ["itching", "skin_rash", "nodal_skin_eruptions"]
        result = infer_from_structured_symptoms(
            runtime=model_runtime,
            selected_symptoms=symptoms,
            disclaimer_text=DISCLAIMER_TEXT,
            config=inference_config,
        )
        assert result["disclaimer"] == DISCLAIMER_TEXT

    def test_disclaimer_on_uncertainty_result(
        self, model_runtime, inference_config
    ):
        result = infer_from_structured_symptoms(
            runtime=model_runtime,
            selected_symptoms=[],
            disclaimer_text=DISCLAIMER_TEXT,
            config=inference_config,
        )
        assert result["disclaimer"] == DISCLAIMER_TEXT

    def test_disclaimer_on_emergency_result(self):
        result = build_emergency_result(
            disclaimer_text=DISCLAIMER_TEXT, use_crisis_message=False
        )
        assert result["disclaimer"] == DISCLAIMER_TEXT


class TestAreasAsDiscussionOnly:
    """FR12/§3: Areas appear only as discussion points, never a verdict."""

    def test_areas_list_bounded(self, model_runtime, inference_config):
        """areas_to_discuss never exceeds areas_count_cap."""
        symptoms = ["itching", "skin_rash", "nodal_skin_eruptions"]
        result = infer_from_structured_symptoms(
            runtime=model_runtime,
            selected_symptoms=symptoms,
            disclaimer_text=DISCLAIMER_TEXT,
            config=inference_config,
        )
        assert len(result["areas_to_discuss"]) <= inference_config.areas_count_cap

    def test_areas_empty_on_uncertainty(self, model_runtime, inference_config):
        """Uncertainty path must have empty areas."""
        result = infer_from_structured_symptoms(
            runtime=model_runtime,
            selected_symptoms=[],
            disclaimer_text=DISCLAIMER_TEXT,
            config=inference_config,
        )
        assert result["areas_to_discuss"] == []

    def test_areas_empty_on_emergency(self):
        """Emergency path must have empty areas."""
        result = build_emergency_result(
            disclaimer_text=DISCLAIMER_TEXT, use_crisis_message=False
        )
        assert result["areas_to_discuss"] == []


class TestModelConfidenceNotExposed:
    """NFR-S5: model_confidence must not be rendered to the user."""

    def test_html_result_page_no_confidence_value(self, client):
        """The result HTML page must not contain model_confidence."""
        response = client.post(
            "/screen",
            data={
                "selected_symptoms": ["itching", "skin_rash",
                                       "nodal_skin_eruptions"],
            },
        )
        html = response.data.decode()
        # The word "confidence" in context of a number should not appear
        assert "model_confidence" not in html
        # Should not contain raw probability values like "0.98" etc.
        # (A loose check — the exact format may vary)
        import re

        prob_pattern = re.compile(r"confidence.*?0\.\d{2,}")
        assert not prob_pattern.search(html)


class TestNoAbsenceAssertion:
    """NFR-S5: System must never assert absence of a problem."""

    ABSENCE_PHRASES = [
        "you do not have",
        "you don't have",
        "there is nothing wrong",
        "nothing to worry about",
        "all clear",
        "no disease",
        "you are fine",
        "you're fine",
        "negative for",
    ]

    def test_normal_result_no_absence_assertion(self, client):
        response = client.post(
            "/screen",
            data={
                "selected_symptoms": ["itching", "skin_rash"],
            },
        )
        html = response.data.decode().lower()
        for phrase in self.ABSENCE_PHRASES:
            assert phrase not in html, (
                f"Absence assertion '{phrase}' found in result page!"
            )
