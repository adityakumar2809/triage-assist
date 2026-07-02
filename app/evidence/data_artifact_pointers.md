# Artifact pointers with short samples

- **Frozen symptom vocabulary/order:** `app/data/frozen_symptom_vocabulary.json`
  - Sample order[0:5]: ['itching', 'skin_rash', 'nodal_skin_eruptions', 'continuous_sneezing', 'shivering']
- **Lookup table:** `app/data/category_lookup.csv`
  - Sample row: {'condition_category': 'Skin & Allergic', 'safe_display_phrasing': 'Skin or allergy-related concerns', 'point_of_care': 'Dermatology', 'point_of_care_note': nan, 'severity_tier': 'Tier 1', 'severity_tier_label': 'Self-limiting'}
- **Synonym lexicon:** `app/data/synonym_lexicon.json`
  - Sample entry: {'phrase': 'achy joints', 'canonical_targets': ['joint_pain'], 'confirmation_bucket': 'understood', 'red_flag_related': False}
- **Red-flag list:** `app/data/red_flag_rules.json`
  - Solo triggers sample: ['chest_pain', 'breathlessness', 'weakness_of_one_body_side', 'slurred_speech', 'altered_sensorium']
- **Danger-phrase list:** `app/data/danger_phrase_rules.json`
  - Sample pattern group: "crushing chest pain", "chest pressure", "tightness in chest", "chest pain radiating" / "pain to arm/jaw"
