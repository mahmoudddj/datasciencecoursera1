## Verification record (preparation, 2026-10-14)

| Check | Result | Evidence |
|---|---|---|
| 28 embedded files: SHA-256 verified; originals byte-identical to supplied ZIP / handcrafted module; pinned scorer identical to GitHub commit `467c49b` | PASS | decoded and re-hashed |
| Notebook schema (nbformat 4.5, cell ids) and code-cell syntax | PASS | nbformat validate + AST parse |
| **Top-to-bottom execution through a real Jupyter kernel**, fresh process, fixture mode | PASS | Python 3.12.3 · numpy 2.5.4 · pandas 3.0.6 · scikit-learn 1.9.1 · torch 2.14.1 (CPU) |
| Same on an older Colab-like stack | PASS | numpy 2.0.2 · pandas 2.2.2 · scikit-learn 1.6.1; DuckDB 1.1.3 auto-upgraded to ≥1.2 (needed for strict CSV parsing) |
| 141 engineering checks (`engineering_checks.json`) | PASS | PhysioNet repair (mock server: auth, resume, SHA-256, quarantine), release preflight (demo, partial and MIXED full/demo raw folders refused before any import, by per-file size and stay count; import-status report), raw adapters (MIMIC + eICU SQL on schema-shaped CSVs), availability timing, urine/irrigant, GCS/ETT, missingness, fresh-measurement trends, first/last events, prefix vs full history at feature **and** adapter level (values + masks), patient isolation, shard resume, full-size forward/backward + padding + prefix + checkpoint equivalence for all six neural arms, guidance stress tests, onset from unwindowed events |
| Vectorised urine/support vs original loops | PASS | 300 randomised cases, 0 mismatches |
| All 8 arms + raw control (OSTA, logistic, boosted trees) + 80% OSTA control, both fixture databases: fit → calibrate → threshold → metrics → export | PASS | 2-epoch smoke; every arm scored identical eligible hours |
| Kernel killed mid-training, rerun | PASS | results and all 16 checkpoints bit-identical to an uninterrupted run |
| Completed-run reuse / changed contract | PASS | rerun retrains nothing; changed config in an existing run directory is refused |
| Full-mode resolution | PASS | resolved table printed in Section 6; nothing launched |
| ricu interval fallback returns the time column's own units (fix for `.subset2 ... get1index` in label batch 5) | PASS | R 4.3 with ricu 0969a52 `interval`/`obeys_interval`/`re_time` semantics: `1 hours` (old: `3600 secs`, which made `re_time` mix secs and hours) |
| Real MIMIC-IV/eICU extraction, R/ricu workers, Colab resources | **NOT RUN** | no clinical data or Colab runtime available to the preparer |
| Full training, clinical performance, final holdouts | **NOT RUN** | by design |

Synthetic fixture numbers are meaningless as performance and are not shown.
