# Draft revision of protocol section 10c.1 (APPLIED on 30 Oct 2026 on the candidate's instruction, with the additions of items 5 to 13 of 10c.2; kept as a record)

The current 10c.1 (added 29 Oct 2026) names three groups, five comparisons and the cross-database rule. The notebook now built implements the design below. If approved, this text replaces 10c.1 in `PROTOCOL.md`; 10c.2 is unchanged except where noted at the end.

---

### 10c.1 The pathophysiology study (notebook `_13_pathophysiology`; descriptive; before the freeze)

**Purpose.** To describe, in both databases, which physiological patterns precede and accompany sepsis by the route into it and by its course, which of them are shared across the two hospital systems, and which are artefacts of practice. Hypotheses H1 to H23 of `dev/pathophysiology/PATHOPHYSIOLOGY_FRAMEWORK.md` are registered before the run; each is reported as supported in both databases, in one, opposite, no signal or not testable.

**Who is in it (training-split and non-cohort patients only; never validation, test or protected patients):**

- *Incident* (ICU-acquired): cohort stays with onset at or after the sixth ICU hour, train and observer-fit splits.
- *Septic on arrival*: candidate stays with an operational onset at or before ICU hour 0 (excluded by YAIB exclusion 7), whose hourly features exist in the unlabelled corpus; onset from the cached label batches. Coverage (candidates found in the corpus) is reported.
- *Early ICU onset*: the same source, onset in hours 0 to 6.
- *Controls*: cohort stays with no onset, train and observer-fit splits, a seeded sample of at most 3,000 per database. Each control receives a **pseudo-onset** drawn from the incident onset distribution of its database within its follow-up, so that onset-relative comparisons are matched on time since admission.
- Transfers (ward or other hospital) are reported as a stratum within each group, not merged.

**Course (every septic stay), read at onset + 48 h (72 h as sensitivity):** *deteriorating* = hospital death, or a rise of at least 2 in the paired sum of SOFA components known at both times (at least four components), or vasopressor escalation to at least 0.1 norepinephrine-equivalent mcg/kg/min above the onset dose; *improving* = alive at hospital discharge, no rise, no vasopressor at the horizon; stays leaving the ICU alive before the horizon are reported separately and counted with improving in the two-way split; otherwise *indeterminate*. Hospital and ICU mortality, discharge timing and sepsis documentation (MIMIC-IV ICD coding of the admission; eICU APACHE admission diagnosis and diagnosis list) come from the small raw tables and are used only to describe.

**What is measured.** Fresh measurements for values (each newly available measurement once, placed at its measurement time); measurement frequency per stay-hour as the practice signal; carried SOFA components, vasopressor dose and window features (urine output, fluids, 24-hour temperature extremes) as states; therapy and device exposure per window.

**Comparisons (rank-based Cliff's delta, 200 stay bootstraps):** C1 incident vs control at hours 1 to 24; C2 incident 12 h before onset vs control 12 h before pseudo-onset; C2b the same at 24 to 12 h; C3 septic on arrival (hours 1 to 6) vs incident (onset to +6 h); C4 early ICU onset vs incident (onset to +6 h); C5 septic on arrival (hours 1 to 12) vs incident 12 h before onset; C6 per-stay slopes, incident vs control; C7 to C10 deteriorating vs improving (incident pre-onset; septic on arrival hours 1 to 6; all septic at +24 to +48 h; all septic at onset to +6 h).

**Cross-database rule (unchanged).** Shared: same sign and |delta| at or above 0.147 in both databases; strong shared at 0.33; database-specific when met in one; no signal otherwise. Measurement rates: shared when the incident-to-control ratio is at or above 1.5 (or at or below 1/1.5) in both.

**Data-driven description (no rule attached; reported for reading):** departure timing per channel (first 4-hour bin of a sustained difference, values and rates); order of signs within patients (19 clinical thresholds; present, new, lead time; precedence matrix; the same thresholds in matched control windows); phenotypes at onset (k-means, k = 4, silhouette for 2 to 6, cross-database centroid reproducibility; sizes, mortality and course by cluster); compensation states per hour; heart-rate response per degree of temperature and relative bradycardia; therapy-stratified deltas; selection check (stays measured in every bin); hospital heterogeneity of values and rates in eICU controls; lactate clearance by course; therapy exposure by stratum, course and window.

**Outputs.** Aggregate tables (CSV), figures, `shared_physiology.json`, `stage2_predictor_sets.json`, `hypothesis_results.csv`, a text digest; counts under 11 masked; no patient-level data leave the runtime.

### 10c.2, item 2 (amended wording)

(b) *shared physiology*: the channels the 10c.1 rule marks shared in the pre-onset comparisons C2, C2b or C6, applied to (a).

### 10c.2, new item 5 (proposed)

**Secondary target to consider.** If the deteriorating incident patients show a distinct pre-onset signature (C7 shared channels), stage 2 may carry a prespecified secondary target, onset followed by deterioration, beside the primary onset target; the alarm budget and utility weights for it would be set with the consultants. Decision recorded here before any stage-2 result exists; the primary target is unchanged.
