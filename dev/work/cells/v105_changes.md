## What changed in V10.4–V10.5 (this `_10`, 18–19 Oct 2026)

Dr. Mohamed's instruction: **include every feature that could predict sepsis.** Each value is used only from the hour it was recorded. Each feature is in both databases where the data exist; otherwise it is "unknown" in that database. The V10.3 changes (next section) are kept.

**Measurements**
- Labs:
  - inflammatory and cell counts: procalcitonin, ferritin, ESR; monocytes, eosinophils, basophils, red-cell count; neutrophil-to-lymphocyte ratio;
  - organ markers: LDH, D-dimer, lipase, amylase, ammonia, BNP, NT-proBNP;
  - anion gap and RDW;
  - urine: WBC, nitrite and leukocyte esterase.
- Monitoring:
  - circulation: CVP, PA mean pressure, cardiac output, ScvO₂;
  - ventilation: PEEP, tidal volume, minute ventilation, peak and plateau pressure;
  - oxygen: O₂ flow, high-flow nasal oxygen, non-invasive ventilation, supplemental oxygen;
  - P/F and S/F ratios.
- Mental status and perfusion: RASS, CAM-ICU delirium, pain score, capillary refill, skin mottling/colour, atrial fibrillation.
- Body size: height and BMI.

**Scores and changes**
- Full SOFA with all six organs (vasopressor dose, P/F, urine), plus the change from the best value so far (Sepsis-3's ΔSOFA ≥ 2).
- NEWS2 among measured values.
- Lab change from the previous result and from baseline, for lactate, creatinine, platelets, WBC, bilirubin, BUN, CRP, procalcitonin, pH, bicarbonate, haemoglobin and albumin.
- KDIGO AKI stage.
- 24-hour highest and lowest values (fever, heart rate, respiratory rate, lowest SBP/MAP/SpO₂).
- SBP and SpO₂ trends.

**Treatments and exposures**
- Norepinephrine-equivalent vasopressor dose.
- Devices: central, arterial and dialysis lines, urinary catheter, drains; ETT/tracheostomy and intubated hours.
- Dialysis/CRRT and bronchoscopy.
- Parenteral and enteral nutrition.
- IV fluids, transfusions and net fluid balance; drain output; stool records.
- Medications:
  - immunosuppressants and chemotherapy;
  - corticosteroids, with hydrocortisone kept separate;
  - beta-blockers, antipyretics, sedatives, opioids, diuretics;
  - PPIs, insulin and anticoagulants.
- Imaging orders and lab-draw intensity.

**Patient background**
- 17 chronic comorbidities (TREWScore list plus Elixhauser-style), each from its documentation time.
- Admission source, ICU type, hours in hospital before the ICU, and time in the ICU.
- eICU admitting diagnosis.
- Prior healthcare contact: admissions in the past year, days since the last discharge, an earlier ICU stay, nursing-facility residence, positive cultures and antibiotics in earlier admissions (MIMIC).

**Deliberately not predictors (user decisions, 19 Oct 2026)**
- Antibiotics and cultures of the current admission: they define the Sepsis-3 label.
- Race/ethnicity and insurance: fairness analysis only.
- Code status: it changes whether an infection work-up happens, i.e. label ascertainment.
- Clinical notes and radiology reports: a separate phase after the meeting.

**Predictors:** 655, including masks and measurement ages (V10.3: 333). Engineering self-tests: 184 in this notebook.
