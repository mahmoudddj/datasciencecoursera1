# Stage 2 build plan (started 31 Oct 2026)

Target: notebook `Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb`, built by `dev/tools/build14.py` from the `_12` data stages plus new cells, embedding the v12 modules. Every step is fixture-tested before it is committed. Nothing runs on real data before the freeze.

## Work breakdown, in build order

| # | Piece | Module or cell | Protocol item | Status |
|---|---|---|---|---|
| 1 | Two-channel feature manifest with audit (physiology, practice, host block; availability-dependent flags) | `v12_manifest.py` | 10c.2 item 14 | done 31 Oct (checks pass) |
| 2 | Suspicion-anchored event and label matrix (sustained antibiotic course, 72 h washout, censor at event, 3 h horizon; 6 h reading) | `v12_labels.py` | item 9 | done 31 Oct (checks pass) |
| 3 | Documented and positive-unlabelled soft labels; pre-treatment hour mask | `v12_labels.py` | items 10, 15 | done 31 Oct (checks pass) |
| 4 | Baseline-relative features (expanding baseline, restricted channels, deviation, z, slope, 24 h extremes), leak audit | `v12_features.py` | item 7 | done 31 Oct (checks pass) |
| 5 | Antibiotic course and culture-time supplement for all stays (start, stop, drug, route; death hour; MIMIC `microbiologyevents`, eICU `microLab`) with its own cache key | `v12_data.py` | items 9, 10 | done 31 Oct (dry run on the raw-schema fixture) |
| 6 | Label variants by the pinned YAIB worker: antibiotic-only on MIMIC-IV (`si_mode='abx'`), culture-paired on eICU where `microLab` times exist; separate caches | notebook cell | item 10 | done 1 Nov (`v12_cohort.py` phases; worker `V12_SI_MODE`; notebook cell 4d) |
| 7 | Full-release cohort: candidates = all stays, exclusion 7 dropped, incident flag kept; eight parallel label batches; reuse of the 20,000 cached candidates | notebook cells, `v9_runtime` settings | items 1, 19 | done 1 Nov (`extract_cohort_batched_v12` with label-batch reuse; worker `V12_KEEP_EARLY_ONSET`; `cohort_index_v12`) |
| 8 | Two-channel model: two flat OSTA encoders, concatenation head, manifest-driven input split; practice-path zeroing and re-standardisation (z-score, quantile mapping) at evaluation; practice-only probe; concept-grouped practice path | `v12_models.py` | item 14 | model done 31 Oct (checks pass); store transforms done 1 Nov (`practice_spec`, `Stage2Store`, concept comparator in the driver) |
| 9 | Pooled-training arm (one model, both databases, one normaliser per database) | `v12_train.py` | section 11 arm 3 | done 1 Nov (`fit_norms`, `pooled_partition`, `leave_hospital_out`) |
| 10 | Weakly supervised multi-task pretraining of the pooled encoder (arrival sepsis, six SOFA components, next-6-h treatment events); zero-shot and 10 % fine-tune evaluation | `v12_train.py` | item 3 | done 1 Nov (`WeakHeads`, `pretrain_weak`, `linear_probe_model`, 10 % fine-tune in `arm_pretrained`) |
| 11 | Label-stratified training (operational, documented-and-operational, PU soft) with the cross-evaluation matrix | `v12_train.py` | item 15 | done 1 Nov (`StayValue`/`StayWeight` in the store; `arm_label_stratified`) |
| 12 | Scoring passes: 6 h reading; pre-treatment evaluation; label sensitivities; documentation strata; abstention variants with adoption rule; threshold transport per hospital; temporal validation by anchor-year group; antibiotic-relative lead | `v12_evaluate.py` | items 8, 10, 16, 17 | done 31 Oct (checks pass); temporal split lives in the driver |
| 13 | Seed tiering and arm order; per-arm completion markers; run manifest | notebook config | section 11 | done 1 Nov (`Stage2Run`, `ARM_ORDER`, `THREE_SEED_ARMS`, `completed.json` per arm; `stage2_config_block.py`) |
| 14 | Team summary for stage 2 (tables, figures, digest) | `team_summary_stage2.py` | | done 1 Nov (`team_summary_stage2.py`) |
| 15 | Fixture run end to end; code notes | `build14.py`, `v12_tests.py` | | done 1 Nov (`build14.py`; `run_checks_stores` in the notebook, `run_checks_training` as the release gate; `STAGE2_CODE_NOTES.md`) |

## Invariants carried from stage 1

Patient-grouped splits keyed by the data key and split seed; protected holdout untouched until the freeze; counts under 11 masked in every printed table; no patient-level output; `FORCE_*` flags false; one heavy notebook at a time; every job resumable from its last epoch; every arm skipped once its completion marker exists.

## Decisions made in the build that the partner should confirm before the freeze

- The training split: the retired observer bank's 30 % development split joins training (`STAGE2_TRAIN_INCLUDES_OBSERVER_FIT=True`; 70 % of development patients train, 15 % validate, 15 % calibrate). Stage 1 trained on 40 %. Recorded in `run_protocol.json`; set False to keep the stage-1 split.
- The eICU leave-hospital-out split: a hash-selected 20 % of development hospitals, fixed before training (`STAGE2_LHO_FRACTION`).
- The pretraining corpus: training-split stays, the unlabelled corpus and the arrival-sepsis stays; validation, calibration, test and protected patients excluded (as section 11 says, TO FREEZE).
- The zero-shot reading of the pretrained core: the core frozen, the prediction head trained at home, scored on the other database (the transfer row); the 10 % fine-tune starts from the home model at a third of the learning rate.
- Arrival-sepsis stays enter only the pretraining corpus; the all-comers stratified evaluation of section 11 needs predictions on arrival stays and is not built (their pre-onset hours are 0 to 5).

## Open decisions feeding the build

The consultants' three answers (alarm budget, course definition, threshold form); the shared physiology set from the full-release pathophysiology repeat; whether the deterioration target is prespecified (contingent on that repeat).
