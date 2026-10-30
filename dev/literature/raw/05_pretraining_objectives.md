# Review item 5: pretraining objectives for ICU time series (search report, 31 Oct 2026)

Access caveat recorded by the searcher: arXiv, PMC, PMLR, OpenReview, Nature and medRxiv full texts were not reachable; numbers come from snippets, abstracts and secondary summaries; [unverified] items need the full text before citing.

## Key papers

Masked and forecasting self-supervision: McDermott 2021 (CHIL; MIMIC-III and eICU): gains concentrated at 1 % fine-tuning and on imbalanced rolling tasks; weakly supervised multi-task pretraining gave the largest gains; no evidence that pretraining fixes population shift. Zerveas 2021 (TST), Tipirneni 2022 (STraTS, forecasting pretext, gains when labels are few), Labach 2023 (DuETT, 0.007 to 0.02 AUROC over XGBoost). Jagd 2025 (NeurIPS; Bi-Axial Transformer, forecasting on pooled MIMIC and eICU inside YAIB): beats supervised baselines mainly when the target set is under about 5,000 stays; pooled pretraining most robust [deltas unverified]. ICU-BERT 2025 [unverified].

Contrastive: Yèche 2021 (NCL): decompensation AUPRC 35.1 vs 34.2 end to end; label-preserving neighbourhoods 37.1; no cross-site. Weatherhead 2022 (TRACE), King 2024 (contrastive on MIMIC-III, linear probe to eICU) [unverified]; Wanyan 2023 argues supervised contrastive beats self-supervised for sepsis [unverified]. No ICU sepsis paper with cross-site evaluation of SimCLR or TS-TCC style objectives found.

Clinically meaningful auxiliary targets: Harutyunyan 2019 (multitask beats single-task); SeqSNR 2021 (six organ-dysfunction and intervention endpoints; routed multi-task beats shared-bottom; warns about negative transfer); IOC-MT 2025 (six SOFA organ systems, three databases) [unverified]; an MIT 2021 thesis found SOFA-component multitask gains only versus unregularised nets; PULSE-ICU 2025 (masked-event pretraining with 18 tasks including six SOFA components; external eICU and HiRID with minimal fine-tuning) [unverified].

Cross-site evidence: Moor 2023 (internal 0.846, external 0.761, 0.807 with 10 % target data); Rockenschaub 2024 (Crit Care Med; four databases; sepsis AUROC 0.749 to 0.824 internally, drops up to 0.20 externally; multi-source training mitigates; dedicated domain-generalisation methods no noticeable benefit); Guo 2024 (CLMBR-T-base; continued pretraining on the target site +3 % on average); ICareFM 2025 (time-to-event self-supervision on about 650k stays; zero-shot median AUROC 0.837 across held-out hospitals; local models needed a median 14,709 stays to match; not open-sourced) [sepsis numbers unverified]. HiRID benchmark and YAIB: no pretraining experiments; dataset and preprocessing effects larger than model-class effects.

## Best-supported objective for a few-event warning task

Weakly supervised multi-task pretraining on cheap clinical labels (recognition, SOFA components, treatments), then pooled multi-site training with a small target-site fine-tune. Generic masked reconstruction and forecasting give small full-data gains (at most 0.01 AUROC) and help mainly below about 5,000 target stays.

## Expected gain and cost

Within-site ceiling about 0.01 AUROC or 0.01 to 0.03 AUPRC, consistent with what we observed. Cross-site is the better-evidenced lever: pooled pretraining plus 10 % target fine-tuning recovered about 0.05 AUROC in Moor. Cost: low for multi-task weak-label heads on the existing pipeline (hours on one GPU for 140k stays); medium for contrastive; high for foundation-style pooled pretraining.

## Recommendation

Modify the recognition arm into a weakly supervised multi-task pretraining arm (recognition plus SOFA-component and treatment heads) on the pooled encoder, evaluated zero-shot across sites and with a 10 % target fine-tune. Keep the generic masked arm as a reported small-gain result; keep forecasting as discussion. Drop a pure SimCLR or TS-TCC arm (no cross-site vitals evidence, small within-site gains).

## References

McDermott 2021 https://doi.org/10.1145/3450439.3451877 · Zerveas 2021 https://arxiv.org/abs/2010.02803 · Tipirneni 2022 https://arxiv.org/abs/2107.14293 · Labach 2023 https://arxiv.org/abs/2304.13017 · Jagd 2025 https://arxiv.org/abs/2509.19885 · ICU-BERT 2025 https://arxiv.org/abs/2502.19593 · Yèche 2021 https://proceedings.mlr.press/v139/yeche21a.html · Weatherhead 2022 https://proceedings.mlr.press/v174/weatherhead22a.html · King 2024 https://arxiv.org/abs/2410.09199 · Wanyan 2023 https://doi.org/10.1109/ICHI57859.2023.00024 · Harutyunyan 2019 https://arxiv.org/abs/1703.07771 · SeqSNR 2021 https://discovery.ucl.ac.uk/10130273/ · IOC-MT 2025 https://doi.org/10.1186/s13040-025-00445-w · PULSE-ICU 2025 https://arxiv.org/abs/2511.22199 · Moor 2023 https://doi.org/10.1016/j.eclinm.2023.102124 · Rockenschaub 2024 https://arxiv.org/abs/2303.15354 · Guo 2024 https://doi.org/10.1038/s41746-024-01166-w · Burger 2024 https://arxiv.org/abs/2411.16346 · ICareFM 2025 https://doi.org/10.1101/2025.07.25.25331635 · HiRID benchmark https://arxiv.org/abs/2111.08536 · YAIB https://arxiv.org/abs/2306.05109 · arXiv 2312.06855
