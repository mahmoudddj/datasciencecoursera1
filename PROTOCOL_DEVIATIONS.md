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

**Design item to settle before the full-cohort run (not a further deviation):** the unlabelled pretraining corpus is currently "raw stays not in the labelled cohort, protected patients excluded". At full scale nearly every eligible stay is in the cohort, so this corpus shrinks. Other stays of validation and test patients are also not excluded. The full-cohort build will define the corpus before any full-cohort result exists. The definition will be non-cohort stays plus training-split stays (inputs only, no labels), excluding every stay of a validation, test or protected patient.
