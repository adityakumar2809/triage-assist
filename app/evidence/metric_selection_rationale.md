# Model selection rationale

- **Chosen model:** BernoulliNB
- **Primary metric:** macro-F1 (maximize).
- **Tie-breaks:** vignette behavior (expected category in top-3, then top-1), then smaller serialized model size.
- **Outcome:** all models tie on synthetic split metrics; BernoulliNB wins tie-break with strong vignette behavior and small artifact size.
- **Synthetic-data caveat recorded:** Metrics are from a synthetic disease-symptom dataset. High split accuracy reflects pattern learning on synthetic generation, not clinical diagnostic performance. Macro-F1 and vignette behavior are reported for honest characterization.
