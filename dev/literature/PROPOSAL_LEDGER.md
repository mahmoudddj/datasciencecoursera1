# Proposal ledger: everything proposed since the pathophysiology study (30 to 31 October 2026)

Rule for this ledger: no item is dropped without a written rationale. "Status" says where the item stands today; "Closes with" says what decides it. Items marked *in protocol* were applied on 30 October on the candidate's instruction; the rest wait for a go.

## A. Targets and labels

| # | Item | Origin | Status | Closes with |
|---|---|---|---|---|
| A1 | Primary target unchanged: YAIB `sep3_alt` onset, 6-hour horizon | protocol | in protocol | freeze |
| A2 | Suspicion-anchored alternative target: first antibiotic course at or after ICU hour 6, no antibiotic in the prior 72 h, continued; 3-hour horizon; scored without the PhysioNet utility | user and candidate, 30 Oct | in protocol (10c.2 item 9) | literature item 1; stage 2 build |
| A3 | Label sensitivity scoring of the primary model: antibiotic-only label in MIMIC-IV; culture-confirmed label in eICU where recorded; documented-sepsis stratum | 30 Oct | in protocol (10c.2 item 10) | stage 2 build |
| A4 | Documented-sepsis label as a sensitivity *training* target, budget permitting | revised run reading, 31 Oct | proposed | literature item 6; compute plan |
| A5 | Deterioration as secondary target, contingent; basis now renal and respiratory reserve and the coagulation axis | 30 to 31 Oct | in protocol as contingent (10c.2 item 11); basis updated in the reading | full-release pathophysiology repeat; consultants |
| A6 | Lead time against the first antibiotic as a primary presentation beside onset lead | 30 Oct | in protocol (10c.2 item 8) | stage 2 build |
| A7 | The two suspicion rules differ; no cross-database comparison of rates | 30 Oct | in protocol (label section) | none |

## B. Predictors and architecture

| # | Item | Origin | Status | Closes with |
|---|---|---|---|---|
| B1 | Shared pre-onset physiology set, read from the study at the freeze (now 14 channels) | 29 to 31 Oct | in protocol (10c.2 item 2b) | full-release repeat |
| B2 | Physiology-only and no-mask predictor arms | 29 Oct | in protocol (10c.2 item 2) | stage 2 build |
| B3 | Database-specific channels flagged: anion gap, CRP, lactate, FiO2, rates and ages | 30 Oct | in protocol (10c.2 item 6) | none |
| B4 | Baseline-relative arm (patient's own hours 1 to 24 as reference) | 30 Oct | in protocol (10c.2 item 7) | literature item 2 decides window and summaries |
| B5 | Two-channel arm: physiology path and practice path, separate encoders, concatenated at the head; practice path re-standardised per hospital; evaluation rows with the practice path zeroed and re-standardised | user, 31 Oct ("in development, training and evaluation") | proposed, definition drafted | literature item 3; stage 2 protocol revision |
| B6 | Host block (age, sex, weight, body-mass index, 17 comorbidity flags) in the physiology path and in the physiology-only set, with a with/without sensitivity row | user, 31 Oct | proposed | stage 2 protocol revision |
| B7 | Recognition-to-anticipation pretraining, judged by its effect on the incident warning | 29 to 30 Oct | in protocol (10c.2 items 3 and 5) | literature item 5 |
| B8 | Pooled-training arm (both databases together) | 25 Oct | in protocol as proposed, to confirm | freeze |
| B9 | Organ heads: not supported by the stage 1b rule; not revisited on the full cohort | stage 1b, 31 Oct | decided; to record in 10b outcome | go for item C1 |
| B10 | Hospital-aware arm (per-hospital standardisation plus hospital embedding, tested on unseen hospitals) | candidate, 31 Oct | **postponed by the user** until after the run; kept for the discussion | after stage 2 |

## C. Settings, policy and process

| # | Item | Origin | Status | Closes with |
|---|---|---|---|---|
| C1 | Record stage 1b outcome (run b9b18c8632cf33d0): flat OSTA, dropout 0, quantile point, persistence 2 h, all hours | stage 1b | **done 31 Oct** (protocol 10b.4; config block) | none |
| C2 | Alarm abstention (conformal "indeterminate") as a policy variant beside persistence | literature list, 31 Oct | open | literature item 4 |
| C3 | Consultants' two questions: value of a warning after the first antibiotic; course definition (48 or 72 h, vasopressor threshold) | 30 Oct | in protocol (10c.2 item 12); draft offered, not yet sent | user |
| C4 | Freeze checklist and preregistration before the holdout is opened | 31 Oct | proposed | after the review and the consultants |
| C5 | Full-release label and feature build to start as soon as the protocol text is settled | 31 Oct | proposed | go |
| C6 | Full-cohort pathophysiology study, holdout included, after results are final, as discussion material | user, 31 Oct | agreed; to write into the protocol as a post-results analysis | stage 2 protocol revision |
| C7 | Recalibration policy for deployment, numbers for the discussion | literature list | open | literature item 7 |
| C8 | Deployment argument (three layers; pooled training and local recalibration over whole-network fine-tuning; mixed-effects frame on practice inputs; transfer to another health system) | 31 Oct | discussion notes drafted | paper |

## Closure

All items were closed by `PRE_FREEZE_REVIEW.md` (31 Oct 2026) and the protocol revision of the same day applied the adds and modifications to Sections 10b.4, 10c.2 (items 3, 7, 9, 10, 12, 14 to 19) and 11. Open decisions: seed tiering; the consultants' three answers.

## D. Items from the pathophysiology reading not yet acted on

| # | Item | Status | Closes with |
|---|---|---|---|
| D1 | Documentation is a mixture marker: report every stage-2 result stratified by documented versus undocumented sepsis | proposed | stage 2 protocol revision |
| D2 | Treat measurement rates as a practice signal in the report, never as a transferable finding | in protocol (item 6) | none |
| D3 | Heart-rate response per degree of temperature (blunted in incident patients, 14 stays): re-read on the full release before any claim | noted | full-release repeat |
| D4 | Lactate clearance at 6 h did not separate courses in MIMIC-IV arrivals; starting lactate did | noted for the discussion | paper |

Any item above that the pre-freeze review recommends dropping will carry its rationale in that document; absence of evidence is recorded as "keep for discussion", not as a drop.
