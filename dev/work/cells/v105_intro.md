# Early sepsis warning in the ICU: MIMIC-IV and eICU (notebook `_10`, V10.5)
**Prepared for Dr. Mahmoud Mohamed and team · 19 Oct 2026 · interim validation run (development data only; the final test set stays sealed)**

## 1. The clinical question
Every hour of an ICU stay, can a model warn that a patient will meet **Sepsis-3 criteria within the next 6 hours**, early enough to act, with few false alarms?
- **Sepsis onset** is the Sepsis-3 definition as implemented by YAIB/ricu (`sep3_alt`): suspected infection plus an acute SOFA rise of ≥ 2.
  - MIMIC-IV: suspected infection = antibiotics + cultures.
  - eICU: antibiotics only.
- **Target:** at each hour, "onset occurs within the next 6 h". Hours after onset are never used for training or for incident-risk metrics. They are kept only so the official PhysioNet utility score can be computed.
- **Strict causality:** every value enters the model only from the hour it was *recorded and available* (lab result time, chart store time), never from when it was measured. Each feature also carries "observed?" and "how old?" channels.

## 2. Data in this run
- MIMIC-IV 3.1 (Boston, 1 hospital) and eICU-CRD 2.0 (US, 208 hospitals).
- The **same prespecified random samples** as runs `_8` and `_9`: 10,000 candidate ICU stays per database.
  - After YAIB exclusions: about 7,000 MIMIC and 4,400 eICU development stays.
  - About 350 and 230 of them develop sepsis in a predictable window.
- 20% of patients are sealed in a **final holdout** that no run has ever opened.
- Because `_8`, `_9` and `_10` use the same patients and splits, differences between them are caused only by the features and the training loss.

## 3. What is new in `_10`: every predictor that could forecast sepsis
655 model inputs: about 300 clinical features plus their "measured?" masks and "how old?" ages. Full list in the next section.
- **Vital signs and monitoring:**
  - vitals, with trends, variability and 24 h extremes;
  - CVP, PA pressure, cardiac output, ScvO₂;
  - ventilator settings, oxygen flow, high-flow oxygen and NIV;
  - P/F and S/F ratios.
- **Laboratory:** about 60 blood and urine tests (including procalcitonin, lactate, the white-cell differential, BNP, D-dimer, urinalysis), plus the change from the previous and from the baseline value, and KDIGO AKI stage.
- **Bedside assessment:** GCS (an intubated verbal score is kept unknown, never imputed), RASS, CAM-ICU delirium, pain, capillary refill, skin mottling, atrial fibrillation.
- **Clinical scores:** full SOFA (all six organs) and ΔSOFA, qSOFA, SIRS, NEWS2.
- **Treatments and exposures:**
  - vasopressor dose (norepinephrine equivalent);
  - fluids and transfusions;
  - devices: central, arterial and dialysis lines, urinary catheter, drains, endotracheal tube/tracheostomy;
  - dialysis;
  - nutrition;
  - immunosuppressants, chemotherapy, steroids and other key medications;
  - imaging orders.
- **Background:** 17 chronic comorbidities, admission source and ICU type, time in hospital and in ICU, previous admissions, earlier positive cultures and antibiotics, eICU admitting diagnosis.
- **Not used as predictors, by design:**
  - antibiotics and cultures of the current admission (they *define* the sepsis label; using them would leak it);
  - race/ethnicity and insurance (kept for fairness analysis only);
  - code status;
  - clinical notes (a separate later phase).

## 4. Models compared (same patients, same hours, same budget)
1. **OSTA**: the organ-system attention transformer, trained with its **original loss** (focal, time-weighted, organ terms). Plain cross-entropy is reported alongside.
2. Three ways of adding organ "observer" information:
   - observer features as inputs;
   - output fusion;
   - gated or ungated attention guidance.
3. **CNN–Transformer.**
4. **Logistic regression** and **gradient-boosted trees** (strong classical baselines).
5. **Controls:**
   - raw values only versus the full feature set;
   - an extra-label-budget version of OSTA.

## 5. How performance is judged (principal panel)
- PhysioNet 2019 **normalized utility**.
- **AUPRC** and **AUROC**.
- **Sepsis cases caught** at a fixed burden of ≤ 0.5 false alarms per patient-day.
- **Median warning time** before onset.
- **False alarms per patient-day.**
- **Calibration and Brier score.**

All come with patient-level bootstrap 95% CIs. Thresholds are set on a separate calibration split and applied unchanged to the test split.

## 6. What this run is (and is not)
- **Is:** the check that every new data source fills in correctly on the real databases, and a like-for-like comparison with `_8`/`_9`.
- **Is not:** the final result.
  - With about 175 septic training stays, models with many inputs overfit quickly; we saw this in `_9`.
  - The **full cohort** (about 94,000 MIMIC and 200,000 eICU stays, 3 seeds) is the definitive run that follows.
- Nothing here is used to pick a winner on the test data. The final holdout stays sealed.

## 7. How to run
1. Colab with an A100 GPU and high RAM. **Runtime → Run all.** Do not change settings.
2. The first output must read `Mode: full | data: clinical | full holdout released: False`.
3. Expect **about 8–10 hours**.
   - Section 5 (raw-table scan and hourly features, about 2–3 h) is the step that exercises the new extraction. If an error appears there, copy it to Claude.
   - Then training prints `Completed <database> <feature set> <time>` lines.
4. At the end, `COMPLETE: …` appears. Download this notebook and collect the audit files: coverage, extraction counts, item dictionary, training histories and team summary.
5. If Colab disconnects, reopen and **Run all** again. Every finished stage (labels, raw scan, feature batches, each model) is reused.

## Technical notes
- **Self-contained:** all code is embedded below with SHA-256 checks. The original OSTA/CNN sources, your handcrafted feature module and the pinned PhysioNet scorer are preserved. Nothing calls an external AI service; patient data never leave your Colab/Drive.
- **Saved outputs:** the outputs stored in this file come from a *synthetic* engineering test (no patient data). Real results appear only when you run it.
- **Settings:** in Section 1. Paths default to `MyDrive/sepsis_colab_project`. Keep `FORCE_*=False` and `RELEASE_FINAL_HOLDOUT=False`.
- **Completion markers:**
  - whole run: `validation_v10/runs/<RUN_KEY>/COMPLETE.json`;
  - each model: `…/<feature set>/<database>/seed_<s>/<model>/completed.json`.
