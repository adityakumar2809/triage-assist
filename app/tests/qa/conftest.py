"""Shared fixtures for the QA test suite."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.web.app import create_app
from app.web.inference import InferenceConfig, ModelRuntime, load_model_runtime
from app.web.safety import SafetyRuntime, load_safety_runtime
from app.nlp import NlpRuntime, load_nlp_runtime


@pytest.fixture(scope="session")
def app() -> Flask:
    """Create a Flask app in testing mode."""
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture(scope="session")
def client(app: Flask) -> FlaskClient:
    """Provide a test client for HTTP-level integration tests."""
    return app.test_client()


@pytest.fixture(scope="session")
def safety_runtime() -> SafetyRuntime:
    """Load the frozen safety runtime once for the session."""
    return load_safety_runtime()


@pytest.fixture(scope="session")
def model_runtime() -> ModelRuntime:
    """Load the model runtime once for the session."""
    return load_model_runtime()


@pytest.fixture(scope="session")
def nlp_runtime() -> NlpRuntime:
    """Load the NLP cascade runtime once for the session."""
    return load_nlp_runtime()


@pytest.fixture(scope="session")
def inference_config() -> InferenceConfig:
    """Return the frozen inference config used in production."""
    return InferenceConfig(
        areas_count_cap=3,
        areas_probability_floor=0.10,
    )
