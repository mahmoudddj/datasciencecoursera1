# Stage 2 build plan (started 31 Oct 2026)

Target: notebook `Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb`, built by `dev/tools/build14.py` from the `_12` data stages plus new cells, embedding the v12 modules. Every step is fixture-tested before it is committed. Nothing runs on real data before the freeze.

## Work breakdown, in build order

| # | Piece | Module or cell | Protocol item | Status |
|---|---|---|---|---|
| 1 | Two-channel feature manifest with audit (physiology, practice, host block; availability-dependent flags) | `v12_manifest.py` | 10c.2 item 14 | started 31 Oct |
| 2 | Suspicion-anchored event and label matrix (sustained antibiotic course, 72 h washout, censor at event, 3 h horizon; 6 h reading) | `v12_labels.py` | item 9 | started 31 Oct |
| 3 | Documented and positive-unlabelled soft labels; pre-treatment hour mask | `v12_labels.py` | items 10, 15 | started 31 Oct |
| 4 | Baseline-relative features (expanding baseline, restricted channels, deviation, z, slope, 24 h extremes), leak audit | `v12_features.py` | item 7 | started 31 Oct |
| 5 | Antibiotic course and culture-time supplement for all stays (start, stop, drug, route; death hour; MIMIC `microbiologyevents`, eICU `microLab`) with its own cache key | `v12_data.py` | items 9, 10 | next |
| 6 | Label variants by the pinned YAIB worker: antibiotic-only on MIMIC-IV (`si_mode='abx'`), culture-paired on eICU where `microLab` times exist; separate caches | notebook cell | item 10 | next |
| 7 | Full-release cohort: candidates = all stays, exclusion 7 dropped, incident flag kept; eight parallel label batches; reuse of the 20,000 cached candidates | notebook cells, `v9_runtime` settings | items 1, 19 | next |
| 8 | Two-channel model: two flat OSTA encoders, concatenation head, manifest-driven input split; practice-path zeroing and re-standardisation (z-score, quantile mapping) at evaluation; practice-only probe; concept-grouped practice path | `v12_models.py` | item 14 | next |
| 9 | Pooled-training arm (one model, both databases, one normaliser per database) | `v12_train.py` | section 11 arm 3 | next |
| 10 | Weakly supervised multi-task pretraining of the pooled encoder (arrival sepsis, six SOFA components, next-6-h treatment events); zero-shot and 10 % fine-tune evaluation | `v12_train.py` | item 3 | next |
| 11 | Label-stratified training (operational, documented-and-operational, PU soft) with the cross-evaluation matrix | `v12_train.py` | item 15 | next |
| 12 | Scoring passes: 6 h reading; pre-treatment evaluation; label sensitivities; documentation strata; abstention variants with adoption rule; threshold transport per hospital; temporal validation by anchor-year group; antibiotic-relative lead | `v12_evaluate.py` | items 8, 10, 16, 17 | next |
| 13 | Seed tiering and arm order; per-arm completion markers; run manifest | notebook config | section 11 | next |
| 14 | Team summary for stage 2 (tables, figures, digest) | `team_summary_stage2.py` | | next |
| 15 | Fixture run end to end; code notes | `build14.py`, `v12_tests.py` | | next |

## Invariants carried from stage 1

Patient-grouped splits keyed by the data key and split seed; protected holdout untouched until the freeze; counts under 11 masked in every printed table; no patient-level output; `FORCE_*` flags false; one heavy notebook at a time; every job resumable from its last epoch; every arm skipped once its completion marker exists.

## Open decisions feeding the build

The consultants' three answers (alarm budget, course definition, threshold form); the shared physiology set from the full-release pathophysiology repeat; whether the deterioration target is prespecified (contingent on that repeat).
