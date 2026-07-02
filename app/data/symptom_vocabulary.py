"""Load frozen symptom vocabulary from the canonical JSON artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

DATA_DIR = Path(__file__).resolve().parent
VOCAB_PATH = DATA_DIR / "frozen_symptom_vocabulary.json"


def _load_payload() -> dict[str, object]:
    """Read and return the frozen symptom-vocabulary payload."""
    with VOCAB_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


PAYLOAD = _load_payload()
_COLUMNS = PAYLOAD.get("columns", [])
if not isinstance(_COLUMNS, list):
    raise ValueError("frozen_symptom_vocabulary.json has invalid columns.")

FROZEN_SYMPTOM_COLUMNS: Final[tuple[tuple[int, str, str], ...]] = tuple(
    (
        int(column["index"]),
        str(column["name"]),
        str(column["class_tag"]),
    )
    for column in _COLUMNS
)

FROZEN_SYMPTOM_ORDER: Final[tuple[str, ...]] = tuple(
    name for _, name, _ in FROZEN_SYMPTOM_COLUMNS
)

SYMPTOM_CLASS_BY_NAME: Final[dict[str, str]] = {
    name: class_tag.replace("*", "")
    for _, name, class_tag in FROZEN_SYMPTOM_COLUMNS
}

DEFAULT_ZERO_FEATURES: Final[frozenset[str]] = frozenset(
    name
    for name, class_tag in SYMPTOM_CLASS_BY_NAME.items()
    if class_tag == "C"
) | frozenset({"extra_marital_contacts"})

RAW_HEADER_ALIASES: Final[dict[str, str]] = {
    str(raw_header): str(canonical)
    for raw_header, canonical in dict(
        PAYLOAD.get("raw_header_aliases", {})
    ).items()
}

if len(FROZEN_SYMPTOM_ORDER) != 131:
    raise ValueError("Frozen symptom order must contain 131 columns.")

if len(set(FROZEN_SYMPTOM_ORDER)) != len(FROZEN_SYMPTOM_ORDER):
    raise ValueError("Frozen symptom order contains duplicates.")
