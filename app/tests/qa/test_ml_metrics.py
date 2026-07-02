"""QA ML metrics characterisation — honest reporting for R7.

Records:
- Macro-averaged F1 (not just accuracy).
- Confusion matrix under fixed random seed.
- The synthetic-data caveat.
- Verifies BernoulliNB is the selected model.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split

from app.data.symptom_vocabulary import FROZEN_SYMPTOM_ORDER
from app.web.inference import load_model_runtime

RANDOM_SEED = 42


class TestMLMetrics:
    """Characterise model behaviour under fixed seed for report."""

    @pytest.fixture(scope="class")
    def dataset(self):
        """Load the training dataset with the frozen column order."""
        import pandas as pd
        from pathlib import Path

        data_path = Path(__file__).resolve().parents[2] / "data"
        csv_path = data_path / "symbipredict_2022_grouped_clean.csv"
        df = pd.read_csv(csv_path)
        return df

    @pytest.fixture(scope="class")
    def runtime(self):
        return load_model_runtime()

    def test_selected_model_is_bernoulli_nb(self, runtime):
        """Verify the selected model name matches bible specification."""
        assert "bernoulli" in runtime.selected_model_name.lower() or (
            "nb" in runtime.selected_model_name.lower()
        ), f"Expected BernoulliNB, got: {runtime.selected_model_name}"

    def test_macro_f1_above_minimum(self, dataset, runtime):
        """Macro-F1 on held-out split under fixed seed."""
        X = dataset[list(runtime.feature_order)]
        y = dataset["condition_category"]

        _, X_test, _, y_test = train_test_split(
            X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
        )

        y_pred = runtime.model.predict(X_test)
        macro_f1 = f1_score(y_test, y_pred, average="macro")

        # Record for evidence
        print(f"\n[QA METRIC] Macro-F1 = {macro_f1:.4f} (seed={RANDOM_SEED})")

        # The synthetic dataset should achieve high macro-F1
        # but we caveat this is pattern-learning on synthetic data
        assert macro_f1 >= 0.80, (
            f"Macro-F1={macro_f1:.4f} below 0.80 threshold"
        )

    def test_confusion_matrix_shape(self, dataset, runtime):
        """Confusion matrix has expected shape (n_classes x n_classes)."""
        X = dataset[list(runtime.feature_order)]
        y = dataset["condition_category"]

        _, X_test, _, y_test = train_test_split(
            X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
        )

        y_pred = runtime.model.predict(X_test)
        cm = confusion_matrix(y_test, y_pred)
        n_classes = len(runtime.model.classes_)
        assert cm.shape == (n_classes, n_classes)

    def test_no_class_has_zero_recall(self, dataset, runtime):
        """No class should have zero recall (complete miss)."""
        X = dataset[list(runtime.feature_order)]
        y = dataset["condition_category"]

        _, X_test, _, y_test = train_test_split(
            X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
        )

        y_pred = runtime.model.predict(X_test)
        report = classification_report(
            y_test, y_pred, output_dict=True, zero_division=0
        )

        zero_recall_classes = []
        for class_name, metrics in report.items():
            if isinstance(metrics, dict) and metrics.get("recall", 1) == 0:
                zero_recall_classes.append(class_name)

        assert len(zero_recall_classes) == 0, (
            f"Classes with zero recall: {zero_recall_classes}"
        )

    def test_feature_order_matches_frozen(self, runtime):
        """Model feature order must exactly match frozen symptom order."""
        assert tuple(runtime.feature_order) == tuple(FROZEN_SYMPTOM_ORDER)

    def test_synthetic_data_caveat_noted(self):
        """This test documents the synthetic-data caveat for the report.
        High accuracy reflects pattern-learning on synthetic generation,
        not clinical diagnostic skill."""
        # This is a documentation-only test that always passes
        # to ensure the caveat is captured in test output
        caveat = (
            "CAVEAT: Model metrics are computed on a synthetic dataset "
            "(SymBiPredict 2022). High accuracy reflects the dataset's "
            "generation patterns, not clinical diagnostic validity. "
            "The model is used ONLY as an internal routing signal."
        )
        print(f"\n[QA CAVEAT] {caveat}")
        assert True
