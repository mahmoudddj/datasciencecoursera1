# Early sepsis warning in the ICU: MIMIC-IV and eICU (notebook `_11`, architectures and losses)
**Prepared for Dr. Mahmoud Mohamed and team · 19 Oct 2026 · 10,000-stay samples, 1 seed · development data only; the final holdout stays sealed**

## 1. What this run decides
`_11` is the prespecified comparison that chooses, by rules fixed in advance, which **models** and which **training loss** go to the full-cohort run. Nothing is chosen on test data: every rule uses the validation split, and test results are reported for all arms.

| Rule | How it is decided (validation split only) |
|---|---|
| Training loss for the full cohort | best rank-average of validation utility and AUPRC among utility-weighted BCE (primary), plain BCE and temporal label smoothing |
| Organ structure (OSTA) | kept only if OSTA beats the identical transformer without organ grouping (`flat_osta`) |
| Shortlist for the full cohort | the top 2–3 new arms by the same rule, plus OSTA, CNN–Transformer, boosted trees and logistic regression |

## 2. The clinical question and the data
- Hourly warning that **Sepsis-3 onset (YAIB/ricu `sep3_alt`) occurs within the next 6 h**. Antibiotics + cultures define suspicion in MIMIC-IV; antibiotics only in eICU.
- The **same 10,000-stay samples and splits** as `_8`, `_9` and `_10`, so every difference is due to the methods.
- **Strict causality:** each value is used only from the hour it was recorded. Each feature carries a "measured?" mask and a "how old?" age (now in days).
- **New in `_11`:** prophylactic antibiotics as predictors (surgical and medical prophylaxis by guideline rule; MIMIC only, because eICU's label is antibiotic-only), lead time versus the **first antibiotic order**, and an **unlabelled corpus** of up to 75,000 stays per database for self-supervised pretraining (no sepsis labels; protected patients excluded).

## 3. Models compared on identical hours
- **Kept:** OSTA · output fusion · CNN–Transformer · logistic regression · boosted trees (patient-grouped early stopping, up to 1,000 iterations).
- **Literature benchmark:** signature features + boosted trees, the PhysioNet 2019 winner's method.
- **New supervised:** flat OSTA (organ ablation) · GRU-D (learned decay from measurement ages) · causal dilated TCN · per-channel causal CNN → OSTA · event attention over fresh observations → OSTA.
- **Self-supervised:** the per-channel CNN pretrained on the unlabelled corpus with four label-free tasks (next fresh value, measured within 6 h, SOFA organ components at +6/12/24 h, any organ worsening within 6/12/24 h), then fine-tuned with an OSTA head or a flat head; a site encoder (own database) and a pooled encoder (both databases, reported as adaptation); a discrete-time **hazard head** (1/3/6/12/24 h).
- **Secondary:** a prespecified mean ensemble of OSTA, CNN–Transformer and SSL-CNN-OSTA (no learned weights).
- **Dropped after `_8`/`_9`:** gated and ungated attention, observer features, the 80%-label control, and the original OSTA loss (all documented there; still selectable in the code).

## 4. Losses
- **Primary: utility-weighted BCE.** Each positive hour is weighted by the PhysioNet reward gap (1.0 at 6 h before onset → 2.0 at 3 h after), normalised to mean 1; the three hours after onset are added as weighted training positives. Evaluation hours are unchanged.
- **Comparators** (on OSTA and SSL-CNN-OSTA): plain BCE; temporal label smoothing (soft targets rising towards onset, Yèche et al. 2023).
- The hazard arm trains a survival likelihood; its 6 h risk is 1 − S(6 h).
- Protocol changes applied to every neural arm: batch 32, AdamW weight decay 1e-4, dropout 0.2, early stopping on validation AUPRC.

## 5. How performance is judged
Your principal panel: PhysioNet **utility** · **AUPRC** · **AUROC** · **sepsis cases caught** at ≤ 0.5 false alarms/patient-day · **median warning time** · **false alarms/patient-day** · **calibration/Brier**, all with patient-cluster bootstrap CIs; plus:
- **lead time versus the first antibiotic order** (how many hours before the clinician acted did the model alarm?);
- **transfer rows:** each database's model scored on the *other* database's development patients (the sealed holdout is untouched);
- a **conformal secondary alarm policy** (abstain on out-of-distribution hours; distribution-free hourly false-positive bound);
- the **trajectory-rich subset** (hours with dense monitoring);
- sensitivity **without clinician-suspicion proxies** (hydrocortisone, imaging orders, prophylaxis) and the raw-values control.

## 6. What this run is not
Not the final result. With about 175 septic training stays, all models overfit within a few epochs (`_9` histories); the shortlist goes to the **full cohort** (about 94,000 + 200,000 stays, 3 seeds), where the pretraining corpus and the labelled data are both an order of magnitude larger.

## 7. How to run
1. Colab, A100 and high RAM. **Runtime → Run all.** Do not change settings.
2. Check the first output: `Mode: full | data: clinical | full holdout released: False`.
3. Stages and rough times: supplementary stage (minutes) → features for the labelled sample (~45 min, parallel) → **unlabelled corpus** (raw scan + features, ~3–4 h) → pretraining (~1 h) → arms (~6–8 h). Total about **11–14 h**. Every stage resumes after a disconnect: reopen and Run all.
4. Progress lines: `miiv hourly features …`, `SSL site epoch …`, `Completed <database> <feature set> hh:mm`. At the end: `COMPLETE: …`.
5. Then download this notebook and collect the audit zip (team summary, coverage, prophylaxis counts, training histories).

## Technical notes
- Self-contained: all code embedded with SHA-256 checks; nothing calls an external AI service; patient data never leave your Colab/Drive.
- Saved outputs in this file come from a synthetic engineering run (no patient data).
- Settings are in Section 1; keep `FORCE_*=False` and `RELEASE_FINAL_HOLDOUT=False`.
