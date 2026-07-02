# Web module

This directory holds the deployable web application.

In Chunk B8 it contains:

- intake route (`/`) with:
  symptom search/autocomplete, grouped body-system checklist,
  optional risk-factor questionnaire, and optional duration/severity inputs;
- safety-first screening route (`/screen`) that runs:
  deterministic safety scan → classical NLP cascade → confirmation;
- confirmation route behavior:
  understood, unsure, and unmatched sets are surfaced with no silent drops;
- optional risk answers carried through confirmation and mapped with safe
  defaults (`yes` only contributes a feature; unanswered/no/prefer-not = 0);
- sensitive-field handling:
  `extra_marital_contacts` is intentionally never asked or inferred;
- terminal result route (`/result`) for emergency or non-emergency outputs;
- deterministic urgency rules (no urgency ML model), using severity tier plus
  duration/self-severity/combination modifiers;
- uncertainty routing for both nothing-recognised and low-confidence paths;
- result rendering that always includes the frozen disclaimer text.

Chunk B9 adds:

- SQLite persistence for each completed screening using anonymous session IDs;
- held-session history view (`/history`) with date, urgency, and point of care;
- printable/downloadable summaries (`/summary/<session_id>`);
- token-gated admin analytics dashboard (`/admin/analytics`) and JSON endpoint
  (`/api/admin/analytics`) with aggregate-only metrics.

Chunk B9.5 adds:

- shared base template with one stylesheet + one vanilla-JS enhancement file
  applied to all screens;
- presentation-only humanized labels for symptom/category display strings;
- polished portal-style layouts for intake, confirmation, result, history,
  analytics, and printable summary surfaces;
- JS enhancements for intake accordion behavior, live filtering, and selected
  symptom chips without changing form values or screening logic.
