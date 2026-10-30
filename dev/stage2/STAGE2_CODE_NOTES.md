# Stage 2 notebook: what the code does (built 31 Oct 2026, before the freeze)

Notebook `Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb`, built by `dev/tools/build14.py` from the `_12` notebook. The v9/v10/v11 modules are embedded unchanged; the v12 modules and a worker with two environment switches are added. Nothing in this notebook has run on real data. Test-split rows are sealed on disk until `PROTOCOL_FROZEN=True` with the signed tag.

## Settings added in cell 1 (to confirm before the freeze)

| Setting | Default | Meaning |
|---|---|---|
| `FULL_SAMPLE_STAYS_PER_DATASET` | `None` | all candidate stays of both releases |
| `FULL_SEEDS` | `[42, 7, 123]` | three seeds for arms 1 to 5, the first seed for arms 6 to 9 (`THREE_SEED_ARMS` in `v12_train`) |
| `STAGE2_ARMS` | the nine arms in section-11 order | remove from the end to cut the budget |
| `STAGE2_KEEP_EARLY_ONSET` | `True` | YAIB exclusion 7 not applied; the index carries `Incident` and `ArrivalSepsis` |
| `STAGE2_LABEL_VARIANTS` | `{'miiv':'abx','eicu':'and'}` | item 10 (a), (b): labels phase only, own cache, onsets read back for the scoring pass |
| `STAGE2_REUSE_LABEL_ROOTS` | `[]` | earlier `cohorts_v9/<key>/sepsis` roots whose completed label batches are carried into the new plan (the 20,000 labelled candidates) |
| `STAGE2_SUSPICION_HORIZON` | 3 | item 9 |
| `STAGE2_TRAIN_INCLUDES_OBSERVER_FIT` | `True` | the retired observer bank's 30 % development split joins training (70 % of development patients train; 15 % validation; 15 % calibration; 20 % test). Stage 1 trained on 40 %. **A change to confirm**: it is recorded in `run_protocol.json` either way |
| `STAGE2_SHARED_PHYSIOLOGY` | the 14 channels of the 31 Oct run | item 2 (b); to fix from the full-release pathophysiology repeat |
| `STAGE2_BEST_NON_PROJECT_ARM` | `two_channel` | item 9: the suspicion target also runs on this arm |
| `STAGE2_LHO_FRACTION` | 0.2 | eICU leave-hospital-out share of development hospitals (hash-selected, fixed before training) |
| `STAGE2_FINETUNE_FRACTION` | 0.1 | item 3 target-site fine-tune |
| `STAGE2_PRETRAIN_EPOCHS` | 5 | item 3 |
| `PROTOCOL_FROZEN`, `PROTOCOL_FREEZE_TAG` | `False`, `''` | test rows released only when both are set after the signed tag |
| `LABEL_PARALLEL_BATCHES` | 8 | item 19 |

## Cell by cell (what changed from `_12`)

**Cell 3 (modules).** Adds `v12_manifest`, `v12_labels`, `v12_features`, `v12_data`, `v12_models`, `v12_evaluate`, `v12_train`, `v12_cohort`, `v12_fixture`, `v12_tests` and the stage-2 `v9_yaib_worker.py`. The worker is the stage-1 worker plus two environment switches: `V12_SI_MODE` (ricu `si_mode` for the `sep3_alt` load: `abx` antibiotic-only, `and` antibiotic paired with a culture) and `V12_KEEP_EARLY_ONSET=1` (drops the criterion whose description is "Sepsis onset before 6h in the ICU" from the pinned criteria list; every other criterion and the pinned `sepsis.py` are untouched). Unset, the worker behaves as in stage 1. Its hash changes, so the cohort key is new.

**Cell 4 (checks).** Stage-1 checks plus the v12 groups: manifest, labels and baseline features (`run_checks`), models and scoring passes (`run_checks_models_and_scoring`), stores, transforms and splits (`run_checks_stores`). The driver run on the fixture (`run_checks_training`) is the release gate, run by the builder, not in the notebook.

**Cell 8 (cohort key).** `COHORT_PROTOCOL` gains `version='v12_all_comers'` and `stage2={'keep_early_onset': True}`.

**Cell 12 (4d, extraction).** `v12_cohort.extract_cohort_batched_v12`: the v9 plan, worker, memory watchdog and merge, plus (a) label-batch reuse: completed LABELS batches of the earlier plans whose stays are all candidates are copied into the new plan as their own batches, so the pinned sep3 computation is not repeated for them; the COHORT phase runs again for every batch because the criteria (exclusion 7) and the eICU hospital prevalence (now over the full release) differ; (b) `phases=('labels',)` for the two label variants, which need only the onsets. The variant onsets are read from `labels.parquet` (`time` of the non-missing `sep3_alt` events) into `ALT_ONSETS[ds]` keyed `ds|stay_id`.

**Cell 14 (5, data).** `cohort_index_v12` (v9 index plus `Incident`, `ArrivalSepsis`); the raw stage and v11 supplement as before; the v12 supplement `CourseExtractor.supplement2()` (antibiotic courses with start, stop, agent, route; culture times; hospital outcomes; MIMIC `anchor_year_group`; documented sepsis by ICD code or eICU diagnosis string) under `SUPP2_KEY`; `DATA_KEY` includes `SUPP2_KEY` and `v12_cohort.py`. The stay tables for the driver are built here: suspicion hours (`v12_labels.suspicion_events` on the courses and death hours), first treatment hour (first antibiotic or culture), documented flag, antibiotic start lists, arrival flags, anchor-year groups, the documentation prior per database, the variant onsets. `TRAIN_INDEX` = incident stays (primary cohort); `ARRIVAL_INDEX` = arrival-sepsis stays (pretraining corpus only). The two-channel manifest is audited and written.

**Cell 16 (5c, corpus).** Unchanged: the unlabelled corpus (stays never in the cohort, protected patients excluded).

**Cell 17 (6-7, training).** `TRAIN_CONFIG` = the stage-1 config plus the stage-2 keys; `RUN_KEY` binds data, code, configuration, features and the table sizes; `run_protocol.json` records the seed tiering, the training-split rule, the freeze state. `v12_train.run_stage2(TRAIN_INDEX, FEATURES, TRAIN_CONFIG, RESULTS_ROOT, STAGE2_TABLES, DATASETS, PRETRAIN_CORPUS)`; `PRETRAIN_CORPUS` = the unlabelled corpus plus the arrival-sepsis stays.

**Cell 18 (7b, team summary).** Validation rows by arm and database (mean over seeds), the project model's seed spread, the abstention table with the adoption rule, a bar figure, a digest. Sealed test files are counted, never read.

## The driver (`v12_train.Stage2Run`)

Arms in `ARM_ORDER`; each arm checks its `completed.json` per seed, database and name, so a stopped session resumes at the next unfinished arm and, within an arm, from `last.pt` of the current epoch.

| Arm | What runs | Rows beyond validation and test (sealed) |
|---|---|---|
| `project` | `flat_osta` per database; the MIMIC temporal validation on the first seed (`temporal_partition`: train/val/calib on the earlier anchor-year groups, test on the latest group with at least 20 septic development stays) | transfer; `temporal_absolute`, `temporal_quantile` with O:E ratio, calibration slope, realised alarm fraction |
| `two_channel` | `TwoChannelOSTA` per database; then the practice-only probe (`practice_path`) and the concept-grouped comparator (`two_channel_concept`: the practice columns replaced by one measurement-intensity and one freshest-age column per organ group) | `practice_zero`, `practice_zscore` (per eICU hospital with at least 20 stays; whole test population on MIMIC), `practice_quantile` on the same trained model |
| `pooled` | `flat_osta` on both databases' development splits with one normaliser per database (`fit_norms`); then the eICU leave-hospital-out training (MIMIC development plus the non-held-out eICU hospitals, tested on the held-out hospitals) | `pooled_model_own_test` per database with the scoring passes |
| `suspicion` | `flat_osta@suspicion` per database (the store rebuilds y and eligibility from `SuspicionHour` with the 3 h horizon; the utility is not computed); `two_channel@suspicion` when `best_non_project_arm` is `two_channel` | `suspicion_reading_3h`, `suspicion_reading_6h` |
| `pretrained` | `pretrain_weak`: a flat OSTA core with three heads (arrival sepsis on hours 1 to 6; the six SOFA components at +6/+12/+24 h; vasopressor start, invasive airway, antibiotic start within 6 h), uncertainty-weighted, on the pooled corpus (training-split stays, unlabelled corpus, arrival stays; validation, calibration, test and protected patients excluded); then `flat_osta_weakpre` (full fine-tune at home), `flat_osta_weakpre_zeroshot` (core frozen, head trained at home; its transfer row is the zero-shot reading), `flat_osta_weakpre_finetune10_from_<home>` (the home model fine-tuned on 10 % of the other database's training patients at a third of the learning rate, scored on that database's test split) | |
| `predictor_sets` | `physiology_path`, `physiology_path_nohost`, `shared_physiology` (value, mask and age columns of the shared base names), `baseline_relative`, `baseline_absolute`, `baseline_both` (`BaselineStore`: the patient's expanding baseline summaries computed from the shard per stay; ICU time kept; no masks or counts) | |
| `label_stratified` | `flat_osta@documented` (undocumented operational positives weight 0) and `flat_osta@pu_soft` (their hourly label scaled by the documentation prior), through `StayWeight` and `StayValue` in the index | `eval_label_documented_and_operational` (the cross-evaluation row); the operational and suspicion labels come from the standard passes |
| `benchmarks` | `grud`, `tcn`, `logistic`, `boosted_tree` | |
| `exploratory` | the v11 SSL pooled encoder, then `ssl_cnn_flat_pooled` and `ssl_cnn_osta_pooled` | |

Scoring passes on every saved test (and transfer) frame: `pre_treatment_hours`; `documentation_documented` / `documentation_undocumented`; `suspicion_label_3h` / `_6h` (operational models against the suspicion label); `alternative_operational_label` (antibiotic-only on MIMIC, culture-paired on eICU); `threshold_transport_absolute` / `_quantile` dispersion across eICU hospitals; lead versus the first antibiotic; O:E ratio and calibration slope. Abstention variants (`reset`, `transparent`, `gated`) with the adoption rule run on the validation split only and are returned.

Every model, store and loss used by the primary target is the stage-1 code path (`predict`, `calibrate`, `select_threshold`, `utility_block`, `evaluate_v11`); `train_stage2` is `train_neural` with the per-hour target and weight read from the store, which equal the label and eligibility for the primary target.

## Fixture gate

`v12_tests.run_checks_training(root)` builds the stage-2 fixture (`v12_fixture.make_stage2_fixture`: the v10 fixture plus the stay tables and a corpus) and runs every arm with 1 epoch, small models, 1 seed on CPU; it asserts that every arm wrote test rows, that every scoring pass produced rows, that transfer rows exist, that the returned frame holds no test row when the protocol is not frozen, and that a second call reuses every completion marker.
