"""Classical free-text NLP cascade for symptom mapping and confirmation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
from spellchecker import SpellChecker

from app.data.load_curated import load_synonym_lexicon
from app.data.symptom_vocabulary import FROZEN_SYMPTOM_ORDER

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

NEGATION_BIGRAM_START_TOKENS: Final[frozenset[str]] = frozenset(
    first for first, _ in NEGATION_BIGRAMS
)

CONTRAST_CONJUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        "but",
        "however",
        "although",
        "yet",
        "though",
    }
)

STOPWORD_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "my",
        "now",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
    }
)

TIME_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "day",
        "days",
        "week",
        "weeks",
        "month",
        "months",
        "hour",
        "hours",
        "since",
        "last",
        "today",
        "yesterday",
        "couple",
        "few",
    }
)

SEVERITY_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "mild",
        "moderate",
        "severe",
        "unbearable",
        "intense",
        "excruciating",
        "slight",
        "minor",
        "worst",
        "pain",
    }
)

NUMBER_WORDS: Final[dict[str, int]] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "couple": 2,
    "few": 3,
}

SEVERE_CUES: Final[frozenset[str]] = frozenset(
    {"severe", "unbearable", "intense", "excruciating", "worst"}
)
MODERATE_CUES: Final[frozenset[str]] = frozenset({"moderate"})
MILD_CUES: Final[frozenset[str]] = frozenset({"mild", "slight", "minor"})

ED_SUFFIX_EXCEPTIONS: Final[frozenset[str]] = frozenset(
    {
        "tired",
        "scared",
        "bored",
        "stressed",
        "worried",
        "excited",
        "exhausted",
    }
)


@dataclass(frozen=True)
class LexiconEntry:
    """One synonym-lexicon mapping row."""

    phrase: str
    phrase_tokens: tuple[str, ...]
    canonical_targets: tuple[str, ...]
    confirmation_bucket: str


@dataclass(frozen=True)
class UnsureCandidate:
    """One unsure confirmation row shown to the user."""

    source_text: str
    canonical_targets: tuple[str, ...]
    prompt: str


@dataclass(frozen=True)
class CascadeResult:
    """Output of the free-text cascade before user confirmation."""

    understood_symptoms: list[str]
    unsure_candidates: list[UnsureCandidate]
    unmatched_tokens: list[str]
    extracted_duration_days: int | None
    extracted_self_severity: int | None


@dataclass(frozen=True)
class _FuzzyChoice:
    """Fuzzy lookup metadata for a candidate term."""

    canonical_targets: tuple[str, ...]
    confirmation_bucket: str


@dataclass(frozen=True)
class NlpRuntime:
    """Loaded NLP artifacts and deterministic stage configuration."""

    lexicon_entries: tuple[LexiconEntry, ...]
    fuzzy_terms: tuple[str, ...]
    fuzzy_metadata: dict[str, _FuzzyChoice]
    known_tokens: frozenset[str]
    spellchecker: SpellChecker
    fuzzy_high_threshold: int
    fuzzy_unsure_threshold: int
    embeddings_enabled: bool


@dataclass(frozen=True)
class _SpanMatch:
    """Intermediate matched span from stage 2 or stage 3."""

    start: int
    end: int
    source_text: str
    canonical_targets: tuple[str, ...]
    confirmation_bucket: str
    negated: bool


def load_nlp_runtime() -> NlpRuntime:
    """Load and freeze stage-2/3 assets for the free-text cascade."""
    valid_symptoms = set(FROZEN_SYMPTOM_ORDER)
    lexicon_payload = load_synonym_lexicon()
    lexicon_entries: list[LexiconEntry] = []
    known_tokens: set[str] = set()

    for raw_entry in lexicon_payload:
        phrase = str(raw_entry["phrase"]).strip().lower()
        phrase_tokens = tuple(
            _lemmatize_token(token) for token in _split_tokens(phrase)
        )
        canonical_targets = tuple(
            target
            for target in (
                str(item).strip()
                for item in raw_entry.get("canonical_targets", [])
            )
            if target in valid_symptoms
        )
        confirmation_bucket = str(raw_entry["confirmation_bucket"]).strip()
        if not phrase_tokens or not canonical_targets:
            continue

        lexicon_entries.append(
            LexiconEntry(
                phrase=phrase,
                phrase_tokens=phrase_tokens,
                canonical_targets=canonical_targets,
                confirmation_bucket=confirmation_bucket,
            )
        )
        known_tokens.update(phrase_tokens)

    lexicon_entries.sort(
        key=lambda item: len(item.phrase_tokens),
        reverse=True,
    )

    fuzzy_metadata: dict[str, _FuzzyChoice] = {}
    for symptom_name in FROZEN_SYMPTOM_ORDER:
        fuzzy_term = symptom_name.replace("_", " ")
        fuzzy_metadata[fuzzy_term] = _FuzzyChoice(
            canonical_targets=(symptom_name,),
            confirmation_bucket="understood",
        )
        known_tokens.update(_split_tokens(fuzzy_term))

    for entry in lexicon_entries:
        normalized_phrase = " ".join(entry.phrase_tokens)
        if normalized_phrase not in fuzzy_metadata:
            fuzzy_metadata[normalized_phrase] = _FuzzyChoice(
                canonical_targets=entry.canonical_targets,
                confirmation_bucket=entry.confirmation_bucket,
            )

    # Preserve negation cues exactly so spell-correction never mutates them.
    known_tokens.update(NEGATION_CUES)
    known_tokens.update(NEGATION_BIGRAM_START_TOKENS)
    known_tokens.update({"cant", "cannot", "wont"})

    spellchecker = SpellChecker(distance=1)
    return NlpRuntime(
        lexicon_entries=tuple(lexicon_entries),
        fuzzy_terms=tuple(fuzzy_metadata.keys()),
        fuzzy_metadata=fuzzy_metadata,
        known_tokens=frozenset(known_tokens),
        spellchecker=spellchecker,
        fuzzy_high_threshold=90,
        fuzzy_unsure_threshold=86,
        embeddings_enabled=False,
    )


def run_nlp_cascade(
    runtime: NlpRuntime,
    raw_text: str,
) -> CascadeResult:
    """Run normalize -> synonyms -> fuzzy -> confirmation bucketing."""
    normalized_tokens = _normalize_tokens(raw_text, runtime=runtime)
    if not normalized_tokens:
        return CascadeResult(
            understood_symptoms=[],
            unsure_candidates=[],
            unmatched_tokens=[],
            extracted_duration_days=None,
            extracted_self_severity=None,
        )

    normalized_text = " ".join(normalized_tokens)
    extracted_duration_days = _extract_duration_days(normalized_text)
    extracted_self_severity = _extract_self_severity(normalized_text)

    consumed: set[int] = set()
    understood_set: set[str] = set()
    unsure_candidates: list[UnsureCandidate] = []

    stage2_matches = _match_lexicon_spans(
        tokens=normalized_tokens,
        runtime=runtime,
    )
    for match in stage2_matches:
        consumed.update(range(match.start, match.end))
        _record_match_outcome(
            match=match,
            understood_set=understood_set,
            unsure_candidates=unsure_candidates,
        )

    stage3_matches = _match_fuzzy_spans(
        tokens=normalized_tokens,
        consumed=consumed,
        runtime=runtime,
    )
    for match in stage3_matches:
        consumed.update(range(match.start, match.end))
        _record_match_outcome(
            match=match,
            understood_set=understood_set,
            unsure_candidates=unsure_candidates,
        )

    understood_symptoms = [
        symptom
        for symptom in FROZEN_SYMPTOM_ORDER
        if symptom in understood_set
    ]
    unmatched_tokens = _collect_unmatched_tokens(
        tokens=normalized_tokens,
        consumed=consumed,
    )
    return CascadeResult(
        understood_symptoms=understood_symptoms,
        unsure_candidates=_dedupe_unsure(unsure_candidates),
        unmatched_tokens=unmatched_tokens,
        extracted_duration_days=extracted_duration_days,
        extracted_self_severity=extracted_self_severity,
    )


def _normalize_tokens(
    raw_text: str,
    runtime: NlpRuntime,
) -> list[str]:
    """Lowercase, normalize punctuation, lemmatize, and fix non-word typos."""
    lowered = raw_text.lower()
    normalized = re.sub(r"[^a-z0-9'\s]+", " ", lowered)
    collapsed = re.sub(r"\s+", " ", normalized).strip()
    if not collapsed:
        return []

    tokens: list[str] = []
    for raw_token in _split_tokens(collapsed):
        lemmatized = _lemmatize_token(raw_token)
        corrected = _spell_correct_non_word(lemmatized, runtime=runtime)
        if corrected:
            tokens.append(corrected)
    return tokens


def _split_tokens(text: str) -> list[str]:
    """Split text into alphanumeric token chunks, stripping apostrophes."""
    return [
        match.group(0).replace("'", "")
        for match in re.finditer(r"[a-z0-9']+", text.lower())
    ]


def _lemmatize_token(token: str) -> str:
    """Apply lightweight deterministic lemmatization rules."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        stem = token[:-3]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if len(token) > 4 and token.endswith("ed"):
        if token in ED_SUFFIX_EXCEPTIONS:
            return token
        stem = token[:-2]
        if len(stem) < 4:
            return token
        if len(stem) > 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        if len(stem) < 4:
            return token
        return stem
    if (
        len(token) > 3
        and token.endswith("s")
        and not token.endswith("ss")
        and not token.endswith("is")
    ):
        return token[:-1]
    return token


def _spell_correct_non_word(token: str, runtime: NlpRuntime) -> str:
    """Correct only true non-words, keeping valid words untouched."""
    if token.isdigit() or token in runtime.known_tokens:
        return token
    if runtime.spellchecker.known([token]):
        return token

    candidate = runtime.spellchecker.correction(token)
    if not candidate:
        return token
    if Levenshtein.distance(token, candidate) > 1:
        return token
    return candidate


def _match_lexicon_spans(
    tokens: list[str],
    runtime: NlpRuntime,
) -> list[_SpanMatch]:
    """Map phrase spans using exact synonym-lexicon matches."""
    matches: list[_SpanMatch] = []
    consumed: set[int] = set()

    for entry in runtime.lexicon_entries:
        phrase_len = len(entry.phrase_tokens)
        for start in range(0, len(tokens) - phrase_len + 1):
            end = start + phrase_len
            if any(index in consumed for index in range(start, end)):
                continue
            if tuple(tokens[start:end]) != entry.phrase_tokens:
                continue
            match = _SpanMatch(
                start=start,
                end=end,
                source_text=" ".join(tokens[start:end]),
                canonical_targets=entry.canonical_targets,
                confirmation_bucket=entry.confirmation_bucket,
                negated=_is_negated(tokens=tokens, span_start=start),
            )
            matches.append(match)
            consumed.update(range(start, end))
    return matches


def _match_fuzzy_spans(
    tokens: list[str],
    consumed: set[int],
    runtime: NlpRuntime,
) -> list[_SpanMatch]:
    """Map remaining token spans using conservative fuzzy matching."""
    matches: list[_SpanMatch] = []
    local_consumed = set(consumed)

    for phrase_len in (2, 1):
        for start in range(0, len(tokens) - phrase_len + 1):
            end = start + phrase_len
            if any(index in local_consumed for index in range(start, end)):
                continue
            span_tokens = tokens[start:end]
            if phrase_len == 2 and any(
                token in STOPWORD_TOKENS
                or token in NEGATION_CUES
                or token in NEGATION_BIGRAM_START_TOKENS
                for token in span_tokens
            ):
                continue

            candidate_text = " ".join(span_tokens)
            if phrase_len == 1 and (
                candidate_text in STOPWORD_TOKENS
                or candidate_text in NEGATION_CUES
                or candidate_text in NEGATION_BIGRAM_START_TOKENS
                or len(candidate_text) <= 2
            ):
                continue

            fuzzy_hit = process.extractOne(
                candidate_text,
                runtime.fuzzy_terms,
                scorer=fuzz.ratio,
            )
            if fuzzy_hit is None:
                continue
            fuzzy_term, score, _ = fuzzy_hit
            if score < runtime.fuzzy_unsure_threshold:
                continue

            metadata = runtime.fuzzy_metadata[fuzzy_term]
            if score >= runtime.fuzzy_high_threshold:
                bucket = metadata.confirmation_bucket
            else:
                bucket = "unsure"

            match = _SpanMatch(
                start=start,
                end=end,
                source_text=candidate_text,
                canonical_targets=metadata.canonical_targets,
                confirmation_bucket=bucket,
                negated=_is_negated(tokens=tokens, span_start=start),
            )
            matches.append(match)
            local_consumed.update(range(start, end))

    return matches


def _is_negated(tokens: list[str], span_start: int) -> bool:
    """Return true for explicit negation cues in a local three-token window."""
    if span_start < 0 or span_start >= len(tokens):
        return False

    if tokens[span_start] in NEGATION_CUES:
        return True
    if (
        span_start + 1 < len(tokens)
        and (
            tokens[span_start],
            tokens[span_start + 1],
        )
        in NEGATION_BIGRAMS
    ):
        return True

    if span_start == 0:
        return False

    window_start = max(0, span_start - 3)
    for index in range(span_start - 1, window_start - 1, -1):
        token = tokens[index]
        if token in CONTRAST_CONJUNCTIONS:
            break
        if token in NEGATION_CUES:
            return True
        if (
            index - 1 >= window_start
            and (
                tokens[index - 1],
                token,
            )
            in NEGATION_BIGRAMS
        ):
            return True
    return False


def _record_match_outcome(
    match: _SpanMatch,
    understood_set: set[str],
    unsure_candidates: list[UnsureCandidate],
) -> None:
    """Put one span match into understood vs unsure confirmation sets."""
    if match.negated:
        unsure_candidates.append(
            UnsureCandidate(
                source_text=match.source_text,
                canonical_targets=match.canonical_targets,
                prompt=(
                    "This looked negated in your text. Confirm it only if "
                    "the symptom is actually present."
                ),
            )
        )
        return

    if (
        match.confirmation_bucket == "understood"
        and len(match.canonical_targets) == 1
    ):
        understood_set.add(match.canonical_targets[0])
        return

    unsure_candidates.append(
        UnsureCandidate(
            source_text=match.source_text,
            canonical_targets=match.canonical_targets,
            prompt="Did you mean one of these symptoms?",
        )
    )


def _collect_unmatched_tokens(
    tokens: list[str],
    consumed: set[int],
) -> list[str]:
    """Collect unmatched non-noise tokens to enforce no-silent-drop."""
    unmatched: list[str] = []
    seen: set[str] = set()
    noise_tokens = STOPWORD_TOKENS | TIME_TOKENS | SEVERITY_TOKENS

    for index, token in enumerate(tokens):
        if index in consumed:
            continue
        if token in noise_tokens or token.isdigit():
            continue
        if token not in seen:
            unmatched.append(token)
            seen.add(token)
    return unmatched


def _dedupe_unsure(candidates: list[UnsureCandidate]) -> list[UnsureCandidate]:
    """Drop duplicate unsure prompts while preserving order."""
    deduped: list[UnsureCandidate] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for item in candidates:
        key = (item.source_text, item.canonical_targets)
        if key in seen:
            continue
        deduped.append(item)
        seen.add(key)
    return deduped


def _extract_duration_days(normalized_text: str) -> int | None:
    """Extract free-text duration as a best-effort day count."""
    for pattern in (
        r"\bfor\s+(\d{1,2})\s+(day|days|week|weeks|month|months|hour|hours)\b",
        r"\b(\d{1,2})\s+(day|days|week|weeks|month|months|hour|hours)\b",
    ):
        match = re.search(pattern, normalized_text)
        if match:
            count = int(match.group(1))
            return _convert_to_days(count=count, unit=match.group(2))

    for pattern in (
        r"\bfor\s+(one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s+(day|days|week|weeks|month|months|hour|hours)\b",
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|couple|few)"
        r"\s+(day|days|week|weeks|month|months|hour|hours)\b",
    ):
        match = re.search(pattern, normalized_text)
        if match:
            number_word = match.group(1)
            return _convert_to_days(
                count=NUMBER_WORDS[number_word],
                unit=match.group(2),
            )

    if re.search(r"\blast\s+week\b", normalized_text):
        return 7
    if re.search(r"\byesterday\b", normalized_text):
        return 1
    if re.search(r"\btoday\b", normalized_text):
        return 0
    return None


def _convert_to_days(count: int, unit: str) -> int:
    """Convert parsed count+unit duration mentions into day counts."""
    if unit.startswith("hour"):
        return 0
    if unit.startswith("day"):
        return count
    if unit.startswith("week"):
        return count * 7
    if unit.startswith("month"):
        return count * 30
    return count


def _extract_self_severity(normalized_text: str) -> int | None:
    """Extract optional self-severity score from free-text intensity cues."""
    score_match = re.search(
        r"\b([1-9]|10)\s*(?:/|out of)\s*10\b", normalized_text
    )
    if score_match:
        return int(score_match.group(1))

    tokens = set(_split_tokens(normalized_text))
    if tokens.intersection(SEVERE_CUES):
        return 8
    if tokens.intersection(MODERATE_CUES):
        return 5
    if tokens.intersection(MILD_CUES):
        return 2
    return None
