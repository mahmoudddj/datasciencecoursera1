# Sepsis V10.2 — MIMIC-IV and eICU (main development notebook)
**Prepared for Dr. Mahmoud Mohamed · `RUN_MODE='smoke'` by default · MIMIC-IV and eICU only**

Self-contained: all code is embedded below with SHA-256 checks; the original v8 OSTA/CNN sources, your handcrafted feature module and the pinned PhysioNet scorer are preserved byte-for-byte. Nothing in training or inference calls a language-model API.

**What the saved outputs are.** The cell outputs in this file come from a *synthetic-fixture* engineering run executed through a real Jupyter kernel (Python 3.12, CPU). They prove the code paths run; they contain **no clinical data and no clinical performance**. Real MIMIC-IV/eICU extraction, the R/ricu label workers, Colab resource use and full training have **not** been run by the preparer.

**Where to set things (Section 1):** `PROJECT_PATH` (project folder; default `MyDrive/sepsis_colab_project` in Colab), `RAW_SOURCE_PATHS['miiv']` (parent of `hosp/` and `icu/`) and `RAW_SOURCE_PATHS['eicu']` (folder with `patient.csv.gz`). Optional: `REUSE_COHORT_ROOT` for an existing v9 cohort. `PRIOR_TEST_EXPOSURE` must be filled in before full mode.

**One-time prerequisite.** If ricu imports or YAIB cohorts are missing, the notebook stops *before* any heavy setup. Setting `ALLOW_FULL_RAW_IMPORT=True` authorises the whole-table ricu import (a large one-off job that smoke mode cannot make small). Completed imports, label batches, raw-table stages, feature batches, epochs and arms are all reused. Keep `FORCE_RICU_REIMPORT=False` and `FORCE_YAIB_REEXTRACT=False`.

**Resume.** Rerun from the top with unchanged settings after any interruption. Completion markers: `validation_v10/runs/<RUN_KEY>/COMPLETE.json` (whole run) and `.../<feature_set>/<target>/seed_<s>/<arm>/completed.json` (each arm).
