# Dataset summary and cleaning notes

- **Samples (grouped dataset):** 4961
- **Unique raw diseases (prognosis_raw):** 41
- **Unique grouped categories:** 10
- **Symptom feature columns:** 131
- **Raw CSV row count:** 4961

## Class balance (grouped categories)

| Category | Count |
|---|---:|
| Cardiovascular | 363 |
| Endocrine & Metabolic | 484 |
| Gastrointestinal | 484 |
| Infectious & Febrile | 605 |
| Liver & Hepatic | 968 |
| Musculoskeletal | 363 |
| Neurological | 363 |
| Respiratory | 484 |
| Skin & Allergic | 726 |
| Urological | 121 |

## Cleaning notes

- Raw headers are normalized to canonical snake_case and matched to the frozen column order artifact.
- Header alias mappings captured: 132 entries.
- Default-zero features (C-class + extra_marital_contacts) are explicitly set to 0 in the grouped dataset build.
