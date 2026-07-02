"""Deterministic emergency safety gate for structured and raw-text input."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from app.data.load_curated import load_danger_phrase_rules, load_red_flag_rules
from app.data.symptom_vocabulary import FROZEN_SYMPTOM_ORDER

STANDARD_EMERGENCY_MESSAGE: Final[str] = (
    "Your symptoms may need emergency care now. Please go to the nearest "
    "emergency department or call your local emergency number immediately. "
    "Do not wait for an online result."
)

CRISIS_EMERGENCY_MESSAGE: Final[str] = (
    "It sounds like you may be in crisis, and your safety matters. Please "
    "reach out right now to a crisis line or emergency services in your "
    "area — they can help immediately. If you may have taken an overdose or "
    "are in physical danger, go to the nearest emergency department now. "
    "You don't have to face this alone, and you don't need to wait for an "
    "online result."
)

NEGATION_CUES: Final[frozenset[str]] = frozenset(
    {
        "no",
        "not",
        "without",
        "denies",
        "deny",
        "never",
    }
)

NEGATION_BIGRAMS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("dont", "have"),
        ("didnt", "have"),
        ("havent", "had"),
        ("never", "had"),
    }
)

NESTED_AMBIGUITY_BIGRAMS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("cant", "say"),
        ("cannot", "say"),
    }
)

INTERVENING_WORDS: Final[frozenset[str]] = frozenset(
    {
        "is",
        "are",
        "was",
        "were",
        "am",
        "be",
        "been",
        "being",
        "started",
        "keeps",
        "keep",
        "up",
    }
)


@dataclass(frozen=True)
class DangerPhrase:
    """One raw-text emergency phrase and metadata."""

    phrase: str
    is_self_harm: bool


@dataclass(frozen=True)
class SafetyRuntime:
    """Loaded safety rules used by the deterministic pre-model gate."""

    solo_triggers: frozenset[str]
    combination_symptoms: frozenset[str]
    swelling_cues: frozenset[str]
    danger_phrases: tuple[DangerPhrase, ...]
    symptom_text_cues: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SafetyDecision:
    """Emergency-routing decision produced by the safety gate."""

    emergency_routed: bool
    use_crisis_message: bool


@dataclass(frozen=True)
class _Token:
    """Token text and span offsets in normalized raw text."""

    text: str
    start: int
    end: int


def load_safety_runtime() -> SafetyRuntime:
    """Load frozen B2 safety rule artifacts into immutable structures."""
    red_flags = load_red_flag_rules()
    phrase_payload = load_danger_phrase_rules()

    solo_triggers = frozenset(str(item) for item in red_flags["solo_triggers"])
    combination_symptoms = frozenset(
        str(item) for item in red_flags["combination_trigger_symptoms"]
    )
    swelling_cues = frozenset(
        str(item) for item in red_flags["anaphylaxis_swelling_cues"]
    )

    phrases: list[DangerPhrase] = []
    for entry in phrase_payload:
        emergency_category = str(entry.get("emergency_category", "")).lower()
        is_self_harm = "self-harm" in emergency_category or "overdose" in (
            emergency_category
        )
        for raw_phrase in entry["phrases"]:
            phrase = str(raw_phrase).strip().lower()
            if phrase:
                phrases.append(
                    DangerPhrase(phrase=phrase, is_self_harm=is_self_harm)
                )

    relevant_symptoms = sorted(solo_triggers | combination_symptoms)
    symptom_text_cues = tuple(
        (symptom, symptom.replace("_", " ")) for symptom in relevant_symptoms
    )

    return SafetyRuntime(
        solo_triggers=solo_triggers,
        combination_symptoms=combination_symptoms,
        swelling_cues=swelling_cues,
        danger_phrases=tuple(phrases),
        symptom_text_cues=symptom_text_cues,
    )


def evaluate_safety_gate(
    runtime: SafetyRuntime,
    selected_symptoms: list[str],
    raw_text: str,
) -> SafetyDecision:
    """Evaluate deterministic emergency rules before inference."""
    valid_symptoms = set(FROZEN_SYMPTOM_ORDER)
    structured_hits = {
        symptom.strip()
        for symptom in selected_symptoms
        if symptom.strip() in valid_symptoms
    }
    (
        raw_hits,
        danger_phrase_hit,
        use_crisis_message,
    ) = _scan_raw_text_for_emergency_signals(
        runtime,
        raw_text,
    )
    signal_symptoms = structured_hits | raw_hits
    emergency_from_symptoms = _matches_red_flag_rules(
        runtime=runtime,
        signal_symptoms=signal_symptoms,
    )
    emergency_routed = (
        emergency_from_symptoms or danger_phrase_hit or use_crisis_message
    )

    return SafetyDecision(
        emergency_routed=emergency_routed,
        use_crisis_message=use_crisis_message,
    )


def build_emergency_result(
    disclaimer_text: str,
    use_crisis_message: bool,
) -> dict[str, object]:
    """Build the frozen emergency output object from §12.7/§12.8."""
    urgency_message = (
        CRISIS_EMERGENCY_MESSAGE
        if use_crisis_message
        else STANDARD_EMERGENCY_MESSAGE
    )
    return {
        "urgency": "emergency",
        "urgency_message": urgency_message,
        "point_of_care": "Emergency Department",
        "point_of_care_note": "",
        "symptoms_understood": [],
        "areas_to_discuss": [],
        "seek_sooner_if": [],
        "model_confidence": None,
        "low_confidence": False,
        "emergency_routed": True,
        "disclaimer": disclaimer_text,
    }


def _scan_raw_text_for_emergency_signals(
    runtime: SafetyRuntime,
    raw_text: str,
) -> tuple[set[str], bool, bool]:
    """Scan raw text for non-negated danger phrases and red-flag mentions."""
    normalized = _normalize_text(raw_text)
    if not normalized:
        return set(), False, False

    tokens = _tokenize(normalized)
    symptom_hits: set[str] = set()
    danger_phrase_hit = False
    crisis_phrase_hit = False

    for phrase in runtime.danger_phrases:
        for span_start, _ in _iter_phrase_spans(
            tokens=tokens,
            phrase=phrase.phrase,
        ):
            if _is_span_negated(tokens=tokens, span_start_index=span_start):
                continue
            danger_phrase_hit = True
            if phrase.is_self_harm:
                crisis_phrase_hit = True

    for symptom_name, cue in runtime.symptom_text_cues:
        for span_start, _ in _iter_phrase_spans(tokens=tokens, phrase=cue):
            if _is_span_negated(tokens=tokens, span_start_index=span_start):
                continue
            symptom_hits.add(symptom_name)
            break

    return symptom_hits, danger_phrase_hit, crisis_phrase_hit


def _matches_red_flag_rules(
    runtime: SafetyRuntime,
    signal_symptoms: set[str],
) -> bool:
    """Apply frozen solo and combination red-flag rules."""
    solo_hits = signal_symptoms.intersection(runtime.solo_triggers)
    combo_hits = signal_symptoms.intersection(runtime.combination_symptoms)

    # CR1 remains satisfied because any solo trigger is sufficient.
    if solo_hits:
        return True
    if len(combo_hits) >= 2:
        return True
    if {"stiff_neck", "high_fever"}.issubset(signal_symptoms):
        return True
    if "drying_and_tingling_lips" in signal_symptoms and (
        "breathlessness" in signal_symptoms
        or bool(signal_symptoms.intersection(runtime.swelling_cues))
    ):
        return True
    return False


def _normalize_text(raw_text: str) -> str:
    """Lowercase and collapse whitespace for phrase scanning."""
    lowered = raw_text.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def _tokenize(text: str) -> list[_Token]:
    """Tokenize normalized text with per-token spans."""
    tokens: list[_Token] = []
    for match in re.finditer(r"[a-z0-9']+", text):
        token_text = match.group(0).replace("'", "")
        tokens.append(
            _Token(
                text=token_text,
                start=match.start(),
                end=match.end(),
            )
        )
    return tokens


def _iter_phrase_spans(
    tokens: list[_Token],
    phrase: str,
) -> list[tuple[int, int]]:
    """Find phrase spans in token space with optional function-word gaps."""
    phrase_tokens = _split_phrase_tokens(phrase)
    if not phrase_tokens:
        return []

    matches: list[tuple[int, int]] = []
    for start_index, token in enumerate(tokens):
        if token.text != phrase_tokens[0]:
            continue

        cursor = start_index
        matched = True
        for target in phrase_tokens[1:]:
            next_index = cursor + 1
            if next_index < len(tokens) and tokens[next_index].text == target:
                cursor = next_index
                continue

            gap_index = cursor + 2
            if (
                gap_index < len(tokens)
                and next_index < len(tokens)
                and tokens[next_index].text in INTERVENING_WORDS
                and tokens[gap_index].text == target
            ):
                cursor = gap_index
                continue

            matched = False
            break

        if matched:
            matches.append((start_index, cursor + 1))
    return matches


def _split_phrase_tokens(phrase: str) -> list[str]:
    """Tokenize a phrase using the same normalization as raw-text tokens."""
    return [
        match.group(0).replace("'", "")
        for match in re.finditer(r"[a-z0-9']+", phrase.lower())
    ]


def _is_span_negated(
    tokens: list[_Token],
    span_start_index: int,
) -> bool:
    """Return true only for explicit adjacent negation cues (≤3 tokens)."""
    if span_start_index <= 0:
        return False

    cue_start_indexes = _find_negation_starts(
        tokens=tokens,
        start_index=max(0, span_start_index - 3),
        end_index=span_start_index,
    )
    if not cue_start_indexes:
        return False

    for cue_start in cue_start_indexes:
        nested_negations = _find_negation_starts(
            tokens=tokens,
            start_index=max(0, cue_start - 3),
            end_index=cue_start,
        )
        if nested_negations:
            return False
        if _has_nested_ambiguity_marker(
            tokens=tokens,
            start_index=max(0, cue_start - 3),
            end_index=cue_start,
        ):
            return False

    return True


def _find_negation_starts(
    tokens: list[_Token],
    start_index: int,
    end_index: int,
) -> list[int]:
    """Find negation cue starts within the token slice [start, end)."""
    starts: list[int] = []
    for index in range(start_index, end_index):
        word = tokens[index].text
        if word in NEGATION_CUES:
            starts.append(index)
            continue

        next_index = index + 1
        if next_index >= end_index:
            continue
        pair = (word, tokens[next_index].text)
        if pair in NEGATION_BIGRAMS:
            starts.append(index)
    return starts


def _has_nested_ambiguity_marker(
    tokens: list[_Token],
    start_index: int,
    end_index: int,
) -> bool:
    """Detect hedge patterns that should resolve to fire, not suppression."""
    for index in range(start_index, end_index - 1):
        pair = (tokens[index].text, tokens[index + 1].text)
        if pair in NESTED_AMBIGUITY_BIGRAMS:
            return True
    return False
