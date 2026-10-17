## What changed in V10.4 (this `_10`, 18 Oct 2026)

Dr. Mohamed's instruction: **include every feature that could predict sepsis.** Everything below is causal: each value is used only from the hour it was recorded. Everything is in both databases where the data exists. The V10.3 changes (see the next section) are all kept.

**New measurements.**
- Labs: procalcitonin, LDH, D-dimer, ferritin, lipase, BNP, NT-proBNP, anion gap and RDW. MIMIC items are resolved by name, blood specimens only.
- Monitoring: CVP and PEEP.
- Derived: PaO₂/FiO₂ (P/F) and SpO₂/FiO₂ (S/F).

**Admission context**, known at ICU admission.
- Hours in hospital before the ICU.
- Where the patient came from: ED, operating room/PACU, ward, or another hospital.
- ICU type: medical, surgical, cardiac or neuro.
- eICU admitting diagnosis (infection-related, operative), from its entry time. MIMIC-IV has no timestamped admitting diagnosis, so these stay unknown there.

**Invasive devices** (infection sources). Each has a flag plus the hours since it was first documented.
- Central venous line (including PICC), arterial line, dialysis catheter, urinary catheter, and drains/chest tubes.
- Sources: MIMIC procedures (removals ignored); eICU treatments.
- The ETT/tracheostomy from V10.3 is kept.

**Medications** (given or ordered in the last 24 h), from MIMIC prescriptions and infusions and eICU medication orders and infusions.
- Immunosuppressants, chemotherapy, corticosteroids, and hydrocortisone, kept separate because stress-dose hydrocortisone often follows shock.
- Beta-blockers (mask tachycardia), antipyretics (mask fever), sedatives (affect GCS), opioids and diuretics (affect urine).

**Imaging orders** in the last 24 h: MIMIC radiology orders and eICU imaging treatments.

**IV fluids and transfusions**, in the last 6 h and 24 h. A volume counts only once the administration has ended or the volume was charted.

**Deliberately NOT predictors.** Antibiotics and cultures (including specimen site): their timing defines the Sepsis-3 suspicion of infection, i.e. the label itself. They remain for subgroup analysis only.

**Predictors:** 415 (V10.3: 333). The engineering self-tests rose to 170 checks in this notebook.
