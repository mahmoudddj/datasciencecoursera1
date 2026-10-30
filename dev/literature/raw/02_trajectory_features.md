# Review item 2: temporal feature summaries in leading ICU models; implications for the baseline-relative arm (search report, 31 Oct 2026)

Access caveat recorded by the searcher: full texts on PMC, arXiv, Nature, PhysioNet, Lancet, ScienceDirect and medRxiv were not reachable and the search budget ran out before four targeted queries; [UNVERIFIED] items rest on snippets or recall.

## Key papers and what carried the weight

- PhysioNet 2019 winners: Morrill (1st) log-signatures of six vitals over a 6-hour lookback plus clinical features into gradient boosting (AUC 0.81, utility 0.41); ICU length of stay said to dominate importance [UNVERIFIED]. Zabihi (3rd): 407 features, five-XGBoost ensemble, ICU length of stay and hospital admission time among them. Other entries: 6-hour sliding windows stepped hourly, raw and differenced series, 168 features with current-minus-previous differences, 20-hour windows with carry-forward and hours since each variable was last measured. Common thread: absolute last value, short 6-hour window statistics, first differences, missingness and time since measurement, time since admission. No entry used a patient-own-baseline normalisation. Reyna 2020: generalisation to the sequestered third hospital "remains a challenge".
- Nemati 2018 AISE: 65 hourly features plus high-resolution heart-rate and blood-pressure dynamics; AUROC 0.83 to 0.85 at 4 to 12 h [top features UNVERIFIED].
- DeepAISE (Shashikumar 2021): GRU on hourly inputs; top features recent surgery, ICU length of stay, heart rate, GCS, WBC, temperature; AUC 0.90 internal, 0.87 external; masking the top locally relevant features hurt more than masking global ones.
- Hyland 2020 (circulatory failure, HiRID): LightGBM, 8-hour horizon, AUROC about 0.94; SHAP dominated by the event-defining variables (lactate, MAP); multi-horizon summaries and measurement-intensity features used [exact horizons UNVERIFIED].
- HiRID benchmark (Yèche 2021): whole-history min, max, mean and measurement density per variable helped modestly on one task only (respiratory failure AUPRC 0.585 to 0.604) and not on circulatory failure (0.389 vs 0.388); sequence models learned equivalent summaries from raw hourly input.
- Moor 2023: internal 0.847, external 0.761, 0.807 with 10 % target fine-tuning; reimplementations forward-fill hourly with missingness flags and time since last record.
- Thorsen-Meyer 2020 (hourly LSTM, SHAP): importance of features changes over the stay. Lauritsen 2020: raw event sequences without engineered features, AUROC 0.856 at 3 h to 0.756 at 24 h. Kamran 2024 (NEJM AI): Epic model AUROC 0.62 before criteria and 0.47 before the first treatment indicator; 84.8 % of cases had treatment indicators before criteria (echoes our antibiotic-anchored finding: much apparent pre-onset signal is clinician reaction).
- Transfer: Rockenschaub 2024 (sepsis AUROC 0.749 to 0.824 at the training site, drops up to 0.20 elsewhere; multi-source training helps; domain-generalisation methods did not); npj Digit Med 2026 (zero-shot 0.61 to 0.69 vs 0.75 to 0.77 with target training; fine-tuning underperformed); medRxiv 2026 (observation-process features improve internal discrimination, worsen external calibration). No ICU study tests patient-baseline-normalised features for cross-site transfer; the only support is generic (RevIN, ICLR 2022: per-instance normalisation mitigates shift in forecasting).

## Implications for the baseline-relative arm

- Channels: the six vitals and the slow Sepsis-3 labs (lactate, creatinine, bilirubin, platelets, WBC). Skip missingness and count channels (the most site-specific features).
- Baseline window: an hours 1 to 24 median is defensible but undefined or leaky in the first day of a stay against a 6-hour horizon; use an expanding baseline (median of hours 1 to min(t−6, 24)) or the first value of the stay (already present as lab deltas).
- Summaries: level deviation (value minus baseline, and a z-score on the baseline IQR), 6-hour slope of the deviation, 24-hour extreme of the deviation; drop duplicate 3-hour variance and skew. Keep time since ICU admission as an explicit input.

## Expected gain, cost, recommendation

- Gain small internally (flat to −0.01 AUROC: our own finding that the signal is a from-admission difference predicts that baseline-relative features remove part of it at home); the plausible upside is cross-site robustness, untested in the literature and therefore a genuine contribution if measured MIMIC-IV to eICU and back.
- Cost low: one pass per stay, 50 to 100 extra columns, no new model; the main cost is the leakage audit of the baseline window and the extra cross-site runs.
- Recommendation: keep, modified and reframed as a transfer and robustness arm (absolute vs baseline-relative vs both, with and without observation-process features; AUROC, AUPRC and calibration), with the expanding or first-value baseline. If both internal and cross-site gains are nil, move to discussion.

## References

Morrill 2020 doi:10.1097/CCM.0000000000004510; CinC2019-014, -238, -280, -423, -020 (physionet.org/files/challenge-2019/1.0.0/papers/) · Reyna 2020 Crit Care Med 48:210 · Nemati 2018 doi:10.1097/CCM.0000000000002936 · Shashikumar 2021 doi:10.1016/j.artmed.2021.102036 · Hyland 2020 doi:10.1038/s41591-020-0789-4 · Yèche 2021 arXiv:2111.08536 · Moor 2023 doi:10.1016/j.eclinm.2023.102124 · Thorsen-Meyer 2020 doi:10.1016/S2589-7500(20)30018-2 · Lauritsen 2020 doi:10.1016/j.artmed.2020.101820 · Kamran 2024 doi:10.1056/AIoa2300032 · Rockenschaub 2024 arXiv:2303.15354 · npj Digit Med 2026 doi:10.1038/s41746-026-02364-4 · medRxiv 2026 doi:10.64898/2026.04.05.26350209 · Kim 2022 RevIN (ICLR) · Hüser arXiv:2105.05728 · unverified: Mao 2018 BMJ Open (InSight), Agniel 2018 doi:10.1136/bmj.k1479
