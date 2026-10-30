# Review item 1: lead time relative to clinician action versus the Sepsis-3 timestamp (search report, 31 Oct 2026)

Access caveat recorded by the searcher: publisher pages not reachable; [V] verified against code or text on GitHub, [S] from search summaries of abstracts, [U] unconfirmed.

## Key papers

| Paper | Cohort | Target or anchor | Horizon | Main result |
|---|---|---|---|---|
| Henry 2015 Sci Transl Med (TREWScore) [S] | JHH ICU, MIMIC-II | septic shock onset | continuous | median lead 28.2 h before shock; AUC 0.83 |
| Henry 2022 Nat Med (TREWS adoption) [S] | 5 hospitals, 590,736 monitored, 9,805 sepsis | alert versus clinician confirmation; outcome time to first antibiotic | confirmation within 3 h | 82 % of cases flagged; 38 % of alerts confirmed; confirmation within 3 h gave 1.85 h shorter time to antibiotic |
| Adams 2022 Nat Med (TREWS outcomes) [S] | 6,877 sepsis patients whose alert fired before antibiotics | only pre-antibiotic alerts counted | 3 h | adjusted in-hospital mortality −3.3 points absolute, −18.7 % relative |
| Shashikumar 2021 npj Digit Med (COMPOSER) [S] | UCSD and external ICU and ED | Sepsis-3 onset anchored to clinical suspicion (antibiotic plus culture); positive label 4 to 48 h before suspicion | 4 to 48 h | AUC ICU 0.925 to 0.953; alerts a median 12.2 h (ICU) and 2.1 h (ED) before the first antibiotic order |
| Boussina 2024 npj Digit Med [S] | 2 EDs, 6,217 septic patients | nurse-facing advisory | | mortality −1.9 points absolute; bundle compliance +5.0 |
| Wong 2021 JAMA Intern Med (Epic) [S] | Michigan, 38,455 hospitalisations | onset at earliest clinician intervention [U] | | AUROC 0.63; only 7 % of sepsis cases flagged that clinicians had not already treated |
| Kamran 2024 NEJM AI [S] | Michigan inpatients 2018 to 2020 | predictions scored only before the first treatment indicator (culture or antibiotic order) | | AUROC 0.62 before criteria, 0.47 before clinical recognition; 84.8 % of cases had treatment indicators before the Sepsis-3 criteria were met ("label leakage") |
| Escobar 2020 NEJM (Kaiser AAM) [S] | 21 hospitals | general deterioration, 12-h risk | 12 h | 30-day mortality relative risk 0.84 |
| Reyna 2020 Crit Care Med (PhysioNet 2019) [V code] | 60k stays | t_suspicion = antibiotic plus culture; t_sepsis = earlier of suspicion and SOFA; labels shifted 6 h early | 6 h | utility window −12 / −6 optimum / +3 late |
| Moor 2023 eClinicalMedicine [S/V] | 4 databases, 136,478 admissions | ricu-style suspicion with −48/+24 h SOFA window; repo also computes an online onset = max(SOFA, antibiotic, sample time) | 6 h before / 24 h after onset in the repo config | 80 % sensitivity 3.7 h before onset at 1.4 false alerts per true alert |
| YAIB / ricu [V] | MIMIC-IV, eICU, HiRID, AUMC | sep3_alt: antibiotic course with no uncovered gap over 24 h in the next 72 h, plus sampling; antibiotics only on eICU and HiRID; onset = first SOFA row with a rise of 2 inside [SI −48 h, SI +24 h], that is the SOFA-change time, not the antibiotic time | 6 h | benchmark |
| Cohen 2024 Sci Rep [S] | MIMIC | onset at organ-dysfunction time versus suspicion time versus earlier | | performance markedly sensitive to the anchor |
| Yu 2022 Front Digit Health [S] | general wards | time of suspicion = earlier of antibiotic order and culture, prior 48 h excluded | 6 h before | suspicion-anchored ward model |
| Lauritsen 2021; Schamoni 2019 [S] | wards; ICU | labels and evaluation must account for antibiotics already started; consensus labels are circular | | framing changes results |

## Horizon supported

No study shows that lead time relative to the Sepsis-3 SOFA timestamp predicts benefit. The outcome-linked evidence is action-anchored: TREWS benefit required an alert before antibiotics and confirmation within 3 h; COMPOSER trained 4 to 48 h before suspicion and reported lead against the first antibiotic order; Kamran scored only pre-recognition predictions. With the 3-hour bundle target and the hour-by-hour antibiotic-delay gradient [Seymour 2017, U], the defensible actionable window is 3 to 6 h before the first antibiotic or culture: 3 h is the conservative, bundle-aligned bound; 6 h matches the PhysioNet optimum and Yu 2022.

## Expected gain, cost, recommendation

Our median 7-hour antibiotic-before-onset lag mirrors Kamran's 84.8 %. Under the SOFA-anchored label part of the 6-hour positive window lies after treatment has begun, so features reflect treatment and "successful" alerts may be late. Expect the antibiotic-anchored target to give lower nominal AUPRC and sensitivity but deployment-comparable numbers and lead times comparable to COMPOSER and TREWS. Risk: antibiotic courses without sepsis add label noise; mitigate with the sustained-course rule and culture pairing where available. Cost low to moderate: a relabelling of the existing hourly matrix (positive = [t_abx − 3 h, t_abx), censor at t_abx, exclude stays on antibiotics at admission or in the prior 48 h); one extra training run per model, database and seed; one script for the lag distribution. Recommendation: add as a secondary arm, keep Sepsis-3 primary for benchmark comparability, present the two side by side with the lag distribution.

## References

Henry 2015 doi:10.1126/scitranslmed.aab3719 · Henry 2022 doi:10.1038/s41591-022-01895-z [U] · Adams 2022 doi:10.1038/s41591-022-01894-0 · Shashikumar 2021 doi:10.1038/s41746-021-00504-6 · Boussina 2024 doi:10.1038/s41746-023-00986-6 · Wong 2021 doi:10.1001/jamainternmed.2021.2626 · Kamran 2024 doi:10.1056/AIoa2300032 · Escobar 2020 doi:10.1056/NEJMsa2001090 · Reyna 2020 doi:10.1097/CCM.0000000000004145; github.com/physionetchallenges/evaluation-2019 · Moor 2023 doi:10.1016/j.eclinm.2023.102124; github.com/BorgwardtLab/multicenter-sepsis · YAIB github.com/rvandewater/YAIB-cohorts · ricu github.com/eth-mds/ricu · Cohen 2024 doi:10.1038/s41598-024-51989-6 · Yu 2022 doi:10.3389/fdgth.2022.848599 · Lauritsen 2021 doi:10.1038/s41746-021-00529-x [U] · Schamoni 2019 doi:10.1016/j.artmed.2019.101725 · Seymour 2017 doi:10.1056/NEJMoa1703058 [U] · Front Artif Intell 2025 doi:10.3389/frai.2025.1452471 [U]
