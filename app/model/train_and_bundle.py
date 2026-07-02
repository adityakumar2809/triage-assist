"""Train, evaluate, and bundle the B3 classical model artifacts."""

from __future__ import annotations

import io
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import BernoulliNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

if __package__ is None or __package__ == "":
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from app.data.load_curated import (
    load_category_lookup,
    load_frozen_symptom_vocabulary,
    load_synonym_lexicon,
)
from app.data.symptom_vocabulary import (
    DEFAULT_ZERO_FEATURES,
    FROZEN_SYMPTOM_ORDER,
)

RANDOM_SEED = 42
TEST_SIZE = 0.2
STOPPING_TOLERANCE = 1e-9

MODEL_DIR = Path(__file__).resolve().parent
DATA_DIR = MODEL_DIR.parent / "data"
GROUPED_DATASET_PATH = DATA_DIR / "symbipredict_2022_grouped_clean.csv"
MODEL_BUNDLE_PATH = MODEL_DIR / "triage_model_bundle.joblib"
MODEL_METRICS_PATH = MODEL_DIR / "model_comparison_metrics.json"
CONFUSION_MATRIX_PATH = MODEL_DIR / "selected_model_confusion_matrix.csv"
VIGNETTE_CHECK_PATH = MODEL_DIR / "realistic_vignette_check.json"

SYNTHETIC_CAVEAT = (
    "Metrics are from a synthetic disease-symptom dataset. "
    "High split accuracy reflects pattern learning on synthetic generation, "
    "not clinical diagnostic performance. Macro-F1 and vignette behavior are "
    "reported for honest characterization."
)

STOPPING_RULE = (
    "Evaluate the fixed agreed set of five classical models under one "
    "stratified split with RANDOM_SEED=42. Select the best by highest "
    "macro-F1. If models tie within tolerance, prefer stronger realistic "
    "2–4 symptom vignette behavior, then choose the smaller serialized model "
    "size to preserve free-tier memory headroom."
)

VIGNETTE_PROFILES = [
    {
        "id": "skin-01",
        "expected_category": "Skin & Allergic",
        "symptoms": ["itching", "skin_rash", "nodal_skin_eruptions"],
    },
    {
        "id": "gi-01",
        "expected_category": "Gastrointestinal",
        "symptoms": ["acidity", "abdominal_pain", "indigestion"],
    },
    {
        "id": "hepatic-01",
        "expected_category": "Liver & Hepatic",
        "symptoms": ["yellowish_skin", "dark_urine", "loss_of_appetite"],
    },
    {
        "id": "infectious-01",
        "expected_category": "Infectious & Febrile",
        "symptoms": ["high_fever", "malaise", "chills"],
    },
    {
        "id": "respiratory-01",
        "expected_category": "Respiratory",
        "symptoms": ["cough", "breathlessness", "phlegm"],
    },
    {
        "id": "cardio-01",
        "expected_category": "Cardiovascular",
        "symptoms": ["chest_pain", "palpitations", "sweating"],
    },
    {
        "id": "neuro-01",
        "expected_category": "Neurological",
        "symptoms": ["headache", "dizziness", "loss_of_balance"],
    },
    {
        "id": "endocrine-01",
        "expected_category": "Endocrine & Metabolic",
        "symptoms": ["weight_loss", "excessive_hunger", "polyuria"],
    },
    {
        "id": "msk-01",
        "expected_category": "Musculoskeletal",
        "symptoms": ["joint_pain", "knee_pain", "movement_stiffness"],
    },
    {
        "id": "uro-01",
        "expected_category": "Urological",
        "symptoms": [
            "burning_micturition",
            "spotting_urination",
            "bladder_discomfort",
        ],
    },
]


@dataclass(frozen=True)
class ModelEvaluation:
    """Evaluation record for one candidate model."""

    model_name: str
    estimator: Any
    macro_f1: float
    weighted_f1: float
    accuracy: float
    serialized_size_bytes: int
    confusion_matrix: list[list[int]]
    labels: list[str]
    vignette_top1_match_count: int
    vignette_expected_in_top3_count: int


def _load_training_data() -> tuple[pd.DataFrame, pd.Series]:
    """Load grouped training data in frozen feature-column order."""
    frame = pd.read_csv(GROUPED_DATASET_PATH)
    features = frame.loc[:, list(FROZEN_SYMPTOM_ORDER)].astype(int)
    target = frame["condition_category"].astype(str)
    return features, target


def _build_model_candidates() -> dict[str, Any]:
    """Return the agreed set of candidate classical models."""
    return {
        "DecisionTree": DecisionTreeClassifier(random_state=RANDOM_SEED),
        "RandomForest": RandomForestClassifier(
            n_estimators=300,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        "BernoulliNB": BernoulliNB(),
        "KNN": KNeighborsClassifier(n_neighbors=5),
        "SVM": SVC(probability=True, random_state=RANDOM_SEED),
    }


def _serialized_size_bytes(estimator: Any) -> int:
    """Measure serialized estimator size in bytes."""
    buffer = io.BytesIO()
    joblib.dump(estimator, buffer)
    return buffer.tell()


def _evaluate_models() -> tuple[list[ModelEvaluation], np.ndarray, np.ndarray]:
    """Train and evaluate all agreed model candidates."""
    features, target = _load_training_data()
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=target,
    )
    labels = sorted(target.unique().tolist())

    evaluations: list[ModelEvaluation] = []
    for model_name, estimator in _build_model_candidates().items():
        estimator.fit(x_train, y_train)
        predictions = estimator.predict(x_test)
        matrix = confusion_matrix(y_test, predictions, labels=labels)
        vignette_payload = _run_vignette_checks_for_estimator(estimator)
        vignette_summary = vignette_payload["summary"]
        evaluations.append(
            ModelEvaluation(
                model_name=model_name,
                estimator=estimator,
                macro_f1=float(f1_score(y_test, predictions, average="macro")),
                weighted_f1=float(
                    f1_score(y_test, predictions, average="weighted")
                ),
                accuracy=float(accuracy_score(y_test, predictions)),
                serialized_size_bytes=_serialized_size_bytes(estimator),
                confusion_matrix=matrix.astype(int).tolist(),
                labels=labels,
                vignette_top1_match_count=vignette_summary["top1_match_count"],
                vignette_expected_in_top3_count=vignette_summary[
                    "expected_in_top3_count"
                ],
            )
        )
    return evaluations, x_test.to_numpy(dtype=int), y_test.to_numpy()


def _select_best_model(evaluations: list[ModelEvaluation]) -> ModelEvaluation:
    """Select the best model by frozen stopping rule."""
    top_macro = max(item.macro_f1 for item in evaluations)
    top_models = [
        item
        for item in evaluations
        if abs(item.macro_f1 - top_macro) <= STOPPING_TOLERANCE
    ]
    ranked = sorted(
        top_models,
        key=lambda item: (
            -item.macro_f1,
            -item.vignette_expected_in_top3_count,
            -item.vignette_top1_match_count,
            item.serialized_size_bytes,
            item.model_name,
        ),
    )
    return ranked[0]


def _build_spell_corrector_config(
    synonym_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build compact non-word-only spell-correction resources."""
    term_set: set[str] = set()

    for symptom in FROZEN_SYMPTOM_ORDER:
        term_set.update(symptom.split("_"))
        term_set.add(symptom)

    for entry in synonym_entries:
        phrase = str(entry["phrase"]).strip().lower()
        if phrase:
            term_set.add(phrase)
            term_set.update(phrase.split())
        for target in entry["canonical_targets"]:
            target_text = str(target).strip().lower()
            if target_text:
                term_set.add(target_text)
                term_set.update(target_text.split("_"))

    return {
        "strategy": "non_word_only",
        "max_edit_distance": 1,
        "dictionary_terms": sorted(term_set),
    }


def _run_vignette_checks_for_estimator(model: Any) -> dict[str, Any]:
    """Run quick 2–4 symptom vignette checks for one estimator."""
    labels = list(model.classes_)
    index_by_symptom = {
        name: index for index, name in enumerate(FROZEN_SYMPTOM_ORDER)
    }

    results: list[dict[str, Any]] = []
    top1_match_count = 0
    top3_contains_expected_count = 0

    for vignette in VIGNETTE_PROFILES:
        vector = np.zeros((1, len(FROZEN_SYMPTOM_ORDER)), dtype=int)
        for symptom in vignette["symptoms"]:
            vector[0, index_by_symptom[symptom]] = 1

        frame = pd.DataFrame(vector, columns=FROZEN_SYMPTOM_ORDER)
        probabilities = model.predict_proba(frame)[0]
        ranked = sorted(
            zip(labels, probabilities),
            key=lambda item: item[1],
            reverse=True,
        )
        top3 = [
            {
                "category": category,
                "probability": round(float(probability), 6),
            }
            for category, probability in ranked[:3]
        ]
        top1 = ranked[0][0]
        expected = vignette["expected_category"]
        top1_match = top1 == expected
        top3_contains = expected in {entry["category"] for entry in top3}

        if top1_match:
            top1_match_count += 1
        if top3_contains:
            top3_contains_expected_count += 1

        results.append(
            {
                "id": vignette["id"],
                "symptoms": vignette["symptoms"],
                "expected_category": expected,
                "predicted_top1": top1,
                "top1_matches_expected": top1_match,
                "expected_in_top3": top3_contains,
                "top3": top3,
            }
        )

    return {
        "note": (
            "Quick behavior sanity check on short 2–4 symptom inputs. "
            "This is not a clinical validation set."
        ),
        "summary": {
            "vignette_count": len(VIGNETTE_PROFILES),
            "top1_match_count": top1_match_count,
            "expected_in_top3_count": top3_contains_expected_count,
        },
        "results": results,
    }


def _save_confusion_matrix(evaluation: ModelEvaluation) -> None:
    """Persist confusion matrix for the selected model."""
    matrix = pd.DataFrame(
        evaluation.confusion_matrix,
        index=evaluation.labels,
        columns=evaluation.labels,
    )
    matrix.to_csv(CONFUSION_MATRIX_PATH, index=True)


def _save_metrics_json(
    evaluations: list[ModelEvaluation],
    selected: ModelEvaluation,
) -> None:
    """Persist model comparison and selection metadata."""
    payload = {
        "random_seed": RANDOM_SEED,
        "test_size": TEST_SIZE,
        "primary_metric": "macro_f1",
        "stopping_rule": STOPPING_RULE,
        "synthetic_data_caveat": SYNTHETIC_CAVEAT,
        "selected_model": selected.model_name,
        "results": [
            {
                "model_name": item.model_name,
                "macro_f1": round(item.macro_f1, 6),
                "weighted_f1": round(item.weighted_f1, 6),
                "accuracy": round(item.accuracy, 6),
                "vignette_top1_match_count": item.vignette_top1_match_count,
                "vignette_expected_in_top3_count": (
                    item.vignette_expected_in_top3_count
                ),
                "serialized_size_bytes": item.serialized_size_bytes,
            }
            for item in sorted(
                evaluations,
                key=lambda current: (
                    -current.macro_f1,
                    -current.vignette_expected_in_top3_count,
                    -current.vignette_top1_match_count,
                    current.serialized_size_bytes,
                    current.model_name,
                ),
            )
        ],
    }
    MODEL_METRICS_PATH.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_model_bundle(selected: ModelEvaluation) -> dict[str, Any]:
    """Build the single deployable model bundle payload."""
    synonym_entries = load_synonym_lexicon()
    spell_corrector = _build_spell_corrector_config(synonym_entries)
    now_utc = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": "b3.bundle.v1",
        "created_at_utc": now_utc,
        "python_version": platform.python_version(),
        "sklearn_version": sklearn.__version__,
        "random_seed": RANDOM_SEED,
        "selected_model_name": selected.model_name,
        "model": selected.estimator,
        "feature_order": list(FROZEN_SYMPTOM_ORDER),
        "default_zero_features": sorted(DEFAULT_ZERO_FEATURES),
        "frozen_vocabulary": load_frozen_symptom_vocabulary(),
        "synonym_lexicon": synonym_entries,
        "spell_corrector": spell_corrector,
        "lookup_table": load_category_lookup(),
        "synthetic_data_caveat": SYNTHETIC_CAVEAT,
    }


def _save_bundle(bundle_payload: dict[str, Any]) -> None:
    """Persist model bundle and perform immediate local load check."""
    joblib.dump(bundle_payload, MODEL_BUNDLE_PATH)
    loaded = joblib.load(MODEL_BUNDLE_PATH)

    if loaded["sklearn_version"] != sklearn.__version__:
        raise ValueError(
            "Bundle sklearn version does not match installed version."
        )

    model = loaded["model"]
    vector = np.zeros((1, len(loaded["feature_order"])), dtype=int)
    frame = pd.DataFrame(vector, columns=loaded["feature_order"])
    _ = model.predict_proba(frame)


def _save_vignette_checks(payload: dict[str, Any]) -> None:
    """Persist quick 2–4 symptom vignette behavior checks."""
    VIGNETTE_CHECK_PATH.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Run B3 model training, evaluation, and bundling end-to-end."""
    evaluations, _, _ = _evaluate_models()
    selected = _select_best_model(evaluations)

    _save_metrics_json(evaluations, selected)
    _save_confusion_matrix(selected)

    bundle_payload = _build_model_bundle(selected)
    _save_bundle(bundle_payload)

    vignette_payload = _run_vignette_checks_for_estimator(
        bundle_payload["model"]
    )
    _save_vignette_checks(vignette_payload)


if __name__ == "__main__":
    main()
