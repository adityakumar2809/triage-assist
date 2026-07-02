"""Build B2 offline data artifacts from frozen design and raw dataset."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parent
DESIGN_BIBLE_PATH = ROOT_DIR / "design_reference" / "design-bible.md"
RAW_DATASET_PATH = DATA_DIR / "symbipredict_2022_raw.csv"


@dataclass(frozen=True)
class SymptomColumn:
    """One canonical symptom-column record from the frozen §4.1 table."""

    index: int
    name: str
    class_tag: str

    @property
    def class_kind(self) -> str:
        """Return class without marker suffixes such as H*."""
        return self.class_tag.replace("*", "")

    @property
    def default_zero(self) -> bool:
        """Return whether this feature must be held at zero by design."""
        return self.class_kind == "C" or self.name == "extra_marital_contacts"


def _strip_markdown(value: str) -> str:
    """Strip simple markdown control characters used in table cells."""
    return value.replace("**", "").replace("*", "").replace("`", "").strip()


def _extract_section(
    lines: list[str],
    start_heading: str,
    end_heading: str,
) -> list[str]:
    """Extract a section by heading markers."""
    start_index = next(
        index
        for index, line in enumerate(lines)
        if line.startswith(start_heading)
    )
    end_index = next(
        index
        for index, line in enumerate(lines[start_index + 1 :], start_index + 1)
        if line.startswith(end_heading)
    )
    return lines[start_index + 1 : end_index]


def _extract_markdown_rows(section_lines: list[str]) -> list[list[str]]:
    """Extract markdown table rows from a section block."""
    rows: list[list[str]] = []
    for line in section_lines:
        if not line.startswith("|"):
            continue
        if line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append(cells)
    return rows


def _parse_frozen_symptom_columns(lines: list[str]) -> list[SymptomColumn]:
    """Parse the frozen §4.1 symptom table."""
    section = _extract_section(
        lines,
        "### 4.1 Frozen symptom vocabulary & column order",
        "## 5. Users & use cases",
    )
    rows = _extract_markdown_rows(section)

    columns: list[SymptomColumn] = []
    for row in rows:
        if len(row) < 3:
            continue
        if not row[0].isdigit():
            continue
        ordinal = int(row[0])
        columns.append(
            SymptomColumn(
                index=ordinal - 1,
                name=row[1],
                class_tag=row[2],
            )
        )

    if len(columns) != 131:
        raise ValueError("Frozen symptom table must have 131 rows.")
    return columns


def _parse_condition_category_mapping(
    lines: list[str],
) -> list[dict[str, str]]:
    """Parse the frozen §13.4 raw-label to category mapping."""
    section = _extract_section(
        lines,
        "### 13.4 Disease → condition-category grouping (the model's "
        "training target)",
        "### 13.5 Lookup table (category → safe phrasing → "
        "specialist group → severity tier)",
    )
    rows = _extract_markdown_rows(section)

    mappings: list[dict[str, str]] = []
    for row in rows:
        if len(row) != 2:
            continue
        if not row[0].startswith("**"):
            continue
        category = _strip_markdown(row[0])
        labels = [label.strip() for label in row[1].split(";")]
        for label in labels:
            mappings.append(
                {
                    "raw_label": label,
                    "condition_category": category,
                }
            )

    if len(mappings) != 41:
        raise ValueError("Expected 41 raw-label mappings from §13.4.")
    return mappings


def _parse_lookup_table(lines: list[str]) -> list[dict[str, str]]:
    """Parse the frozen §13.5 lookup table."""
    section = _extract_section(
        lines,
        "### 13.5 Lookup table (category → safe phrasing → "
        "specialist group → severity tier)",
        "### 13.6 Symptom → body-system grouping (intake checklist UX only)",
    )
    rows = _extract_markdown_rows(section)

    lookup_rows: list[dict[str, str]] = []
    for row in rows:
        if len(row) != 5:
            continue
        if row[0] == "Condition category" or row[0].startswith("---"):
            continue
        tier_parts = [part.strip() for part in row[4].split("—")]
        if len(tier_parts) != 2:
            continue
        tier_name = tier_parts[0]
        tier_label = tier_parts[1]
        point_note = row[3]
        if point_note in {"—", "-"}:
            point_note = ""
        else:
            point_note = point_note.strip('"')
        lookup_rows.append(
            {
                "condition_category": row[0],
                "safe_display_phrasing": row[1].strip('"'),
                "point_of_care": row[2],
                "point_of_care_note": point_note,
                "severity_tier": tier_name,
                "severity_tier_label": tier_label,
            }
        )

    if len(lookup_rows) != 10:
        raise ValueError("Expected 10 lookup rows from §13.5.")
    return lookup_rows


def _parse_red_flag_rules(lines: list[str]) -> dict[str, Any]:
    """Parse deterministic red-flag symptom rules from §12.3."""
    section = _extract_section(
        lines,
        "### 12.3 Red-flag symptom rules (structured / known symptoms — "
        "immediate emergency path)",
        "### 12.4 Free-text danger-phrase list (scanned in raw free text, "
        "before NLP)",
    )
    section_text = "\n".join(section)

    rows = _extract_markdown_rows(section)
    solo_triggers: list[str] = []
    combination_rules: list[dict[str, str]] = []
    for row in rows:
        if (
            len(row) == 2
            and row[0] != "Red-flag symptom (canonical, §4.1)"
            and row[0] != "---"
        ):
            solo_triggers.append(row[0])
        if len(row) == 3 and row[0].startswith("CR"):
            combination_rules.append(
                {
                    "id": row[0],
                    "rule": row[1],
                    "cluster": row[2],
                }
            )

    combo_sentence = next(
        line
        for line in section
        if "combination-trigger symptoms are exactly" in line
    )
    combo_body = combo_sentence.split("exactly:", maxsplit=1)[1]
    combo_body = combo_body.split("plus the", maxsplit=1)[0]
    combination_set = re.findall(r"`([^`]+)`", combo_body)

    swelling_match = re.search(
        r"risk:\s*`([^`]+)`,\s*`([^`]+)`",
        section_text,
    )
    if not swelling_match:
        raise ValueError("Could not parse swelling-cue set from §12.3.")
    swelling_cues = [swelling_match.group(1), swelling_match.group(2)]

    for cue in swelling_cues:
        if cue not in combination_set:
            combination_set.append(cue)

    return {
        "solo_triggers": solo_triggers,
        "combination_trigger_symptoms": combination_set,
        "anaphylaxis_swelling_cues": swelling_cues,
        "combination_rules": combination_rules,
        "audit_only_solo_triggers": [
            "acute_liver_failure",
            "fluid_overload",
        ],
    }


def _parse_danger_phrases(lines: list[str]) -> list[dict[str, Any]]:
    """Parse free-text danger-phrase entries from §12.4."""
    section = _extract_section(
        lines,
        "### 12.4 Free-text danger-phrase list (scanned in raw free text, "
        "before NLP)",
        "### 12.5 Negation handling and its strict bound",
    )
    rows = _extract_markdown_rows(section)

    entries: list[dict[str, Any]] = []
    for row in rows:
        if len(row) != 2:
            continue
        if row[0] == "Danger phrase / pattern" or row[0].startswith("---"):
            continue
        phrases = re.findall(r'"([^"]+)"', row[0])
        entries.append(
            {
                "pattern_group": row[0],
                "phrases": phrases,
                "emergency_category": _strip_markdown(row[1]),
            }
        )
    return entries


def _parse_synonym_lexicon(
    lines: list[str],
    canonical_names: set[str],
    red_flag_related: set[str],
) -> list[dict[str, Any]]:
    """Parse seed synonym entries from §14.2."""
    section = _extract_section(
        lines,
        "### 14.2 Stage details",
        "### 14.3 Confirmation & the no-silent-drop guarantee (FR6)",
    )
    rows = _extract_markdown_rows(section)

    phrase_index: dict[str, dict[str, Any]] = {}
    for row in rows:
        if len(row) != 3:
            continue
        if row[0] == "Lay phrasing (input)" or row[0].startswith("---"):
            continue

        canonical_cell = _strip_markdown(row[1]).lower()
        if "danger phrase" in canonical_cell:
            continue
        targets = _extract_canonical_targets(canonical_cell, canonical_names)
        if not targets:
            continue

        bucket = "unsure" if "unsure" in row[2].lower() else "understood"
        phrases = re.findall(r'"([^"]+)"', row[0])
        if not phrases:
            phrases = [_strip_markdown(row[0])]

        for phrase in phrases:
            key = phrase.lower().strip()
            existing = phrase_index.get(key)
            if existing is None:
                phrase_index[key] = {
                    "phrase": key,
                    "canonical_targets": sorted(targets),
                    "confirmation_bucket": bucket,
                    "red_flag_related": bool(
                        red_flag_related.intersection(targets)
                    ),
                }
                continue
            merged_targets = set(existing["canonical_targets"]) | set(targets)
            existing["canonical_targets"] = sorted(merged_targets)
            if existing["confirmation_bucket"] == "understood":
                existing["confirmation_bucket"] = bucket
            existing["red_flag_related"] = bool(
                red_flag_related.intersection(merged_targets)
            )

    return sorted(phrase_index.values(), key=lambda item: item["phrase"])


def _extract_canonical_targets(
    canonical_cell: str,
    canonical_names: set[str],
) -> list[str]:
    """Extract canonical symptom names from a synonym-row target cell."""
    token_candidates = re.findall(r"[a-z]+(?:_[a-z]+)*", canonical_cell)
    unique_targets: list[str] = []
    seen_targets: set[str] = set()
    for token in token_candidates:
        if token not in canonical_names:
            continue
        if token in seen_targets:
            continue
        seen_targets.add(token)
        unique_targets.append(token)
    return unique_targets


def _normalize_header(raw_header: str) -> str:
    """Normalize raw dataset headers to canonical symptom tokens."""
    cleaned = re.sub(r"\.\d+$", "", raw_header.strip().lower())
    cleaned = cleaned.replace("(", "").replace(")", "")
    cleaned = re.sub(r"\s*_\s*", "_", cleaned)
    cleaned = re.sub(r"[^a-z0-9_ ]+", "", cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")

    corrections = {
        "cold_hands_and_feets": "cold_hands_and_feet",
        "swollen_extremeties": "swollen_extremities",
    }
    return corrections.get(cleaned, cleaned)


def _normalize_label(raw_label: str) -> str:
    """Normalize known raw-label spelling variants."""
    label = raw_label.strip()
    corrections = {
        "Dimorphic Hemmorhoids (piles)": "Dimorphic Hemorrhoids (piles)",
    }
    return corrections.get(label, label)


def _build_grouped_dataset(
    columns: list[SymptomColumn],
    mappings: list[dict[str, str]],
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Build cleaned grouped dataset using frozen canonical column order."""
    raw_df = pd.read_csv(RAW_DATASET_PATH)
    canonical_order = [column.name for column in columns]
    canonical_set = set(canonical_order)
    category_by_label = {
        _normalize_label(item["raw_label"]): item["condition_category"]
        for item in mappings
    }

    alias_map: dict[str, str] = {}
    source_columns_by_canonical: dict[str, list[str]] = defaultdict(list)
    unknown_headers: list[str] = []

    for column in raw_df.columns:
        normalized = _normalize_header(column)
        if normalized == "prognosis":
            continue
        if normalized not in canonical_set:
            unknown_headers.append(column)
            continue
        alias_map[column] = normalized
        source_columns_by_canonical[normalized].append(column)

    if unknown_headers:
        unknown_list = ", ".join(sorted(unknown_headers))
        raise ValueError(f"Unrecognized raw headers: {unknown_list}")

    feature_data: dict[str, Any] = {}
    for canonical_name in canonical_order:
        source_columns = source_columns_by_canonical.get(canonical_name, [])
        if not source_columns:
            feature_data[canonical_name] = 0
            continue
        numeric = raw_df[source_columns].apply(pd.to_numeric, errors="coerce")
        numeric = numeric.fillna(0)
        feature_data[canonical_name] = (numeric.max(axis=1) > 0).astype(int)

    label_column = "prognosis"
    raw_labels = raw_df[label_column].astype(str).map(_normalize_label)
    missing_labels = sorted(set(raw_labels) - set(category_by_label))
    if missing_labels:
        raise ValueError(
            "Missing category mappings for labels: "
            + ", ".join(missing_labels)
        )

    cleaned = pd.DataFrame(feature_data, index=raw_df.index)
    default_zero_features = [
        column.name for column in columns if column.default_zero
    ]
    for feature_name in default_zero_features:
        cleaned[feature_name] = 0

    cleaned["prognosis_raw"] = raw_labels
    cleaned["condition_category"] = raw_labels.map(category_by_label)
    return cleaned, alias_map


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a list of dictionaries to a UTF-8 CSV file."""
    if not rows:
        raise ValueError(f"No rows to write for {path.name}.")
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_low_tier_spotcheck(
    mappings: list[dict[str, str]],
    lookup_rows: list[dict[str, str]],
    danger_phrases: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build spot-check records for labels in low-tier categories."""
    tier_by_category = {
        row["condition_category"]: row["severity_tier"] for row in lookup_rows
    }
    low_tier_categories = {
        category
        for category, tier in tier_by_category.items()
        if tier == "Tier 1"
    }
    low_tier_labels = [
        row
        for row in mappings
        if row["condition_category"] in low_tier_categories
    ]

    all_phrases = {
        phrase for entry in danger_phrases for phrase in entry["phrases"]
    }
    anaphylaxis_required = {
        "throat closing",
        "throat swelling",
        "tongue swelling",
        "lips swelling",
        "swollen lips/tongue",
        "anaphylaxis",
        "anaphylactic",
        "cant breathe",
        "cannot breathe",
        "short of breath",
    }
    normalized_phrases = {
        phrase.lower().replace("'", "") for phrase in all_phrases
    }
    phrase_coverage_ok = anaphylaxis_required.intersection(normalized_phrases)

    spotchecks: list[dict[str, str]] = []
    for row in sorted(low_tier_labels, key=lambda item: item["raw_label"]):
        label = row["raw_label"]
        reason = "baseline Tier 1 label"
        status = "ok"
        if label in {"Allergy", "Drug Reaction"}:
            reason = "unsafe-low seam: verify anaphylaxis phrase coverage"
            status = "covered" if phrase_coverage_ok else "missing-coverage"
        spotchecks.append(
            {
                "raw_label": label,
                "condition_category": row["condition_category"],
                "spotcheck_reason": reason,
                "safety_coverage_status": status,
            }
        )
    return spotchecks


def main() -> None:
    """Build and persist all B2 offline data artifacts."""
    lines = DESIGN_BIBLE_PATH.read_text(encoding="utf-8").splitlines()

    columns = _parse_frozen_symptom_columns(lines)
    mappings = _parse_condition_category_mapping(lines)
    lookup_rows = _parse_lookup_table(lines)
    red_flag_rules = _parse_red_flag_rules(lines)
    danger_phrases = _parse_danger_phrases(lines)

    canonical_names = {column.name for column in columns}
    red_flag_related = set(red_flag_rules["solo_triggers"]) | set(
        red_flag_rules["combination_trigger_symptoms"]
    )
    synonym_entries = _parse_synonym_lexicon(
        lines=lines,
        canonical_names=canonical_names,
        red_flag_related=red_flag_related,
    )

    grouped_df, alias_map = _build_grouped_dataset(columns, mappings)
    grouped_df.to_csv(
        DATA_DIR / "symbipredict_2022_grouped_clean.csv",
        index=False,
    )

    _write_csv(DATA_DIR / "condition_category_mapping.csv", mappings)
    _write_csv(DATA_DIR / "category_lookup.csv", lookup_rows)

    frozen_vocab_payload = {
        "source": "design_reference/design-bible.md §4.1",
        "columns": [
            {
                "index": column.index,
                "name": column.name,
                "class_tag": column.class_tag,
                "class_kind": column.class_kind,
                "default_zero": column.default_zero,
            }
            for column in columns
        ],
        "order": [column.name for column in columns],
        "default_zero_features": sorted(
            [column.name for column in columns if column.default_zero]
        ),
        "raw_header_aliases": dict(sorted(alias_map.items())),
    }
    (DATA_DIR / "frozen_symptom_vocabulary.json").write_text(
        json.dumps(frozen_vocab_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    synonym_payload = {
        "source": "design_reference/design-bible.md §14.2",
        "entries": synonym_entries,
    }
    (DATA_DIR / "synonym_lexicon.json").write_text(
        json.dumps(synonym_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    red_flag_payload = {
        "source": "design_reference/design-bible.md §12.3",
        **red_flag_rules,
    }
    (DATA_DIR / "red_flag_rules.json").write_text(
        json.dumps(red_flag_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    danger_payload = {
        "source": "design_reference/design-bible.md §12.4",
        "entries": danger_phrases,
    }
    (DATA_DIR / "danger_phrase_rules.json").write_text(
        json.dumps(danger_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    spotchecks = _build_low_tier_spotcheck(
        mappings=mappings,
        lookup_rows=lookup_rows,
        danger_phrases=danger_phrases,
    )
    _write_csv(DATA_DIR / "mapping_spotcheck_low_tier.csv", spotchecks)

    manifest = {
        "row_count": int(grouped_df.shape[0]),
        "feature_count": int(grouped_df.shape[1] - 2),
        "raw_label_count": int(grouped_df["prognosis_raw"].nunique()),
        "grouped_category_count": int(
            grouped_df["condition_category"].nunique()
        ),
    }
    (DATA_DIR / "b2_data_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
