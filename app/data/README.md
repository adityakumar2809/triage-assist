# Data artifacts

This directory holds frozen curated inputs and generated outputs.

## B2 artifacts

- `frozen_symptom_vocabulary.json`: canonical 131-column order + classes.
- `symptom_vocabulary.py`: import shim over the canonical JSON artifact.
- `condition_category_mapping.csv`: exhaustive raw label → category map.
- `symbipredict_2022_grouped_clean.csv`: cleaned grouped training dataset.
- `category_lookup.csv`: populated §13.5 lookup table.
- `symptom_body_system_groups.json`: frozen §13.6 intake grouping.
- `synonym_lexicon.json`: populated Stage-2 synonym lexicon.
- `red_flag_rules.json`: populated §12.3 red-flag symptom rules.
- `danger_phrase_rules.json`: populated §12.4 danger-phrase rules.
- `mapping_spotcheck_low_tier.csv`: low-tier mapping safety spot-check log.
- `b2_data_manifest.json`: row/column and category-count summary.
- `build_data_artifacts.py`: reproducible artifact-generation script.
