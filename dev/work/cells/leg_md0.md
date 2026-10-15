# PhysioNet-trained models — independent MIMIC-IV/eICU validation (legacy notebook)
**Prepared for Dr. Mahmoud Mohamed · `RUN_MODE='smoke'` by default · runs independently from a fresh kernel**

The original OSTA (v5) and Paper1 CNN–Transformer definitions are embedded byte-for-byte and loaded by name (their old top-level training scripts never run). Frozen models keep their original layers (including the CNN's BatchNorm), original feature generation, source-fitted normalisation, feature order, threshold and ensemble rule. V10 features never enter these networks.

**Three ways to obtain the source models (Section 1, `LEGACY_MODE`):**
- `'import_original'` — **historical validation.** Point `ORIGINAL_OUTPUT_DIRS` at the folders the original scripts wrote: OSTA `v5_seed{42,7,123}_model.pt` + `v5_preprocessed_cache.npz` + `v5_validation_utility_sweep.csv`; CNN `sepsis_enhanced_transformer.pt` + `preprocessed_data_cache_paper1.npz` + `paper1_validation_utility_sweep.csv`. The scaler comes from the cache, the threshold from the saved validation sweep, OSTA is the uniform 3-seed ensemble (original default). Nothing is retrained.
- `'frozen'` — a complete `legacy-bundle-v2` folder you already packaged.
- `'reproduce'` (default) — a **clearly labelled re-training on PhysioNet source data** with the original feature rule, split rule, losses, optimiser, model selection and threshold grid. It is *not* the historical model; a smoke reproduction (tiny model, 2 epochs) only tests the pipeline.

**Status of the saved outputs:** a synthetic-fixture run through a real Jupyter kernel. The supplied ZIP contains code only — **no trained weights, scalers or sweeps** — so historical validation was not possible here, and no real source or target data were used.

Paths shared with the main notebook (`PROJECT_PATH`, `RAW_SOURCE_PATHS`) are set in Section 1; compatible cohorts and the main notebook's raw-table stage are reused.
