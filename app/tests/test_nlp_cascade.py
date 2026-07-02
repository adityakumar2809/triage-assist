"""Tests for the classical free-text NLP cascade stages."""

from __future__ import annotations

from app.nlp.cascade import (
    _is_negated,
    _lemmatize_token,
    _split_tokens,
    load_nlp_runtime,
    run_nlp_cascade,
)


def test_runtime_loads_lexicon_and_keeps_embeddings_off() -> None:
    """B7 runtime should load stage-2 assets with stage-4 disabled."""
    runtime = load_nlp_runtime()
    assert len(runtime.lexicon_entries) == 35
    assert runtime.embeddings_enabled is False


def test_synonym_cascade_maps_understood_and_unsure_sets() -> None:
    """Stage-2 synonyms should fill understood and ambiguous unsure sets."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="short of breath and stuffy nose",
    )

    assert "breathlessness" in result.understood_symptoms
    unsure_targets = {
        target
        for item in result.unsure_candidates
        for target in item.canonical_targets
    }
    assert "runny_nose" in unsure_targets
    assert "congestion" in unsure_targets


def test_negation_excludes_symptom_from_understood_set() -> None:
    """Negated free-text symptoms should not be auto-registered as present."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="no feverish today but bad cough",
    )

    assert "cough" in result.understood_symptoms
    assert "high_fever" not in result.understood_symptoms


def test_contrast_conjunction_limits_negation_scope() -> None:
    """Negation should not bleed across 'but' to the next symptom span."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="no fever but bad cough",
    )

    assert "cough" in result.understood_symptoms


def test_duration_and_severity_extraction_from_text() -> None:
    """Duration and severity cues should be extracted for urgency modifiers."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="for two weeks now severe tummy ache",
    )

    assert result.extracted_duration_days == 14
    assert result.extracted_self_severity == 8


def test_unmatched_tokens_are_surfaced_not_dropped() -> None:
    """Unknown free-text tokens must remain visible for confirmation."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="zzzxqv",
    )

    assert result.unmatched_tokens


def test_contracted_negation_is_preserved_for_bigram_detection() -> None:
    """Contraction-free negation bigrams should still suppress symptoms."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="I dont have headache",
    )

    assert "headache" not in result.understood_symptoms


def test_ed_lemmatization_does_not_break_common_adjectives() -> None:
    """-ed adjectives like tired should not be truncated to invalid stems."""
    assert _lemmatize_token("tired") == "tired"


def test_negation_cues_are_not_fuzzy_matched_to_symptoms() -> None:
    """Single negation words should never create fuzzy symptom matches."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="no",
    )

    assert result.understood_symptoms == []
    unsure_targets = {
        target
        for item in result.unsure_candidates
        for target in item.canonical_targets
    }
    assert "runny_nose" not in unsure_targets


def test_partial_ratio_noise_phrase_does_not_create_unsure_matches() -> None:
    """Common connector phrases should not emit noisy unsure suggestions."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="i have",
    )

    assert result.understood_symptoms == []
    assert result.unsure_candidates == []


def test_negation_detects_span_starting_with_negation_word() -> None:
    """A span beginning with a negation cue should be treated as negated."""
    tokens = _split_tokens("without nausea")
    assert _is_negated(tokens=tokens, span_start=0) is True


def test_lemmatized_lexicon_phrase_still_maps_to_vomiting() -> None:
    """Stage-2 synonyms must match after token lemmatization."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="throwing up",
    )

    assert "vomiting" in result.understood_symptoms


def test_two_gram_with_stopword_does_not_block_single_token_hit() -> None:
    """Stopword+symptom bigrams should not override true 1-gram matches."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="a headache",
    )

    assert "headache" in result.understood_symptoms


def test_plain_fever_maps_to_high_fever_via_lexicon() -> None:
    """Common term 'fever' should map directly to high_fever."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="fever",
    )

    assert "high_fever" in result.understood_symptoms


def test_plain_vomit_maps_to_vomiting_via_lexicon() -> None:
    """Lemmatized user term 'vomit' should map directly to vomiting."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="vomit",
    )

    assert "vomiting" in result.understood_symptoms


def test_lemmatized_ing_terms_map_to_canonical_symptoms() -> None:
    """-ing canonical inputs should still map after lemmatization."""
    runtime = load_nlp_runtime()
    result = run_nlp_cascade(
        runtime=runtime,
        raw_text="itching shivering sweating bruising",
    )

    assert "itching" in result.understood_symptoms
    assert "shivering" in result.understood_symptoms
    assert "sweating" in result.understood_symptoms
    assert "bruising" in result.understood_symptoms
