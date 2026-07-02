# B10 Evidence Index

This index catalogs every file in `app/evidence` for report use without opening each artifact.

## UI screenshots (desktop, mobile, print)

### Title: Intake screen default (collapsed grouped checklist)
- **File:** ui_intake_desktop_default.png
- **Type:** UI screenshot
- **Description:** Initial intake screen before interaction. All grouped body-system checklists are collapsed, search/filter controls are visible, and the selected count is 0. Captured to document default entry state.
- **Supports:** R6 implementation UI baseline; R7 UX walkthrough.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: none (fresh GET /).

### Title: Intake grouped checklist expanded
- **File:** ui_intake_desktop_group_expanded.png
- **Type:** UI screenshot
- **Description:** Same intake screen with one body-system details panel expanded to show checkbox options and responsive symptom grid layout.
- **Supports:** R6 intake checklist behavior.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: first body-system group expanded.

### Title: Intake live filter in use
- **File:** ui_intake_desktop_filter_in_use.png
- **Type:** UI screenshot
- **Description:** Filter box populated with "rash". Non-matching groups are hidden and matching options remain visible to demonstrate live checklist filtering.
- **Supports:** R6 intake usability; B9.5 progressive enhancement evidence.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: symptom_filter="rash".

### Title: Intake search/autocomplete in use
- **File:** ui_intake_desktop_search_in_use.png
- **Type:** UI screenshot
- **Description:** Search input populated with "chest pain" against datalist-backed autocomplete source, showing search interaction before add action.
- **Supports:** R6 intake search/autocomplete implementation.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: symptom_search="chest pain".

### Title: Intake selected chips and running count
- **File:** ui_intake_desktop_selected_chips_count.png
- **Type:** UI screenshot
- **Description:** Selected symptom chips visible after adding symptoms from search and checklist. Running count updates and removable chips are rendered.
- **Supports:** R6 intake state feedback and chip UX.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: added chest pain + cough.

### Title: Intake optional risk-factor questionnaire section
- **File:** ui_intake_desktop_risk_questionnaire.png
- **Type:** UI screenshot
- **Description:** Focused capture of optional 2x2 risk-factor questionnaire with helper text and aligned dropdown controls.
- **Supports:** R6 optional risk-factor UI and safe default wording.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: section scrolled into view.

### Title: Intake duration and severity controls
- **File:** ui_intake_desktop_duration_severity.png
- **Type:** UI screenshot
- **Description:** Duration numeric input plus severity range slider with live output value displayed. Demonstrates bounded severity input UX.
- **Supports:** R6 modifier input UX and B9.5 slider enhancement.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: duration=14, severity slider=8.

### Title: Intake free-text section populated
- **File:** ui_intake_desktop_free_text.png
- **Type:** UI screenshot
- **Description:** Raw symptom text textarea filled with mixed language input (understood/unsure/unmatched tokens) prior to submission.
- **Supports:** R6 free-text capture and confirmation-path setup.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: raw_text="bad cough and stuffy nose flibbertigibbet".

### Title: Negation input on intake (pre-submit)
- **File:** ui_intake_desktop_negation_input.png
- **Type:** UI screenshot
- **Description:** Intake state used for negation test: structured symptom itching selected with free text "no chest pain today" before submit.
- **Supports:** Safety chapter negation demonstration setup.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: itching + "no chest pain today".

### Title: Confirmation screen with understood/unsure/unmatched
- **File:** ui_confirm_desktop_understood_unsure_unmatched.png
- **Type:** UI screenshot
- **Description:** Confirmation page after raw-text submission. Shows understood symptoms, unsure "did you mean" mappings, and unmatched token list (no silent drop behavior).
- **Supports:** R6 confirmation flow; FR6 no-silent-drop evidence.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: "bad cough and stuffy nose flibbertigibbet".

### Title: Result page low urgency
- **File:** ui_result_desktop_low_urgency.png
- **Type:** UI screenshot
- **Description:** Non-emergency result showing low urgency badge, point of care, symptoms understood chips, areas to discuss, seek-sooner list, and disclaimer.
- **Supports:** R6 deterministic output rendering (low urgency).
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: structured symptoms itching + skin_rash.

### Title: Result page moderate urgency
- **File:** ui_result_desktop_moderate_urgency.png
- **Type:** UI screenshot
- **Description:** Moderate urgency terminal page with yellow badge and full result cards (point_of_care, symptoms, areas_to_discuss, seek_sooner_if, disclaimer).
- **Supports:** R6 deterministic output rendering (moderate urgency).
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: acidity + abdominal_pain + indigestion.

### Title: Result page high urgency
- **File:** ui_result_desktop_high_urgency.png
- **Type:** UI screenshot
- **Description:** High urgency terminal page with orange badge and same non-emergency structure. Demonstrates urgency escalation under modifier inputs.
- **Supports:** R6 deterministic urgency escalation (high urgency).
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: acidity + abdominal_pain + indigestion, duration_days=14, self_severity_1_10=8.

### Title: Emergency result from structured red-flag symptom
- **File:** ui_result_desktop_emergency_redflag.png
- **Type:** UI screenshot
- **Description:** Emergency short-circuit result with red styling and point_of_care set to Emergency Department. Areas/discussion lists are absent; disclaimer remains visible.
- **Supports:** Safety layer deterministic emergency routing from structured input.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: selected_symptoms=[chest_pain].

### Title: Emergency result from free-text danger phrase
- **File:** ui_result_desktop_emergency_dangerphrase.png
- **Type:** UI screenshot
- **Description:** Emergency short-circuit reached from free text danger phrase only; red emergency treatment shown with Emergency Department routing and no condition list.
- **Supports:** Safety layer danger-phrase scan before model inference.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: raw_text="I have crushing chest pain right now" with no structured symptoms.

### Title: Negation handling result (no emergency)
- **File:** ui_result_desktop_negation_no_emergency.png
- **Type:** UI screenshot
- **Description:** Terminal result page captured after submitting intake input `selected_symptoms=[itching]` and `raw_text="no chest pain today"` through confirmation. Shows a non-emergency screening result with non-ED point of care, confirming the negated red-flag phrase does not fire the deterministic emergency gate.
- **Supports:** Safety negation-bound behavior evidence.
- **Captured:** 2026-06-20, working tree after 35b469e, viewport 1280x800, flow: intake -> confirm -> result.

### Title: Uncertainty result from sparse recognized input
- **File:** ui_result_desktop_uncertainty_sparse.png
- **Type:** UI screenshot
- **Description:** Neutral uncertainty presentation with GP routing and empty discussion areas triggered by low-confidence sparse structured signal.
- **Supports:** Uncertainty-path implementation (low confidence).
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: selected_symptoms=[foul_smell_of_urine].

### Title: Uncertainty result from unrecognized input
- **File:** ui_result_desktop_uncertainty_unrecognized.png
- **Type:** UI screenshot
- **Description:** Neutral uncertainty screen after unrecognized free-text input path. Demonstrates graceful fallback with GP routing and empty areas_to_discuss.
- **Supports:** Input-hardening behavior for unrecognized inputs.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: raw_text="blorb blorb xyzqv", then confirm-submit.

### Title: History view
- **File:** ui_history_desktop.png
- **Type:** UI screenshot
- **Description:** Browser-session scoped history table showing multiple saved screenings with session ID, urgency badge, point_of_care, and summary links.
- **Supports:** B9 persistence/history verification.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: multiple completed submissions in one browser context.

### Title: Admin analytics dashboard
- **File:** ui_admin_desktop.png
- **Type:** UI screenshot
- **Description:** Token-gated admin analytics page showing counts, urgency distribution, common symptoms, frequent categories, daily counts, and model-performance summary.
- **Supports:** B9 admin analytics implementation and aggregate-only output.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: GET /admin/analytics?token=b10-admin-token.

### Title: Printable summary (screen media)
- **File:** ui_summary_desktop.png
- **Type:** UI screenshot
- **Description:** Summary page for a stored session with urgency badge, session metadata, result cards, disclaimer, and print/history actions.
- **Supports:** B9 summary output and report-ready rendering.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1280x800, input: opened /summary/<session_id> from low-urgency result.

### Title: Printable summary (print media emulation)
- **File:** ui_summary_print_a4.png
- **Type:** UI screenshot
- **Description:** Summary page captured with print CSS media emulation to show A4 layout adaptation (header/footer hidden, print card layout).
- **Supports:** Printable evidence flow and report print-view documentation.
- **Captured:** 2026-06-19, commit 37129fb, viewport 1240x1754, media=print, source summary session from low-urgency run.

### Title: Intake mobile view (~390px)
- **File:** ui_intake_mobile_390.png
- **Type:** UI screenshot
- **Description:** Narrow mobile intake layout capture demonstrating responsive stacking and full-width controls at phone-width viewport.
- **Supports:** Responsive UI evidence for intake page.
- **Captured:** 2026-06-19, commit 37129fb, viewport 390x844, input: none (fresh GET /).

### Title: Result mobile view (~390px)
- **File:** ui_result_mobile_390.png
- **Type:** UI screenshot
- **Description:** Narrow mobile result layout showing responsive card stacking and action buttons after low-urgency submission.
- **Supports:** Responsive UI evidence for result page.
- **Captured:** 2026-06-19, commit 37129fb, viewport 390x844, input: itching + skin_rash.

## Model evaluation evidence (B3 consolidation)

### Title: Model comparison table (five classical models)
- **File:** metric_model_comparison.md
- **Type:** Metric table
- **Description:** Consolidated macro-F1, weighted-F1, accuracy, vignette behavior, and serialized size for BernoulliNB, RandomForest, KNN, SVM, DecisionTree, with selected-model and caveat notes.
- **Supports:** R7 model evaluation and selection narrative.
- **Captured:** 2026-06-19, commit 37129fb, seed=42, test_size=0.2, source app/model/model_comparison_metrics.json.

### Title: Selected-model classification report
- **File:** metric_selected_model_classification_report.txt
- **Type:** Metric log
- **Description:** Per-class precision/recall/F1 and aggregate macro/weighted scores for the selected bundled model under the fixed stratified split.
- **Supports:** R7 per-class performance reporting.
- **Captured:** 2026-06-19, commit 37129fb, seed=42, test_size=0.2.

### Title: Confusion matrix (raw CSV)
- **File:** metric_confusion_matrix_raw.csv
- **Type:** Metric artifact
- **Description:** Raw selected-model confusion matrix values copied into evidence for direct numeric traceability.
- **Supports:** R7 confusion-matrix appendix and reproducibility.
- **Captured:** 2026-06-19, commit 37129fb, seed=42, test_size=0.2.

### Title: Confusion matrix (markdown table)
- **File:** metric_confusion_matrix_table.md
- **Type:** Metric table
- **Description:** Human-readable confusion matrix table derived from the selected model CSV for report-ready embedding.
- **Supports:** R7 model evaluation write-up.
- **Captured:** 2026-06-19, commit 37129fb, source metric_confusion_matrix_raw.csv.

### Title: Model-selection rationale and stopping-rule outcome
- **File:** metric_selection_rationale.md
- **Type:** Method note
- **Description:** Documents primary metric, tie-break ordering, selected model, and synthetic-data caveat as applied in B3 selection.
- **Supports:** Methodology/model-selection section.
- **Captured:** 2026-06-19, commit 37129fb.

### Title: Seed/split and environment snapshot for metrics
- **File:** metric_seed_split_and_environment.txt
- **Type:** Reproducibility log
- **Description:** Minimal reproducibility record containing commit, capture time, seed, split, Python version, and sklearn version for metric runs.
- **Supports:** Reproducibility appendix.
- **Captured:** 2026-06-19, commit 37129fb, seed=42, test_size=0.2.

## Uncertainty and calibration evidence

### Title: Confidence-distribution tables and below-threshold counts
- **File:** uncertainty_confidence_distribution.md
- **Type:** Calibration table
- **Description:** Min/median/max top-1 confidence and count below tau across holdout split, single-symptom sparse inputs, dataset-derived vignettes, and independent vignettes.
- **Supports:** Tau selection and uncertainty-path justification.
- **Captured:** 2026-06-19, commit 37129fb, tau=0.60, seed=42, test_size=0.2.

### Title: Independent vignette prediction results (JSON)
- **File:** uncertainty_independent_vignette_results.json
- **Type:** Calibration artifact
- **Description:** Independent (non-B3-list) vignette predictions with top-1/top-3 probabilities and below-tau flags for tau=0.60.
- **Supports:** Vignette provenance audit and tau robustness evidence.
- **Captured:** 2026-06-19, commit 37129fb, tau=0.60.

### Title: Tau basis and vignette provenance audit note
- **File:** uncertainty_vignette_provenance.md
- **Type:** Method note
- **Description:** Summarizes dataset-derived vignette outcomes, independent vignette outcomes, and rationale for retaining tau=0.60.
- **Supports:** R7 uncertainty/calibration narrative.
- **Captured:** 2026-06-19, commit 37129fb, tau=0.60.

## Test evidence (B10 conventional tests)

### Title: Full pytest run output
- **File:** test_pytest_full_run.log
- **Type:** Test log
- **Description:** Full conventional suite output for this chunk, including pass count and warning summary from real execution.
- **Supports:** B10 done criteria; R7 implementation validation.
- **Captured:** 2026-06-19, commit 37129fb, command: pytest -q.

### Title: Unit/integration test-case coverage matrix
- **File:** test_case_matrix.md
- **Type:** Test index
- **Description:** Enumerates discovered test functions and maps each to primary coverage areas (safety, urgency, uncertainty, NLP, lookup, humanisation, hardening).
- **Supports:** Testing chapter traceability matrix.
- **Captured:** 2026-06-19, commit 37129fb, source app/tests/*.py.

### Title: Playwright end-to-end capture run log
- **File:** test_playwright_e2e.log
- **Type:** E2E log
- **Description:** Chronological log for Playwright run that generated screenshot states across intake, confirmation, result variants, history, admin, summary, and mobile views.
- **Supports:** UI evidence reproducibility and end-to-end verification.
- **Captured:** 2026-06-19, commit 37129fb, desktop viewport 1280x800, mobile viewport 390x844.

### Title: Playwright visual regression baseline status
- **File:** test_playwright_visual_regression_status.txt
- **Type:** Test status note
- **Description:** Explicit status statement for visual-regression tooling in this repository (snapshot baseline not configured in B10).
- **Supports:** Testing scope declaration for report accuracy.
- **Captured:** 2026-06-19, commit 37129fb.

### Title: Accessibility (axe-core) status
- **File:** test_accessibility_axe_status.txt
- **Type:** Test status note
- **Description:** Explicit record that automated axe-core pipeline is not configured in this repository at B10, to avoid overstating executed tests.
- **Supports:** Testing limitations and transparency statement.
- **Captured:** 2026-06-19, commit 37129fb.

## Input-hardening and safety evidence

### Title: Input hardening behavior log (empty/invalid/unrecognized)
- **File:** safety_input_hardening_checks.log
- **Type:** Behavior log
- **Description:** Flask `test_client` probe log covering empty input, malformed structured+modifier payloads, unrecognized free text on `/screen`, and a two-step negation flow (`/screen` then `/result`) for `raw_text="no chest pain today"`. Records exact path, status, and emergency/non-emergency outcomes.
- **Supports:** Reliability NFR and graceful-degradation evidence.
- **Captured:** 2026-06-20, working tree after 35b469e, command: `venv/bin/python` Flask `test_client` route-probe script (saved output).

### Title: Safety pre-model gate focused pytest checks
- **File:** safety_pre_model_gate_checks.log
- **Type:** Targeted test log
- **Description:** Focused pytest run proving deterministic emergency handling for structured red flags and danger phrases, explicit pre-cascade short-circuit behavior, and negation non-fire.
- **Supports:** Safety-layer precedence and deterministic gate evidence.
- **Captured:** 2026-06-20, working tree after 35b469e, command: `venv/bin/pytest app/tests/test_web_app.py -k "structured_red_flag_routes_to_emergency or danger_phrase_routes_to_emergency or negated_red_flag_does_not_trigger_emergency or danger_phrase_short_circuits_before_cascade" -v`.

## Data evidence (B2 consolidation)

### Title: Dataset summary and cleaning notes
- **File:** data_dataset_summary.md
- **Type:** Data summary
- **Description:** Counts of samples/diseases/categories/features with grouped class balance table and notes on header normalization plus default-zero feature enforcement.
- **Supports:** Data chapter results and preprocessing evidence.
- **Captured:** 2026-06-19, commit 37129fb, source grouped/raw dataset artifacts under app/data.

### Title: Disease to category mapping sample
- **File:** data_condition_category_mapping_sample.csv
- **Type:** Data sample
- **Description:** Representative first rows from full condition_category_mapping.csv to illustrate disease-label to grouped-category mapping format.
- **Supports:** Data mapping explanation with concrete sample rows.
- **Captured:** 2026-06-19, commit 37129fb, source app/data/condition_category_mapping.csv.

### Title: Grouped category list with specialist and severity tier
- **File:** data_grouped_category_list.md
- **Type:** Reference table
- **Description:** Full grouped category listing from lookup table with safe phrasing, point_of_care, and severity tier values.
- **Supports:** Lookup design explanation and routing rationale.
- **Captured:** 2026-06-19, commit 37129fb, source app/data/category_lookup.csv.

### Title: Artifact pointers and short content samples
- **File:** data_artifact_pointers.md
- **Type:** Artifact index
- **Description:** Pointers and sample snippets for frozen vocabulary/order, lookup table, synonym lexicon, red-flag rules, and danger-phrase list.
- **Supports:** Data/artifact traceability and reproducibility section.
- **Captured:** 2026-06-19, commit 37129fb, source app/data/*.json and *.csv.

## Run/setup and environment evidence (local)

### Title: Local setup/run steps used in this chunk
- **File:** run_setup_steps_local.md
- **Type:** Procedure note
- **Description:** Exact local setup and run command sequence (venv, install, run, test) used for B10 verification and evidence capture.
- **Supports:** Reproducibility and runbook section.
- **Captured:** 2026-06-19, commit 37129fb.

### Title: Environment snapshot and pinned dependencies
- **File:** run_environment_snapshot.txt
- **Type:** Environment log
- **Description:** Captured runtime environment (Python/platform/sklearn) plus verbatim pinned requirements.txt content.
- **Supports:** Environment and dependency pinning section.
- **Captured:** 2026-06-19, commit 37129fb.

### Title: Model bundle local load/version/size check
- **File:** run_model_bundle_load_check.txt
- **Type:** Runtime verification log
- **Description:** Confirms bundled artifact loads locally under same sklearn version, records artifact size, and executes predict_proba smoke check.
- **Supports:** Version-compatibility and free-tier memory note.
- **Captured:** 2026-06-19, commit 37129fb, sklearn=1.5.2.

### Title: Flask startup log at localhost
- **File:** run_startup_localhost.log
- **Type:** Runtime log
- **Description:** Development server startup output confirming app bind and run state on localhost:5010 during evidence capture.
- **Supports:** Local end-to-end runtime verification.
- **Captured:** 2026-06-19, commit 37129fb, command: flask --app app.web.app:create_app run --port 5010.

### Title: Local health endpoint output
- **File:** run_localhost_health.json
- **Type:** Runtime JSON output
- **Description:** Direct /health response showing loaded artifacts, selected model, safety counts, NLP configuration, and uncertainty threshold.
- **Supports:** Operational readiness and configuration verification.
- **Captured:** 2026-06-19, commit 37129fb, source GET /health on localhost:5010.

## Index metadata

### Title: Evidence catalog index
- **File:** INDEX.md
- **Type:** Documentation index
- **Description:** Master index for all B10 evidence files. Each entry includes file type, purpose, report linkage, and capture metadata.
- **Supports:** Report-writer navigation and evidence traceability.
- **Captured:** 2026-06-19, commit 37129fb.

---

## QA Test Suite Evidence (Phase 3 — Independent QA)

### Title: QA full automated test run log
- **File:** qa_full_test_run.log
- **Type:** Test execution log
- **Description:** Complete pytest output from the QA adversarial test suite (200 passed, 1 xfailed). Covers safety adversarial tests (solo triggers, combination rules, danger phrases, negation handling, obfuscation), triage vignettes (independent + dataset-derived with provenance), uncertainty-path tests (empty/sparse/threshold), NLP cascade precision/recall, stance fidelity (no alarming labels, disclaimer presence, areas-as-discussion-only), input hardening (malformed input robustness), ML metrics characterisation, and end-to-end Playwright browser tests through the real UI.
- **Supports:** R7 testing chapter; overall test-strategy evidence.
- **Captured:** 2026-06-20, seed=42 for ML metrics, local Flask app on 127.0.0.1:5199 for e2e.

### Title: QA ML metrics report (BernoulliNB, macro-F1, confusion matrix)
- **File:** qa_ml_metrics_report.txt
- **Type:** ML evaluation metrics
- **Description:** BernoulliNB model evaluation on 20% held-out split (seed=42). Reports macro-F1=1.000000 across 10 condition-category classes (993 test samples). Includes full classification report and confusion matrix. Prominently caveated: perfect accuracy reflects pattern-learning on the synthetic SymBiPredict 2022 dataset, NOT clinical diagnostic skill. Model used only as internal routing signal.
- **Supports:** R7 ML evaluation; §19.8 metric reproducibility.
- **Captured:** 2026-06-20, seed=42, model=BernoulliNB, target=condition_category.

### Title: QA NLP cascade precision/recall report
- **File:** qa_nlp_precision_recall.txt
- **Type:** NLP evaluation metrics
- **Description:** Free-text NLP cascade evaluated on 9 curated test sentences. Precision=100% (7/7 understood symptoms correct), Recall=100% (for symptoms that map unambiguously). Multi-target matches correctly routed to "unsure" for user confirmation per design. Documents known gaps: "/" stripped before severity regex (BUG-002), "for a month" duration miss (BUG-003), "nauseous" not in lexicon (BUG-004), "throat irritated" lemmatization gap (BUG-005).
- **Supports:** R7 NLP evaluation chapter; §14 cascade validation.
- **Captured:** 2026-06-20, local runtime.

### Title: QA bug report
- **File:** qa_bug_report.md
- **Type:** Bug report
- **Description:** 5 bugs + 1 informational finding from adversarial QA testing. All P3 (low severity, none blocking delivery): BUG-001 double-negation gap in safety tokenizer; BUG-002 severity "7/10" extraction failure; BUG-003 "for a month" duration miss; BUG-004 "nauseous" unmapped; BUG-005 "throat irritated" lemmatization gap; FINDING-001 admin 503 status code. No P1 (emergency under-triage) or P2 defects found. Safety layer correctly fires on all frozen red-flag and danger-phrase inputs.
- **Supports:** R7 defect summary; safety sign-off evidence.
- **Captured:** 2026-06-20.

### Title: QA bug disposition register (Leader-dispositioned)
- **File:** qa_bug_disposition.md
- **Type:** Disposition register
- **Description:** Leader disposition of all five QA P3 bugs as non-blocking known limitations and candidate future enhancements — no code change in this version. Each bug was independently verified against the safety gate before acceptance: BUG-002–005 reside in the NLP cascade (B7), which runs after and independently of the safety layer (B5) — B5↔B7 independence confirmed; BUG-001 is in the safety tokenizer but the trigger phrasing ("not denying") is clinical charting jargon unreachable by lay users, with all direct phrasings firing correctly. The register records the disposition alongside each original defect (unchanged in qa_bug_report.md): Bug ID, title, severity (all P3), safety-affecting (all No — verified), disposition (Accepted — Known Limitation), rationale, and report linkage (Limitations + Future Scope, R7 results).
- **Supports:** R7 defect disposition; Limitations chapter; Future Scope chapter.
- **Captured:** 2026-06-20.
