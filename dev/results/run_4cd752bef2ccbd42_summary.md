# Run `4cd752bef2ccbd42` (V11, notebook `_11`): complete results digest

Source: aggregate outputs of `Sepsis_V11_Improved_MIMIC_eICU_11_architectures.ipynb` (full copy in `run_4cd752bef2ccbd42_notebook_outputs.txt`). Run completed on Colab (A100, 164 GB RAM): MIMIC-IV rich 04:08, raw 04:36, no_proxies 04:52; eICU rich 10:38, raw 10:57, no_proxies 11:09. One seed (42), 30 epochs, 5 SSL epochs, 200 bootstrap resamples, utility-weighted BCE primary loss, 0.5 false alarms per patient-day budget. 659 predictors (267 raw-control), 16 arms plus loss comparators and the mean ensemble = 21 rows per feature set. Development split only; the sealed holdout is untouched.

**Caveat:** the notebook's pandas display truncated the `utility_CI_low` column. Lower limits must be read from `team_summary_performance.csv` in the run folder before any statement that an eICU interval includes zero. Upper limits are shown.

## Cohorts (team_summary_cohort)

| | MIMIC-IV | eICU |
|---|---|---|
| Candidate stays sampled | 10,000 | 10,000 |
| Stays after YAIB exclusions | 8,758 | 5,623 |
| Sealed final holdout stays | 1,679 | 1,168 |
| Development stays (patients) | 7,079 (6,713) | 4,455 (4,363) |
| Hospitals | 1 | 101 |
| Development stays with a prediction window | 350 | 226 |
| Unlabelled pretraining stays | 67,193 | 74,139 |
| Development test split | 1,422 stays, 63,488 h, 411 positive h (0.65 %), 71 events | 888 stays, 37,648 h, 265 positive h (0.70 %), 45 events |

(The feature stage counted 8,795 and 5,710 labelled stays; the difference from the table is the stays without an eligible hour or belonging to protected patients. Confirm in the run folder before quoting either.)

## Internal development test, rich features, normalised utility (95 % CI upper limit) · hourly AUROC

| Arm | MIMIC-IV utility | MIMIC-IV AUROC | eICU utility (CI high) | eICU AUROC |
|---|---|---|---|---|
| ssl_cnn_osta | 0.294 (0.170–0.386) | 0.824 | 0.007 (0.022) | 0.668 |
| cnn_osta | 0.278 (–0.374) | 0.826 | 0.015 (0.052) | 0.654 |
| ensemble_mean | 0.276 (–0.373) | 0.823 | 0.011 (0.034) | 0.668 |
| output_fusion | 0.247 (–0.345) | 0.811 | 0.018 (0.052) | 0.618 |
| cnn | 0.242 (–0.350) | 0.798 | **0.075 (0.161)** | 0.676 |
| osta | 0.230 (0.125–0.335) | 0.806 | 0.007 (0.022); no alarms within budget | 0.662 |
| flat_osta | 0.230 (0.107–0.344) | 0.799 | 0.026 (0.070) | 0.666 |
| ssl_cnn_osta_pooled | 0.227 (–0.326) | 0.810 | 0.007 (0.022) | 0.668 |
| event_osta | 0.208 (–0.323) | 0.810 | 0.010 (0.030) | 0.653 |
| ssl_cnn_flat | 0.208 (–0.311) | 0.797 | 0.021 (0.065) | 0.668 |
| ssl_cnn_flat_pooled | 0.204 (–0.312) | 0.800 | 0.038 (0.121) | 0.658 |
| grud | 0.186 (0.075–0.286) | 0.773 | 0.066 (0.145) | 0.528 |
| hazard_ssl_cnn_osta | 0.181 (–0.280) | 0.814 | 0.011 (0.030) | 0.649 |
| osta@bce | 0.172 (–0.265) | 0.792 | −0.001 (0.000); no alarms | 0.661 |
| osta@tls | 0.166 (–0.271) | 0.796 | 0.000 (0.003); no alarms | 0.666 |
| tcn | 0.165 (–0.264) | 0.792 | 0.043 (0.105) | 0.579 |
| signature_boosted_tree (winner's approach) | 0.145 (0.060–0.221) | 0.838 | 0.019 (0.054) | 0.595 |
| ssl_cnn_osta@bce | 0.126 (–0.169) | 0.814 | 0.009 (0.023) | 0.646 |
| boosted_tree | 0.100 (–0.169) | 0.806 | 0.036 (0.079) | 0.605 |
| ssl_cnn_osta@tls | 0.092 (–0.202) | 0.814 | 0.002 (0.010) | 0.638 |
| logistic | 0.079 (0.006–0.161) | 0.716 | 0.012 (0.043) | 0.614 |

MIMIC-IV: all 21 above zero with every interval above zero (range 0.08–0.29); AUROC 0.72–0.84. eICU: point estimates −0.001 to 0.075; AUROC 0.53–0.68; the OSTA family at the budget threshold raised no alarms on the test split (event sensitivity 0, false alarms 0), so their utilities are those of silence.

Raw-feature controls (MIMIC / eICU utility): osta 0.175 / 0.007; boosted_tree 0.058 / 0.000; logistic 0.088 / −0.003. No-proxies OSTA: 0.175 / 0.008.

## Transfer (development-level; model of one database scored on the other's development test patients)

| Arm | MIMIC-IV → eICU utility | AUROC | eICU → MIMIC-IV utility | AUROC |
|---|---|---|---|---|
| osta | 0.041 | 0.650 | 0.000 (no alarms) | 0.713 |
| ssl_cnn_osta | 0.041 | 0.669 | 0.000 | 0.725 |
| tcn | 0.030 | 0.669 | 0.028 | 0.636 |
| ssl_cnn_osta_pooled | 0.026 | 0.653 | 0.000 | 0.725 |
| flat_osta | 0.025 | 0.669 | 0.000 | 0.718 |
| signature_boosted_tree | 0.021 | 0.663 | 0.000 | 0.691 |
| cnn_osta | 0.018 (−0.011 to 0.044) | 0.672 | −0.000 | 0.725 |
| hazard_ssl_cnn_osta | 0.018 (−0.026 to 0.060) | 0.666 | 0.000 | 0.730 |
| cnn | 0.014 | 0.626 | 0.027 | 0.636 |
| output_fusion | 0.014 | 0.675 | 0.000 | 0.634 |
| ssl_cnn_flat | 0.013 | 0.659 | −0.000 | 0.708 |
| boosted_tree | 0.012 (−0.003 to 0.027) | 0.626 | 0.000 | 0.675 |
| grud | 0.010 (−0.037 to 0.063) | 0.640 | 0.006 | 0.614 |
| ssl_cnn_osta@bce | 0.006 | 0.669 | −0.000 | 0.720 |
| ssl_cnn_osta@tls | 0.003 | 0.677 | −0.000 | 0.721 |
| event_osta | 0.000 | 0.670 | 0.000 | 0.735 |
| osta@bce | −0.025 | 0.651 | −0.000 | 0.724 |
| osta@tls | −0.031 | 0.653 | −0.001 | 0.731 |
| ssl_cnn_flat_pooled | −0.034 | 0.643 | 0.006 | 0.693 |
| logistic | −0.152 | 0.579 | −0.001 | 0.567 |

The transfer intervals in brackets are the four recovered from the earlier partial output of the same run; the rest need the CSV. MIMIC-IV → eICU: −0.03 to +0.04 for 19 models (logistic −0.15). eICU → MIMIC-IV: −0.00 to +0.03, most OSTA-family models raising no alarms. Read together with the internal rows: MIMIC-IV-trained models on eICU (−0.03 to +0.04) sit in the same band as eICU-trained models on eICU (0.00 to 0.08); on eICU at 45 events, home and transfer are indistinguishable.

## Conformal secondary policy (abstention about 1.7 % eICU, 2.3 % MIMIC-IV)

False alarms per patient-day 0.08–0.18 (eICU) and 0.09–0.21 (MIMIC-IV) with event sensitivity 0.04–0.20 (eICU) and 0.18–0.34 (MIMIC-IV).

## Prespecified rules (validation only)

| Rule | MIMIC-IV | eICU |
|---|---|---|
| Loss, OSTA | bce (val U 0.175) > tls (0.166) > utility-weighted (0.117) | bce (0.022) > tls (0.013) > utility-weighted (0.010) |
| Loss, SSL-CNN→OSTA | utility-weighted (0.223) > bce (0.158) > tls (0.100) | bce (0.023) > tls (0.014) > utility-weighted (0.000) |
| Organ structure | NOT supported (OSTA rank 16.0 vs flat OSTA 6.0) | NOT supported (15.5 vs 2.5) |
| Shortlist | grud, tcn, flat_osta | grud, flat_osta, ssl_cnn_flat_pooled |

Union of shortlists: grud, tcn, flat_osta, ssl_cnn_flat_pooled. Plain cross-entropy ranked first in three of the four loss comparisons. Neither D1 arm (ssl_cnn_osta, ssl_cnn_flat) was chosen by the rule on either database.

## Antibiotic lead (evaluation metadata only)

Median alarm lead versus the first antibiotic order, among events with an alarm: MIMIC-IV about 2–4 h before the order for most models (57 events with an order near onset); eICU about 3.5–8.5 h before (29 events). The fraction of alarms before the first antibiotic is 0.16–0.32 on MIMIC-IV and 0.00–0.14 on eICU.
