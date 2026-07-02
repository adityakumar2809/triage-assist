# Model comparison (B3 consolidated)

| Model | Macro-F1 | Weighted-F1 | Accuracy | Vignette Top-1 | Expected in Top-3 | Serialized size |
|---|---:|---:|---:|---:|---:|---:|
| BernoulliNB | 1.0000 | 1.0000 | 1.0000 | 9 | 10 | 25831 (25.23 KiB) |
| RandomForest | 1.0000 | 1.0000 | 1.0000 | 9 | 10 | 6335401 (6186.92 KiB) |
| KNN | 1.0000 | 1.0000 | 1.0000 | 9 | 9 | 4194468 (4096.16 KiB) |
| SVM | 1.0000 | 1.0000 | 1.0000 | 6 | 9 | 327499 (319.82 KiB) |
| DecisionTree | 1.0000 | 1.0000 | 1.0000 | 5 | 6 | 17625 (17.21 KiB) |

- **Selected model:** BernoulliNB
- **Stopping rule:** Evaluate the fixed agreed set of five classical models under one stratified split with RANDOM_SEED=42. Select the best by highest macro-F1. If models tie within tolerance, prefer stronger realistic 2–4 symptom vignette behavior, then choose the smaller serialized model size to preserve free-tier memory headroom.
- **Synthetic-data caveat:** Metrics are from a synthetic disease-symptom dataset. High split accuracy reflects pattern learning on synthetic generation, not clinical diagnostic performance. Macro-F1 and vignette behavior are reported for honest characterization.
- **Seed / split:** seed=42, test_size=0.2
