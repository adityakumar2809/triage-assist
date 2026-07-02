# QA Bug Report

## BUG-001: Safety tokenizer does not handle double negation ("not denying")
- **Severity:** P3 (Low — edge case, clinical language, not lay usage)
- **Component:** `app/web/safety.py` → `_is_span_negated`
- **Status:** Open

### Description
The safety tokenizer does not lemmatize tokens, so "denying" is not recognized
as a negation cue (only "deny" and "denies" are in NEGATION_CUES). When a user
writes "not denying chest pain" (double negation = affirmation), the safety
layer sees only "not" as a negation cue before "chest pain" and suppresses the
emergency trigger.

### Reproduction
```python
from app.web.safety import load_safety_runtime, evaluate_safety_gate
rt = load_safety_runtime()
d = evaluate_safety_gate(rt, [], "not denying chest pain")
assert d.emergency_routed  # FAILS — returns False
```

### Expected
"Not denying chest pain" = affirmation of chest pain → should fire emergency.

### Actual
Safety gate treats "chest pain" as negated (by "not") and does NOT fire.

### Impact
Very low in practice — no lay user would write "not denying chest pain" (this is
clinical charting language). The bible's safety bias should resolve ambiguity in
favor of firing, but this edge case is extremely rare.

### Recommendation
Add "denying" to NEGATION_CUES or add lemmatization to the safety tokenizer.
Low priority — does not block delivery.

---

## BUG-002: NLP cascade — severity extraction fails when "/" stripped by tokenizer
- **Severity:** P3 (Low — form controls provide explicit severity)
- **Component:** `app/nlp/cascade.py` → `_extract_self_severity`
- **Status:** Open

### Description
When a user writes "pain 7/10", the normalizer strips "/" (non-alphanumeric)
leaving "7 10" in the token stream. The severity regex `r"\b([1-9]|10)\s*(?:/|out of)\s*10\b"`
then cannot match because "/" is gone from the normalized text.

### Reproduction
```python
from app.nlp import load_nlp_runtime, run_nlp_cascade
rt = load_nlp_runtime()
r = run_nlp_cascade(rt, "pain 7/10 in my back")
assert r.extracted_self_severity == 7  # FAILS — returns None
```

### Expected
"7/10" → extracted_self_severity = 7

### Actual
extracted_self_severity = None (the "/" was stripped)

### Impact
Low: users can provide severity via the explicit form slider. This only affects
free-text extraction when no form input is given. Duration/severity form controls
are the primary path.

### Recommendation
Run severity/duration extraction on the pre-normalized (lowercase, whitespace-
collapsed) text BEFORE the tokenizer strips punctuation.

---

## BUG-003: NLP cascade — "for a month" duration not extracted
- **Severity:** P3 (Low — form controls provide explicit duration)
- **Component:** `app/nlp/cascade.py` → `_extract_duration_days`
- **Status:** Open

### Description
The duration regex `r"\bfor\s+(\d{1,2})\s+(day|days|...)\b"` requires a digit
after "for". The pattern "for a month" has "a" (not a digit or number-word from
the word-patterns list). The word-pattern regex does include "a" → but "a" is
not in NUMBER_WORDS.

### Reproduction
```python
from app.nlp import load_nlp_runtime, run_nlp_cascade
rt = load_nlp_runtime()
r = run_nlp_cascade(rt, "pain in my back for a month")
assert r.extracted_duration_days == 30  # FAILS — returns None
```

### Expected
"for a month" → extracted_duration_days = 30

### Actual
extracted_duration_days = None

### Impact
Low: users can provide duration via the explicit numeric input. The fix is to
add "a" → 1 to NUMBER_WORDS.

---

## BUG-004: NLP cascade — "nauseous" not mapped to nausea
- **Severity:** P3 (Low — surfaced as unmatched, not silently dropped)
- **Component:** `app/nlp/cascade.py` (lexicon/fuzzy match coverage)
- **Status:** Open

### Description
"nauseous" after lemmatization may not fuzzy-match above the 86% threshold
to "nausea". The user writes "feeling nauseous" and it appears in unmatched
tokens rather than being mapped.

### Impact
Low: the token IS surfaced as unmatched (no silent drop — NFR-RB3 satisfied).
User can rephrase. Could be fixed by adding "nauseous" → "nausea" to the
synonym lexicon.

---

## BUG-005: NLP cascade — "throat is irritated" not mapped to throat_irritation
- **Severity:** P3 (Low — surfaced as unmatched)
- **Component:** `app/nlp/cascade.py` (lemmatization + lexicon gap)
- **Status:** Open

### Description
"irritated" is lemmatized to "irritate" (strip -ed). The canonical symptom name
is "throat_irritation". The two-token phrase "throat irritate" doesn't match
"throat irritation" via fuzzy match (different ending). The single token "throat"
is too short to fuzzy-match meaningfully.

### Impact
Low: token surfaced as unmatched. Could be fixed by adding "throat irritated" and
"irritated throat" to the synonym lexicon with target "throat_irritation".

---

## FINDING-001: Admin endpoint returns 503 without token (not 401/403)
- **Severity:** Informational (Not a security issue — endpoint IS blocked)
- **Component:** `app/web/app.py` → `_require_admin_token`
- **Status:** Accepted

### Description
The admin analytics endpoint returns HTTP 503 (Service Unavailable) when no
admin token is configured, rather than 401 (Unauthorized) or 403 (Forbidden).
The endpoint IS properly gated — it cannot be accessed without credentials.
The status code choice is unconventional but does not represent a security gap.

### Impact
None — NFR-SEC1 is satisfied (endpoint is access-gated). The 503 approach is
used because no token is configured in the test environment, meaning the admin
service is "unavailable" rather than the request being "unauthorized".
