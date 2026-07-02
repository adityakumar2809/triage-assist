# QA Bug Disposition Register

These five P3 bugs were dispositioned by the **Project Leader** on 2026-06-20 as
**non-blocking known limitations** and **candidate future enhancements**, with
**no code change in this version**. The original QA findings stand unchanged in
`qa_bug_report.md`; this register records the disposition decision alongside
each defect.

## Safety gate verification (pre-disposition)

Before acceptance, each bug was independently verified to confirm it does NOT
cause an emergency or red-flag to be missed or under-triaged, and does not
weaken the uncertainty path's safety behaviour. Verification method:

- **BUG-002 through BUG-005** reside in `app/nlp/cascade.py` (the NLP cascade).
  The safety layer (`app/web/safety.py`) runs on the **raw input before** the
  NLP cascade (line 237–241 in `app.py`), and its `evaluate_safety_gate` function
  takes only `selected_symptoms` and `raw_text` — it never consumes NLP cascade
  output. B5↔B7 independence confirmed: danger phrases and red-flag symptoms in
  the raw text still fire emergency routing regardless of NLP mapping gaps.
  Severity and duration extraction feed the rule-based urgency layer, which can
  only produce `low`/`moderate`/`high` — never `emergency`.

- **BUG-001** is in `app/web/safety.py` itself (the safety tokenizer's negation
  handling). The under-triage occurs only on the double-negation construction
  "not denying …", which is clinical charting jargon never produced by a lay user
  describing their own symptoms. All direct phrasings ("chest pain",
  "I have chest pain", structured `chest_pain`) fire correctly. Verified by
  running `evaluate_safety_gate` against each variant.

**Result: all five pass the safety gate. None are must-fix.**

---

## Disposition table

| Bug ID | Title | Severity | Safety-affecting? | Disposition | Rationale | Documented in |
|--------|-------|----------|-------------------|-------------|-----------|---------------|
| BUG-001 | Safety tokenizer does not handle double negation ("not denying") | P3 | No — verified: trigger phrasing is clinical charting jargon unreachable by lay users; all direct phrasings fire correctly | Accepted — Known Limitation, non-blocking; candidate future enhancement | Non-critical edge case in safety negation handling; the "not denying" construction is medical charting language outside the target user population; safety unaffected for lay input | Limitations + Future Scope; appears in R7 results |
| BUG-002 | NLP cascade — severity "7/10" extraction fails (tokenizer strips "/") | P3 | No — verified: severity extraction is in NLP cascade (B7), runs after the safety layer (B5); B5↔B7 independent; explicit form slider is the primary severity input | Accepted — Known Limitation, non-blocking; candidate future enhancement | Non-critical NLP precision gap; explicit form controls provide the primary severity input path; safety unaffected | Limitations + Future Scope; appears in R7 results |
| BUG-003 | NLP cascade — "for a month" duration not extracted | P3 | No — verified: duration extraction is in NLP cascade (B7), runs after safety layer (B5); duration feeds urgency layer which never emits "emergency"; explicit form input is the primary duration path | Accepted — Known Limitation, non-blocking; candidate future enhancement | Non-critical NLP precision gap; explicit form controls provide the primary duration input path; safety unaffected | Limitations + Future Scope; appears in R7 results |
| BUG-004 | NLP cascade — "nauseous" not mapped to nausea | P3 | No — verified: `nausea` is not in `solo_triggers` or `combination_symptoms`; even if mapped, safety layer would not act on it; token is surfaced as unmatched (NFR-RB3 satisfied) | Accepted — Known Limitation, non-blocking; candidate future enhancement | Non-critical NLP recall gap; symptom is not safety-relevant; unmatched token is surfaced to the user (no silent drop); safety unaffected | Limitations + Future Scope; appears in R7 results |
| BUG-005 | NLP cascade — "throat irritated" not mapped to throat_irritation | P3 | No — verified: `throat_irritation` is not in `solo_triggers` or `combination_symptoms`; even if mapped, safety layer would not act on it; token is surfaced as unmatched (NFR-RB3 satisfied) | Accepted — Known Limitation, non-blocking; candidate future enhancement | Non-critical NLP recall gap; symptom is not safety-relevant; unmatched token is surfaced to the user (no silent drop); safety unaffected | Limitations + Future Scope; appears in R7 results |

---

## Original findings

The full defect descriptions, reproduction steps, expected/actual behaviour, and
recommended fixes remain in **`qa_bug_report.md`** and are unchanged by this
disposition. The defects are real gaps; this register records only that they are
accepted as non-blocking for this version.
