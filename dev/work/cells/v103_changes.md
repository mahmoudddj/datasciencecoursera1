## What changed in V10.3 (this `_9`, 18 Oct 2026)

This is the **definitive validation before the full cohort**. It uses the same 10,000-stay samples, the same arms, the same splits, the original OSTA loss (primary) with the BCE comparison, and the utility panel. All changes below were decided before any V10.3 result existed.

**Extraction gaps fixed.** The raw-table stage runs once more because the extraction code changed.
- eICU: nurse-charted temperature (°C and °F, converted), cuff blood pressure (`vitalAperiodic` non-invasive systolic and diastolic), nurse-charted blood pressure, heart rate, respiratory rate and SpO₂, and the admission weight from the admission record, known at unit admission. eICU GCS eye, motor and verbal components are taken only under the "Glasgow coma score" label.
- MIMIC-IV: daily weight and admission weight in pounds (converted). The SpO₂ alarm-limit item was removed from O2Sat.
- New channels:
  - Hct.
  - EtCO2.
  - SaO2: blood-gas saturation, separate from pulse-oximetry O2Sat, as in PhysioNet 2019.
  - Troponin I: MIMIC items are also resolved by label from `d_labitems`.
- `item_dictionary.csv` in the raw stage lists every mapped MIMIC item ID with its label, so you can verify the mapping (no patient data).

**Intubation (ETT or tracheostomy).**
- An intubated verbal GCS stays **unknown**: it is never set to 1 or to normal. An ETT verbal entry now resets the verbal component.
- `Intubated` is a separate charted state:
  - MIMIC: the O2 delivery device, the ETT verbal entry, and intubation/extubation procedures.
  - eICU: the respiratory-care airway type, and mechanical-ventilation/extubation treatment entries.
- `IntubatedHours` counts the documented hours with an airway, as exposure for ventilator-associated infection.
- The "T convention" is kept for a later sensitivity analysis only.

**GCS and carry-forward.**
- GCS and its components are carried until the next measurement (no expiry). The total is the charted total or the sum of three known components, whichever is newer.
- Vitals are carried 24 h (previously 6 h). Labs stay at 24 h. Weight never expires.
- Every value still has its `_age` channel, so the models can discount stale values.
- `GCS_Below15` decides "GCS < 15" from partial components (eye < 4 or motor < 6) without guessing the missing ones.

**qSOFA in two versions.**
- `qSOFA_Total` (strict): all three criteria must be known.
- `qSOFA_MetAmongMeasured`: the criteria met among those that can be decided now.

**Urine.** The rule no longer requires a record in each of the 6 hours.
- Each record documents the urine since the previous record. The volume in the last 6 h is divided by the hours it documents and by weight, when **≥ 4 of 6 hours** are documented.
- New features: `UrineCoverageFraction_6h` and `Urine_HoursSinceLast`.

**Comorbidity flags (causal).** Chronic heart failure, chronic liver disease/cirrhosis, diabetes, metastatic carcinoma, haematological malignancy, immunocompromised, and chronic organ insufficiency (dialysis/ESRD, chronic respiratory failure, home oxygen).
- MIMIC: ICD codes of **earlier** admissions only. Codes of the current admission have no timestamp and are not used.
- eICU: past history and diagnosis entries, each from its entry time onward.
- A flag means "documented", not "absent" when 0.

**Predictors:** 333 (previously 301). The engineering self-tests rose from 142 to 161 checks, covering each change above.
