# Model module

Classical-ML training and bundling artifacts for B3.

## Train and bundle

Run from repository root:

```bash
venv/bin/python app/model/train_and_bundle.py
```

## Outputs

- `triage_model_bundle.joblib`:
  single bundle containing the chosen model, frozen vocabulary/order,
  synonym lexicon, spell-corrector config, and lookup table.
- `model_comparison_metrics.json`:
  per-model macro-F1/weighted-F1/accuracy, selection, and caveat text.
- `selected_model_confusion_matrix.csv`:
  confusion matrix for the selected model.
- `realistic_vignette_check.json`:
  quick 2–4 symptom sanity-check predictions.

## Reproducibility

- Fixed `RANDOM_SEED = 42`.
- Pinned scikit-learn version from `requirements.txt`.
- Frozen feature order loaded from `app/data/frozen_symptom_vocabulary.json`.
