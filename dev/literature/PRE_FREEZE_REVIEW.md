# Pre-freeze literature review and proposal closure

**31 October 2026. For the candidate and the project partner. Nothing in it is applied; every "add" or "modify" below is a proposal for the stage 2 protocol revision and waits for a go.**

## 1. Purpose and method

Stage 2 is the last point at which an arm can be added without a deviation. Seven questions were put to the literature, one search each, run in parallel on 31 October. Each search returned the evidence with numbers, the expected gain, the build and compute cost, and a recommendation. The raw reports are in `dev/literature/raw/01` to `07`. The searches could read abstracts, search summaries and public code but not the full texts of Nature, PMC, arXiv, medRxiv and several publishers, which were outside the session's network; every number the searchers could not confirm against a primary source is marked unverified in the raw reports and must be checked before it is cited in the thesis. This document reads those reports against the proposal ledger (`PROPOSAL_LEDGER.md`), which lists every proposal made since the pathophysiology study; the rule is that no item is dropped without a written rationale.

## 2. The seven questions and what the evidence says

### 2.1 Lead time against clinician action rather than the Sepsis-3 timestamp

**Evidence.** No study links lead time against the SOFA-based onset timestamp to benefit. The outcome-linked deployments are all anchored on clinician action: the TREWS benefit (3.3 points absolute mortality reduction) was estimated only in patients whose alert preceded the antibiotic and was confirmed within 3 hours; COMPOSER trained on windows 4 to 48 hours before clinical suspicion and reported its lead against the first antibiotic order (12.2 hours in the ICU); the one evaluation of a production model restricted to predictions before the first treatment indicator (Kamran 2024) found near-chance discrimination, AUROC 0.47, with 84.8 % of cases treated before the criteria were met. Our own median lag of 7 hours between the first antibiotic and the operational onset is the same phenomenon. The PhysioNet challenge shifted its labels 6 hours early for this reason; a ward model used 6 hours before suspicion; the 3-hour bundle is the clinical anchor.

**Decision.** Keep the suspicion-anchored alternative target as written in the protocol (10c.2 item 9), horizon 3 hours. Add a 6-hour reading as a sensitivity on the same trained model, scored on saved predictions, which costs nothing and answers the reviewer who prefers the PhysioNet optimum. Add a **pre-treatment evaluation of the primary model**: every metric of the primary target recomputed on the hours before the first treatment indicator (antibiotic or culture), after Kamran. This is a scoring pass, not a new model, and it is the single most useful honesty check the literature offers. The event definition keeps the sustained-course rule and the 72-hour antibiotic-free window already in the protocol.

### 2.2 Trajectory features and the baseline-relative arm

**Evidence.** The leading models used absolute last values, 6-hour window statistics, first differences, time since measurement and time since admission; none used a patient-own-baseline normalisation. Whole-history extremes added at most 0.02 AUPRC on one HiRID task and nothing on another; sequence models learn these summaries from raw input. No ICU study tests baseline-normalised features for cross-site transfer; the only support is generic (per-instance normalisation reduces shift in forecasting). Our own finding that the pre-onset signal is a from-admission difference predicts that baseline-relative features remove part of the signal at home.

**Decision.** Keep the arm, modified and reframed. Channels: the six vital signs and the slow Sepsis-3 laboratories (lactate, creatinine, bilirubin, platelets, white cells); no mask or count channels. Baseline: an expanding median of hours 1 to min(t − 6, 24), or the first value of the stay, instead of a fixed hours 1 to 24 median, which is undefined or leaky on the first day against a 6-hour horizon. Summaries: deviation from baseline, a z-score on the baseline interquartile range, the 6-hour slope of the deviation, and the 24-hour extreme of the deviation; time since admission stays as an explicit input. It is a transfer and robustness arm, judged on MIMIC-IV to eICU and back with calibration reported, not an accuracy arm. If both home and cross-site gains are nil it moves to the discussion.

### 2.3 Missingness as information and the two-channel design

**Evidence.** Both halves are established: measurement patterns predict at home (Agniel 2018; GRU-D; missingness indicators making up over 40 % of selected predictors in one study), and they shift across sites (a physiology-only model beat a missingness-augmented one in a simulated prospective setting; concept grouping cut a temporal AUROC drop from 0.29 to 0.06; a 2026 logistic ablation found the MIMIC-IV to eICU drop 0.047 without count features against 0.082 with them, with external calibration the casualty). Pooled training and 10 % target-site fine-tuning are the best-supported mitigations; domain-adversarial methods are real but modest. No one has built a two-stream physiology/process model for clinical time series or ablated the process channel at a held-out hospital; per-site re-standardisation has never been evaluated cleanly.

**Decision.** Add the two-channel arm as the partner asked, in development, training and evaluation. Definition: a physiology path (raw measurements, derived criteria, handcrafted physiology, and the host block of age, sex, weight, body-mass index and the comorbidity flags, as the candidate decided) and a practice path (masks, measurement ages, exposures, devices, medications, imaging, fluids, charted states, admission source and ICU type), separate flat OSTA encoders, concatenated at the output head. Evaluation rows: full; practice path zeroed at test time; practice path re-standardised per hospital, with per-hospital z-scoring tested against quantile mapping because z-scoring deletes the between-hospital rate differences that predicted at home; and a practice-only probe as a shortcut-strength measure. Report calibration beside discrimination, since the published effect was on calibration. Benchmark the arm against the two cheaper mitigations the literature supports, the pooled-training arm already planned and a concept-grouped practice path in which masks and ages are aggregated to organ-group measurement intensities. The derived Sepsis-3 criteria are the leak point between the paths because they depend on whether a laboratory was drawn; the feature manifest assigns each column to exactly one path and is audited before training.

### 2.4 Uncertainty-aware abstention as a gate on the alarm

**Evidence.** COMPOSER's conformal "indeterminate" abstained about 20 % of non-septic and 8 % of septic windows, the asymmetry being the case for abstention as a false-alarm tool; its deployment reduced mortality but had no component ablation, so the contribution of abstention cannot be isolated. No study combines abstention with a persistence or smoothing rule. The protocol already implements an input-level conformal abstention (section 9), so the mechanism exists; the open question is how an abstained hour enters the 2-hour persistence rule: reset the run (current, largely redundant with persistence), pass through transparently, or gate the firing hour only.

**Decision.** Add as a prespecified policy variant on validation only, at negligible cost: 2-hour persistence with transparent abstained hours, and the alarm-level gate, each with an adoption rule (adopt only if false alarms per patient-day fall at equal or better event sensitivity and the median warning time is not shortened beyond a stated tolerance). Report the abstained fraction of scored hours and of septic pre-onset hours per database and hospital. Claim no numeric benefit from the literature. The upside is expected in the transfer rows, where the out-of-distribution fraction can be far above the 2 % seen at home.

### 2.5 Pretraining objectives

**Evidence.** Generic masked reconstruction and forecasting pretraining give small full-data gains, at most 0.01 AUROC, and help mainly below about 5,000 target stays, which matches what we observed. The better-supported levers are weakly supervised multi-task pretraining on cheap clinical labels and pooled multi-site training followed by a small target-site fine-tune, which recovered about 0.05 AUROC across sites in the one sepsis study that measured it. No sepsis paper evaluates a contrastive objective across sites.

**Decision.** Modify the recognition-to-anticipation arm into a weakly supervised multi-task pretraining arm: the pooled encoder is pretrained to predict sepsis present at ICU arrival, the six SOFA components, and treatment events in the next 6 hours (vasopressor, ventilation, antibiotic), then the warning model is trained on it. Evaluate zero-shot across databases and with a 10 % target fine-tune. This is not a reversal of the stage 1b finding: rule 1 rejected organ heads as auxiliary losses *during supervised training of the warning model*; here the organ targets shape the encoder before that training, which is the use the literature supports. Keep the generic masked arm from the stage 1 shortlist as a reported small-gain result. Drop a pure contrastive arm, with the rationale that it has no cross-site evidence in sepsis, small within-site gains, and a medium build cost in augmentation design.

### 2.6 Label noise and label disagreement

**Evidence.** Operational Sepsis-3 captures about five times more stays than explicit coding in MIMIC-III; coding is specific and misses about two thirds of cases; a third of operational positives were adjudication-negative in a prospective cohort; intensivists agree on sepsis with a kappa of 0.29 and on time zero in 36 % of cases, worse for hospital-onset sepsis. Label choice moves AUROC by 0 to 6 points, more than the choice of model. Our noise is instance-dependent and one-sided: documentation is a high-specificity, low-sensitivity second label, and the operational positive class is a mixture. That is the anchor or positive-unlabelled setting, not the symmetric-flip setting in which co-teaching, label smoothing and bootstrapping were validated. If a fraction of labelled positives is indistinguishable from controls, the AUROC against that label is bounded near one minus half that fraction; with our 50 to 65 % undocumented share the ceiling is about 0.68 to 0.75, which is where published 6-hour ICU results sit.

**Decision.** Add as a prespecified secondary arm plus sensitivity analysis: (a) label-stratified training with a cross-evaluation matrix, train on the operational label, on documented-and-operational, and on a positive-unlabelled soft label (documented positives 1, undocumented operational positives the class prior, controls 0), and evaluate each on each; (b) confident-learning pruning as a cheap second noise-aware variant if budget allows; (c) the pre-treatment evaluation of 2.1. Keep co-teaching, label smoothing and bootstrapping for the discussion, with the rationale that they address the wrong noise model and have no sepsis time-series evidence. Drop multiple-instance and noisy-label survival models, with the rationale that they are a 3-to-6-week new model whose question, onset timing, is not a chapter of this thesis.

### 2.7 Calibration drift and recalibration policy

**Evidence.** The dominant failure of deployed risk models is calibration-in-the-large drift with preserved discrimination (AKI models over nine years; EuroSCORE's observed-to-expected ratio falling from 0.76 to 0.37; alert-rate creep at a stable AUROC; an Epic score alerting on 18 % of inpatients). Parsimonious updating wins at small samples: intercept first, then slope, full revision only with large samples and shrinkage; the calibration slope needs on the order of 150 to 200 events; isotonic overfits below about 1,000 cases; temperature scaling cannot fix intercept drift. No head-to-head study compares a fixed alarm fraction with a fixed probability; indirect evidence consistently favours workload-anchored thresholds (Kaiser chose its threshold to yield one alert per 35 patients per day).

**Decision.** Add two cheap analyses to stage 2: (a) threshold transport on eICU, carrying both the MIMIC-derived quantile and the corresponding fixed probability to each hospital and reporting per-hospital alarm fraction, sensitivity and PPV dispersion, which supports the protocol's central design choice with evidence the literature lacks; (b) temporal validation in MIMIC-IV by anchor-year group, training early and testing later, with discrimination, observed-to-expected ratio, slope and alarm fraction under both rules. A recalibration sample-size curve on eICU is optional, or run reduced (none versus intercept at 50, 100 and 200 events). The policy statement for the discussion: monitor observed-to-expected ratio, slope and realised alarm fraction quarterly, update when drift is observed, intercept-only at about 50 to 100 local events, intercept and slope at about 150 to 200, revision only above about 1,000 cases with shrinkage, carry the quantile point across sites, and treat any retraining as a prespecified modification. Nothing warrants dropping the quantile design.

## 3. Closure of the proposal ledger

| Item | Decision | Rationale |
|---|---|---|
| A1 primary target | keep | benchmark comparability; every other target is read against it |
| A2 suspicion-anchored target, 3 h | keep; add 6 h sensitivity on saved predictions | 2.1 |
| A3 label sensitivity scoring | keep; extend with the pre-treatment evaluation | 2.1, 2.6 |
| A4 documented label as training target | add as the label-stratified secondary arm | 2.6: the anchor setting is the one the data present |
| A5 deterioration target, contingent | keep contingent; basis renal and respiratory reserve and coagulation | pathophysiology addendum; the full-release repeat decides |
| A6 antibiotic-relative lead time | keep as primary presentation | 2.1 |
| A7 suspicion rules differ | keep | protocol |
| B1 shared physiology set | keep; recomputed at the freeze | pathophysiology |
| B2 physiology-only and no-mask arms | keep; physiology-only includes the host block | user decision; 2.3 |
| B3 database-specific channels | keep | pathophysiology; 2.3 confirms anion gap and CRP behaviour is method |
| B4 baseline-relative arm | modify (expanding baseline, restricted channels, transfer framing) | 2.2 |
| B5 two-channel arm | add, with practice-only probe, re-standardisation variants, concept-grouped practice path, calibration | 2.3; user instruction |
| B6 host block in physiology | add; with/without sensitivity row | user decision; coding-layer caveat recorded |
| B7 recognition pretraining | modify into weakly supervised multi-task pretraining | 2.5 |
| B8 pooled-training arm | keep; confirm at the freeze | 2.3, 2.5, 2.7 all name it the best-supported mitigation |
| B9 organ heads not revisited | keep decided | stage 1b rule; 2.5 explains why pretraining heads are a different use |
| B10 hospital-aware arm | postponed by the user; discussion | user instruction; 2.3 notes per-site re-standardisation enters through B5 anyway |
| C1 record stage 1b | awaiting go | |
| C2 abstention policy variant | add on validation with an adoption rule | 2.4 |
| C3 consultants' questions | send; add a third on the threshold form (workload-anchored fraction or probability) | 2.7 |
| C4 freeze checklist, signed tag, registration hash | keep | user agreed; signing discussed 31 Oct |
| C5 full-release build start | keep; after the protocol text | |
| C6 full-cohort pathophysiology after results | keep; write into the protocol as a post-results analysis | user instruction |
| C7 recalibration policy | add analyses (a) and (b); statement in the discussion | 2.7 |
| C8 deployment argument | discussion | |
| D1 stratify every result by documentation | add | 2.6 |
| D2 measurement rates as practice signal | keep | |
| D3 heart-rate response per degree | re-read on the full release | |
| D4 lactate clearance | discussion | |
| new: pure contrastive pretraining arm | drop | 2.5: no cross-site evidence, small gain, medium cost |
| new: multiple-instance / noisy-label survival | drop | 2.6: new model, 3 to 6 weeks, not a thesis question |
| new: co-teaching, smoothing, bootstrapping | discussion | 2.6: wrong noise model |
| new: whole-network fine-tuning as the transfer method | discussion; 10 % fine-tune kept only as an evaluation comparator | 2.3, 2.5: underperforms pooled training |

## 4. The stage 2 arm list that results

Arms trained (each on both databases; seeds below): the project model (flat OSTA, dropout 0); the two-channel model; physiology-only with host block; shared physiology; physiology without masks; baseline-relative; pooled training; weakly supervised multi-task pretraining; the generic masked arm from the shortlist; GRU-D; TCN; boosted trees; logistic regression; the D1 pair as exploratory. Fourteen configurations plus the exploratory pair. Targets: primary; suspicion-anchored on the project model and the best non-project arm; label-stratified training (documented-and-operational; positive-unlabelled soft label) on the project model. Scoring passes on saved predictions, no training: 6-hour reading of the suspicion target; pre-treatment evaluation; label sensitivities (antibiotic-only MIMIC-IV, culture-confirmed eICU, documented stratum); documentation-stratified reporting; abstention variants; threshold transport per hospital; temporal validation by anchor-year group; the two-channel evaluation rows.

**Compute, to be decided.** Stage 1 ran sixteen arms on the 10,000-stay samples, one seed, in about a day of A100 time. The full cohort is roughly eight times the stays. Fourteen arms, three seeds, two databases and the extra targets come to the order of three to four weeks of A100 time if everything runs at three seeds. A tiering is proposed: three seeds for the project model, the two-channel model, the pooled and the multi-task pretraining arms and the suspicion target; one seed for the benchmarks, the predictor-set arms and the exploratory pair, with the seed variance of the project model reported as the yardstick. The temporal validation adds one training split in MIMIC-IV. This is the one decision in this document that is yours rather than the literature's.

## 5. What goes into the protocol revision, on your go

Section 10c.2: item 7 rewritten (baseline-relative definition); item 9 adds the 6-hour sensitivity reading; item 10 adds the pre-treatment evaluation and the documentation-stratified reporting; new items for the two-channel arm with the host block and its evaluation rows, the label-stratified secondary arm, the multi-task pretraining arm replacing item 3's wording, the abstention policy variant with its adoption rule, the threshold-transport and temporal-validation analyses, and the full-cohort pathophysiology study after results as a post-results analysis. Section 10b: the stage 1b outcome and settings. Section 11: the arm list of section 4, the seed tiering once decided, and the freeze procedure (signed tag, hash in the registration, prior test exposure declared). Section 12 or a new section: the recalibration policy statement, marked as discussion. The consultants' third question is added to item 12.
