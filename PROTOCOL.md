# Study protocol: early warning of sepsis that holds across hospital systems

**Candidate:** Mahmoud Essam Elrggal · **Director of Studies:** Prof. Ahmed Al Dubai · **Second supervisor:** Dr Kia Dashtipour
**Protocol version:** v11-1.0 (the `protocol_v11` value written into every run's `run_protocol.json`)

**About this document:**

- **Consolidated:** 19 Oct 2026, from the decisions recorded in the notebooks between 16 and 19 Oct 2026.
- **Checked against:** the code embedded in `Sepsis_V11_Improved_MIMIC_eICU_11_architectures.ipynb`. File and line references point to `dev/work/mods/` and `dev/work/cells/`.
- **Timestamp:** the git commit of this file.
- **Departures:** recorded in `PROTOCOL_DEVIATIONS.md`; this file is never edited silently.
- **TO FREEZE:** items so marked must be decided and committed here before the full-cohort run starts.
- **Status of results:** all results quoted here are preliminary development-split results; the sealed holdout has not been opened.

---

## 1. Question

Using only what a clinician could have known at each hour, can a model warn of sepsis hours before onset with positive clinical utility, and does that utility hold in a hospital system the model has never seen?

- **RQ1, predictors.** Which clinically defined predictors carry signal without leaking the label or the clinician's own suspicion?
- **RQ2, architecture.** Does organ-system structure, or self-supervised pretraining, improve utility over simpler sequence models and the published competition winner's method?
- **RQ3, transfer and trust.** Does utility survive transfer between two hospital systems, and would infectious-disease and critical-care consultants act on the alarm?

## 2. Design

Mixed methods, in three phases.

| Phase | What | Status |
|---|---|---|
| 1. Quantitative, retrospective | Model development and evaluation on open ICU databases (this protocol) | Stage 1 complete on MIMIC-IV; eICU running |
| 2. Qualitative | Online interviews and round-table discussions with 20 infectious-disease and critical-care consultants from different hospitals: trust, alarm burden, action thresholds | In progress; described in its own protocol |
| 3. Prospective (future) | Silent test on hospital patients: live scoring, alerts logged but not shown, compared with outcomes | Needs separate ethics, data-governance and hospital agreements |

Phase 1 runs in two stages:

- **Stage 1, comparison:** the prespecified comparison on a fixed random sample of 10,000 candidate stays per database, with one seed. Rules fixed in advance choose the models and the loss for stage 2.
- **Stage 2, full cohort:** the chosen models on all eligible stays, with three seeds. The sealed holdout is opened once at the end.

**Prior exposure:** development test-split results have been viewed repeatedly during development (runs `_6` to `_11`; Section 14). The development test split is therefore not an untouched test. The unbiased estimate is the sealed holdout. Every run in full mode records this in `PRIOR_TEST_EXPOSURE`.

## 3. Data

| Source | Version | Role |
|---|---|---|
| MIMIC-IV | 3.1 (Beth Israel Deaconess Medical Center, Boston) | Development; transfer target |
| eICU-CRD | 2.0 (208 US hospitals) | Development; transfer target; leave-hospital-out in stage 2 |
| PhysioNet/CinC Challenge 2019 | Public training set (hospital systems A and B; a third, C, was hidden) | Earlier work and the causal OSTA baseline (Section 14); legacy external validation (Notebook B). Hospital system A is Beth Israel Deaconess, the MIMIC-IV hospital (Reyna et al. 2020), so the challenge data are not an external test for a MIMIC-IV-trained model and are not used as one |

**Governance:**

- Access is credentialed under the PhysioNet data use agreements.
- Patient-level data stay in the candidate's Google Drive and Colab runtime.
- No code sends patient-level data to any external service; only aggregate results leave the runtime.

## 4. Cohort, label and prediction target

**Label:**

- Sepsis-3 onset as implemented by the YAIB benchmark (`sep3_alt`), extracted with `ricu` through the embedded label worker (`v9_yaib_worker.py`, sha `3e5e87fd…`).
- The pinned YAIB `abx_cont` callback is patched for empty batches by notebook cell 4c (`cells/fix_4c_abx_cont.py`; pinned sha `f88c1007…` → `b42caa98…`).
- The repository copy of the worker carries a later interval-units fix that the `_11` notebook does not embed. It is unchanged so that the cohort key is kept; the run's logs showed the correct `1 hours` interval.

**Suspected infection:**

- MIMIC-IV: antibiotics paired with cultures.
- eICU: antibiotics only (`si_mode='abx'`).

**Cohort (YAIB exclusions, `pinned_yaib_sepsis.py:44-111`):** a stay is excluded for any of:

- invalid length of stay, or length of stay under 6 h;
- fewer than 4 hours with any measurement;
- a gap of more than 12 h between measurements;
- age under 18;
- sepsis onset less than 6 h after ICU admission;
- in eICU only, a hospital with zero sepsis prevalence (assessed within the sampled candidates).

YAIB ends a septic stay's follow-up at onset + 6 h and caps every stay at 7 days.

**Stage-1 sample:** 10,000 candidate stays per database, drawn at random with seed 42. The sample was prespecified on 16 Oct 2026 and is part of the cohort key; notebooks `_6` to `_11` use the same samples and splits.

**Hourly grid and target:**

- Hours run from 1 to min(120, follow-up).
- Hour *h* is positive if onset falls in (*h*, *h* + 6].
- An hour is **scored** if it is before onset and its 6-hour horizon is observed. Stays with no scored hour are dropped.
- Because the label looks 6 h ahead, a stay whose onset falls between 120 and 126 h has positive hours inside the window and counts as septic. A stay with a later onset counts as non-septic.
- Post-onset hours are kept in the data but are not scored hours. The utility function still scores them, as the official scorer does, and the primary loss uses the onset hour and the 3 hours after it (Section 8).

## 5. Splits and the sealed holdout

1. **Protected holdout (20 % of patients).** A patient is protected if `int(sha256('sepsis-final-v1|' + pid).hexdigest()[:8], 16) mod 5 == 0`.
   - `pid` is `'<miiv|eicu>|<subject_id or uniquepid>'` (`v10_protocol.py:8-9`).
   - The rule does not depend on outcomes and was fixed before any model existed.
   - Protected patients are excluded from every development step, including the unlabelled pretraining corpus.
2. **Development patients** are split by patient, never by stay or hour (`v10_protocol.py:53-82`). Stratification uses whether the patient has any stay with a positive scored hour.

   | Split | Share | Use |
   |---|---|---|
   | Test | 20 % of development patients | Reported for every arm; never used to choose |
   | Training | 60 % of the remaining pool | Model fitting |
   | Observer-fit | 20 % of the pool | Trains the frozen observer bank (Section 7); with training, fits input normalisation |
   | Validation | 10 % of the pool | Early stopping; the decision rules (Section 10) |
   | Calibration | 10 % of the pool | Platt scaling and both alarm thresholds |

   An assertion stops the run if any patient appears in two splits. Each split must contain both classes.
3. **Final evaluation** (`RELEASE_FINAL_HOLDOUT=True`, full mode only; smoke mode cannot release):
   - Models are trained on all development patients of one database, re-partitioned 60/20/10/10 as above.
   - They are tested on the **other** database's protected patients (cross-database test).
   - `PRIOR_TEST_EXPOSURE` must be non-empty before release.
   - **TO FREEZE: unlabelled data at final release.** As written, the "site" self-supervised encoder pretrains on the unlabelled stays of the *test* database in final mode (`v11_train.py:329`). These stays are non-protected and carry no labels, but this is unsupervised adaptation to the target hospital system. Before release, either keep it and declare it as transductive adaptation, or switch the site encoder to the training database's corpus.

## 6. Predictors

There are **659 predictors**: the V10.5 set of 655 plus the two prophylaxis features and their masks (`v9_data.py:41-42, 1166-1167`). Some are always missing in eICU because eICU does not record them: prophylaxis and the earlier-admission history. They include 257 "measured?" masks and 94 "how old?" age channels.

**Availability and causality** (`v9_data.py:383-457`):

- **When a value becomes usable:**
  - MIMIC-IV: at the later of its chart time and store time; a value with no store time is dropped.
  - eICU laboratory results: at the later of the result offset and the revision offset.
  - eICU nurse and respiratory charting: at the entry offset.
  - eICU monitor vital signs: at the observation offset.
- Values from up to 24 h before ICU admission are used.
- Every V11 neural architecture passes a future-perturbation test: changing future inputs cannot change past outputs.

**Carry-forward and expiry** (`v9_data.py:87, 937-1068, 1143`):

- Vital signs, laboratory values and charted states are carried forward for 24 h, then become missing.
- GCS and its components, weight and height never expire.
- An intubated patient's verbal GCS is reset to unknown.
- Vasopressor and inotrope flags need a record in the preceding hour.
- The noradrenaline-equivalent dose sums each drug's latest rate, up to 6 h old.
- After expiry the mask is 0 and the age channel keeps counting.

**Predictor classes:**

- **Vital signs and monitoring:** heart rate; cuff and arterial pressures; respiratory rate; oxygen saturation; temperature; end-tidal CO2; CVP; PA mean; cardiac output; ScvO2; ventilator settings (FiO2, PEEP, tidal and minute volume, peak and plateau pressure); oxygen flow; RASS; pain score.
- **Trend and extreme statistics:** for vital signs, the slope, variance, skew and count of fresh measurements over 3 and 6 h, and 24-hour extremes (`v10_features.py:53-62`).
- **Laboratory values:** chemistry, full blood count with differential, coagulation, lactate, blood gases, procalcitonin, troponin, BNP, ferritin, D-dimer, LDH, lipase, ammonia, amylase, ESR, and urine dipstick results.
- **Laboratory deltas:** for 12 laboratory values, the change from the previous result and from the first result in the stay. Unknown if the latest result is more than 48 h old (`v9_data.py:29, 1018-1030`).
- **Scores and derived values:**
  - full SOFA and its components, with change from the best value so far;
  - qSOFA, SIRS and NEWS2, counting criteria met among measured values;
  - shock index; P/F and S/F ratios; NLR; BMI; net fluid balance; ICU length of stay;
  - KDIGO stage. The 0.3 mg/dL creatinine rise uses a 48-hour window; the creatinine ratio uses the lowest value in the previous 7 days; the urine criterion gives stage 1 only; documented renal replacement gives stage 3 (`v9_data.py:1032-1050`).
- **Organ support and treatment:**
  - vasopressor dose (noradrenaline equivalents) and inotropes;
  - intubation and cumulative airway hours; high-flow oxygen and non-invasive ventilation;
  - renal replacement; bronchoscopy;
  - fluids and transfusion; parenteral and enteral nutrition;
  - drug classes, each recorded in the last 24 h: immunosuppressants, chemotherapy, corticosteroids, stress-dose hydrocortisone, beta-blockers, antipyretics, sedatives, opioids, diuretics, proton-pump inhibitors, insulin and anticoagulants.
- **Devices** (flagged from first documentation onward): central, arterial and dialysis lines; urinary catheters; drains.
- **Context and history:**
  - hours in hospital before ICU; admission source; ICU type;
  - prior ICU stays in the same admission;
  - the eICU admitting diagnosis (infection-related or operative).
  - **MIMIC-IV only** (missing in eICU): prior admissions in the last year; days since last discharge; admission from a nursing facility; positive cultures in the last year and antibiotics in the last 90 days, strictly before the current admission (`v9_data.py:741-828`).
  - **Comorbidities (17):** in MIMIC-IV from ICD codes of earlier admissions discharged before ICU entry; in eICU from past-history and diagnosis entries at their entry times.
- **Prophylactic antibiotics** (MIMIC-IV only; `v11_data.py:30-160`):
  - **Surgical:** a prophylaxis agent given between 8 h before and 1 h after a surgical timestamp, for 24 h or less (48 h if any cardiac or vascular surgical service is recorded in the admission). A once-daily order with no stop time also qualifies.
    - Surgical timestamps: OR, PACU, recovery and procedure transfers; surgical-service transfers; and hour 0 of any admission type containing "surgical".
  - **Medical:** pneumocystis, SBP, neutropenia or transplant prophylaxis by agent and dose pattern, including antifungal and antiviral agents.
  - **Both** also require no culture in the Seymour window (72 h before to 24 h after the dose) and no escalation within 72 h.

**Never used as predictors:**

- empirical or culture-directed antibiotics and the cultures of the current admission (they define the label);
- race, ethnicity and insurance;
- code status;
- clinical notes.

**Feature sets** (`main_14_v11.py`, `main_15_v11.py`):

| Set | Content | Arms |
|---|---|---|
| Rich (primary) | All 659 predictors | All arms |
| Raw | 267 columns: the 83 specified measurement channels plus GCS, weight, age, sex, vasopressor and inotrope flags and urine output, with masks and ages | OSTA, logistic regression, boosted trees |
| No proxies | The rich set without hydrocortisone, imaging orders and the two prophylaxis features (653 columns), which may encode the team's existing suspicion | OSTA only |

The eICU admitting-diagnosis features stay in the no-proxy set.

## 7. Models

All models are scored on identical hours and splits. Groups of predictors follow the feature registry, which assigns every predictor to one of 14 groups:

- the six SOFA organ systems: respiratory, cardiovascular, renal, hepatic, hematologic and neurologic;
- inflammatory, metabolic, systemic composite and demographic;
- infection risk, treatment, admission and comorbidity.

| Group | Model | What it is |
|---|---|---|
| Baselines | Logistic regression | L2 (C = 1, lbfgs, 1,000 iterations) on the hourly predictor vector |
| | Boosted trees | Histogram gradient boosting: learning rate 0.05, 31 leaves, L2 1.0. Up to 1,000 iterations, checked every 50 against validation AUPRC with patience 5, then refit at the best count |
| Literature benchmark | Signature boosted trees | The PhysioNet 2019 winner's approach. Depth-2 path signatures of time plus 7 fast vital signs over trailing 6- and 24-h windows, appended to all predictors, then the same boosted trees. Not LightGBM, and without the winner's full augmentations (`v11_train.py:80-109`) |
| Earlier models of this PhD | OSTA-Transformer | Per-group encoders (d 32) with temporal attention; cross-organ attention; a global transformer (d 128, 4 heads, 2 + 2 layers, causal). Output = global head + 0.3 × attention-weighted per-group risk logits |
| | Output fusion | OSTA plus the frozen observer bank (below), whose outputs are added to OSTA's logit through a bias-free linear layer |
| | CNN–Transformer | Multiscale causal CNN (dilations 1, 2, 4; LayerNorm) followed by a causal transformer (d 128, 2 layers) |
| New supervised | Flat OSTA | OSTA with all predictors in one group: the organ-structure ablation |
| | GRU-D | Recurrent network (hidden 128) with learned decay of carried values towards the mean as their age grows, and of the hidden state |
| | TCN | Causal dilated temporal convolution network: width 96, kernel 3, dilations 1 to 16 |
| | CNN→OSTA | Depthwise per-channel causal CNN over value, mask and age (kernel 3, dilations 1, 2, 4; 15-h receptive field; 2 latents per channel), concatenated with all predictors, then OSTA |
| | Event OSTA | Attention from each hour to fresh observations of 7 fast vital signs within a 24-h lookback (plus a sentinel key), then OSTA |
| Self-supervised | SSL-CNN→OSTA / →flat | The CNN→OSTA encoder pretrained without labels (below), then fine-tuned (not frozen) with an OSTA head or a flat head |
| | Pooled twins | The same, with the encoder pretrained on both databases' corpora; reported as adaptation |
| | Hazard SSL-CNN→OSTA | Discrete-time survival head (bins ending at 1, 3, 6, 12 and 24 h), trained by survival likelihood on all observed pre-onset hours and censored at the last observed hour. Reported 6-h risk = 1 − S(6 h). Ignores the loss setting (`v11_train.py:65-77`) |
| Secondary | Mean ensemble | Unweighted mean of the Platt-calibrated risks of OSTA, CNN–Transformer and SSL-CNN→OSTA (primary-loss runs). Thresholds re-chosen on calibration; no validation, transfer, conformal or stress rows |

**Observer bank** (`v9_models.py:52-104`, `v9_train.py:125-146`):

- Seven per-hour networks (one hidden layer of 32): respiratory, cardiovascular, hepatic, hematologic, renal, inflammatory and neurologic.
- Each reads all predictors of its group and is active only when one of its evidence channels is observed.
- They are trained with cross-entropy on the observer-fit split for 10 epochs and then frozen.
- Their outputs (logit × active, active, coverage × active) feed output fusion.

**Self-supervised pretraining** (`v11_train.py:112-181`, `v11_data.py:170-198`):

- **Corpus:** raw stays of at least 6 h that are not in the labelled sample and whose patient is not protected, randomly capped at 75,000 per database (seed 42). No label of any kind is read.
  - As implemented at stage 1, this includes YAIB-ineligible stays, stays outside the 10,000 sample, and other stays of validation and test patients. Stage 2 changes this (Section 11).
- **Tasks:**
  - the value of each channel at *t* + 1, scored where that channel is freshly measured at *t* + 1;
  - whether each channel is measured within 6 h;
  - the six SOFA components at +6, +12 and +24 h;
  - any SOFA worsening within 6, 12 and 24 h.
- **Losses:** smooth-L1 for the value and organ tasks; cross-entropy for the measurement and worsening tasks.
- **Training:** AdamW at 3e-4 for 5 epochs. Every tenth corpus stay is held out to choose the checkpoint. One encoder per target database and seed.

Retired after the earlier stages (Section 14): observer features, gated and ungated attention guidance, the 80 %-label control, and the original OSTA loss (still selectable in the code).

## 8. Losses and training

**Primary loss, utility-weighted binary cross-entropy** (`v11_train.py:42-57`):

- Positive hours are weighted by the PhysioNet reward gap, rising linearly from 1.0 at 6 h before onset to 2.0 at 3 h after.
- The onset hour and the 3 hours after it are added as weighted training positives (4 hours).
- Positive weights are normalised to mean 1 within each mini-batch.
- Evaluation hours are unchanged.

**Comparator losses** (OSTA and SSL-CNN→OSTA only):

- plain binary cross-entropy;
- one-sided temporal label smoothing (Yèche et al. 2023): positive hours stay at 1, and septic hours 6 to 18 h before onset get a soft target falling linearly from 0.5 to 0 (τ = 12 h).

**Neural training:**

- AdamW, learning rate 3e-4, weight decay 1e-4;
- dropout 0.2, batch 32, gradient-norm clip 1.0;
- up to 30 epochs, with early stopping on validation AUPRC (uncalibrated, scored hours) with patience 5; the best epoch is restored.

**Normalisation:**

- z-scores from all hours of the training and observer-fit stays;
- masks unscaled; ages divided by 24 (days);
- values clipped to ±20, and missing values set to 0.

**Seeds:** stage 1 uses one seed (42); stage 2 uses three (42, 7, 123).

## 9. Evaluation

**Calibration:**

- Platt scaling on up to 250,000 scored calibration hours. A non-positive fitted slope falls back to intercept-only recalibration (disclosure E1).
- Brier score and ECE (10 equal-width bins).
- Calibration slope and intercept from a diagnostic logistic refit on test.

**Two thresholds, both chosen on the calibration split:**

| Threshold | How it is chosen | What it drives |
|---|---|---|
| Utility threshold (`v10_train.py:123-133`) | First maximum of the normalised utility over 60 quantiles (50 % to 99.9 %) of calibrated risk on all calibration hours. The alarm fires every hour that risk is at or above it, with no cooldown | Normalised utility only |
| Budget threshold (`v9_train.py:252-261`) | Over 101 quantiles, the highest event sensitivity with at most 0.5 false alarms per patient-day (ties go to the higher threshold) | Every event metric: sensitivity, false alarms per patient-day, warning time, antibiotic lead time, trajectory-rich subset, transfer event metrics |

**Normalised utility:**

- Uses the official `compute_prediction_utility` (PhysioNet commit `467c49b`), run per stay on the first 120 h.
- Step labels start at onset − 6 h.
- Results are summed and normalised as (observed − no alarms) / (perfect − no alarms).

**Event metrics** (`v9_train.py:238-271`):

- Alarms have a 6-hour cooldown.
- An event is detected by an alarm 0 to 6 h before onset; every other alarm is a false alarm.
- Patient-days are counted from scored hours.
- Warning time is measured from the earliest timely alarm.

**Uncertainty:**

- Patient-cluster bootstrap 95 % intervals (200 resamples) for AUPRC, Brier score and normalised utility.
- Hospital-cluster intervals for AUPRC and Brier when there are at least 5 hospitals.
- Paired bootstrap differences against OSTA for AUPRC.
- AUROC and the event metrics are reported as point estimates.

**Additional analyses:**

- **Lead time against the first antibiotic:** the reference is the first systemic antibiotic within onset ± 24 h (evaluation metadata only). Lead = antibiotic time − first timely alarm. Also reported: the fraction of septic stays alarmed before the antibiotic.
- **Transfer rows:** all unprotected patients of the other database, scored with the source model's normaliser, Platt parameters and both thresholds. Patient- and hospital-cluster intervals.
- **Conformal secondary policy** (`v11_train.py:262-284`):
  - The out-of-distribution score of an hour is the fraction of its observed channels with |z| > 3.5.
  - Hours above the 98th percentile of calibration scores (α = 0.02) abstain, with risk set to 0.
  - The alarm threshold bounds the hourly false-positive rate on negative calibration hours at 0.5/24.
- **Trajectory-rich subset:** hours with at least 3 fresh measurements each of heart rate, MAP, respiratory rate and oxygen saturation in the previous 6 h, scored at the budget threshold.
- **Observer-stress conditions** (output fusion only): the observer-bank outputs are perturbed as missing all, missing half, incorrect, conflicting, 6 h stale and 2 h delayed (`v9_models.py:106-121`).
- **Sensitivity analyses:** the raw and no-proxy feature sets.
- **Secondary analysis notebook** (definitions fixed 17 Oct 2026):
  - bedside-score comparators on the same hours (qSOFA, SIRS, SOFA proxy);
  - onset-anchored AUROC at 6, 4 and 2 h;
  - patient-level AUROC;
  - seed ensemble.
- **Planned, not yet implemented (TO FREEZE before stage 2):**
  - subgroup fairness analysis by sex and age, and by race, ethnicity and insurance, which would be extracted for analysis only, never as predictors;
  - eICU leave-hospital-out evaluation.
  - paired patient-level bootstrap of the utility difference between arms, computed from the saved per-stay utilities (`utility_per_stay.parquet`). Until it is run, no arm is reported as better than another on utility; overlapping intervals do not settle the question either way.

Test results are reported for every arm and are never used to choose anything. The one declared exception is D1 in `PROTOCOL_DEVIATIONS.md`.

## 10. Decision rules (fixed before any stage-1 result)

**As implemented** (`team_summary_v11.py:26-34`):

1. Within each target database, every rich-feature arm is ranked on validation utility and on validation AUPRC, across all arms including baselines and loss variants.
2. The two ranks are averaged.

| Rule | Decision |
|---|---|
| Loss | For OSTA and SSL-CNN→OSTA, the loss variant with the best average rank. The stage-2 loss follows the rule across both databases |
| Organ structure | Kept only if OSTA's average rank is strictly better than flat OSTA's |
| Shortlist | The top three of the new arms (flat OSTA, GRU-D, TCN, CNN→OSTA, event OSTA, the self-supervised arms, the hazard arm and signature boosted trees), plus OSTA, CNN–Transformer, boosted trees and logistic regression |

**Stage-1 outcome on MIMIC-IV** (run `4cd752bef2ccbd42`; development split; preliminary):

| Item | Outcome |
|---|---|
| Organ structure | Not supported (validation utility: flat OSTA 0.283, OSTA 0.117) |
| Loss | No single winner on MIMIC-IV alone. Plain cross-entropy ranked first for OSTA, utility-weighted for SSL-CNN→OSTA, and temporal label smoothing last for both. See the cross-database reading below |
| Shortlist | GRU-D, TCN and flat OSTA |
| Test results (normalised utility) | All 21 arms above zero, with every 95 % interval above zero; range 0.08 to 0.29. OSTA 0.23 (0.13 to 0.34); signature boosted trees 0.15 (0.06 to 0.22) |
| Declared deviation D1 | SSL-CNN→OSTA and SSL-CNN→flat added as an exploratory pair |

**Stage-1 outcome on eICU** (same run, completed 22 Oct 2026; development split; 888 test stays, 45 events; preliminary; digest in `dev/results/run_4cd752bef2ccbd42_summary.md`):

| Item | Outcome |
|---|---|
| Organ structure | Not supported (validation rank: flat OSTA 2.5, OSTA 15.5; validation utility flat OSTA 0.039, OSTA 0.010) |
| Loss | Plain cross-entropy ranked first for both OSTA and SSL-CNN→OSTA; temporal label smoothing second; utility-weighted last |
| Shortlist | GRU-D, flat OSTA and SSL-CNN→flat (pooled encoder) |
| Test results (normalised utility) | Point estimates −0.001 to 0.075 (CNN–Transformer 0.075, GRU-D 0.066, TCN 0.043); upper 95 % limits up to 0.16; lower limits to be read from `team_summary_performance.csv` (the notebook display truncated the column). At the false-alarm budget OSTA, OSTA@bce and OSTA@tls raised no alarm. Hourly AUROC 0.53–0.68 |
| Transfer | MIMIC-IV models on eICU patients −0.03 to +0.04 (logistic −0.15), the same band as eICU's own models; eICU models on MIMIC-IV patients −0.00 to +0.03, most OSTA variants silent |
| D1 pair | Neither `ssl_cnn_osta` nor `ssl_cnn_flat` was chosen by the rule on eICU; D1 stands as written |

**Cross-database reading of the rules (for the stage-2 freeze):**

- Organ structure: not supported on either database. Flat OSTA goes forward; OSTA stays only as a fixed baseline.
- Loss: plain cross-entropy ranked first in three of the four comparisons and the utility-weighted loss in one; temporal label smoothing never ranked first. Reading the rule "across both databases" by rank average, the stage-2 loss is plain cross-entropy. **TO FREEZE:** the candidate confirms this reading (or records a deviation) before the full-cohort run.
- Shortlist union: GRU-D, TCN, flat OSTA, SSL-CNN→flat (pooled).

## 10b. Stage 1b: training recipe and alarm policy, decided on validation only (added 24 Oct 2026)

**Status and disclosure.** This section was written after the stage-1 development results of run `4cd752bef2ccbd42` had been seen (Section 10) and before any stage-1b code ran. It is therefore not blind to stage 1, and it says so. It is blind to the test splits: no test-split number is computed, displayed or read during stage 1b, and the sealed holdout stays sealed. Everything below is chosen on the training and validation splits of the two prespecified 10,000-stay samples, by rules fixed here.

**Why.** Stage 1 left three things undecided that stage 2 needs: (1) the project's own architecture, after the organ grouping was not supported on either database; (2) the alarm threshold, after an absolute probability threshold set on the calibration split left OSTA, OSTA@bce and OSTA@tls silent on the eICU test split (no alarm within the false-alarm budget); (3) the alarm policy, which the consultants' study will tune and which must exist before their answers can be used.

### 10b.1 What is tried (the complete list; nothing is added during the stage)

| Item | Options compared | Fixed settings |
|---|---|---|
| A. Backbone | `flat_osta` (reference) vs `flat_osta_heads`: the same flat backbone with fourteen organ heads at the output | d_global 128, 4 heads, 2 + 2 layers, dropout 0.2, batch 32, AdamW wd 1e-4, 30 epochs, early stopping on validation AUPRC (patience 5), seed 42, as in V11 |
| B. Organ heads | Seven heads, each a linear readout on the shared stay representation, trained jointly with the sepsis head on its own label-free target: for each of the six SOFA organs (respiration, coagulation, liver, cardiovascular, central nervous system, renal), whether that organ's SOFA component rises within 6, 12 and 24 h; and one "any organ" head for a rise in any component. These are the per-component form of the `worsen` target already built for self-supervised pretraining in `ssl_targets` (which currently reduces over components with `.any(-1)`; stage 1b keeps the per-component values). Auxiliary loss weight 0.2, fixed in advance and not tuned. Heads never feed back into the sepsis risk | The eight non-SOFA predictor groups of the V11 mapping get no head: they have no organ-failure target, and a head without its own target would be decoration |
| C. Input dropout | 0 (reference), 0.1, 0.2: each predictor's value, measured flag and age channels are hidden together with that probability during training only | Applied to both backbones; 2 × 3 = 6 trainings per database |
| D. Loss | Plain cross-entropy for every stage-1b training (Section 10 rule, three of four comparisons). No loss comparison in stage 1b | — |
| E. Operating point | Absolute threshold (as implemented in V11) vs **quantile operating point**: each threshold (budget and utility) is found on the calibration split exactly as before, then carried to any scored population as an alarm rate, not a probability: the fraction of calibration hours at or above the threshold is recorded, and on the scored population the alarm fires on the same fraction of its own hours (the same quantile of its own score distribution). The quantile is label-free, so it can be set on a new hospital's unlabelled hours. It needs at least 10,000 scored hours; below that the absolute threshold is used and the fallback is recorded | Budget 0.5 false alarms per patient-day on the calibration split, unchanged. Applied to internal rows and to transfer rows |
| F. Alarm policy | Persistence 1 h (as now) vs 2 h (risk at or above the operating point in the current and the previous hour); cooldown 6 h (as now, kept); fresh-information hours: alarms allowed in every hour (as now) vs only in hours in which at least one predictor was newly charted (age channel under 1 h, the same "fresh" rule `ssl_targets` uses) | Evaluated on validation only; false alarms per patient-day always counted over every hour of the day |

Items E and F are evaluation settings applied to saved predictions; they need no retraining. The PhysioNet utility is always reported on the plain hourly predictions (no persistence, no cooldown, no fresh-hour rule) so that it stays comparable with the published score; the policy is judged on the clinical metrics (event sensitivity, false alarms per patient-day, warning time, antibiotic lead).

### 10b.2 Decision rules (fixed now)

1. **Backbone and input dropout.** Rank the six trainings per database by the Section 10 rule (rank-average of validation utility and validation AUPRC). The setting with the best average rank across both databases goes to stage 2 as "the project's model". `flat_osta_heads` is kept only if its best configuration is not ranked below the best `flat_osta` configuration on the cross-database average; otherwise the heads are reported as not supported and the stage-2 model is `flat_osta` with the chosen input dropout.
2. **Organ heads as explanation.** Reported regardless of rule 1: per-organ validation AUROC of each head's 6 h target. A head with AUROC below 0.60 on both databases is reported as uninformative. This does not affect rule 1; it tells the consultants' study which organ readings can be trusted.
3. **Operating point.** The quantile operating point replaces the absolute threshold for every event metric and every transfer row in stage 2 if, on the validation splits, it keeps the false-alarm rate within 0.5 per patient-day on both databases and leaves no model silent. Otherwise the absolute threshold stays and the silence is reported as found. The PhysioNet utility on internal rows keeps the absolute utility threshold, for comparability; on transfer rows both forms are reported.
4. **Policy.** Among the four policy combinations (persistence 1 or 2 h × all hours or fresh hours), the one with the highest validation event sensitivity at or under the budget, averaged over both databases, is the stage-2 default. Ties go to the simpler policy. The consultants' study may move the budget and the persistence; that change is recorded, dated, before the holdout opens.
5. **No other change.** Predictor set, label, splits, calibration, bootstrap, horizon (6 h) and every other setting stay as in Section 1 to 9.
6. **Power, stated plainly.** Each validation split holds about 35 septic stays (MIMIC-IV) and about 22 (eICU). The rules above will be noisy, and early stopping already uses the same validation split, so validation numbers are optimistic for every configuration alike. That is why rule 1 defaults to the simpler model unless the heads are at least as good, and why none of these choices is a result: the result is the holdout.

### 10b.3 Outputs and audit trail

- A validation-only summary table per database: arm × input dropout × operating point × policy, with validation utility, AUPRC, event sensitivity, false alarms per patient-day, warning time, and per-organ head AUROC.
- The team summary code refuses to print any test-split row while `STAGE='1b'`; the test predictions are still written to disk, unread, so that the chosen configuration can later be reported on the development test split once, together with the stage-2 results, labelled "chosen on validation in stage 1b".
- The outcome of rules 1 to 4 is appended to this section with the run key and date, and Section 11 is updated in the same commit. That commit is the stage-2 freeze candidate.

## 11. Stage 2, full cohort

- **Data:** all eligible stays in both databases (`FULL_SAMPLE_STAYS_PER_DATASET=None`); the same split rules; three seeds.
- **Arms (TO FREEZE):**
  - the union of the MIMIC-IV and eICU shortlists: GRU-D, TCN, flat OSTA, SSL-CNN→flat (pooled encoder);
  - OSTA, CNN–Transformer, boosted trees and logistic regression;
  - signature boosted trees;
  - the D1 pair, labelled exploratory.
- **Loss (decided 24 Oct 2026):** plain cross-entropy for every arm, by the Section 10 rule (first in three of four validation comparisons). The utility-weighted loss is kept selectable and runs once as a prespecified secondary comparator on `ssl_cnn_osta` only, where it ranked first on MIMIC-IV validation; it cannot replace the primary.
- **Project model (TO FREEZE by stage 1b, Section 10b):** `flat_osta` or `flat_osta_heads`, with the input-dropout setting chosen on validation; it replaces `flat_osta` in the arm list.
- **Operating point and alarm policy (TO FREEZE by stage 1b):** quantile operating point and the policy chosen by rule 10b.2.4, unless rule 3 fails.
- **Pretraining corpus (TO FREEZE):**
  - non-cohort stays plus training-split stays (inputs only, no labels);
  - excluding every stay of a validation, test or protected patient.
- **Final-release encoder (TO FREEZE):** Section 5.3.
- **eICU leave-hospital-out (TO FREEZE):** hospital grouping and the minimum events per hospital.
- **Then:**
  1. freeze this protocol (commit);
  2. declare `PRIOR_TEST_EXPOSURE`;
  3. open the holdout once;
  4. report every prespecified arm and analysis, whatever its result.
- **Reporting standards:** TRIPOD+AI for reporting and PROBAST+AI for the risk-of-bias assessment.

## 12. Reproducibility

- Each notebook embeds its code with SHA-256 checks and runs with **Run all** only. No manual or AI-assistant edits are made between runs.
- Stages are cached under keys built from code, data and configuration: `COHORT_KEY`, `RAW_STAGE_KEY`, `SUPP_KEY`, `DATA_KEY`, `SSL_KEY` and `RUN_KEY`.
  - A changed input produces a new key.
  - A per-run `contract.json` refuses a changed contract.
  - `FORCE_*` settings stay False.
- Each arm writes `completed.json`. Every run writes `run_protocol.json` with the configuration, the feature list and the rules.
- `_11` runs 212 engineering self-tests before training, covering causality, split leakage, scorer agreement and the loss definitions. The repository copy has one more.
- A synthetic fixture run of the whole notebook must pass before any notebook is released.
- Only one heavy notebook runs on the project Drive at a time.

## 13. Legacy external validation (Notebook B)

Notebook B applies the PhysioNet 2019-trained models, frozen, with no fitting on the target data, to the full 120-hour step-labelled trajectories of MIMIC-IV and eICU development patients. Stays with onset before 7 h are excluded. Because challenge hospital system A is Beth Israel Deaconess, the MIMIC-IV results of Notebook B are a same-hospital check and only the eICU results are external.

| Model | Original training recipe |
|---|---|
| Causal OSTA v5 | 3 seeds, 50 epochs, patience 10, batch 256, learning rate 5e-4, cosine schedule |
| Paper-1 CNN–Transformer | 1 seed, 30 epochs, patience 7 |

- **Original split:** 17.5 % test and 12.5 % validation.
- **Original choices:** checkpoint by validation patient-level AUROC every 2 epochs; threshold by validation utility over 0.05 to 0.95.
- **Modes:** `import_original` (the original output folders; reproduces their predictions to 1e-5), `frozen`, or a clearly labelled `reproduce`.
- **Status:** not yet run on real data; it awaits the original model folders.

## 14. Development history: how the work reached this protocol

The models and the pipeline were built in three stages. Each stage was triggered by a finding from the one before. All numbers are causal; results from the earlier leaky pipeline are never reported.

### 14.1 Stage 1: earlier work on PhysioNet 2019 (to March 2026)

| Model | What led to it | What it is | Outcome |
|---|---|---|---|
| CNN–Transformer (Paper 1) | First architecture | Convolution over short local trends, then transformer attention across the stay | Trained with look-ahead leakage; withdrawn; manuscript withheld |
| OSTA-Transformer (v2) | The CNN–Transformer treated every variable alike and could not explain itself | Predictors grouped by organ system (as in SOFA), per-organ temporal attention, cross-organ attention, a risk per organ | Trained with look-ahead leakage; withdrawn; manuscript withheld |
| OSTA v5, causal | The leakage audit found post-onset hours labelled positive, values used before they were available, and label-defining treatments among the inputs | The same architecture on a causal pipeline, three-seed ensemble. Purpose-built loss: focal loss (γ 2, α 0.75/0.25), time weights exp(−0.3 × hours before onset) and 1.5 from onset on, an organ-consistency term (weight 0.1), an organ-diversity term (weight 0.05) | PhysioNet 2019 test: hourly AUROC 0.797, patient AUROC 0.807, normalised utility 0.221 (0.299 at the conformal threshold). The honest PhysioNet baseline |

### 14.2 Stage 2: V10 on MIMIC-IV and eICU (October 2026)

**Design (Notebook A).** Eight arms on identical hours:

- OSTA;
- the observer bank, used in four ways:
  - as extra inputs (observer features);
  - added at the output (output fusion);
  - steering OSTA's cross-organ attention through learned gates (gated guidance);
  - the same steering always on, as a control for the gate (ungated guidance);
- CNN–Transformer;
- L2 logistic regression;
- histogram gradient-boosted trees.

Controls:

- raw values only, to test whether feature engineering adds anything;
- OSTA trained on the observer-fit patients as well (80 % label budget), to test whether any observer gain is only extra labels.

The protocol stated that gated guidance must not be assumed to win.

| Notebook | Purpose | Finding |
|---|---|---|
| `_1` to `_4` | Labels and cohorts for both databases; smoke runs | Repaired: an interval-units bug in the label worker, the YAIB `abx_cont` empty-batch defect, and eICU ionized-calcium units. A mixed demo/full MIMIC-IV folder was detected and replaced |
| `_5` | Timing test (local disk copy, 500 stays per batch) | About 20 times faster per stay than reading from Drive |
| `_6` | First interim run, 10,000-stay samples, 1 seed | MIMIC-IV plausible (OSTA hourly AUROC 0.82). eICU implausible (AUROC 0.31–0.39) |
| `_7` | Calibration fix | A negative Platt slope fitted on the small eICU calibration split had reversed the ranking. Non-positive slopes now fall back to intercept-only recalibration (E1) |
| `_8` | Three seeds (E2) | MIMIC-IV hourly AUROC about 0.81 for the OSTA family. Gated − OSTA AUPRC +0.002 (95 % CI −0.001 to 0.005). Raw values matched engineered features. The extra-label control did not help |
| `_9` (V10.3) | Extraction audit, carry-forward rules, comorbidities, original OSTA loss restored (E3), utility added | eICU coverage fixed (temperature 5 % → 94 %, blood pressure 21 % → 99.5 %). The original loss was no better than cross-entropy. Neural models peaked within 1–3 epochs, so the gated, ungated and OSTA checkpoints were identical |
| `_10` (V10.4–V10.5) | Every candidate predictor class (655 shared predictors) | The raw scan stalled on a date join; fixed (v10.6) |
| `_11` (V11) | The prespecified comparison in this protocol | Sections 10 and 11; an AKI boundary crash was fixed on the first real run |

**Secondary analysis** (run `ed26e1692aa04d2c`): hourly OSTA exceeded qSOFA on MIMIC-IV by +0.28 AUROC (95 % CI 0.21 to 0.35). In eICU, onset-anchored, the models were not better than qSOFA or SIRS.

### 14.3 Stage 3: V11 (this protocol)

The findings of stage 2 shaped stage 3:

- **No integration of organ evidence beat OSTA.** The observer features, the gated and ungated guidance and the extra-label control were retired, and output fusion was kept.
- **Models overfitted within a few epochs.** The response combines three things:
  - testing the organ hypothesis directly (flat OSTA);
  - adding models built for irregular ICU data (GRU-D, TCN, the winner's method);
  - using scarce labels better (self-supervised pretraining, per-channel encoders, event attention, the hazard head), with a loss aligned to the utility score.
- **The original OSTA loss gave no gain.** It was retired.

## 15. Known code notes (no effect on stage-1 results; to correct before stage 2)

- The `utility.json` scope text says that post-onset hours are never trained on, and that an onset after the window counts as non-septic. Under the V11 primary loss and the 6-hour look-ahead, Sections 4 and 8 are the correct statements.
- The secondary analysis notebook still names the V10 arm list.
- The `_11` notebook embeds the earlier label worker (Section 4); the repository copy carries the interval-units fix.
