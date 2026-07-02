"""Tests for B3 model-training outputs and bundle integrity."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import joblib
import pandas as pd
import sklearn

BUNDLE_PATH = Path("app/model/triage_model_bundle.joblib")
METRICS_PATH = Path("app/model/model_comparison_metrics.json")
CONFUSION_PATH = Path("app/model/selected_model_confusion_matrix.csv")
VIGNETTE_PATH = Path("app/model/realistic_vignette_check.json")
GROUPED_DATASET_PATH = Path("app/data/symbipredict_2022_grouped_clean.csv")


def test_model_bundle_loads_under_pinned_sklearn() -> None:
    """Bundle should load and run predict_proba under pinned sklearn."""
    bundle = joblib.load(BUNDLE_PATH)
    assert bundle["sklearn_version"] == sklearn.__version__

    required_keys = {
        "model",
        "feature_order",
        "frozen_vocabulary",
        "synonym_lexicon",
        "spell_corrector",
        "lookup_table",
    }
    assert required_keys.issubset(bundle)

    model = bundle["model"]
    feature_order = list(bundle["feature_order"])
    grouped = pd.read_csv(GROUPED_DATASET_PATH)
    sample = grouped[feature_order].iloc[[0]]
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=RuntimeWarning,
            module="sklearn.utils.extmath",
        )
        probabilities = model.predict_proba(sample)
    assert probabilities.shape[0] == 1
    assert probabilities.shape[1] == 10


def test_metrics_and_confusion_matrix_are_recorded() -> None:
    """Model metrics should include all agreed candidates and caveat."""
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    assert metrics["random_seed"] == 42
    assert len(metrics["results"]) == 5
    assert metrics["primary_metric"] == "macro_f1"
    assert "synthetic" in metrics["synthetic_data_caveat"].lower()

    matrix = pd.read_csv(CONFUSION_PATH, index_col=0)
    assert matrix.shape == (10, 10)
    assert (matrix.values >= 0).all()


def test_vignette_sanity_check_uses_short_profiles() -> None:
    """Quick behavior check should use realistic 2–4 symptom inputs."""
    payload = json.loads(VIGNETTE_PATH.read_text(encoding="utf-8"))
    results = payload["results"]
    assert results

    for row in results:
        symptom_count = len(row["symptoms"])
        assert 2 <= symptom_count <= 4
        assert len(row["top3"]) == 3
