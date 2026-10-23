# OSTA design tree (our own models only), 23 Oct 2026

Readable version: https://claude.ai/artifact/M1pvJ92wA5yD8nFvDqskdo. Numbers: normalised utility on the development test splits of run `4cd752bef2ccbd42` (MIMIC-IV 1,422 stays / 71 events; eICU 888 / 45), one seed; "val" = validation utility, the only number the rules look at. Comparators from the literature (GRU-D, TCN, boosted trees, logistic, signature trees) are omitted.

**The idea.** Read each organ's history with its own attention, let organs inform each other, output a risk per organ. Every node below tests that sentence.

## Generation 1, PhysioNet 2019 (to March 2026)
| Node | Bet | Found | Status |
|---|---|---|---|
| CNN-Transformer (Paper 1) | local trends + attention, every variable alike | leaky; withdrawn. Causal rebuild = `cnn` arm: MIMIC 0.242, eICU 0.075 (best there) | baseline kept |
| OSTA v2 | organ grouping = explanation + prior | leaky (the 0.97 AUROC); withdrawn | withdrawn |
| OSTA v5 causal | architecture survives without the leak | PhysioNet AUROC 0.80, utility 0.22 | honest baseline |

## Generation 2, V10 on raw MIMIC-IV + eICU (Oct 2026)
| Node | Bet | Found | Status |
|---|---|---|---|
| `osta` on the causal pipeline | one label, two raw DBs, 659 predictors | MIMIC 0.230 (val 0.117); eICU 0.007, silent at budget; transfer to eICU 0.041 | kept |
| Observer features | independent organ evidence as inputs | no gain | retired |
| Output fusion | observers added at output | MIMIC 0.247 (val 0.210); eICU 0.018 | kept |
| Gated guidance | observers steer cross-organ attention | AUPRC +0.002 (−0.001, 0.005); checkpoints identical to OSTA | retired |
| Ungated guidance | control for the gate | same | retired |
| Raw-values control | is feature engineering needed? | OSTA raw 0.175 vs rich 0.230: breadth helps | kept as feature set |
| 80 % labels control | is any gain just more labels? | no help | retired |
| Original OSTA loss | purpose-built loss should matter | equal to original code; no better than CE | retired |

## Generation 3, V11 (19 to 22 Oct 2026)
**A. Is the organ grouping doing anything?**
| Flat OSTA (same code, one group) | if the prior helps, OSTA beats flat on validation | test tie 0.230; val flat 0.283 vs OSTA 0.117 (MIMIC), rank 2.5 vs 15.5 (eICU); eICU test 0.026 vs 0.007 | organ NOT supported; flat OSTA goes forward (both shortlists) |
|---|---|---|---|

Why: 14 encoders starve on ~175 septic stays; each organ squeezed to 32 numbers before organs interact (loses the sum of weak signals); the mapping is a guess.

**B. Can scarce labels be used better?**
| Node | Bet | Found | Status |
|---|---|---|---|
| CNN→OSTA (supervised encoder) | cleaner inputs | MIMIC 0.278 (val 0.172); eICU 0.015 | open |
| SSL CNN→OSTA, site | pretrain on 67k unlabelled stays | MIMIC 0.294 (top point; val 0.223, not chosen); eICU 0.007; transfer 0.041 | exploratory, D1 |
| SSL CNN→OSTA, pooled | one encoder, both DBs | MIMIC 0.227 (val 0.267); eICU 0.007 | open |
| SSL CNN→flat, site / pooled | pretraining without the bottleneck | 0.208 / 0.204; pooled eICU 0.038, top eICU val; pooled transfer −0.034 | pooled on eICU shortlist; site = D1 |
| Hazard head | predict when, not only whether | MIMIC 0.181; eICU 0.011 | retired |
| Event OSTA | attention over charted events | MIMIC 0.208 (val 0.223); transfer 0.000 | retired |

**C. Should the loss follow the utility score?**
| Node | Found | Status |
|---|---|---|
| Utility-weighted CE (primary) vs plain CE vs label smoothing | OSTA test 0.230 / 0.172 / 0.166; on validation plain CE first for OSTA on both DBs and for SSL on eICU (3 of 4), smoothing never | rule reads plain CE for stage 2 unless a deviation is recorded |
| Mean ensemble (osta+cnn+ssl_cnn_osta) | MIMIC 0.276; eICU 0.011 | prespecified secondary |

## Five lessons
1. Every version of our model works on MIMIC-IV once the pipeline is causal (0.17 to 0.29, all CIs above zero).
2. Nothing bolted onto OSTA beat OSTA; every neural model peaks within 3 epochs on ~175 septic stays. The sample, not the idea.
3. Organ grouping not supported on either database; flat OSTA is the honest version today. Explanation can be kept without the bottleneck.
4. Self-supervised pretraining is the one addition with a signal, but the rule did not choose it (D1 pair).
5. eICU is near zero for everything, ours and comparators, home and transferred: 45 events, ~100 hospitals, weaker label. Stage 2's question, not a reason to redesign.

## The decision
| Path | What | For | Against |
|---|---|---|---|
| 1. Stage 2 as prespecified | flat OSTA + rule-chosen + baselines + D1 pair | cleanest protocol; fastest | organ idea gets only D1; "our model" may lose to GRU-D |
| **2. One bounded fix, then stage 2 (recommended)** | stage 1b on train/validation only: flat backbone + per-organ heads, quantile threshold, persistence/cooldown, input dropout; one week; list written first; no test numbers viewed; then freeze | keeps the organ-level reading in a form the data supports; stays prespecified; fixes the eICU silence | one week; one more arm; discipline to stop at one fix |
| 3. Drop the organ idea | flat OSTA is the model | matches evidence; simplest | gives up the clinical explanation; decides on 175 stays when 3,500 are coming |

## Next steps in order
1. Choose the path; confirm the stage-2 loss (rule: plain CE).
2. If path 2: write stage 1b into PROTOCOL.md (dated commit) before any run.
3. Decide the compute plan (cloud machine with local disk, or a prespecified sample). Labels extracted once.
4. Freeze and preregister (OSF).
5. Build and run `_12`: 3 seeds, eICU leave-hospital-out, antibiotic-only label sensitivity, paired utility, lead time; holdout sealed.
6. Finish the consultants' study; it fixes the alarm budget and explanation.
7. Open the holdout once; report every arm; TRIPOD+AI.
