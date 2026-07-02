"""Tests for deterministic safety-layer emergency routing logic."""

from __future__ import annotations

from app.web.safety import evaluate_safety_gate, load_safety_runtime


def test_no_chest_pain_is_negated_and_does_not_fire() -> None:
    """An explicitly negated red-flag phrase should be suppressed."""
    runtime = load_safety_runtime()
    decision = evaluate_safety_gate(
        runtime=runtime,
        selected_symptoms=[],
        raw_text="I have no chest pain today.",
    )
    assert decision.emergency_routed is False


def test_unnegated_chest_pain_phrase_fires() -> None:
    """An unnegated emergency phrase should route to emergency."""
    runtime = load_safety_runtime()
    decision = evaluate_safety_gate(
        runtime=runtime,
        selected_symptoms=[],
        raw_text="I have crushing chest pain right now.",
    )
    assert decision.emergency_routed is True


def test_negation_scope_is_local_not_global() -> None:
    """Negating one cue must not suppress a different emergency cue."""
    runtime = load_safety_runtime()
    decision = evaluate_safety_gate(
        runtime=runtime,
        selected_symptoms=[],
        raw_text="No fever, but crushing chest pain started suddenly.",
    )
    assert decision.emergency_routed is True


def test_intervening_verb_variants_fire_anaphylaxis_phrases() -> None:
    """Common swelling/closing phrasing variants must still fire."""
    runtime = load_safety_runtime()
    samples = [
        "my throat is swelling up",
        "my throat is closing",
        "my lips are swelling",
        "my tongue is swelling",
    ]
    for sample in samples:
        decision = evaluate_safety_gate(
            runtime=runtime,
            selected_symptoms=[],
            raw_text=sample,
        )
        assert decision.emergency_routed is True


def test_double_negation_does_not_suppress_red_flag() -> None:
    """Double-negation and hedging should resolve toward emergency firing."""
    runtime = load_safety_runtime()
    decision = evaluate_safety_gate(
        runtime=runtime,
        selected_symptoms=[],
        raw_text="I cant say I dont have chest pain",
    )
    assert decision.emergency_routed is True


def test_contracted_words_do_not_suppress_red_flags() -> None:
    """Contractions like 'cant' should not act as standalone negation."""
    runtime = load_safety_runtime()
    samples = [
        "I cant believe this chest pain",
        "I cant stand this chest pain",
        "I cant stop the chest pain",
    ]
    for sample in samples:
        decision = evaluate_safety_gate(
            runtime=runtime,
            selected_symptoms=[],
            raw_text=sample,
        )
        assert decision.emergency_routed is True
