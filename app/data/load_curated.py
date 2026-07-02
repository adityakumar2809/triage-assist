"""Helpers to load curated data artifacts from this directory."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent


def load_category_lookup() -> list[dict[str, str]]:
    """Load the frozen category lookup table from CSV."""
    lookup_path = DATA_DIR / "category_lookup.csv"
    with lookup_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def load_condition_category_mapping() -> list[dict[str, str]]:
    """Load the frozen raw-label to condition-category mapping."""
    mapping_path = DATA_DIR / "condition_category_mapping.csv"
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def load_body_system_groups() -> dict[str, list[str]]:
    """Load the frozen symptom-to-body-system intake grouping map."""
    groups_path = DATA_DIR / "symptom_body_system_groups.json"
    with groups_path.open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    return {name: list(items) for name, items in payload.items()}


def load_frozen_symptom_vocabulary() -> dict[str, Any]:
    """Load the canonical frozen symptom-vocabulary artifact."""
    vocab_path = DATA_DIR / "frozen_symptom_vocabulary.json"
    with vocab_path.open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    return payload


def load_synonym_lexicon() -> list[dict[str, Any]]:
    """Load the NLP synonym-lexicon artifact."""
    lexicon_path = DATA_DIR / "synonym_lexicon.json"
    with lexicon_path.open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    entries = payload.get("entries", [])
    return [dict(entry) for entry in entries]


def load_red_flag_rules() -> dict[str, Any]:
    """Load deterministic red-flag symptom rules."""
    rules_path = DATA_DIR / "red_flag_rules.json"
    with rules_path.open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    return payload


def load_danger_phrase_rules() -> list[dict[str, Any]]:
    """Load free-text danger-phrase rules."""
    rules_path = DATA_DIR / "danger_phrase_rules.json"
    with rules_path.open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    entries = payload.get("entries", [])
    return [dict(entry) for entry in entries]


def load_grouped_dataset_rows() -> list[dict[str, str]]:
    """Load the cleaned grouped dataset as row dictionaries."""
    dataset_path = DATA_DIR / "symbipredict_2022_grouped_clean.csv"
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]
