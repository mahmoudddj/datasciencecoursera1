# Sepsis V10.2 — handoff for Dr. Mahmoud Mohamed

Two self-contained notebooks, both defaulting to `RUN_MODE='smoke'`:

- `Sepsis_V10_Improved_MIMIC_eICU.ipynb` — main development notebook (MIMIC-IV + eICU).
- `PhysioNet_Models_External_Validation_MIMIC_eICU.ipynb` — legacy PhysioNet-model external validation. It runs on its own from a fresh session.

All code is embedded with SHA-256 checks (29 files). The original OSTA and CNN scripts, your handcrafted module and the pinned PhysioNet scorer are embedded byte-for-byte. Nothing calls a language-model API during training or inference. The notebooks are delivered **without outputs**, so no stale synthetic numbers or local paths are shown.

## What changed and why

### Main notebook
| Issue found in the V10.1 audit | Fix |
|---|---|
| Trend features (`*_Slope/Variance/Skew`) were computed on hourly values carried forward by the TTL. A single measurement counted up to 6×, and slopes were flattened. | Trend features now use only fresh measurements at their real measurement times (Hour − age) with a true OLS slope. A `*_Count{3,6}h` channel was added. Carried-value detection is safe after the float32 round trip. |
| `elapsed_since_event` was defined but never used. There was no first-vs-latest distinction. | Added `Vasopressor_HoursSinceFirst/Last` and `qSOFA2_HoursSinceFirst/Last`. Unknown hours neither create nor erase an event. Antibiotic timing is deliberately excluded because it defines the label. |
| Weight expired after 24 h, which silently disabled weight-normalised urine output after day 1. | Weight no longer expires within the window. |
| `PostoperativeAdmission` was an always-missing predictor, despite a comment saying it was dropped. | It is now metadata only. |
| Feature building cost about 0.6 s per 120-h stay and could not resume. A Colab disconnect restarted a whole database. | Urine and support loops are vectorised (about 4× faster in a synthetic benchmark; identical to the old code on 300 randomised cases). Feature shards resume per batch. |
| The raw-table stage was keyed to feature code, so any feature change forced new whole-table DuckDB scans. | The stage is now keyed only by extraction code, under `raw_stage_v10/<key>`. The legacy notebook reuses it. |
| The raw-vs-engineered control covered OSTA only. | The control now also covers logistic regression and boosted trees, where engineered features matter most. |
| The registry listed raw channels only, and coverage only checked urine. | The registry now covers every predictor, mask and age column with its organ group. The run stops if a core channel was never captured. |
| A DuckDB version below 1.2 cannot do strict CSV parsing. This was found on the older test stack. | The config cell upgrades DuckDB before its first import. |
| Prior test exposure was not recorded. | `PRIOR_TEST_EXPOSURE` is required before full mode and is written into `run_protocol.json`. |

These are unchanged, because existing caches depend on them: the cohort protocol, the YAIB worker, the Python 3.10 / R 4.2.2 environment, the strict CSV parser, the RAM watchdog, balanced batches, the eICU nested-dictionary repair, onset from unwindowed `sep3_alt`, the split and holdout rules, and all 8 arms. **Existing ricu imports and YAIB cohorts remain reusable.** The feature cache will be rebuilt once.

### Legacy notebook
| Issue | Fix |
|---|---|
| Real historical outputs could not be loaded. The bundle format required a hand-made single state dict. The originals are a 3-seed OSTA ensemble with the scaler in a cache `.npz` and the threshold in a sweep CSV. | New `LEGACY_MODE='import_original'`. It packages the original output folders without retraining. The original checkpoint format is supported, along with a uniform or weighted ensemble or stacking, and the threshold is the first maximum of the saved validation sweep. A test shows the import reproduces the original scripts' predictions to 1e-5. |
| The original training CSV ("previous values gpbyID") appears to be forward-filled. The adapter always fed sparse data, so the original missingness and `_tslm` features would have been shifted. | The source representation is detected from the data or declared. The adapter then reproduces either a sparse or a forward-filled input. A backward-filled or ambiguous source is refused. |
| The carried-value stripping compared float32 times exactly, so it would have stripped nothing on real shards. | Comparison now uses a tolerance. |
| Reproduction used a 14-channel schema, BCE loss, the wrong CNN size in full mode, and a different split and threshold grid. | Reproduction now uses the original column rule, split rule, losses, optimiser and schedule. Model selection is validation patient AUROC every 2 epochs, with the original threshold grid. Full mode uses the original architectures and 3 OSTA seeds. It is still clearly labelled a re-training. Each bundle records its source-internal test utility as a fidelity check. |
| Normalisation differed from the original handling of infinities. | It now matches the original exactly (tested). |
| HospAdmTime was missing on the target side. | It is extracted from MIMIC admissions and eICU `hospitaladmitoffset`. |
| The original scripts chose thresholds with an hourly policy but evaluated with a latched, backdated first alarm. | The hourly policy is used for both selection and evaluation. Bundles whose evaluation policy differs from their threshold-selection policy are refused. |
| Source checks could happen after expensive work. | Schema, representation and units are checked before any training or target extraction. |

## What actually ran and passed (synthetic data only)
- Both notebooks ran top to bottom through a real Jupyter kernel in fresh processes, in fixture mode, on two library stacks (pandas 3.0 / numpy 2.5 and pandas 2.2 / numpy 2.0). Python 3.12, CPU.
- 137 main engineering checks and 49 legacy checks passed. The lists are in `verification/*.json`.
- All 8 arms plus the raw and 80% controls ran through fit, calibration, threshold, metrics and export on both fixture databases. Every arm was scored on identical patient-hours.
- I killed the kernel mid-training in both notebooks and reran. Results and checkpoints were bit-identical to uninterrupted runs. Completed runs are reused, and a changed config is refused.
- A clinical-path dry run on schema-shaped synthetic MIMIC-IV/eICU CSVs passed: extraction, onset audit, shard building, and legacy target building with stage reuse.

**None of this is real-data validation.** No MIMIC-IV, eICU or PhysioNet records were available to me.

## Remaining limitations and blockers
1. **Real extraction is unverified.** That includes ricu/R workers, labels, coverage and Colab RAM/time. Smallest action: run the main notebook in smoke mode on Colab with your Drive mounted, then check `labels_complete.json`, `v10_onset_audit.parquet`, `coverage_all.csv` and `units.csv`.
2. **Historical validation is blocked.** The ZIP has no weights, scalers or sweeps. Smallest action: set `LEGACY_MODE='import_original'` and point `ORIGINAL_OUTPUT_DIRS` at your original `outputs/osta` and `outputs/paper1` folders, plus `PHYSIONET_SOURCE` at the CSV so the representation and units are measured. Note that the CNN cache file `preprocessed_data_cache_paper1.npz` is required, because the CNN checkpoint does not store its scaler.
3. If your original OSTA run used `OSTA_ENSEMBLE_WEIGHTING` other than uniform, set `OSTA_HISTORICAL_ENSEMBLE` explicitly (weights, or stacking coefficients).
4. These are documented, not fixed: eICU's antibiotic-only suspicion proxy; YAIB whole-stay selection filters; eICU entry-time proxies for vitals and infusions; urine coverage is not proof of complete collection; EtCO2, SaO2, TroponinI and Hct are unavailable on the target side for the legacy models; `SOFAproxy` is not SOFA.
5. Full-mode runtime on Colab is unmeasured. Expect many GPU hours. Everything checkpoints.

## The two stops you may see first on real data
- **"Raw source is not a full release"**: the folder in `RAW_SOURCE_PATHS` holds a demo or partial copy. A MIMIC-IV folder with 140 ICU stays is the MIMIC-IV Clinical Database Demo; the full release has about 73k (v2.2) or 94k (v3.x) stays. Point the path at the full release. Nothing has been imported at this point.
- **"One-time prerequisite needed for ..."**: there is no completed cohort yet, so ricu must import that database once, over whole tables. The table printed above the error shows, per database, whether `.fst` files or import markers already exist. Smoke mode cannot shrink this step. Set `ALLOW_FULL_RAW_IMPORT=True` when you are ready (Colab High-RAM recommended, several hours per database, free Drive space roughly comparable to the raw files). Imported tables are written next to the raw files and reused by every later run.

## Where to set paths (Section 1 of each notebook)
- `PROJECT_PATH` (default `MyDrive/sepsis_colab_project`).
- `RAW_SOURCE_PATHS['miiv']`: the parent of `hosp/` and `icu/`.
- `RAW_SOURCE_PATHS['eicu']`: the folder containing `patient.csv.gz`.
- Optional: `REUSE_COHORT_ROOT`.
- Legacy notebook only: `LEGACY_MODE`, `PHYSIONET_SOURCE`, `ORIGINAL_OUTPUT_DIRS`, or `HISTORICAL_BUNDLES`.

You can set the same paths with the environment variables `SEPSIS_PROJECT_ROOT`, `SEPSIS_MIMIC_ROOT`, `SEPSIS_EICU_ROOT` and `SEPSIS_PHYSIONET_SOURCE`.

## Switching to full mode
1. Finish a real smoke run and review the audit files.
2. Fill in `PRIOR_TEST_EXPOSURE`.
3. Set `RUN_MODE='full'` and run all cells.
4. Leave `RELEASE_FINAL_HOLDOUT=False` until the protocol is frozen.

Main notebook Section 6 prints the resolved smoke-vs-full settings without launching anything.

## Resume and completion markers
To resume, rerun from the top with unchanged settings. Keep `FORCE_RICU_REIMPORT=False` and `FORCE_YAIB_REEXTRACT=False`.

| Notebook | Item | Marker |
|---|---|---|
| Main | Whole run | `validation_v10/runs/<RUN_KEY>/COMPLETE.json` and `all_results.csv`, `summary_normal_condition.csv` |
| Main | Each arm | `.../<feature_set>/<target>/seed_<s>/<arm>/completed.json` |
| Main | Feature batches | `validation_v10/data/<DATA_KEY>/<ds>/shards/parts/*.done.json` |
| Main | Raw stage | `raw_stage_v10/<key>/<ds>/raw_complete.json` |
| Legacy | Whole run | `legacy_validation_v10/runs/<key>/COMPLETE.json` and `legacy_results.csv` |
| Legacy | Source bundles | `source_bundles/<key>/<arm>/manifest.json`, `member_seed*.done.json` |
| Legacy | Target trajectories | `targets/<key>/<ds>/complete.json` |
| Both | Logs | `pipeline_logs_v10/` |
