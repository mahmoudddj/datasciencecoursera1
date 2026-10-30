# Pathophysiology study notebook: what the code does (29 Oct 2026; revised 30 Oct 2026)

Notebook `Sepsis_V11_Improved_MIMIC_eICU_13_pathophysiology.ipynb`, built by `dev/tools/build13.py` from the `_12` notebook (data stages reused unchanged, `STAGE_1B=False` so the unlabelled corpus index is loaded) plus the study cells in `dev/work/cells/pathophys_13.py`. Descriptive only: no model is trained; validation, test and protected patients are never read.

## Settings at the top of cell 7a (to confirm with the partner)

| Setting | Default | Meaning |
|---|---|---|
| `COURSE_HORIZONS` | 48 h (primary), 72 h (sensitivity) | hours after onset at which the course is read |
| `DET_PRESSOR_MIN` | 0.1 NE-eq mcg/kg/min | vasopressor dose at the course hour that counts as escalation when above the onset dose |
| `CONTROL_CAP` | 3,000 per database | controls read (seeded sample); all septic stays are read |
| `PRE_WINDOW` | 48 h | hours before onset read for septic stays and before the pseudo-onset of controls |

## Cell by cell

**7a Strata, outcomes, manifest.** Development stays (train + observer-fit splits) give *incident* (onset at or after hour 6) and *controls*. Every candidate with a sepsis event in the cached label batches (`time` of rows whose `sep3_alt` is not missing, the same source as the cohort onsets) and onset before hour 6 is looked up in the unlabelled corpus; those found become *septic on arrival* (onset at or before hour 0) or *early ICU onset* (0 to 6 h). Coverage (candidates found in the corpus) is printed. Controls get a pseudo-onset drawn from the incident onset distribution of the same database within their follow-up. Outcomes come from the small raw tables through DuckDB: MIMIC-IV `icustays` + `admissions` (hospital death, death hour, lengths of stay) and `diagnoses_icd` (sepsis coded for the admission: A40, A41, R65.2, 038, 995.91, 995.92, 785.52); eICU `patient` (hospital and unit discharge status, offsets, APACHE admission diagnosis containing "sepsis") and `diagnosis` (sepsis or septic in the diagnosis string). In fixture mode outcomes are synthetic and flagged.

**7b One pass over the shards (cached).** The hourly tables are cached under `cache/` in the run folder, keyed by the manifest, so a rerun on the same manifest does not reread the shards. Incident stays are rebuilt from the raw-stage events with the same `build_sequence` code and follow-up extended to the ICU discharge (120 h at most), because the cohort shards end shortly after onset and the course at 48 h was unreadable in the first run. Each stay also carries an antibiotic anchor (first systemic antibiotic within onset ± 24 h for incident stays; a pseudo-antibiotic time for controls) and a documented-sepsis flag.  Each shard file is read once with only the needed columns; for each stay it keeps hours 1 to 30 and the window around the anchor. It produces: `FRESH` (each newly available measurement once, at its own measurement time, so laboratory results are not lost to their result lag), `HOURLY` (carried vitals, SOFA components and totals, therapy and device flags, window features), `STATIC` (admission context, comorbidity documentation) and `ONSET_STATE` (last-known values over the three hours ending at the onset; hours 1 to 3 for onset at or before admission). The course is then assigned per septic stay: *deteriorating* = hospital death, or paired SOFA-component rise of at least 2 (sum over components known at both times, at least 4 components), or vasopressor escalation to at least `DET_PRESSOR_MIN` above the onset dose; *improving* = alive, no rise, no vasopressor at the horizon; *left ICU alive before the horizon* reported separately (counted with improving in the two-way split); otherwise *indeterminate*. Agreement between the 48 h and 72 h readings is printed.

**7c Prespecified comparisons.** Trajectories by 4-hour bin (relative to onset and since admission; by course), rank-based Cliff's delta with 200 stay bootstraps for C1 to C10, the cross-database rule (shared at 0.147, strong at 0.33), measurement rates and the rate rule (1.5-fold), temperature tails (24-hour maximum at or above 38.3 °C, minimum at or below 36 °C) by stratum and course.

| Comparison | a | b |
|---|---|---|
| C1 | incident, hours 1 to 24 | control, hours 1 to 24 |
| C2 | incident, 12 h before onset | control, 12 h before pseudo-onset |
| C2b | incident, 24 to 12 h before onset | control, matched |
| C3 | septic on arrival, ICU hours 1 to 6 | incident, onset to +6 h |
| C4 | early ICU onset, onset to +6 h | incident, onset to +6 h |
| C5 | septic on arrival, ICU hours 1 to 12 | incident, 12 h before onset |
| C6 | slope per hour, incident 12 h before onset | control, matched |
| C7 | incident deteriorating, 12 h before onset | incident improving |
| C8 | septic on arrival deteriorating, hours 1 to 6 | improving |
| C9 | all septic deteriorating, +24 to +48 h | improving |
| C10 | all septic deteriorating, onset to +6 h | improving |
| C2a / C6a | incident, 12 h before the first antibiotic (values / slopes) | control, 12 h before the pseudo-antibiotic time |
| C2d / C2u | documented / undocumented incident, 12 h before onset | control |
| C3d | documented septic on arrival, hours 1 to 6 | documented incident, onset to +6 h |

**7d Beyond the hypotheses.** (a) Departure timing: delta per 4-hour bin over the 48 h before onset, first bin of a sustained departure, for values and for measurement-rate ratios; repeated anchored on the first antibiotic. (b) Order of signs within patients: 19 clinical thresholds, fraction present and fraction *new* (a normal value preceded it) in the 48 h before onset, the same in matched control windows, median lead time, and the precedence matrix P(sign A before sign B). (c) Phenotypes at onset: k-means (k = 4, silhouette for k = 2 to 6) on pooled standardised onset-state values of all septic strata, cluster profiles, sizes by stratum and database, mortality and course by cluster, and the cross-database reproducibility of centroids. (d) Compensation states per hour (quiet, compensated, decompensated). (e) Within-stay heart-rate response per degree of temperature and relative bradycardia. (f) Therapy-stratified deltas (respiratory rate by ventilation, heart rate by beta-blocker, temperature by antipyretic, GCS by sedation, WBC by steroid, urine by diuretic, MAP by vasopressor, glucose by insulin). (g) Selection check: delta restricted to stays measured in every 4-hour bin. (h) Hospital heterogeneity in eICU controls: between-hospital share of variance in values and in measurement rates. (i) Lactate clearance over the first 6 h after onset by stratum and course.

**7e Therapy exposure** by stratum, course and window (12 h before, 0 to 6 h, 6 to 24 h, 24 to 48 h), and antibiotic timing relative to onset for incident stays.

**7f Figures.** Trajectories (onset-relative, admission-relative, incident by course), departure timing, precedence heatmaps, phenotype profiles, compensation states.

**7g Hypotheses and outputs.** H1 to H23 of the framework document scored where a sign test applies (supported in both databases, in one, opposite, no signal, not testable), severity at onset by database (H19), the stage-2 predictor sets (physiology only, without masks, shared pre-onset physiology), and `digest.txt`: every table in text, aggregate only, counts under 11 masked, for pasting to the team.

## Outputs

Under `validation_v10/pathophysiology/<key>/`: `manifest_no_ids.parquet`, `course_no_ids.parquet`, `admission_context_by_stratum.csv`, `trajectories_*.csv`, `comparisons_cliffs_delta.csv`, `measurement_rates.csv`, `temperature_tails*.csv`, `departure_bins.csv`, `departure_timing.csv`, `signs_*.csv`, `precedence_<db>.csv`, `phenotype_*.csv`, `phenotypes.json`, `compensation_states.csv`, `temp_hr_coupling.csv`, `relative_bradycardia.csv`, `therapy_stratified_deltas.csv`, `selection_check.csv`, `hospital_heterogeneity.csv`, `lactate_clearance.csv`, `therapy_exposure.csv`, `antibiotic_timing_incident.csv`, `onset_severity.csv`, `hypothesis_results.csv`, `shared_physiology.json`, `stage2_predictor_sets.json`, `fig1` to `fig7` PNG, `digest.txt`.

## Status

First real-data run: key `3101b901d915324b` (30 Oct 2026), read in `READING_run_3101b901d915324b.md`. Protocol section 10c revised on 30 Oct 2026. The revised notebook (incident course from the raw stage, cache, antibiotic anchor, documented strata) is to be rerun on the owner's account; the first run's cache does not apply because the manifest gained the antibiotic anchor, so the shards are read once more.
