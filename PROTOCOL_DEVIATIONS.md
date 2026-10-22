# Protocol deviations

Every departure from the prespecified V11 protocol (`run_protocol.json`, `protocol_v11='v11-1.0'`) is recorded here, with its date, before the results it could affect exist. The git commit that adds an entry is its timestamp.

## D1. Self-supervised pair added to the full-cohort shortlist (19 Oct 2026)

**Decision (the candidate, 19 Oct 2026):** the full-cohort run trains `ssl_cnn_osta` and `ssl_cnn_flat` in addition to the models chosen by the prespecified shortlist rule.

**What the protocol said:** the full cohort trains the top two or three new arms by the validation rule (rank-average of validation-split utility and AUPRC) plus the fixed baselines (`osta`, `cnn`, `boosted_tree`, `logistic`). On the MIMIC-IV 10,000-stay sample (run `4cd752bef2ccbd42`) the rule chose `grud`, `tcn` and `flat_osta`. The eICU shortlist was not yet known when this entry was written.

**Why this is a deviation:** the trigger was a development **test-split** result. `ssl_cnn_osta` had the highest test point estimate (normalised utility 0.294, 95 % CI 0.170 to 0.386) but was not in the validation top three (validation utility 0.223, AUPRC 0.036). Choosing a model because of its test score breaks the rule that test results are never used for selection.

**Why the pair and not one model:** `ssl_cnn_osta` carries the organ-grouped head that the organ-structure rule did not support (`osta` validation utility 0.117 against `flat_osta` 0.283). `ssl_cnn_flat` is the same model with the same self-supervised site encoder and no organ grouping (test 0.208, validation 0.208). Training both separates the effect of pretraining from the effect of organ grouping.

**How it will be reported (fixed now):**

1. Both arms are labelled *exploratory, added after the development test split (deviation D1)* in every table and figure, and in the manuscript's methods.
2. The primary full-cohort conclusions come from the rule-chosen arms and the baselines only. The pair cannot replace a rule-chosen arm in the primary comparison.
3. Both arms use the primary loss (utility-weighted BCE) and the same settings as the other full-cohort arms: 3 seeds, the same splits, and no extra tuning.
4. The organ question at full scale is the paired bootstrap difference `ssl_cnn_osta` minus `ssl_cnn_flat`, reported next to `osta` minus `flat_osta`. Any keep-or-drop decision uses validation, as before.
5. The 10,000-stay development test numbers for these two arms are not an unbiased estimate, because they prompted the choice. The unbiased estimate is the sealed holdout, opened once after the protocol is frozen.

**Addendum, 22 Oct 2026 (eICU complete):** the eICU validation rule chose `grud`, `flat_osta` and `ssl_cnn_flat_pooled`. Neither D1 arm was chosen on eICU either (`ssl_cnn_osta` validation utility 0.000, test 0.007; `ssl_cnn_flat` validation 0.024, test 0.021). D1 stands exactly as written above; the full-cohort arm list is the union of the two shortlists, the baselines, signature boosted trees and the D1 pair.

**Design item to settle before the full-cohort run (not a further deviation):** the unlabelled pretraining corpus is currently "raw stays not in the labelled cohort, protected patients excluded". At full scale nearly every eligible stay is in the cohort, so this corpus shrinks. Other stays of validation and test patients are also not excluded. The full-cohort build will define the corpus before any full-cohort result exists. The definition will be non-cohort stays plus training-split stays (inputs only, no labels), excluding every stay of a validation, test or protected patient.

## Earlier disclosures (development notebooks `_6` to `_10`, before protocol v11-1.0)

These decisions were taken after interim development results had been seen. They are disclosed here and in each run's `PRIOR_TEST_EXPOSURE` text. None tuned a model on test results.

- **E1. Calibration fix (`_7`, 17 Oct 2026).**
  - **Trigger:** implausible eICU results in run `bd4f8ab28e59f7e2`, with AUROC 0.31–0.39 and calibration slopes of about −3.
  - **Cause:** a negative Platt slope fitted on the small eICU calibration split had reversed every ranking.
  - **Change:** a non-positive fitted slope now falls back to intercept-only recalibration, and the fitted slope and the fallback are recorded. This corrects a monotonicity bug; it is not tuning.
- **E2. Three seeds (`_8`, 17 Oct 2026).**
  - **Trigger:** decided after viewing run `ed26e1692aa04d2c`, to measure seed-to-seed variation.
  - **Outcome:** it lowered the headline MIMIC-IV estimate (hourly AUROC 0.819 with one seed, about 0.81 over three).
- **E3. Original OSTA loss restored (`_9`, 17–18 Oct 2026).**
  - **Trigger:** V10 had trained OSTA with plain cross-entropy instead of its purpose-built loss. This was an implementation departure, noticed after interim results.
  - **Change:** the original loss was ported, verified equal to the original code on 20 random batches, and compared directly with cross-entropy. It gave no gain and was retired in V11.
- **E4. Extraction and predictor changes (`_9`, `_10`, 18–19 Oct 2026).**
  - **Trigger:** a coverage audit of run `ed26e1692aa04d2c` (for example, eICU temperature 5 % and blood pressure 21 % of hours). The changes fix how data are read, and the predictor classes were added for clinical completeness. Performance was not the reason for either.
  - **Changes:** eICU nurse-charted vital signs, admission weight, the MIMIC-IV item corrections, carry-forward rules, comorbidities, and every candidate predictor class (655 shared predictors).
