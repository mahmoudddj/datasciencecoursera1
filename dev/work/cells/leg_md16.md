## 8. Finish, resume and full mode
Completion marker: `legacy_validation_v10/runs/<key>/COMPLETE.json` with `legacy_results.csv`, per-arm predictions/alarms/calibration and `paired_comparisons.csv`. Source reproductions checkpoint every epoch (`last_seed*.pt`) and per seed (`member_seed*.done.json`); target trajectories resume per chunk. Rerun from the top with unchanged settings to resume.

Full mode: set `RUN_MODE='full'`, fill `PRIOR_TEST_EXPOSURE`, and choose `LEGACY_MODE`. Smoke or synthetic bundles are refused in full mode. Final target holdouts additionally need `RELEASE_FINAL_HOLDOUT=True`. Run this notebook last, and do not redesign either model from its target results.
