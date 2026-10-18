## What changed in V11 (this `_11`, 19 Oct 2026)

All V10.5 features are kept. Decisions were made with Dr. Mohamed on 19 Oct 2026, before any V11 result existed.

**Data**
- Raw-stage fix (v10.6): `PriorPositiveCulture_1y` and `PriorAntibiotics_90d` are computed with a single equality join on the person against a pre-joined stays+admissions table. The `_10` form (events JOIN stays JOIN admissions with the date comparison between events and admissions) made DuckDB merge-join the full tables on the date first and never finished; `_10` stalled there for 8 h. The raw-table scan therefore runs once more under a new key (about 20–30 min per database).
- Prophylactic antibiotics (MIMIC-IV only): `Prophylaxis_Surgical_24h` and `Prophylaxis_Medical`, from a supplementary stage keyed separately from the main scan. Surgical prophylaxis = a prophylaxis agent, perioperative timing (PACU/OR transfer or ICU admission from the OR), order ≤ 24 h (48 h cardiac), no culture in the Seymour window [−72 h, +24 h], no escalation within 72 h. Medical prophylaxis = PJP/SBP/neutropenia/transplant agents at prophylactic dosing, no culture pairing. Empirical and culture-directed antibiotics are never predictors (they define the label). eICU: unknown.
- First antibiotic order around onset: evaluation metadata only (never a predictor), both databases.
- Unlabelled pretraining corpus: stays never labelled by YAIB, protected-hash patients excluded, capped at 75,000 per database; features built in parallel with the same code.
- Measurement ages are now scaled to days (fixed), not z-scored, so "fresh" is well defined for every model.

**Arms** (all causal; every new arm passes a future-perturbation invariance test)
- kept: OSTA, output fusion, CNN–Transformer, logistic, boosted trees (now with patient-grouped early stopping, ≤ 1,000 iterations);
- benchmark: signature features + boosted trees (PhysioNet 2019 winner);
- new: flat OSTA, GRU-D, causal TCN, CNN→OSTA, event attention→OSTA;
- self-supervised: CNN encoder pretrained on the unlabelled corpus (site and pooled), with OSTA head, flat head, and a hazard (survival) head;
- secondary: mean ensemble of OSTA + CNN–Transformer + SSL-CNN-OSTA;
- dropped: gated/ungated attention, observer features, 80%-label control, original OSTA loss.

**Losses:** utility-weighted BCE (primary), BCE, temporal label smoothing; hazard likelihood for the hazard arm. Selection by validation utility + AUPRC rank-average.

**Evaluation additions:** lead time versus the first antibiotic order; transfer rows to the other database's development patients; conformal abstention and conformal alarm threshold; trajectory-rich subset; no-proxy sensitivity; paired bootstrap differences versus OSTA for every arm.

**Protocol:** batch 32, weight decay 1e-4, dropout 0.2 for every neural arm; 1 seed here, 3 seeds in the full cohort with the shortlist rule.
