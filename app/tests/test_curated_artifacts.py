"""Tests for frozen curated data artifacts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.data.load_curated import (
    load_body_system_groups,
    load_category_lookup,
    load_condition_category_mapping,
    load_danger_phrase_rules,
    load_frozen_symptom_vocabulary,
    load_grouped_dataset_rows,
    load_red_flag_rules,
    load_synonym_lexicon,
)
from app.data.symptom_vocabulary import (
    DEFAULT_ZERO_FEATURES,
    FROZEN_SYMPTOM_ORDER,
    SYMPTOM_CLASS_BY_NAME,
)


def _normalize_label(label: str) -> str:
    """Normalize known spelling variation in the raw prognosis labels."""
    corrections = {
        "Dimorphic Hemmorhoids (piles)": "Dimorphic Hemorrhoids (piles)",
    }
    return corrections.get(label.strip(), label.strip())


def test_frozen_symptom_order_has_expected_boundaries() -> None:
    """The canonical symptom order remains a single 131-column artifact."""
    assert len(FROZEN_SYMPTOM_ORDER) == 131
    assert FROZEN_SYMPTOM_ORDER[0] == "itching"
    assert FROZEN_SYMPTOM_ORDER[-1] == "yellow_crust_ooze"
    assert len(set(FROZEN_SYMPTOM_ORDER)) == 131


def test_default_zero_feature_set_matches_design_rule() -> None:
    """All C-class columns and extra_marital_contacts are default-zero."""
    c_features = {
        name
        for name, class_tag in SYMPTOM_CLASS_BY_NAME.items()
        if class_tag == "C"
    }
    assert c_features.issubset(DEFAULT_ZERO_FEATURES)
    assert "extra_marital_contacts" in DEFAULT_ZERO_FEATURES


def test_curated_tables_are_loadable_and_complete() -> None:
    """Curated mapping and lookup artifacts load with expected cardinality."""
    lookup = load_category_lookup()
    mapping = load_condition_category_mapping()
    grouped = load_body_system_groups()

    assert len(lookup) == 10
    assert len(mapping) == 41
    assert len(grouped) == 10
    assert all(grouped.values())


def test_mapping_is_total_for_raw_labels_and_lookup_is_complete() -> None:
    """Every raw prognosis label maps exactly once and has lookup metadata."""
    raw_path = Path("app/data/symbipredict_2022_raw.csv")
    raw_df = pd.read_csv(raw_path)
    raw_labels = {_normalize_label(label) for label in raw_df["prognosis"]}

    mapping_rows = load_condition_category_mapping()
    mapped_labels = [row["raw_label"] for row in mapping_rows]
    assert len(mapped_labels) == len(set(mapped_labels))
    assert set(mapped_labels) == raw_labels

    lookup_rows = load_category_lookup()
    lookup_by_category = {
        row["condition_category"]: row for row in lookup_rows
    }
    mapped_categories = {row["condition_category"] for row in mapping_rows}
    assert mapped_categories == set(lookup_by_category)
    assert all(row["point_of_care"] for row in lookup_rows)
    assert all(row["severity_tier"] for row in lookup_rows)


def test_grouped_dataset_and_vocab_artifact_are_loadable() -> None:
    """The cleaned grouped dataset follows the frozen canonical order."""
    dataset_rows = load_grouped_dataset_rows()
    assert dataset_rows

    first_row = dataset_rows[0]
    column_names = list(first_row)
    assert column_names[:131] == list(FROZEN_SYMPTOM_ORDER)
    assert column_names[-2:] == ["prognosis_raw", "condition_category"]

    vocab_payload = load_frozen_symptom_vocabulary()
    assert len(vocab_payload["order"]) == 131
    assert vocab_payload["order"][0] == FROZEN_SYMPTOM_ORDER[0]
    assert vocab_payload["order"][-1] == FROZEN_SYMPTOM_ORDER[-1]


def test_synonyms_and_safety_lists_are_populated() -> None:
    """Synonym lexicon, red flags, and danger phrases load with content."""
    synonym_entries = load_synonym_lexicon()
    red_flag_rules = load_red_flag_rules()
    danger_phrase_entries = load_danger_phrase_rules()

    assert synonym_entries
    phrase_set = {entry["phrase"] for entry in synonym_entries}
    assert "short of breath" in phrase_set
    assert "throwing up" in phrase_set

    assert "chest_pain" in red_flag_rules["solo_triggers"]
    assert "breathlessness" in red_flag_rules["solo_triggers"]
    assert "coma" in red_flag_rules["solo_triggers"]
    assert red_flag_rules["combination_rules"]
    assert red_flag_rules["anaphylaxis_swelling_cues"] == [
        "puffy_face_and_eyes",
        "swollen_extremities",
    ]

    flat_danger_phrases = {
        phrase
        for entry in danger_phrase_entries
        for phrase in entry["phrases"]
    }
    assert "throat swelling" in flat_danger_phrases
    assert "vomiting blood" in flat_danger_phrases
    assert "short of breath" in flat_danger_phrases


def test_grouped_dataset_default_zero_features_are_constant_zero() -> None:
    """Grouped dataset enforces the frozen default-zero metric-honesty rule."""
    grouped_df = pd.read_csv("app/data/symbipredict_2022_grouped_clean.csv")

    assert len(DEFAULT_ZERO_FEATURES) == 8
    for feature_name in DEFAULT_ZERO_FEATURES:
        assert int(grouped_df[feature_name].max()) == 0


def test_low_tier_spotcheck_covers_known_risk_labels() -> None:
    """Tier-1 mapping spot-check captures Allergy and Drug Reaction seams."""
    spotcheck_path = Path("app/data/mapping_spotcheck_low_tier.csv")
    spotcheck_df = pd.read_csv(spotcheck_path)

    labels = set(spotcheck_df["raw_label"])
    assert {"Allergy", "Drug Reaction"}.issubset(labels)

    risk_rows = spotcheck_df[
        spotcheck_df["raw_label"].isin(["Allergy", "Drug Reaction"])
    ]
    assert set(risk_rows["safety_coverage_status"]) == {"covered"}
