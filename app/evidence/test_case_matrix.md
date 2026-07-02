# Unit/integration test-case coverage matrix

| File | Test case | Type | Covers |
|---|---|---|---|
| test_curated_artifacts.py | `test_frozen_symptom_order_has_expected_boundaries` | unit | Lookup mapping |
| test_curated_artifacts.py | `test_default_zero_feature_set_matches_design_rule` | unit | Lookup mapping |
| test_curated_artifacts.py | `test_curated_tables_are_loadable_and_complete` | unit | Lookup mapping |
| test_curated_artifacts.py | `test_mapping_is_total_for_raw_labels_and_lookup_is_complete` | unit | Lookup mapping |
| test_curated_artifacts.py | `test_grouped_dataset_and_vocab_artifact_are_loadable` | unit | Lookup mapping |
| test_curated_artifacts.py | `test_synonyms_and_safety_lists_are_populated` | unit | Lookup mapping, NLP cascade, Safety layer |
| test_curated_artifacts.py | `test_grouped_dataset_default_zero_features_are_constant_zero` | unit | Lookup mapping |
| test_curated_artifacts.py | `test_low_tier_spotcheck_covers_known_risk_labels` | unit | Lookup mapping |
| test_model_artifacts.py | `test_model_bundle_loads_under_pinned_sklearn` | unit | General regression |
| test_model_artifacts.py | `test_metrics_and_confusion_matrix_are_recorded` | unit | General regression |
| test_model_artifacts.py | `test_vignette_sanity_check_uses_short_profiles` | unit | General regression |
| test_nlp_cascade.py | `test_runtime_loads_lexicon_and_keeps_embeddings_off` | unit | NLP cascade |
| test_nlp_cascade.py | `test_synonym_cascade_maps_understood_and_unsure_sets` | unit | NLP cascade |
| test_nlp_cascade.py | `test_negation_excludes_symptom_from_understood_set` | unit | NLP cascade |
| test_nlp_cascade.py | `test_contrast_conjunction_limits_negation_scope` | unit | NLP cascade |
| test_nlp_cascade.py | `test_duration_and_severity_extraction_from_text` | unit | NLP cascade, Urgency rules |
| test_nlp_cascade.py | `test_unmatched_tokens_are_surfaced_not_dropped` | unit | NLP cascade |
| test_nlp_cascade.py | `test_contracted_negation_is_preserved_for_bigram_detection` | unit | NLP cascade |
| test_nlp_cascade.py | `test_ed_lemmatization_does_not_break_common_adjectives` | unit | Input hardening, NLP cascade |
| test_nlp_cascade.py | `test_negation_cues_are_not_fuzzy_matched_to_symptoms` | unit | NLP cascade |
| test_nlp_cascade.py | `test_partial_ratio_noise_phrase_does_not_create_unsure_matches` | unit | NLP cascade |
| test_nlp_cascade.py | `test_negation_detects_span_starting_with_negation_word` | unit | NLP cascade |
| test_nlp_cascade.py | `test_lemmatized_lexicon_phrase_still_maps_to_vomiting` | unit | NLP cascade |
| test_nlp_cascade.py | `test_two_gram_with_stopword_does_not_block_single_token_hit` | unit | NLP cascade |
| test_nlp_cascade.py | `test_plain_fever_maps_to_high_fever_via_lexicon` | unit | NLP cascade |
| test_nlp_cascade.py | `test_plain_vomit_maps_to_vomiting_via_lexicon` | unit | NLP cascade |
| test_nlp_cascade.py | `test_lemmatized_ing_terms_map_to_canonical_symptoms` | unit | NLP cascade |
| test_web_app.py | `test_index_renders_intake_form` | integration | General regression |
| test_web_app.py | `test_health_reports_curated_artifacts` | integration | General regression |
| test_web_app.py | `test_result_round_trip_renders_full_result_shape` | integration | General regression |
| test_web_app.py | `test_empty_selection_routes_to_uncertainty_path` | integration | Uncertainty path |
| test_web_app.py | `test_invalid_inputs_degrade_to_uncertainty_without_errors` | integration | Input hardening, Uncertainty path |
| test_web_app.py | `test_screen_handles_invalid_risk_values_gracefully` | integration | Input hardening |
| test_web_app.py | `test_input_normalizers_tolerate_non_string_payloads` | integration | General regression |
| test_web_app.py | `test_humanize_label_formats_identifiers_for_ui_display` | integration | Humanisation |
| test_web_app.py | `test_structured_red_flag_routes_to_emergency` | integration | Safety layer |
| test_web_app.py | `test_danger_phrase_routes_to_emergency` | integration | Safety layer |
| test_web_app.py | `test_negated_red_flag_does_not_trigger_emergency` | integration | Safety layer |
| test_web_app.py | `test_emergency_short_circuits_before_model` | integration | Safety layer |
| test_web_app.py | `test_urgency_escalates_with_duration_and_severity_modifiers` | integration | Urgency rules |
| test_web_app.py | `test_screen_shows_confirmation_understood_unsure_unmatched` | integration | General regression |
| test_web_app.py | `test_screen_preserves_risk_questionnaire_choices` | integration | General regression |
| test_web_app.py | `test_screen_extracts_duration_and_severity_for_result_flow` | integration | Urgency rules |
| test_web_app.py | `test_danger_phrase_short_circuits_before_cascade` | integration | NLP cascade, Safety layer |
| test_web_app.py | `test_risk_factor_yes_is_mapped_and_sensitive_field_ignored` | integration | General regression |
| test_web_app.py | `test_result_persists_screening_and_history_view` | integration | General regression |
| test_web_app.py | `test_printable_summary_renders_and_downloads` | integration | General regression |
| test_web_app.py | `test_admin_analytics_requires_token_and_returns_aggregates` | integration | General regression |
| test_web_inference.py | `test_runtime_feature_order_matches_frozen_artifact` | unit | Urgency rules |
| test_web_inference.py | `test_inference_uses_frozen_one_hot_order_for_predict_proba` | unit | Urgency rules |
| test_web_inference.py | `test_inference_returns_safe_discussion_phrasing_only` | unit | Urgency rules |
| test_web_inference.py | `test_empty_or_unknown_symptoms_route_to_uncertainty` | unit | Uncertainty path, Urgency rules |
| test_web_inference.py | `test_below_threshold_prediction_routes_to_uncertainty` | unit | Uncertainty path, Urgency rules |
| test_web_inference.py | `test_rule_based_urgency_table_cells` | unit | Urgency rules |
| test_web_safety.py | `test_no_chest_pain_is_negated_and_does_not_fire` | unit | Safety layer |
| test_web_safety.py | `test_unnegated_chest_pain_phrase_fires` | unit | Safety layer |
| test_web_safety.py | `test_negation_scope_is_local_not_global` | unit | Safety layer |
| test_web_safety.py | `test_intervening_verb_variants_fire_anaphylaxis_phrases` | unit | Safety layer |
| test_web_safety.py | `test_double_negation_does_not_suppress_red_flag` | unit | Safety layer |
| test_web_safety.py | `test_contracted_words_do_not_suppress_red_flags` | unit | Safety layer |
