# Review item 4: uncertainty-aware abstention as a gate on clinical alarms (search report, 31 Oct 2026)

Access caveat recorded by the searcher: full-text hosts (PMC, Nature, medRxiv, arXiv, PhysioNet, CinC) not reachable and the search budget ran out after 12 queries; [unverified] items from memory. Local finding: protocol section 9 already implements a COMPOSER-style conformal input-level abstention (fraction of observed channels with |z| above 3.5; hours above the 98th calibration percentile, alpha 0.02, abstain with risk set to 0). The open question is how it combines with the 2-hour persistence rule and the quantile operating point.

## Key papers

- COMPOSER, Shashikumar 2021 (npj Digit Med 4:134): conformal prediction on the input representation flags windows unlike the training data as indeterminate. Six cohorts, 515,720 patients, ICU and ED. About 20 % of non-septic and 8 % of septic windows indeterminate; sequential AUC 0.925 to 0.953 (ICU); median warning before the first antibiotic order 12.2 h ICU, 2.1 h ED. No with/without-filter false-alarm contrast in the abstract [body unverified]. The 2.5-fold asymmetry between negative and positive abstained windows is the case for abstention as a false-alarm tool.
- COMPOSER deployment, Boussina 2024 (npj Digit Med 7:14): before/after quasi-experiment, two EDs, 6,217 septic patients; indeterminate = no alert; in-hospital sepsis mortality −1.9 percentage points absolute (17 % relative), bundle compliance +5.0 points; no component ablation, so the contribution of abstention cannot be isolated; effect on lead time not reported.
- Pimentel 2019 (CinC, PhysioNet 2019): one model for sepsis probability, one for its uncertainty due to missing data, combined by a tuned decision rule; test AUC 0.769, utility 0.225; the suppressed fraction and the isolated effect of the gate not in the abstract.
- Dusenberry 2020 (CHIL): calibrated deep-ensemble members disagree widely on individual patients; proposes deferral; no alarm policy.
- Feng et al. (Biometrics): selective prediction sets with coverage guarantees on MIMIC-III mortality; static.
- Kompa, Snoek, Beam 2021: perspective. Sepsyn-OLCP 2025 [unverified]. Moor 2023 for scale: 1.4 false alerts per true alert at 80 % detected 3.7 h before onset.
- No study found that evaluates an abstention rule together with a consecutive-window or smoothing rule in deterioration alerting.

## Hourly probability or alarm decision

The abstention signal is an input-level score computed per hour. Three ways an abstained hour can enter the 2-hour persistence rule: (a) reset, risk 0 and the run breaks (current section 9 behaviour; conservative, costs lead time when one artefactual hour interrupts a rising trajectory); (b) transparent, abstained hours neither count nor reset, so an alarm needs two consecutive determinate hours above threshold; (c) alarm-level gate, fire only if the firing hour is determinate, else defer to the next determinate hour. Since persistence already suppresses single-hour spikes, (a) is largely redundant with it; (b) and (c) are the variants worth measuring. Report abstention as a coverage metric: fraction of scored hours, and of septic stays' pre-onset hours, silent by design.

## Expected gain, cost, recommendation

- Internally bounded and probably small (about 2 % of calibration hours abstain; persistence already removes transients); a one-line diagnostic on validation, the share of false-alarm hours that are abstained, settles it. The upside is in the transfer rows, where the out-of-distribution fraction can be far above 2 % because of scale shift; there abstention and the quantile operating point are complementary, but abstention can also remove septic hours (COMPOSER 8 %), so sensitivity and warning time must be reported beside it.
- Cost negligible: the per-hour score exists; variants (b) and (c) are evaluation settings on saved predictions; minutes of compute. Deliverable: policy table rows (abstention variant × persistence × operating point) with event sensitivity, false alarms per patient-day, warning time, antibiotic lead and abstained fractions per database and hospital.
- Recommendation: add as a prespecified policy variant on validation only, 2-hour persistence with transparent abstained hours plus the alarm-level gate, with an adoption rule (adopt only if false alarms per patient-day fall at equal or better event sensitivity and median warning time is not shortened beyond a stated tolerance; otherwise section 9 stays as the secondary row). Claim no numeric benefit from the literature; the only clinical evidence is observational without ablation. Frame persistence and abstention as handling different failure modes (transient noise versus unfamiliar inputs).

## References

Shashikumar 2021 doi:10.1038/s41746-021-00504-6 · Boussina 2024 doi:10.1038/s41746-023-00986-6 · Pimentel 2019 doi:10.23919/CinC49843.2019.9005942 · Dusenberry 2020 arXiv:1906.03842 · Feng et al. arXiv:1906.05473 · Kompa 2021 doi:10.1038/s41746-020-00367-3 · Sepsyn-OLCP arXiv:2503.14663 · Moor 2023 doi:10.1016/j.eclinm.2023.102124 · unverified leads: Wardi 2021 Ann Emerg Med; Amrollahi 2022 Sci Rep (COMPOSER continual learning)
