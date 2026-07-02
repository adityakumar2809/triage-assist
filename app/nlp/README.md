# NLP module

This directory contains the Chunk B7 classical free-text symptom cascade.

Implemented stages:

- Stage 1 normalize:
  lowercase, punctuation normalization, lightweight lemmatization, and
  non-word-only spell correction.
- Stage 2 synonym lexicon:
  deterministic lay-phrase mapping from `app/data/synonym_lexicon.json`.
- Stage 3 fuzzy match:
  conservative `rapidfuzz` matching against canonical symptom names and
  synonym phrases.
- Stage 4 embeddings:
  explicitly off in this build (`embeddings_enabled = false`).
- Stage 5 confirmation payload:
  understood, unsure, and unmatched outputs with no-silent-drop behavior.

Cross-cutting extraction:

- local free-text negation detection for mapped symptoms;
- free-text duration and severity extraction feeding B6 urgency modifiers.
