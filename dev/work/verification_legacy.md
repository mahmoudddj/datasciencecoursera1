## Verification record (preparation, 2026-10-14)

| Check | Result | Evidence |
|---|---|---|
| Embedded code checksums; original OSTA/CNN sources byte-identical to the ZIP; scorer identical to GitHub commit `467c49b` | PASS | re-hashed |
| Top-to-bottom execution through a real Jupyter kernel, fresh process, fixture mode, two library stacks | PASS | see main notebook record |
| 49 legacy checks (`legacy_engineering.json`) | PASS | both archived utility functions = official scorer on 45 trajectories incl. edge cases; normalised utility = original; single 6 h label shift; persistence not backdated; early/late alarm classes; exact original normalisation incl. inf handling; source representation detection; adapter TTL stripping (float32-safe) and forward-fill reproduction; unsupported channels kept missing; feature-order generator; frozen prefix invariance; BatchNorm preserved; **import of original-format checkpoints + cache scaler + sweep threshold reproduces the original scripts' preprocessing→normalisation→ensemble output to 1e-5**; policy-mismatch and tampered-weight refusal; full-size original architectures forward/backward with the original losses; clinical-path dry run on schema-shaped raw MIMIC/eICU CSVs (onset, HospAdmTime, discharge follow-up, early-onset exclusion, sealed protected patients, raw-stage reuse identical) |
| Source reproduction (smoke) → reload without retraining → target scoring, both arms, both fixture targets | PASS | 2 epochs, tiny models |
| Kernel killed during source training, rerun | PASS | member weights and all results identical |
| Historical PhysioNet-trained weights / scalers / sweeps | **UNAVAILABLE** | the ZIP contains code only |
| Real PhysioNet source, real MIMIC/eICU targets, full reproduction | **NOT RUN** | data not available to the preparer |
