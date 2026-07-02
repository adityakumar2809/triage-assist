"""QA input hardening and robustness tests (NFR-RB1–RB4).

Verifies:
- Empty, gibberish, very long, non-English, injection-looking input
  all degrade gracefully to uncertainty path rather than crashing.
- Result object always conforms to §18 contract on every path.
- No exceptions or 500 errors on malformed input.
"""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient


MALFORMED_INPUTS = [
    ("empty_string", ""),
    ("whitespace_only", "     "),
    ("special_chars", "!@#$%^&*()_+-=[]{}|;':\",./<>?"),
    ("unicode_non_latin", "我有头疼 肚子痛"),
    ("emoji_only", "🤕🤒😷💀"),
    ("very_long", "headache " * 500),
    ("sql_injection", "'; DROP TABLE screenings; --"),
    ("xss_attempt", '<script>alert("xss")</script>'),
    ("null_bytes", "headache\x00\x00pain"),
    ("newlines_tabs", "headache\n\n\t\tvomiting\r\n"),
    ("numbers_only", "12345 67890"),
    ("single_char", "x"),
    ("repeated_negation", "no no no no no no"),
    ("html_entities", "&lt;b&gt;chest pain&lt;/b&gt;"),
]


class TestInputHardeningFreeText:
    """Malformed free-text input must not crash the app."""

    @pytest.mark.parametrize(
        "label,text",
        MALFORMED_INPUTS,
        ids=[m[0] for m in MALFORMED_INPUTS],
    )
    def test_malformed_free_text_no_crash(
        self, client: FlaskClient, label: str, text: str
    ):
        """POST /screen with malformed raw_text must return 200."""
        response = client.post(
            "/screen",
            data={
                "selected_symptoms": [],
                "raw_text": text,
            },
        )
        assert response.status_code == 200, (
            f"Input '{label}' caused status {response.status_code}"
        )

    @pytest.mark.parametrize(
        "label,text",
        MALFORMED_INPUTS,
        ids=[m[0] for m in MALFORMED_INPUTS],
    )
    def test_malformed_free_text_no_500(
        self, client: FlaskClient, label: str, text: str
    ):
        """No 500 server error on any malformed input."""
        response = client.post(
            "/screen",
            data={
                "selected_symptoms": [],
                "raw_text": text,
            },
        )
        assert response.status_code != 500


class TestInputHardeningStructured:
    """Malformed structured symptom names handled gracefully."""

    def test_invalid_symptom_names_ignored(self, client: FlaskClient):
        """Invalid symptom names must be silently ignored, not crash."""
        response = client.post(
            "/screen",
            data={
                "selected_symptoms": [
                    "not_a_symptom",
                    "<script>alert(1)</script>",
                    "'; DROP TABLE--",
                ],
            },
        )
        assert response.status_code == 200

    def test_empty_form_submission(self, client: FlaskClient):
        """Completely empty form → valid response (uncertainty)."""
        response = client.post("/screen", data={})
        assert response.status_code == 200

    def test_duplicate_symptoms(self, client: FlaskClient):
        """Duplicate symptom names handled without error."""
        response = client.post(
            "/screen",
            data={
                "selected_symptoms": ["headache", "headache", "headache"],
            },
        )
        assert response.status_code == 200


class TestResultObjectContract:
    """§18: Result object always contains required fields."""

    REQUIRED_FIELDS = [
        "urgency",
        "urgency_message",
        "point_of_care",
        "symptoms_understood",
        "areas_to_discuss",
        "seek_sooner_if",
        "low_confidence",
        "emergency_routed",
        "disclaimer",
    ]

    def test_normal_result_has_all_fields(self, client: FlaskClient):
        """Normal-path result contains all required fields."""
        from app.web.inference import (
            InferenceConfig,
            infer_from_structured_symptoms,
            load_model_runtime,
        )

        runtime = load_model_runtime()
        result = infer_from_structured_symptoms(
            runtime=runtime,
            selected_symptoms=["itching", "skin_rash", "nodal_skin_eruptions"],
            disclaimer_text="test",
            config=InferenceConfig(),
        )
        for field in self.REQUIRED_FIELDS:
            assert field in result, f"Missing field '{field}' in normal result"

    def test_uncertainty_result_has_all_fields(self):
        from app.web.inference import (
            InferenceConfig,
            infer_from_structured_symptoms,
            load_model_runtime,
        )

        runtime = load_model_runtime()
        result = infer_from_structured_symptoms(
            runtime=runtime,
            selected_symptoms=[],
            disclaimer_text="test",
            config=InferenceConfig(),
        )
        for field in self.REQUIRED_FIELDS:
            assert field in result, (
                f"Missing field '{field}' in uncertainty result"
            )

    def test_emergency_result_has_all_fields(self):
        from app.web.safety import build_emergency_result

        result = build_emergency_result(
            disclaimer_text="test", use_crisis_message=False
        )
        for field in self.REQUIRED_FIELDS:
            assert field in result, (
                f"Missing field '{field}' in emergency result"
            )


class TestEndpointRobustness:
    """All main endpoints handle edge cases gracefully."""

    def test_get_index_returns_200(self, client: FlaskClient):
        assert client.get("/").status_code == 200

    def test_get_health_returns_200(self, client: FlaskClient):
        assert client.get("/health").status_code == 200

    def test_get_history_returns_200(self, client: FlaskClient):
        assert client.get("/history").status_code == 200

    def test_admin_without_token_blocked(self, client: FlaskClient):
        """Admin endpoint without token → non-200 (blocked)."""
        response = client.get("/admin/analytics")
        assert response.status_code != 200, (
            f"Admin endpoint accessible without token! Got {response.status_code}"
        )

    def test_summary_invalid_id_returns_404(self, client: FlaskClient):
        """Summary with non-existent ID → 404."""
        response = client.get("/summary/nonexistent-id-12345")
        assert response.status_code == 404
