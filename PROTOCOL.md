# Study protocol: early warning of sepsis that holds across hospital systems

**Candidate:** Mahmoud Essam Elrggal · **Second supervisor:** Dr Kia Dashtipour
**Protocol version:** v11-1.0 (the `protocol_v11` value written into every run's `run_protocol.json`)
**This document:** consolidated 19 Oct 2026 from the decisions recorded in the notebooks between 16 and 19 Oct 2026, before any result they govern existed. Its git commit is its timestamp. Departures are recorded in `PROTOCOL_DEVIATIONS.md`, never by editing this file silently. Items marked **TO FREEZE** must be fixed and committed here before the full-cohort run starts.

---

## 1. Question

Using only what a clinician could have known at each hour, can a model warn of sepsis hours before onset with positive clinical utility, and does that utility hold in a hospital system the model has never seen?

- **RQ1, predictors.** Which clinically defined predictors carry signal without leaking the label or the clinician's own suspicion?
- **RQ2, architecture.** Does organ-system structure, or self-supervised pretraining, improve utility over simpler sequence models and the published competition winner's method?
- **RQ3, transfer and trust.** Does utility survive transfer between two hospital systems, and would intensive-care and infectious-disease consultants act on the alarm?

## 2. Design

Mixed methods, in three phases.

| Phase | What | Status |
|---|---|---|
| 1. Quantitative, retrospective | Model development and evaluation on two open ICU databases (this protocol) | Stage 1 complete on MIMIC-IV; eICU running |
| 2. Qualitative | Online interviews and round-table discussions with 20 infectious-disease and critical-care consultants from different hospitals, on trust, alarm burden and action thresholds | In progress; described in its own protocol |
| 3. Prospective (future) | Silent test on hospital patients: live scoring, alerts logged but not shown, compared with outcomes | Needs separate ethics, data-governance and hospital agreements |

Phase 1 runs in two stages:

- **Stage 1, comparison:** a prespecified comparison on a fixed random sample of 10,000 candidate stays per database, with one seed. Rules fixed in advance choose the models and the loss.
- **Stage 2, full cohort:** the shortlisted models on all eligible stays, with three seeds. The sealed holdout is opened once at the end.

## 3. Data

| Source | Version | Role |
|---|---|---|
| MIMIC-IV | 3.1 (Beth Israel Deaconess, Boston; ~94,000 ICU stays) | Development and transfer target |
| eICU-CRD | 2.0 (208 US hospitals; 200,859 unit stays) | Development and transfer target; leave-hospital-out in stage 2 |
| PhysioNet/CinC Challenge 2019 | public training set (40,336 stays) | Historical comparison only (leakage audit, causal rebuild of the earlier models) |

**Governance:**

- All access is credentialed under the PhysioNet data use agreements.
- Patient-level data stay in the candidate's Google Drive and Colab runtime.
- No patient-level data are sent to any external service, AI services included; only aggregate results leave the runtime.

## 4. Cohort, label and prediction target

- **Label:** Sepsis-3 onset as implemented by the YAIB benchmark (`sep3_alt`, through the pinned `ricu` code). Onset is the time of suspected infection paired with a SOFA increase of 2 or more.
- **Suspected infection:** antibiotics with cultures in MIMIC-IV; antibiotics only in eICU, which records no cultures in the same form.
- **Cohort:** the YAIB sepsis cohort definition and exclusions, unchanged.
- **Stage 1 sample:** 10,000 candidate stays per database, drawn at random (seed 42). The sample was prespecified on 16 Oct 2026, and the same samples and splits were used from `_8` to `_11`.
- **Target:** at every hour, will sepsis onset occur within the next 6 hours?
- **Scored hours:** the first 120 hours of each stay. Step labels start at onset minus 6 h. An onset after the 120-hour window counts as non-septic.
- **Post-onset hours:** scored by the utility function, as the official scorer does. They enter training only through the utility-weighted loss (Section 7).

## 5. Splits and the sealed holdout

1. **Protected holdout (20 % of patients):** a patient is protected if `sha256('sepsis-final-v1|' + patient id) mod 5 == 0`.
   - The rule does not depend on outcomes and was fixed before any model existed.
   - Protected patients are excluded from every development step, including the unlabelled pretraining corpus.
2. **Development patients** are split by patient, never by stay or hour, and stratified by whether the patient has a sepsis event:
   - **Test:** 20 % of development patients.
   - **Training pool:** the remaining 80 %, divided as:
     - training, 60 % of the pool;
     - observer-fit, 20 % (trains the small per-organ observer models used by output fusion; also used with training to fit input normalisation);
     - validation, 10 %;
     - calibration, 10 %.

   An assertion stops the run if any patient appears in two splits.
3. **Final evaluation:**
   - The holdout is opened once, after this protocol is frozen, with `RELEASE_FINAL_HOLDOUT=True`.
   - Any prior exposure to test data is declared in `PRIOR_TEST_EXPOSURE` before release.
   - Each database's protected patients are scored by models trained on the **other** database's development patients (cross-database test).

## 6. Predictors

There are 655 predictors, including a "measured?" mask and a "how old?" age (in days) for each measured channel.

**Causality:**

- Every value is used only from the hour it was charted, or, for results, when it became available.
- Values are carried forward with their age, never interpolated from the future.
- Every neural architecture passes a future-perturbation test: changing future inputs cannot change past outputs.

**Classes:**

- vital signs and laboratory values, with deltas from the previous value and from baseline;
- full SOFA and its components, with change from the best value so far;
- KDIGO acute kidney injury stage (48-hour creatinine window);
- vasopressor noradrenaline-equivalent dose;
- ventilation and oxygen therapy (including high-flow and non-invasive), sedation and delirium scores;
- urine output rate and fluid balance;
- devices and procedures (renal replacement, bronchoscopy, drains), nutrition, and selected drug exposures (proton-pump inhibitors, insulin, anticoagulants);
- comorbidities;
- admission context: prior admissions, prior ICU stays in the same admission, admission source, and, in MIMIC-IV only, positive cultures and antibiotics from earlier admissions, strictly before the current one;
- NEWS2;
- prophylactic antibiotics (MIMIC-IV only), surgical and medical, by guideline rule:
  - **Surgical:** a prophylaxis agent with perioperative timing, given for 24 h or less (48 h after cardiac surgery), with no culture in the Seymour window (72 h before to 24 h after) and no escalation within 72 h.
  - **Medical:** the agent and dose pattern of PJP, SBP, neutropenia or transplant prophylaxis.

**Never used as predictors:**

- empirical or culture-directed antibiotics and cultures of the current admission (they define the label);
- race, ethnicity and insurance (subgroup fairness analysis only);
- code status;
- clinical notes (a separate later phase).

**Sensitivity sets:**

- **raw:** core vital signs and laboratory values only;
- **no proxies:** without hydrocortisone, imaging orders and prophylaxis, which reflect the clinician's suspicion.

## 7. Models

All models are scored on identical hours and splits.

| Group | Model | What it is |
|---|---|---|
| Baselines | Logistic regression | Linear model on the hourly predictor vector |
| | Boosted trees | Histogram gradient boosting (learning rate 0.05, 31 leaves, L2 1.0) with patient-grouped early stopping on validation, up to 1,000 iterations |
| Literature benchmark | Signature boosted trees | The PhysioNet 2019 winner's method (path-signature features + gradient boosting), rebuilt in this pipeline |
| Earlier models of this PhD | OSTA-Transformer | Organ-system-aware temporal attention: predictors grouped by organ system, per-organ encoders, cross-organ attention, per-organ risk |
| | Output fusion | OSTA plus a bank of small per-organ-group observer networks (trained on the separate observer-fit split), whose risk estimates are added to OSTA's output through a learned linear layer |
| | CNN–Transformer | Convolutional front end followed by a transformer |
| New supervised | Flat OSTA | OSTA with all predictors in one group: the organ-structure ablation |
| | GRU-D | Recurrent network with learned decay towards the mean as measurements age |
| | TCN | Causal dilated temporal convolution network |
| | CNN→OSTA | Per-channel causal CNN encoder over value, mask and age, then an OSTA head |
| | Event OSTA | Attention from each hour to fresh observations of the fast vital-sign channels within 24 h, then an OSTA head |
| Self-supervised | SSL-CNN→OSTA / →flat | The same per-channel encoder pretrained without labels, then an OSTA head or a flat head |
| | Pooled twins | The same, with an encoder pretrained on both databases (reported as adaptation) |
| | Hazard SSL-CNN→OSTA | Discrete-time survival head (1, 3, 6, 12, 24 h); the 6-hour risk is 1 − S(6 h) |
| Secondary | Mean ensemble | Unweighted mean of OSTA, CNN–Transformer and SSL-CNN→OSTA |

**Self-supervised pretraining:**

- **Corpus:** stays not in the labelled cohort, protected patients excluded, capped at 75,000 per database. No label of any kind is read.
- **Tasks:**
  - the next fresh value of each channel;
  - whether each channel is measured within 6 h;
  - the six SOFA components at +6, +12 and +24 h;
  - any SOFA worsening within 6, 12 and 24 h.
- **Length:** 5 epochs.

Retired after stage-1 predecessors (`_8`, `_9`): the observer outputs used as input features (observer features) or as gates on OSTA's cross-organ attention (gated and ungated attention), the 80 %-label control, and the original OSTA loss.

## 8. Losses and training

- **Primary loss, utility-weighted binary cross-entropy:**
  - Each positive hour is weighted by the PhysioNet reward gap (1.0 at 6 h before onset rising to 2.0 at 3 h after), normalised to mean 1.
  - The three hours after onset are added as weighted training positives.
  - Evaluation hours are unchanged.
- **Comparator losses** (OSTA and SSL-CNN→OSTA only): plain binary cross-entropy, and temporal label smoothing (Yèche et al. 2023; linear ramp, τ = 12 h).
- **Neural training:**
  - AdamW, learning rate 3e-4, weight decay 1e-4;
  - dropout 0.2, batch 32, up to 30 epochs;
  - early stopping on validation AUPRC with patience 5.
- **Seeds:** stage 1 uses one seed (42); stage 2 uses three (42, 7, 123).

## 9. Evaluation

**Primary measure:** PhysioNet 2019 normalised utility, computed with the official scorer (unchanged).

- The alarm fires when calibrated risk is at or above a threshold.
- The threshold is the first maximum of a utility sweep on the **calibration** split, then applied once to test.

**Principal panel** (all with patient-cluster bootstrap 95 % CIs, 200 resamples):

- hourly AUROC and AUPRC;
- sensitivity for sepsis events at a budget of 0.5 false alarms per patient-day (6 h alarm cooldown);
- median warning time before onset;
- false alarms per patient-day;
- calibration: Platt scaling fitted on the calibration split, Brier score, ECE and calibration slope.

**Additional analyses:**

- **Lead time against the first antibiotic order:** both databases; evaluation metadata only, never a predictor.
- **Transfer rows:** each database's model scored on the other database's development patients. The holdout stays sealed.
- **Conformal secondary alarm policy:** abstention on out-of-distribution hours, with a distribution-free hourly false-positive bound (α = 0.02).
- **Trajectory-rich subset:** hours with dense monitoring.
- **Data-stress conditions** (OSTA-family arms): missing all, missing half, incorrect, conflicting, 6 h stale, 2 h delayed.
- **Paired bootstrap differences** against OSTA for every arm.
- **Sensitivity analyses:** the raw and no-proxy feature sets.

Test results are reported for every arm. They are never used to choose anything (see `PROTOCOL_DEVIATIONS.md` for the one declared exception).

## 10. Decision rules (fixed before any stage-1 result)

All rules use the **validation** split only. The ranking statistic is the rank-average of validation utility and validation AUPRC.

| Rule | Decision |
|---|---|
| Loss | The loss with the best rank-average among the three is used in stage 2 |
| Organ structure | OSTA's organ structure is kept only if OSTA ranks above flat OSTA |
| Shortlist | The top 2–3 new arms go to stage 2, with OSTA, CNN–Transformer, boosted trees and logistic regression |

**Stage-1 outcome on MIMIC-IV** (run `4cd752bef2ccbd42`; development split; preliminary):

| Rule | Outcome |
|---|---|
| Organ structure | Not supported (validation utility: flat OSTA 0.283, OSTA 0.117) |
| Loss | No single winner. Plain cross-entropy ranked first for OSTA, utility-weighted for SSL-CNN→OSTA, and temporal label smoothing last for both. **TO FREEZE:** the stage-2 loss, decided by the same rule once eICU is complete |
| Shortlist | GRU-D, TCN and flat OSTA |
| Declared deviation D1 | SSL-CNN→OSTA and SSL-CNN→flat added as an exploratory pair |

**Stage-1 outcome on eICU:** pending (run in progress).

## 11. Stage 2, full cohort

- **Data:** all eligible stays in both databases (`FULL_SAMPLE_STAYS_PER_DATASET=None`); the same split rules; three seeds.
- **Arms (TO FREEZE):**
  - the union of the MIMIC-IV and eICU shortlists;
  - OSTA, CNN–Transformer, boosted trees and logistic regression;
  - the signature boosted trees benchmark;
  - the D1 pair, labelled exploratory.
- **Loss (TO FREEZE):** decided by Section 10 across both databases.
- **Pretraining corpus (TO FREEZE):**
  - non-cohort stays plus training-split stays (inputs only, no labels);
  - excluding every stay of a validation, test or protected patient.
- **eICU leave-hospital-out evaluation** (TO FREEZE: hospital grouping and the minimum events per hospital).
- **Then:**
  1. freeze this protocol (commit);
  2. declare `PRIOR_TEST_EXPOSURE`;
  3. open the holdout once;
  4. report every prespecified arm and analysis, whatever its result.

## 12. Reproducibility

- Each notebook embeds its code with SHA-256 checks and runs with **Run all** only. No manual edits between runs.
- Every stage is cached under a key built from code, data and configuration: `RAW_STAGE_KEY`, `SUPP_KEY`, `DATA_KEY`, `SSL_KEY` and `RUN_KEY`. A changed input produces a new key; nothing stale is reused. `FORCE_*` settings stay False.
- Each arm writes `completed.json`. Every run writes `run_protocol.json` with the configuration, the feature list and the rules above.
- Engineering self-tests run before training. Stage 1 `_11` has 212 checks, including causality, split leakage and scorer agreement.
- A synthetic fixture run must pass before any notebook is released.

## 13. Version history (short)

| Version | Change |
|---|---|
| V8–V9 | Leakage audit of the earlier pipeline; earlier OSTA and CNN–Transformer results retired; causal rebuild on PhysioNet 2019 (OSTA utility 0.22) |
| V10.3–V10.5 | Raw-table extraction for MIMIC-IV and eICU, one label, extraction audit, 655 predictors |
| V11 (this protocol) | Prophylaxis predictors, self-supervised pretraining, new architectures, loss comparison, transfer rows, conformal policy; raw-stage query fix (v10.6) and AKI window fix |
