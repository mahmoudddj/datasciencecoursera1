# Review item 3: missingness and process features, cross-site failure, physiology/process separation (search report, 31 Oct 2026)

Access caveat recorded by the searcher: PMC, nature.com and medRxiv full texts were not reachable from the search session; figures come from abstracts and snippets; items marked [unverified] were not confirmed against a primary source.

## Key findings

- Process features predict at home: Agniel 2018 (BMJ 361:k1479; 669,452 patients, 272 lab tests; presence of an order associated with survival for 86 % of tests, order timing beat the value for 68 % [unverified aggregator figure]); Lipton 2016 (missingness indicators raise PICU diagnosis AUC); Che 2018 GRU-D (mask + time since last observation with learned decay); Sharafoddini 2019 (over 40 % of selected predictors were missingness indicators); Futoma 2017 (MGP-RNN, informative missingness at Duke, sepsis about 4 h ahead); Rubanova 2019 (Latent ODE with a separate Poisson head for observation times).
- Process features shift: Singh 2021 (JMIR Med Inform 9(12):e25022): missingness features improved retrospective AUROC by 1.2 to 7.7 % but in a simulated prospective setting a physiology-only model won by 0.9 % AUROC; instability attributed to intra- and inter-hospital process variation. Zech 2018 (site identifiable from images, site label alone AUC 0.861). Nestor 2019 (MLHC): AUROC fell 0.29 across MIMIC's 2008 record-keeping change; grouping raw items into clinical concepts cut the drop to 0.06. Moor 2023 (eClinicalMedicine 62:102124): internal 0.846, external 0.761, 0.807 with 10 % target-site fine-tuning. Tranchellini 2026 (npj Digit Med): transfer direction matters; fewer dynamic features shift MIMIC-IV versus eICU than versus HiRID. Finlayson 2021 (NEJM) taxonomy.
- The ablation closest to ours: medRxiv 2026 (doi 10.64898/2026.04.05.26350209), logistic regression, MIMIC-IV to eICU AUROC drop about 0.047 without count features versus 0.082 with them; internal discrimination up, external calibration degraded [unverified preprint; its repository notes a MIMIC-IV FiO2 extraction error later corrected]. BlendedICU four-database study (Crit Care 2026): drug-exposure features as portability-degrading shortcuts, pooling the best mitigation [unverified].

## Separation designs with evidence (ranked)

1. Concept grouping / feature abstraction (Nestor): largest measured recovery, essentially free.
2. Target-site fine-tuning (Moor +0.046 AUROC at 10 % labels).
3. Explicit process-channel ablation (one logistic-regression preprint).
4. Domain-adversarial training (AdaDiag JBI 2022; arXiv:2310.07799; npj Digit Med 2023 across four UK hospital groups): real but modest; Crit Care Med 2024 found dedicated generalisability methods gave no noticeable gain.
- Per-site re-standardisation: no clean evaluation found (J Clin Med 2026 confounds scaling with retraining).
- Two-stream physiology/process encoders for clinical time series: not found; nearest analogues outside EHR. Nobody has evaluated a deep clinical sequence model with the process channel ablated at a held-out hospital.

## Expected gain, cost, recommendation

- Internal AUROC: about 0 to −0.01 (two encoders concatenated are no more expressive than one). External: plausibly 0.02 to 0.04 AUPRC recovered against a single-encoder baseline, within a total transfer gap of about 0.085 AUROC (Moor). Per-hospital re-standardisation is label-free and matches our variance decomposition, but z-scoring the practice channel per hospital removes exactly the between-hospital rate differences that predicted at home; test per-hospital z-scoring against quantile mapping.
- Cost: low in compute (1.5 to 2 times the parameters); the real work is a feature manifest assigning every column to one channel; derived Sepsis-3 criteria are the leak point because they depend on whether a lab was drawn. Two to four weeks on an existing pipeline.
- Recommendation: add as an arm, with calibration reported beside discrimination, a practice-only probe, and benchmarks against 10 % fine-tuning and concept grouping.

## References

Agniel 2018 https://doi.org/10.1136/bmj.k1479 · Lipton 2016 https://arxiv.org/abs/1606.04130 · Che 2018 https://doi.org/10.1038/s41598-018-24271-9 · Sharafoddini 2019 https://doi.org/10.2196/11605 · Shi 2025 https://doi.org/10.1186/s12911-025-03058-9 [unverified] · Futoma 2017 arXiv:1706.04152, 1708.05894 · Rubanova 2019 https://arxiv.org/abs/1907.03907 · Singh 2021 https://doi.org/10.2196/25022 · Finlayson 2021 https://doi.org/10.1056/NEJMc2104626 · Zech 2018 https://doi.org/10.1371/journal.pmed.1002683 · Nestor 2019 https://proceedings.mlr.press/v106/nestor19a.html · Moor 2023 https://doi.org/10.1016/j.eclinm.2023.102124 · Tranchellini 2026 https://doi.org/10.1038/s41746-026-02364-4 · medRxiv 2026 https://doi.org/10.64898/2026.04.05.26350209 · BlendedICU Crit Care 2026 https://doi.org/10.1186/s13054-026-06034-5 · YAIB arXiv:2306.05109 · AdaDiag https://doi.org/10.1016/j.jbi.2022.104168 · arXiv:2310.07799 · npj Digit Med 2023 https://doi.org/10.1038/s41746-023-00805-y · Crit Care Med 2024 https://doi.org/10.1097/CCM.0000000000006359 · Pardo 2026 https://doi.org/10.3390/jcm15186957 · arXiv:2007.08213 · REFORMS arXiv:2308.07832
