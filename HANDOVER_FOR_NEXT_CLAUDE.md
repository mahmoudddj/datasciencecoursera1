# Handover: Sepsis V10.2 project (MIMIC-IV + eICU) for Dr. Mahmoud Mohamed

> **Status, 16 Oct 2026: the real smoke run of Notebook A has COMPLETED on Colab** (V11 notebook, cohort key `52af15d8cc7f3935`, with cell 4c). The next phase is **full mode on a rented high-memory cloud machine**. You lead that move: see **Section 11** (Google Cloud recommended, AWS as the alternative). Do the Section 8 archive of the smoke outputs first.

**For the next Claude session.** Read this whole file before acting. It records what was built, every error met on real data and how it was fixed, the exact current state, what to expect next, and what is still pending. **Your standing instruction from Dr. Mohamed: save every output needed to write the paper (see Section 8).**

- Repository: `mahmoudddj/datasciencecoursera1`, branch `claude/happy-thompson-ngxbp8` (latest commit `bcffa7c` plus this handover).
- Deliverables at the repo root:
  - `Sepsis_V10_Improved_MIMIC_eICU.ipynb` — main development notebook ("Notebook A").
  - `PhysioNet_Models_External_Validation_MIMIC_eICU.ipynb` — legacy external validation ("Notebook B").
- Both notebooks default to `RUN_MODE='smoke'`. Dr. Mohamed runs them himself on Google Colab with Google Drive.
- Other repo files:
  - `HANDOFF.md` — user-facing handoff: paths, resume, full mode.
  - `verification/*.json` — the check lists that passed.
  - `dev/` — the sources the notebooks are built from (Section 9).

---

## 1. Goal and scientific design (do not change without the user)

**Notebook A** develops and compares eight arms on MIMIC-IV 3.1 and eICU-CRD 2.0 only (no HiRID):
- OSTA
- observer information as input features
- observer prediction fusion at the output
- gated attention guidance
- ungated attention guidance
- CNN–Transformer
- L2 logistic regression
- histogram gradient-boosted trees

Two controls run alongside the arms:
- **Raw vs engineered features**: OSTA, logistic and boosted trees on raw values, masks and measurement ages only.
- **Extra label budget for observers**: OSTA trained on the 80% that includes the observer-fitting patients.

Shared design:
- **Task**: sepsis onset (YAIB `sep3_alt`) within (t, t+6] hours.
- **Rows**: post-onset hours are excluded, and negatives are censored when the horizon is not fully observed.
- **Splits**: patient-grouped. All arms use the same eligible patient-hours.
- **Holdout**: a deterministic patient hash seals 20% per database as the final holdout. It is released only in full mode with `RELEASE_FINAL_HOLDOUT=True`.
- **Neutrality**: gated attention must **not** be assumed to win.

**Notebook B** externally validates the PhysioNet 2019-trained OSTA (3-seed ensemble) and Paper1 CNN–Transformer on MIMIC and eICU, with frozen models and full hourly trajectories.
- **Scorer**: the official PhysioNet utility, pinned to commit `467c49b`. Step labels start at onset − 6 h and are applied once only.
- **Model sources**:
  - `import_original`: packages the original scripts' output folders.
  - `frozen`: loads a bundle.
  - `reproduce` (default): a clearly labelled re-training. It is not the historical model.
- **Status**: no historical weights have been supplied yet.

---

## 2. What was achieved (V10.1 → V10.2)

**Main notebook**
- **Trend features**: these were wrong before. They used TTL-carried hourly values, so one reading counted up to 6 times. They now use fresh measurements at real measurement times, with a true OLS slope, plus `*_Count{3,6}h`.
- **New event-timing features**: time since the first and the most recent *observed* event, for vasopressor support and for a decidable qSOFA ≥ 2. Antibiotic timing is deliberately excluded because it defines the label.
- **Data fixes**:
  - Weight no longer expires after 24 h; before, weight-based urine output vanished after day 1.
  - `PostoperativeAdmission` is metadata only.
- **Speed and resume**:
  - Urine and support windows are vectorised: about 4× faster, and identical to the old code on 300 random cases.
  - Feature shards resume per batch.
  - The raw-table stage is keyed only by extraction code, so Notebook B can reuse it.
- **Registry and checks**:
  - A full feature registry assigns every column to an organ group.
  - Coverage gates stop the run if a core channel is never captured.
  - DuckDB is upgraded to ≥ 1.2, which strict CSV parsing needs.
  - `PRIOR_TEST_EXPOSURE` must be recorded before full mode.
- **New pre-flight steps (added during the real-data run)**:
  - A per-file size audit refuses demo or mixed folders.
  - Per-table consent for ricu re-import (`ALLOW_FULL_RAW_IMPORT`).
  - An optional PhysioNet repair: credentialed download, SHA-256 verification, resumable, demo copies quarantined.

**Legacy notebook**
- **`import_original`**: loads the original output files directly:
  - OSTA: `v5_seed{42,7,123}_model.pt`, `v5_preprocessed_cache.npz` (scaler), `v5_validation_utility_sweep.csv` (threshold).
  - CNN: `sepsis_enhanced_transformer.pt`, `preprocessed_data_cache_paper1.npz`, `paper1_validation_utility_sweep.csv`.
  - A test shows the import reproduces the original pipeline's predictions to 1e-5.
- **Source representation**: detects whether the PhysioNet source is sparse PSV or forward-filled CSV, and the target adapter mirrors it.
- **Carried-value stripping**: now float32-safe. Before, it silently stripped nothing on real shards.
- **Reproduction recipe**: now follows the originals — column rule, split, losses, selection rule, threshold grid and full-size architectures (the CNN size was wrong before).
- **Exact original normalisation**, plus HospAdmTime on the target side.
- **Alarm policy**: one hourly policy for both threshold selection and evaluation. The originals evaluated with a latched, backdated alarm that their threshold selection did not use.
- **Order of checks**: source preflight runs before any training or target extraction.

---

## 3. Errors met on real data, cause, and fix (chronological)

| # | Symptom on Colab | Real cause | Fix (commit) |
|---|---|---|---|
| 1 | `RuntimeError: Cohort extraction is unfinished … set ALLOW_FULL_RAW_IMPORT` with `Raw candidate stay counts: {'miiv': 140, 'eicu': 200859}` | Not a code error. 140 is the MIMIC-IV **demo** stay count. | Release check by stay count; gate explained with a per-database status table (`f65205b`). |
| 2 | User showed the folder is `mimic-iv-3.1` (full) | Drive metadata showed a **mixed** folder: four core files were demo copies dated Oct 11–12 — `icu/icustays.csv.gz` 5.7 KB, `icu/chartevents.csv.gz` 5.5 MB, `hosp/patients.csv.gz` 1 KB, `hosp/admissions.csv.gz` 11 KB. The rest were full (Aug 28). The ricu import of `chartevents` had also been rebuilt from the demo file. **The earlier v9 MIMIC cohort contained only 140 demo stays and is invalid.** | Per-file size audit that refuses mixed folders and names the files; the blanket gate replaced by per-table consent at the import step (`56c93e2`). One-step PhysioNet repair (`12a6130`). |
| 3 | `ValueError: MIXED folder …` listing the 4 files | Correct detection | User uploaded the full files. Verified on Drive: `chartevents` 3.50 GB, `icustays` 3.34 MB, then `patients` and `admissions` (the audit then passed). |
| 4 | `RuntimeError: miiv: 4 ricu table(s) are new or changed … ['admissions','patients','icustays','chartevents']` | Expected consent stop: those 4 tables needed re-import. | User set `ALLOW_FULL_RAW_IMPORT=True`. The re-import completed; the run proceeded to labels. |
| 5 | Label batches 1–4 of 19 succeeded; batch 5 failed: `RRuntimeError: Error in .subset2(x, i, exact = exact): attempt to select less than one element in get1index`, right after `V9_INTERVAL_NAMESPACE_FALLBACK: 3600 secs` | Bug in the worker's ricu interval fallback (inherited from v9). It returned the grid as `3600 secs`, while ricu's `interval.difftime` returns it in the time column's units (`hours`). ricu `re_time()` and the sep3 windows then mixed secs and hours. | Fallback now sets `units(res) <- units(x)`, and the self-test checks the units. Verified in R 4.3 against ricu commit `0969a52` semantics: old gave `secs`, new gives `1 hours` (`bcffa7c`). **Not yet confirmed on Colab; this is the first thing to check.** |

| 6 | Two people ran notebooks on the same Drive project at once (the user and the collaborator `elrggalme`) | Logs in `pipeline_logs_v10/` were overwritten by both. Drive's "Owner" column shows the file's creator, not the last writer. | The user only ran the top cells, which write identical small notes; saved batches were not touched. **Rule: only one notebook may run past the release-check cell at a time on this Drive.** |
| 7 | Collaborator's run (`Sepsis_V11_Improved_MIMIC_eICU_1.ipynb`): MIMIC labels and cohort **complete**, eICU label batches 1–14 of 19 complete; batch 15 (folder `00014`) failed: `Error in .checkTypos(e, names_x): Object 'max_gap' not found amongst patientunitstayid, infusionoffset, dur_var, index_var, death_icu`, after the warning `max(numeric(0))` | Bug in the **pinned YAIB** callback `abx_cont()` (`ricu-extensions/callbacks/callback-sepsis.R`, commit 74ac699f). When no stay in the batch has an antibiotic record before death, `ricu::slide()` returns its empty input unchanged (the `hopper()` early return), so the `max_gap` column is never created and `res[max_gap <= abx_max_gap]` fails. | Notebook cell **4c** (`dev/work/cells/fix_4c_abx_cont.py`), inserted between the raw-import cell and the extract-labels cell. It patches only the empty case to return the same empty `abx_cont` table the normal path would give. It checks the pinned file's SHA-256 first (`f88c1007…` → `b42caa98…`), is idempotent, and writes `cohorts_v9/<key>/yaib_callback_amendment.json`. Tested on ricu 0.6.0 sources in R 4.3 (`dev/tools/test_abx_cont.R`): reproduces the exact Colab error; patched empty batch returns 0 rows with columns `id, index, abx_cont`; non-empty batch is `identical()` to the original; `susp_inf_alt`/`sep3_alt` accept the empty table, and a positive control still yields a `sep3_alt` label. Because the worker is unchanged, the cohort key stays `52af15d8cc7f3935` and batches 1–14 are reused. Completed batches never reached this code path, so reusing them is valid. **Not yet confirmed on Colab.** |

Earlier, in v9 only: eICU labels failed with `assert_that(): y is not a list`. The worker's eICU nested-dictionary bridge works on real eICU: batches 1–14 passed with `V9_EICU_NESTED_DICTIONARY_OK`.

**Which notebook is actually running.** The collaborator's `Sepsis_V11_Improved_MIMIC_eICU_1.ipynb` is the V10.2 build from **before** commit `bcffa7c`. Its embedded worker is the original one (sha `3e5e87fd…`, without the `units(res) <- units(x)` line), and it has no PhysioNet-repair cell (cell 7 is empty). It also has two debug cells (log reader and `sep3_alt` concept print). In that run the interval fallback printed `1 hours`, not `3600 secs`, and all 19 MIMIC batches finished. So error #5 did not recur there, and why it appeared in the user's earlier run is not fully explained. **Keep using that V11 notebook until labels are complete.** Switching to the repo's notebook (worker sha `13a2d99e…`) changes the cohort key and restarts all label extraction.

---

## 4. Current state (as of 15 Oct 2026)

- **Raw data on Drive (verified by file names and sizes only)**:
  - `/content/drive/MyDrive/mimic-iv-3.1/mimic-iv-3.1` (full MIMIC-IV 3.1; the 4 files are replaced).
  - `/content/drive/MyDrive/eicu-collaborative-research-database-2.0/eicu-collaborative-research-database-2.0` (full eICU, intact).
  - A demo folder `mimic-iv-clinical-database-demo-2.2` still exists elsewhere on the Drive. Do not use it.
- **Project folder**: `/content/drive/MyDrive/sepsis_colab_project`.
- **ricu imports**: complete for both databases, including the 4 re-imported MIMIC tables.
- **Labels and cohorts**, under cohort key `52af15d8cc7f3935` (V11 notebook):
  - MIMIC: complete (`sepsis/miiv/v9_complete.json`).
  - eICU: label batches 1–14 of 19 complete (plan folder `batches/fcb2514d8e9794ca`). Batch 15 needs fix #7. The eICU cohort pass (19 more batches) has not started.
  - Each batch takes about 7 minutes.
- **Never run on real data yet**: feature building, training, evaluation, and Notebook B on real data.
- **Settings in the V11 notebook that must change before any rerun from the top.** It had `FORCE_RICU_REIMPORT=True` and `ALLOW_FULL_RAW_IMPORT=True`, which is why it re-imported every eICU ricu table (about 11:00–12:02). Set:
  - `FORCE_RICU_REIMPORT=False`
  - `ALLOW_FULL_RAW_IMPORT=False`

  Neither is part of the cohort key. Keep the rest unchanged:
  - `RUN_MODE='smoke'`
  - `SMOKE_STAYS_PER_DATASET=1200`
  - `RANDOM_STATE`
  - `FORCE_YAIB_REEXTRACT=False`

  Also, don't touch the raw folders: file sizes and modification times are in the key.
- **Resume after the fix.**
  - If the Colab kernel is still alive: insert cell 4c, run it, then rerun only the extract-labels cell.
  - If the kernel restarted: correct the two flags above, then run all cells. Environment setup re-clones YAIB, and cell 4c re-applies the fix after it.

  You should see `Reuse completed cohort: miiv` and `eicu: reuse completed labels batch 1/19 … 14/19`.

---

## 5. Expected outcome of the next smoke run (Notebook A)

1. **Section 4 audit**: every row `ok`. Stay counts about 94,000 (miiv) and 200,859 (eicu).
2. **Raw import**: "all table markers are current … validated", then skipped.
3. **Labels**: miiv `balanced batch plan (1200 candidate stays): [64,…]`, 19 label batches, then 19 cohort batches; then the same for eICU, including a global hospital-prevalence pass. Batch 5 should now pass; the fallback message should read `1 hours instead of sparse inferred interval`. Check that every batch has a `labels_complete.json`, and read `attrition_by_batch.csv`.
4. **Raw-table stage**: one DuckDB scan per database, which streams whole CSVs (MIMIC `chartevents` is 3.5 GB, so expect tens of minutes) but keeps only cohort stays. Then the feature shards.
5. **Coverage audit**: must not report a core channel as never observed.
6. **Training**: smoke training (2 epochs, small models) for all arms and controls.
7. **Completion**: `validation_v10/runs/<RUN_KEY>/COMPLETE.json` exists, along with `all_results.csv` and `summary_normal_condition.csv`.

**Known risk**: the smoke sample (1,200 candidates, then YAIB exclusions, then the 20% sealed hash, then 5 splits) may leave a validation or calibration split without positive stays. The error is `both classes required; enlarge smoke sample`. If so, raise `SMOKE_STAYS_PER_DATASET`, e.g. to 3000. This creates a new cohort key, and more label batches are extracted. Do not lower the safeguards.

Smoke numbers are **execution evidence only**. Never rank models or tune anything from them.

---

## 6. Pending tasks (priority order)

1. **Done (16 Oct):** fix #7 worked and the real smoke run of Notebook A completed. Its numbers were not reviewed in the previous session. First, ask the user for the aggregate files only:
   - `COMPLETE.json`, `summary_normal_condition.csv`
   - `attrition_by_batch.csv` (both databases), `coverage_all.csv`, `units.csv`, `feature_registry.csv`
   - the batch log tails

   Check them:
   - every arm scored the same number of eligible hours,
   - no core channel is all-missing,
   - the sepsis counts are plausible.

   Never treat smoke scores as results. Then archive the smoke outputs per Section 8 (`paper_outputs/<date>_smoke_<RUN_KEY>/`, plus a `RUN_LOG.md` row). Record how many label batches took the empty-antibiotic path; `yaib_callback_amendment.json` exists, and the batch logs show which batches.
2. **Prepare full mode (Section 11).**
   - Add cell 4c to the repo notebooks (`dev/work/cells/fix_4c_abx_cont.py`, rebuild with `dev/tools/build.py`, rerun the fixture tests).
   - Add a full-mode label batch-size setting.
   - Run the timing test on the cloud machine.
   - Then the user decides between all stays and a prespecified large sample.
3. **Notebook B**:
   - Ask the user for the original output folders (`outputs/osta`, `outputs/paper1`), then use `LEGACY_MODE='import_original'`.
   - The CNN needs `preprocessed_data_cache_paper1.npz`, because its checkpoint has no scaler.
   - Set `PHYSIONET_SOURCE` (PSV folder or the cleaned CSV) so that the source representation and units are measured.
   - If the original outputs are unavailable, run the labelled `reproduce` path instead.
4. Before full mode (on the cloud machine, Section 11): the user fills in `PRIOR_TEST_EXPOSURE` (v9 results were seen), then sets `RUN_MODE='full'`. Full mode is a long GPU job, but it checkpoints and resumes. Keep `RELEASE_FINAL_HOLDOUT=False` until the protocol is frozen.
5. Final evaluation: the prespecified cross-database directions on protected patients, run once. No retuning after the results are seen.
6. Paper: TRIPOD+AI reporting and PROBAST+AI risk-of-bias assessment.

---

## 7. Rules you must keep

- **Data use agreement.** MIMIC and eICU are PhysioNet credentialed data. Do not pull patient-level records or row-level outputs into the chat or session. Only file names and sizes (Drive metadata), logs, and aggregate CSVs are acceptable. The user runs the notebooks on Colab.
- **No silent escalation.** Keep `FORCE_*=False`. Full raw imports and full training happen only when the user asks.
- **Honest labelling.** Synthetic or fixture checks are not real-data validation. Smoke results are not performance. Source reproductions are not the historical models.
- **Holdouts stay protected.** Never tune calibration, thresholds or model choice on final or external results. The two notebooks use different alarm policies: a 0.5 false-alarm/patient-day budget in A, the hourly utility policy in B. Do not mix them.
- **Debugging.** Always ask for the full traceback plus the last ~60 lines of the log file it names, and fix the root cause.
- **When changing code, edit `dev/work/...` and rebuild** (Section 9). Do not hand-edit the notebooks' embedded blobs. Changing `v9_yaib_worker.py` changes the cohort key and forces label re-extraction. Changing extraction code changes the raw-stage key. Feature changes only rebuild the feature shards.

---

## 8. SAVE ALL OUTPUTS FOR THE PAPER (user instruction)

The notebooks already write everything to Drive under `/content/drive/MyDrive/sepsis_colab_project/`. Your job:
1. Make sure each run finishes with its completion markers.
2. After each real run, have the user create a **dated, read-only archive** (a copy of the folders below into `paper_outputs/<date>_<mode>_<RUN_KEY>/`).
3. Keep a **run log** (`paper_outputs/RUN_LOG.md`), one row per run: date, notebook, mode, `COHORT_KEY`, `DATA_KEY`, `RUN_KEY`, commit hash, stays per database, status, notes.

Patient-level files stay on Drive only. Only aggregate CSVs and JSONs may be shared in chat.

**Cohort and labels (methods and flow diagram)**
- `cohorts_v9/<COHORT_KEY>/source_protocol.json`
- `.../sepsis/<ds>/attrition_by_batch.csv`
- `.../batch_protocol.json`
- `.../v10_onset_audit.parquet` (patient-level; Drive only)
- `.../batches/*/hospital_prevalence.csv`
- `extraction_patch.json`
- `cohorts_v9/<COHORT_KEY>/yaib_callback_amendment.json` (the YAIB `abx_cont` fix; cite it in the methods as a deviation from pinned YAIB)
- `validation_v10/yaib_environment_manifest.json` (R/Python/package versions)
- `validation_v10/v10_candidate_counts.json`
- `physionet_repair_log.json` (if used)

**Data and features (Table 1 and supplementary tables)**
- `raw_stage_v10/<key>/<ds>/extraction_counts.csv`
- `validation_v10/data/<DATA_KEY>/feature_registry.csv`
- `.../coverage_all.csv`
- `.../<ds>/shards/units.csv`
- `.../<ds>/shards/schema.json`
- `.../index.parquet` (Drive only)

**Results, Notebook A**
- `validation_v10/runs/<RUN_KEY>/run_protocol.json` (config, features, prior exposure)
- `all_results.csv`, `summary_normal_condition.csv`, `COMPLETE.json`
- Per arm: `calibration_and_threshold.json`, `threshold_sweep.csv`, `calibration_*.csv`, `training_history.json`, `gates_*.json`
- Per seed: `paired_comparisons.csv`
- `*_calibration.png`
- Logs: `<target>_<feature_set>.log`
- Predictions and alarms parquet files: patient-level, Drive only.

**Results, Notebook B**
- `legacy_validation_v10/source_bundles/<key>/source_preflight.json`
- Per arm: `manifest.json` (provenance, threshold, policy, source internal test), `source_threshold_sweep.csv`
- `runs/<key>/legacy_results.csv`, `paired_comparisons.csv`, `*_calibration.csv`, `COMPLETE.json`
- `targets/<key>/<ds>/excluded_clipped_onsets.parquet` (Drive only)

**Verification and reproducibility**
- `pipeline_logs_v10/engineering_checks.json`
- `pipeline_logs_v10/legacy_engineering.json`
- All `pipeline_logs_v10/*.log`
- The exact notebook files used, plus the git commit hash.

---

## 9. How the code is organised (for fixes)

- **`dev/work/mods/`**: the 29 embedded modules.
  - Main pipeline: `v9_data.py`, `v10_features.py`, `v10_protocol.py`, `v10_train.py`, `v9_train.py`, `v9_models.py`.
  - Legacy path: `v10_legacy.py`, `v10_clinical.py`.
  - Checks: `v10_preflight.py`, `v10_tests.py`, `v10_legacy_tests.py`.
  - Extraction (R/YAIB): `v9_yaib_worker.py`.
  - The originals are kept byte-identical: `legacy_*_original.py`, `supplied_handcrafted_original.py`, `official_evaluate_sepsis_score.py`.
- **`dev/work/cells/`**: notebook cell sources. `dev/in/` holds the V10.1 notebooks whose unchanged cells are reused.
- **Rebuild**: `python3 dev/tools/build.py dev <outdir>`. The committed sources reproduce the delivered notebooks byte-for-byte.
- **Test**: run each notebook in fixture mode with `SEPSIS_DATA_SOURCE=fixture` using `dev/tools/runnb.py <nb> <out.ipynb> <project_dir>` (needs Python 3.12, torch, pandas, duckdb≥1.2, nbclient, ipykernel). Expected: 141 main and 49 legacy checks pass, and both runs end in `COMPLETE`.
- **R check of the worker fix**: `dev/tools/test_patch.R` (needs base R only).
- **R check of the abx_cont fix**: `dev/tools/test_abx_cont.R`. It needs the ricu 0.6.0 sources (`git clone https://github.com/eth-mds/ricu`), YAIB-cohorts at `74ac699f`, and the packages rlang, vctrs, cli, data.table and assertthat. CRAN is blocked here, so they are built from `github.com/cran/<pkg>` with `R CMD INSTALL`. Paths and instructions are at the top of the script.

---

## 10. Message for Dr. Mohamed to paste into the new session

> I am continuing my sepsis V10.2 project. Read `HANDOVER_FOR_NEXT_CLAUDE.md` in repo `mahmoudddj/datasciencecoursera1`, branch `claude/happy-thompson-ngxbp8`, The real smoke run has finished on Colab. Lead me through Section 11: archiving the smoke outputs, moving to a high-memory cloud machine (Google Cloud preferred, AWS as an alternative), the timing test, and then full mode and the legacy validation. Explain each step in plain language, because I am not a cloud engineer. Save all outputs needed to write the paper exactly as described in its Section 8. I run the notebooks myself on Colab; ask me for tracebacks and log tails when something fails.


---

## 11. Full mode: moving off Colab to a high-memory cloud machine (you lead this)

### 11.1 Why
Measured on Colab in the smoke run:
- About **7 minutes per label batch** of 64 stays (eICU batches 6–13, from Drive timestamps).
- The whole smoke run took about 10 h. Some of that was avoidable: an unnecessary full eICU ricu re-import caused by `FORCE_RICU_REIMPORT=True`.

Full mode has about 94,458 MIMIC and about 200,859 eICU candidate stays. At 64 per batch that is about 4,600 label batches **plus** the same number of cohort batches, so **hundreds of hours. Not workable on Colab.**

Most of the 7 minutes is probably fixed cost per batch rather than per patient. **This is a hypothesis: verify it with the timing test (11.4).** The likely fixed costs:
- starting R and renv,
- parsing the concept dictionary,
- ricu scanning the large partitioned `.fst` tables (chartevents, vitalPeriodic, …) to pick out 64 patients,
- doing all of that through the **Google Drive FUSE mount**, which is slow for large files.

The batch size of 64 exists only because of Colab's RAM (`COHORT_BATCH_STAYS`, the RAM watchdog in `v9_runtime.py`). With 128–256 GB of RAM and local SSD, batches can be much larger.

### 11.2 Recommendation: Google Cloud first, AWS second
Both work. The notebook runs on any x86-64 Linux machine; it was tested outside Colab:
- `RUNTIME_ROOT` becomes `PROJECT/runtime` when Drive is not mounted.
- Paths can be set through `SEPSIS_PROJECT_ROOT`, `SEPSIS_MIMIC_ROOT` and `SEPSIS_EICU_ROOT`.
- The conda R 4.2.2 / Python 3.10 environment is built by `v9_environment_setup.py`.

**Google Cloud is the smaller step for this user:**
- same Google account and billing,
- the data is already on Google Drive,
- Colab can connect to a rented Compute Engine VM, so the Colab interface the user knows stays the same.

Check the current Colab menu wording: "Connect to a custom GCE VM" (paid Colab plans), or use Colab Enterprise / Vertex AI Workbench. **AWS** is equally capable, but needs a new account, plain Jupyter over an SSH tunnel, and copying the data out of Drive.

Prices below are approximate on-demand list prices. **Always confirm in the provider's pricing calculator with the user before creating anything.**

| Stage | Google Cloud | AWS | RAM / GPU | ≈ price |
|---|---|---|---|---|
| Labels + raw stage + features | `n2-highmem-16` / `n2-highmem-32` | `r6i.4xlarge` / `r6i.8xlarge` | 128 / 256 GB | ≈ $1 / $2 per h |
| Neural training (8 arms, 3 seeds) | `g2-standard-8` (L4 24 GB) | `g5.xlarge` (A10G 24 GB) | 24 GB GPU | ≈ $1 per h |
| Disk | pd-ssd / pd-balanced 500 GB | gp3 500 GB | — | ≈ $40–85 per month |

Use the CPU machine for extraction, then stop it and attach the same disk to a GPU machine for training. Or use one GPU machine with enough RAM. Spot/preemptible machines are cheaper, but they can be stopped at any time. Batch-level resume makes that tolerable for extraction; use on-demand for anything that is not resumable.

### 11.3 Setup steps (the user runs them; you explain each in plain language)
1. **Data agreement and security.** PhysioNet credentialed data may be used on commercial cloud if kept secure. The user must check the wording of their DUA. Rules:
   - private VM, no public buckets or disks,
   - firewall closed except SSH,
   - Jupyter reached only through an SSH tunnel or the Colab/Workbench connector, never an open port,
   - disk encrypted (the default on both clouds),
   - no other users.
2. **Budget guardrail.** Before anything else, create a budget alert (for example $100 and $300). Teach the user to **stop the VM when it is idle**. A stopped VM still bills for its disk.
3. **Create the machine.**
   - Ubuntu 22.04 LTS, x86-64, 16 or 32 vCPU / 128 or 256 GB.
   - 500 GB SSD boot or data disk, in a region close to the user.
   - Google Cloud: either connect Colab to it, or install JupyterLab and tunnel (`gcloud compute ssh VM -- -L 8888:localhost:8888`).
   - AWS: `ssh -i key.pem -L 8888:localhost:8888 ubuntu@host`.
4. **Put the data on the machine's local disk**, not on a Drive mount. Option (a) is better.
   - (a) PhysioNet's own cloud access for credentialed users: MIMIC-IV and eICU are offered on Google Cloud and AWS after linking the cloud account on PhysioNet. Check the dataset pages for the current method.
   - (b) Copy from Drive with `rclone` (configured with the user's Google login) or `gdown`.
   - Then verify sizes with the per-file audit (Section 4 cell). It also catches demo copies, see error #2.
5. **Copy the project folder** `sepsis_colab_project` to local disk. That includes `ricu_import_status_v9`, the ricu `.fst` files under the raw folders, and the logs. **Reusing the ricu import saves hours.**
   - Caution: the import markers and the cohort key contain raw-file fingerprints, which include modification time. A copy that changes mtimes looks like "changed tables", and the import step then stops and asks for consent.
   - Preserve times when copying (`rclone copy` keeps modtimes by default; `rsync -t`). Otherwise accept one re-import (`ALLOW_FULL_RAW_IMPORT=True`), which is hours, not days, on a big machine.
6. **Point Section 1 at local paths.** Set `PROJECT_PATH` and `RAW_SOURCE_PATHS` (or the `SEPSIS_*` environment variables). Keep:
   - `FORCE_RICU_REIMPORT=False`
   - `FORCE_YAIB_REEXTRACT=False`
   - `RELEASE_FINAL_HOLDOUT=False`
7. **At the end of each stage, copy the outputs back to Drive** and make the dated read-only archive (Section 8).

### 11.4 Timing test before committing to full mode (code work for you)
1. **Notebook to use.** Full mode creates a new cohort key anyway (`candidate_n=None`), so smoke labels are not reused. That makes it the right time to switch to the **repo notebook**, whose worker has the units fix (`13a2d99e…`), **plus cell 4c**. Rebuild from `dev/`, rerun the fixture tests (141 + 49 checks), commit, then give the user the new notebook.
2. **Add the batch-size settings.** Add `FULL_COHORT_BATCH_STAYS` (and the RAM-watchdog threshold) to Section 1. The batch plan signature already includes the batch size, so plans never mix.
3. **Run the test** on the cloud machine. Use smoke mode with a temporary `SMOKE_STAYS_PER_DATASET` of about 3000 (a new key; disposable) and batch sizes 64, 500 and 1500. Record for each:
   - minutes per batch,
   - peak RAM (`free -g`, or the watchdog log),
   - the label counts.
4. **Extrapolate** the full-mode time and cost and present them to the user. Options if it is still too slow:
   - (i) parallel batch processes, which is a code change (a process pool in `extract_cohort_batched`, RAM-bounded) and must keep the per-batch markers;
   - (ii) one YAIB run per database without batching, if RAM allows;
   - (iii) a **prespecified random sample** (for example 20,000 stays per database). That is the user's scientific decision. Write it into `run_protocol.json` and the paper **before** any full-mode results are seen.
5. **The raw-table stage and features** (Section 5, DuckDB) also scan whole CSVs once per database. On local SSD with `DUCKDB_MEMORY` raised (for example to 64 GB) this should take tens of minutes, not hours. Measure it in the same test.

### 11.5 Then full mode
1. The user fills in `PRIOR_TEST_EXPOSURE`, sets `RUN_MODE='full'`, and keeps `RELEASE_FINAL_HOLDOUT=False`.
2. Extraction runs on the high-memory machine. Training runs on the GPU machine: same disk, rerun from the top; completed stages are reused through their markers.
3. Archive per Section 8 after every stage.
4. The final holdout evaluation runs once, only after the protocol is frozen.
5. Notebook B (legacy) can run on the same machine. It reuses the raw stage (`raw_stage_v10/<key>`).
