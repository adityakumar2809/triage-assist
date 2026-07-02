# Vignette provenance audit and tau notes

- **Dataset-derived vignette source:** `app/model/realistic_vignette_check.json` (10 cases).
- **Dataset-derived top-1 matches:** 9 / 10.
- **Dataset-derived expected in top-3:** 10 / 10.
- **Independent vignette set:** 6 cases (see `uncertainty_independent_vignette_results.json`).
- **Independent cases below tau=0.60:** 1.
- **Decision:** retain tau=0.60 to keep low-information/sparse inputs on the uncertainty path while preserving confident category routing.
