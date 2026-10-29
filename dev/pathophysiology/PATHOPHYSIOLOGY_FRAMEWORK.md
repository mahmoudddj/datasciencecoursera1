# Sepsis pathophysiology framework for the early-warning study

**Status: proposal for correction, 29 October 2026.** Written for the candidate and the project partner before anything further is built. Nothing in the protocol, the notebooks or the cohort has been changed on the basis of this document. Where a statement comes from a paper I could check, the paper is cited. Where it comes from clinical teaching or my own reasoning, it is marked *[clinical knowledge; to check]* so that the partner can correct it.

**Why this document exists.** The partner's instruction was to understand the disease and the data before predicting. The stage-1 cohort learned sepsis from the minority of ICU patients who become septic after the sixth ICU hour and treated the patients who arrived septic as if they did not exist. The two databases differ far more in practice than in biology. A model that is to transfer between hospitals must therefore be built on the physiology that the disease produces in every hospital, and it must be told, explicitly, which parts of the data are physiology and which parts are the behaviour of clinicians. This document tries to write down what that physiology is, in the order in which it appears, what our 659 predictor columns can see of it, what treatment does to each sign, and what we expect to find before we look.

---

## 1. Sepsis in the terms our data can see

### 1.1 Definition versus biology

Sepsis-3 defines sepsis as life-threatening organ dysfunction caused by a dysregulated host response to infection, operationalised as a rise of at least 2 SOFA points with suspected infection (Singer et al., JAMA 2016). Our label (`sep3_alt`, from the YAIB benchmark) marks the *onset hour* as the hour at which that operational definition is first met: antibiotics (and, in MIMIC-IV, a culture) mark suspicion; a SOFA rise of 2 marks organ dysfunction; the earlier of the two within the window is the onset.

Three consequences follow, and they shape everything below.

1. **Onset is a recognition time, not a biological time.** The host response begins hours to days before a clinician orders antibiotics. The hours before onset therefore contain two things mixed together: the physiology of a developing host response, and the behaviour of a team that is starting to worry (more vital signs, a lactate, a blood gas, a culture, a chest film). The study must separate them. Fresh measured values describe the physiology. Measurement rates describe the practice.
2. **The organ-dysfunction half of the label is built from our own predictors.** SOFA components (platelets, bilirubin, MAP and vasopressors, creatinine and urine output, GCS, P/F ratio) are both predictors at hour *t* and parts of the outcome at hour *t*+6. That is legitimate for a 6-hour warning, but it means a "warning" model partly learns to recognise organ dysfunction that is already appearing. The physiology that precedes the organ dysfunction (section 2) is the part worth learning.
3. **The suspicion half differs between the databases.** In MIMIC-IV, suspicion needs an antibiotic and a culture close in time. In eICU, it needs only an antibiotic. The eICU onset is therefore earlier and looser, and the eICU arrived-septic group is likely to contain more patients treated empirically for a possible infection. Comparisons between databases must keep this in mind.

### 1.2 The phases of the host response

The sequence below is the consensus picture *[clinical knowledge; reviews cited where found]*.

| Phase | What happens | How long after infection | What it produces in measured data |
|---|---|---|---|
| Local infection | Pathogen recognition (toll-like receptors), local cytokines | hours | Nothing systemic. Site-specific signs only (sputum, urine, wound). |
| Systemic inflammation | TNF-α, IL-1, IL-6 release; endothelial activation; nitric-oxide vasodilatation; capillary leak; neutrophil mobilisation; acute-phase response (CRP, fibrinogen, ferritin); hypothalamic set-point change (fever) | hours to a day | Tachypnoea and tachycardia first; fever or hypothermia; leucocytosis with left shift or leucopenia; procalcitonin rise within 2 to 4 h, CRP within 6 to 12 h *[kinetics: clinical knowledge]* |
| Neuro-endocrine and autonomic stress | Catecholamines, cortisol, glucagon; insulin resistance; loss of vagal tone | hours | Hyperglycaemia; loss of heart-rate variability (reported 25 % fall about 35 h before diagnosis in a small adult cohort, [Ahmad et al. 2009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2721415/)); rising lactate partly from adrenergic glycolysis, not only hypoperfusion |
| Coagulation activation | Tissue-factor expression, fall of protein C and antithrombin, immunothrombosis, consumption | first day | Falling platelets (reported to precede other signs of sepsis in a small burn-injury series, [Arch Surg](https://jamanetwork.com/journals/jamasurgery/article-abstract/595582)); rising INR, PTT, D-dimer; fibrinogen high then low |
| Circulatory failure | Vasoplegia, relative hypovolaemia, myocardial depression, microcirculatory shunting | 12 to 48 h | Falling diastolic pressure first, then MAP; rising shock index; lactate; mottling, slow capillary refill; later troponin and BNP |
| Organ dysfunction | Hypoperfusion plus direct cytokine and mitochondrial injury | 1 to 3 days | Oliguria before creatinine; hypoxaemia and falling P/F; encephalopathy; cholestatic bilirubin rise; thrombocytopenia |
| Immunosuppression | Lymphocyte apoptosis, monocyte deactivation, exhausted T cells | from day 2 onwards, persisting | Lymphopenia; blunted fever and leucocytosis; secondary infections; the stage in which most late deaths occur ([Sepsis: inflammation is a necessary evil, 2019](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6596337/); [Critical Care 2024 narrative review on lymphopenia](https://ccforum.biomedcentral.com/counter/pdf/10.1186/s13054-024-05099-4.pdf)) |

The last row matters for the ICU-acquired group in particular: a patient who has survived surgery, trauma, a stroke or a first septic episode is often already in the immunosuppressed phase when the second infection arrives. Their host response to it is blunted, so the inflammatory signs (fever, leucocytosis) are weaker and the deterioration is quieter and later recognised.

---

## 2. Organ by organ: mechanism, earliest sign, what we hold, what masks it

Each row names the mechanism, the sign in the order in which it appears, the predictor columns that carry it, and the treatments or conditions that hide or imitate it. "Masks" means that a therapy removes the sign while the disease continues; "mimics" means that something other than sepsis produces the same sign. The predictor names are those of the feature registry (`feature_registry.csv`).

### 2.1 Respiratory

- **Mechanism.** Cytokine and chemoreceptor drive, compensation for a metabolic acidosis, and early alveolar-capillary leak. Tachypnoea is the earliest and most sensitive vital sign of sepsis and is the first qSOFA criterion to turn positive *[clinical knowledge]*. Hypoxaemia and a falling P/F ratio come later, with lung injury.
- **Order.** Respiratory rate up; PaCO2 down (compensatory); then O2 saturation down and FiO2 up; then PEEP up and P/F down (ARDS).
- **Our columns.** `Resp` (+ slopes, variance, max 24 h), `PaCO2`, `pH`, `O2Sat`, `SF_Ratio`, `PF_Ratio`, `FiO2`, `PEEP`, `MinuteVentilation`, `TidalVolume`, `SOFA_Resp`, `SIRS_Resp`, `qSOFA_Resp`, `O2_HighFlow`, `O2_NIV`, `Intubated`.
- **Masks.** Controlled mechanical ventilation fixes the respiratory rate; deep sedation removes the drive. In a ventilated patient, minute ventilation, FiO2 and PEEP changes replace the respiratory rate as the signal. Supplemental oxygen hides desaturation (`SF_Ratio` is only interpretable with `SupplementalO2`).
- **Mimics.** Pain, anxiety, heart failure, pulmonary embolism, COPD exacerbation, atelectasis, aspiration.

### 2.2 Cardiovascular

- **Mechanism.** Nitric-oxide mediated vasodilatation lowers systemic vascular resistance; capillary leak lowers effective volume; the heart compensates with rate. Diastolic pressure falls before systolic, so pulse pressure widens *[clinical knowledge]*. Later, septic cardiomyopathy (reversible depression of contractility) adds pump failure. Lactate rises from tissue hypoperfusion, from adrenergic stimulation of glycolysis, and from impaired hepatic clearance.
- **Order.** Heart rate up and diastolic pressure down (hours before); MAP down and shock index up; lactate up; capillary refill slows and skin mottles; vasopressor started; troponin and BNP later.
- **Our columns.** `HR` (+ slopes, variance, max 24 h), `SBP`, `DBP`, `MAP`, `PulsePressure`, `DerivedMAP`, `ShockIndex`, `Lactate` (+ deltas), `CapRefill_Abnormal`, `Skin_Abnormal`, `VasopressorRecorded`, `VasopressorDose_NEeq`, `Vasopressor_HoursSinceFirst`, `InotropeRecorded`, `CVP`, `ScvO2`, `CardiacOutput`, `PAmean`, `TroponinT/I`, `BNP`, `NTproBNP`, `SOFA_CV`, `qSOFA_SBP`, `Rhythm_AF`, `FluidIn_6h/24h`, `NetBalance_24h`.
- **Masks.** Beta-blockers blunt the tachycardia (patients on beta-blockers may present without it, a well-recognised pitfall in older patients: [Relias Media](https://reliasmedia.com/articles/19497-beta-blockers-may-mask-symptoms-in-septic-elders)); vasopressors normalise MAP while the dose rises, so MAP alone is misleading and the dose is the signal; fluid boluses transiently restore pressure and dilute lactate; analgesia and sedation lower heart rate; pacing fixes it.
- **Mimics.** Pain, agitation, bleeding, hypovolaemia from diuresis, atrial fibrillation, cardiogenic or haemorrhagic shock, post-operative vasoplegia, drug effects (vasodilators), epidural analgesia.

### 2.3 Temperature

- **Mechanism.** IL-1, IL-6 and prostaglandin E2 reset the hypothalamic set point. About one in ten septic patients is hypothermic rather than febrile; hypothermia marks a failing response and carries roughly double the mortality (38.1 % vs 17.9 % at 28 days in [Kushimoto et al. 2013](https://ccforum.biomedcentral.com/track/pdf/10.1186/cc13106); independent association confirmed in [Wiewel et al. 2016](https://doi.org/10.1186/s13054-016-1510-3), where the authors attributed it to vascular dysfunction rather than to a weaker immune response). The effect is age-dependent: in the elderly, temperature is not associated with mortality ([Kushimoto et al. 2020](https://doaj.org/article/eb8bb58aa86b4e5bb69e1a4442d4e307)). Older and immunosuppressed patients mount less fever.
- **Order.** Fever or hypothermia is often present at the time the team becomes suspicious, so its lead time is short; the 24-hour maximum and minimum carry more information than the current value because fever spikes are intermittent.
- **Our columns.** `Temp`, `Temp_Max24h`, `Temp_Min24h`, `Temp_Slope/Variance`, `SIRS_Temp`, `TempxHR`.
- **Masks.** Antipyretics (paracetamol, NSAIDs), corticosteroids, renal replacement therapy (extracorporeal cooling), targeted temperature management, an open abdomen or large burns, cold fluids. Measurement site (core versus axillary or temporal) differs by unit and by database.
- **Mimics.** Post-operative inflammation (first 24 to 48 h), drug fever, transfusion reaction, pancreatitis, thromboembolism, neurological fever, heat illness, thyroid storm.

### 2.4 White cells and the immune state

- **Mechanism.** Neutrophil mobilisation from the marrow (leucocytosis with immature forms, "bands"); margination and consumption in severe infection (leucopenia, a worse sign); lymphocyte apoptosis (lymphopenia, the marker of immunosuppression; persistent lymphopenia on day 3 to 4 predicts death *[Drewry et al. 2014; clinical knowledge, to check]*). The neutrophil-to-lymphocyte ratio captures both movements.
- **Order.** Leucocytosis and bandaemia within a day; lymphopenia from day 1 to 2 and persisting; eosinopenia early *[clinical knowledge]*.
- **Our columns.** `WBC` (+ deltas), `Bands`, `Neutrophils`, `Lymphocytes`, `Monocytes`, `Eosinophils`, `Basophils`, `NLR`, `SIRS_WBC`.
- **Masks and confounders.** Corticosteroids raise the neutrophil count and lower lymphocytes on their own; chemotherapy and immunosuppressants cause neutropenia; granulocyte colony-stimulating factor raises counts; haematological malignancy makes counts uninterpretable. Comorbidity and medication flags (`Comorbidity_hematological_malignancy`, `Comorbidity_immunocompromised`, `Med_Corticosteroid_24h`, `Med_Chemotherapy_24h`, `Med_Immunosuppressant_24h`) are needed to read these channels, which is an argument for keeping them available to the study even if they are dropped from a physiology-only predictor set.
- **Data reality.** A differential (bands, lymphocytes) is measured far less often than the total count in both databases; the order itself is a worry signal.

### 2.5 Coagulation and red cells

- **Mechanism.** Tissue-factor driven coagulation, platelet consumption and marrow suppression (thrombocytopenia); consumption of clotting factors (INR and PTT up); fibrinogen high early (acute phase) and low late (consumption); D-dimer up; red-cell distribution width rises with inflammation. Haemoglobin falls with haemodilution and inflammation, not specifically with sepsis.
- **Order.** Platelets fall over the first days; a fall of more than 25 % from baseline, with a nadir around day 5, is associated with higher 30-day mortality ([Platelets 2023](https://www.aminer.cn/pub/645bdf63f11ef10fc6370b9b/diagnostic-and-prognostic-role-of-platelets-in-patients-with-sepsis-and-septic)). The pre-onset timing in adults is not well pinned down in the literature I could reach, which makes it one of the questions our study can answer.
- **Our columns.** `Platelets` (+ `_DeltaPrev`, `_DeltaBaseline`), `INR`, `PTT`, `Fibrinogen`, `DDimer`, `RDW`, `Hgb`, `Hct`, `RBC`, `MCV`, `SOFAproxy_Coag`, `Transfusion_24h`.
- **Masks and confounders.** Heparin (PTT), warfarin and direct anticoagulants (INR), transfusion (platelets, haemoglobin rise), haemodilution after resuscitation (every count falls), surgery and bleeding (consumption without sepsis), cardiopulmonary bypass, liver disease (baseline low platelets and high INR), heparin-induced thrombocytopenia, cytotoxic drugs.

### 2.6 Kidney

- **Mechanism.** Renal hypoperfusion, intrarenal shunting, inflammatory tubular injury. Urine output falls within hours; creatinine, a lagging marker, rises over 24 to 48 h *[clinical knowledge]*.
- **Order.** Oliguria first; creatinine and urea later; renal replacement last.
- **Our columns.** `UrineOutput_6h/24h`, `Urine_mlkg_h_6h`, `Oliguria6h`, `UrineCoverage_6h/24h`, `Creatinine` (+ deltas), `BUN`, `BUNCreatinineRatio`, `AKI_Stage`, `SOFA_Renal`, `SOFAproxy_Creatinine`, `Procedure_RRT_24h`.
- **Masks and confounders.** Diuretics raise urine output and hide oliguria; fluids restore it; renal replacement lowers creatinine; chronic kidney disease raises the baseline; contrast, nephrotoxic antibiotics (vancomycin, aminoglycosides) and rhabdomyolysis injure the kidney without sepsis; absence of a urinary catheter means urine is not measured hourly, so coverage columns must be read with the volumes.

### 2.7 Liver

- **Mechanism.** Cholestasis of sepsis (cytokine inhibition of bile transporters), hypoxic hepatitis in shock, reduced synthesis and capillary leak (albumin falls), impaired lactate clearance.
- **Order.** Bilirubin rises over 24 to 72 h; transaminases rise in shock; albumin falls over days.
- **Our columns.** `Bilirubin_total/direct`, `AST`, `ALT`, `Alkalinephos`, `Albumin` (+ deltas), `Ammonia`, `LDH`, `SOFAproxy_Liver`.
- **Masks and confounders.** Parenteral nutrition, haemolysis, transfusion, pre-existing cirrhosis, biliary obstruction, drug injury, cardiac congestion.

### 2.8 Brain

- **Mechanism.** Sepsis-associated encephalopathy from inflammation, blood-brain barrier disruption and microcirculatory failure; it is common, early, and in the elderly often the presenting feature *[clinical knowledge]*.
- **Order.** Inattention and fluctuating consciousness (delirium) before a measurable GCS fall.
- **Our columns.** `GCS`, `GCS_Below15`, `qSOFA_GCS`, `SOFAproxy_CNS`, `Delirium`, `RASS`, `PainScore`.
- **Masks.** Sedation and opioids make GCS uninterpretable (the verbal score is reset to unknown with an endotracheal tube in our pipeline); dementia, stroke and alcohol withdrawal confound. The CNS channel is only readable in unsedated patients, which the study must stratify.

### 2.9 Metabolism and acid-base

- **Mechanism.** Stress hyperglycaemia (catecholamines, cortisol, insulin resistance), then hypoglycaemia in liver failure or advanced sepsis; lactic acidosis with falling bicarbonate and base excess and a rising anion gap; low ionised calcium and phosphate; hypoalbuminaemia.
- **Our columns.** `Glucose`, `HCO3` (+ deltas), `BaseExcess`, `AnionGap`, `pH` (+ deltas), `CalciumIonized`, `Calcium`, `Phosphate`, `Magnesium`, `Sodium`, `Potassium`, `Chloride`.
- **Masks and confounders.** Insulin, dextrose and feeding (glucose), corticosteroids (glucose up), bicarbonate and renal replacement (acid-base), diabetic ketoacidosis, chloride load from saline (hyperchloraemic acidosis, bicarbonate falls without lactate).

### 2.10 Inflammatory markers

- `CRP` (rises in 6 to 12 h, peaks after about 2 days), `Procalcitonin` (rises in 2 to 4 h, peaks at 12 to 24 h, more specific for bacterial infection, falls with effective treatment), `Ferritin`, `ESR` *[kinetics: clinical knowledge]*. They are measured in a minority of stays and mostly when infection is already suspected, so in our data they are at least as much a practice signal as a physiological one. Steroids lower CRP; renal failure raises procalcitonin.

### 2.11 Autonomic function

Loss of heart-rate variability precedes clinical sepsis by many hours in small adult cohorts and in neonates ([Ahmad et al. 2009](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2721415/); [composite HRV measure, 2012](https://ruor.uottawa.ca/items/d465fd23-785c-4d0c-8ec7-03962320e0e9/full)). Our hourly grid can only approximate it (`HR_Variance3h/6h`, `HR_Skew`), and the approximation is better in eICU, where the monitor feed is aggregated from 5-minute values, than in MIMIC-IV, where the chart holds hourly validated values. This is one channel where a database difference is a measurement artefact and not a biological one, and the study should state so rather than count it as a database-specific finding.

---

## 3. The clinical-process layer in the data

These columns describe what the team did, not what the patient's body did. They are predictive, and they are exactly the part that does not transfer between hospitals.

| Signal | Columns | Why it predicts | Why it does not transfer |
|---|---|---|---|
| Measurement intensity | every `*_age` and `*_observed` column; `LabResults_24h`; the slope and count features | Teams measure more when worried. Completeness of vital signs falls from 100 % of septic patients in the 6 h before onset to 32 % at 24 to 30 h before ([Lauritsen et al. 2019](https://arxiv.org/pdf/1906.02956)) | Charting policy differs by hospital and by database (MIMIC-IV hourly validated vitals; eICU aggregated monitor data and sparser labs) |
| Diagnostic orders | `CultureTaken`, `Imaging_24h`, lactate and blood-gas ages, procalcitonin and CRP ages | A culture or lactate is ordered because infection is suspected: it is almost the label | Culture is part of the MIMIC label and not of the eICU label |
| Treatments near the label | `VasopressorRecorded`, `VasopressorDose_NEeq`, `FluidIn_6h`, `Med_Hydrocortisone_24h` | Resuscitation begins when shock is recognised | Vasopressor thresholds and fluid habits differ |
| Masking treatments | `Med_BetaBlocker_24h`, `Med_Antipyretic_24h`, `Med_Sedative_24h`, `Med_Opioid_24h`, `Med_Corticosteroid_24h`, `Med_Insulin_24h`, `Med_Diuretic_24h`, `Procedure_RRT_24h`, `Intubated` | Needed to read the physiology correctly (section 2) | Prescribing habits differ |
| Exposure and route | `Device_*`, `Device_*_Hours`, `Nutrition_TPN_24h`, `Nutrition_Enteral_24h`, `StoolRecords_24h`, `DrainOutput_24h`, `Intubated`, `IntubatedHours` | Lines, catheters, ventilators and TPN are the routes of ICU-acquired infection | Device use is fairly universal; dwell times and documentation differ |
| Context | `Admit*`, `ICUType_*`, `HospitalHoursBeforeICU`, `PriorAdmissions_1y`, `Comorbidity_*`, `Prophylaxis_*` | Who gets ICU-acquired sepsis (section 4) | Case mix and coding differ |

The proposal in section 8 keeps all of these available to the *description*, because the physiology cannot be read without them, and separates them from the physiology in the *predictor sets*.

---

## 4. Three routes into sepsis in our two databases

### 4.1 Admitted for sepsis (community- or ward-onset, onset at or before ICU hour 0)

The host response is hours to days old when the patient reaches the ICU. Organ dysfunction is at or near its first peak at admission and then either resolves with treatment or progresses. What we see in the first ICU hours is therefore *recognised sepsis plus the effects of resuscitation that has already begun*: fluids (haemodilution of haemoglobin, albumin, platelets; transient restoration of pressure), vasopressors (MAP normal, dose informative), antibiotics (fever may already be falling), oxygen (saturation normal, FiO2 informative).

The Sepsis Endotyping in Emergency Care phenotypes ([Seymour et al., JAMA 2019](https://jamanetwork.com/journals/jama/fullarticle/2733996)) were derived in exactly this group, at presentation: α (about a third of patients; low vasopressor use; 28-day mortality 2 %), β (older, more chronic illness and renal dysfunction; 5 %), γ (more inflammation and pulmonary dysfunction, higher temperature; 15 %), δ (liver dysfunction, shock, high lactate; 32 %). The vital-sign trajectory subphenotypes of [Bhavani et al. 2022](https://link.springer.com/content/pdf/10.1007/s00134-022-06890-z.pdf) use the first 8 hours of temperature, heart rate, respiratory rate and blood pressure and separate groups whose mortality and whose association between fluid volume and outcome differ *[the exact group definitions should be checked against the paper before they are used]*. Both frameworks say the same thing for our purpose: *admitted-for-sepsis patients are not one physiology but several, distinguished mostly by the cardiovascular and hepatic axis (lactate, pressure, bilirubin) and by temperature trajectory*.

**What this group is good for.** It is the largest set of septic hours in both databases and the only set in which the physiology of *established* sepsis can be studied by onset phenotype. It cannot tell us what sepsis looks like before anyone suspects it, because the pre-suspicion hours happened outside the ICU record.

### 4.2 ICU-acquired sepsis after a non-infectious admission (the incident group)

This is the group the warning model is for, and the one the stage-1 cohort was built on. It is about a quarter of ICU sepsis with organ dysfunction (24.4 %, 95 % CI 16.7 to 34.2, [Markwart et al. 2020](https://pubmed.ncbi.nlm.nih.gov/32591853/)) and 12.1 % of all hospital sepsis in the US cohort of Rhee et al. (Crit Care Med 2019), where hospital-onset cases had twice the mortality of community-onset cases (about 34 % versus 17 %, adjusted odds ratio about 2.1) and more comorbidity. Mortality of ICU-acquired sepsis with organ dysfunction was 52.3 % in the Markwart meta-analysis.

Its physiology differs from community-onset sepsis in four ways that matter for a model *[clinical reasoning; literature on hospital-onset severity cited above]*:

1. **The baseline is abnormal and moving.** After surgery, trauma, a stroke or cardiac surgery the patient is already tachycardic, febrile, leucocytotic and oedematous for a day or two, and then improving. The sepsis signal is a *deviation from an improving trajectory*, a "second hit", not a departure from normal. Features relative to the patient's own baseline (the `_DeltaBaseline` and `_DeltaPrev` columns, slopes) should matter more here than absolute values.
2. **The response is blunted.** The first insult has pushed many of these patients into the immunosuppressed phase (section 1.2). Fever and leucocytosis are weaker; hypothermia and lymphopenia are more likely; the first visible sign may be organ dysfunction itself (new oliguria, new confusion, new oxygen requirement).
3. **The route is a device or a ventilator.** Ventilator-associated pneumonia, catheter bloodstream infection, catheter urinary infection, surgical-site and intra-abdominal infection, *Clostridioides difficile*. Device dwell time (`Device_*_Hours`, `IntubatedHours`) is the exposure clock, and the usual onset is day 3 to 7 of the stay rather than day 1.
4. **Recognition is later.** The new organ dysfunction is at first attributed to the primary condition, and the patient may be sedated and ventilated, so two of the three qSOFA signs (respiratory rate, mental state) are unreadable. Later recognition explains part of the higher mortality.

For the all-comers idea this has a direct implication: a model trained on both groups must not be allowed to learn "arrived with fever, lactate and a vasopressor" as *the* sepsis pattern and then miss the quiet ICU-acquired case. The pre-onset signatures of the two groups are hypothesised to differ (section 7).

### 4.3 Early ICU onset (onset between hour 0 and hour 6)

A mixed group: patients admitted for another reason whose sepsis is recognised on arrival, patients whose SOFA rise completed in the ICU after suspicion in the emergency department, and in eICU patients given antibiotics on admission for a possible infection. The partner's suggestion to split the arrived-septic group into *onset at or before hour 0* and *onset in hours 0 to 6* is adopted in the proposal below, because the first subgroup is cleanly "admitted for sepsis" and the second is not.

### 4.4 Transfers

Patients from wards (`AdmitSource_Ward`, long `HospitalHoursBeforeICU`) and from other hospitals are often ward-onset sepsis recognised late; their pre-ICU hours are not in our record. They sit between groups 4.1 and 4.2 and are reported as a stratum, not merged.

---

## 5. Deteriorating and improving courses after onset

### 5.1 Why the split matters

Once sepsis is recognised, treatment begins and the measured physiology becomes a mixture of disease and response. The partner's point is that the deteriorating patients show the disease's own trajectory with the least successful masking, and that this group is the one an early warning is for. The improving patients show what treatment does to each marker, which is equally useful: it tells us which channels are *reversible by therapy* (and therefore confounded in the post-onset window) and which are not.

### 5.2 Markers of each course in the literature

| Course | Marker | Source |
|---|---|---|
| Deteriorating | SOFA rising over the first 48 h (an increase predicts mortality of at least 50 %) | Ferreira et al., JAMA 2001 *[from memory; to check]* |
| Deteriorating | Lactate not clearing by at least 10 % over the first 6 h | Nguyen et al., Crit Care Med 2004 *[from memory; to check]* |
| Deteriorating | Hypothermia at presentation or developing | Kushimoto 2013; Wiewel 2016 (cited above) |
| Deteriorating | Platelet fall over 25 % from baseline, nadir about day 5 | Platelets 2023 (cited above) |
| Deteriorating | Persistent lymphopenia at day 3 to 4 | Drewry et al. 2014 *[from memory; to check]* |
| Deteriorating | Rising vasopressor dose, rising bilirubin, falling urine output despite resuscitation, falling P/F, new delirium | clinical knowledge |
| Improving | Lactate clearance, falling vasopressor dose, fever resolving within 24 to 48 h, urine output recovering, platelets recovering after day 3 to 5, CRP falling by 48 to 72 h, procalcitonin falling by 80 % | clinical knowledge |

### 5.3 Proposed operational definitions (for the partner to decide)

Measured for every septic stay (incident, early-onset, admitted-for-sepsis), from the onset hour:

- **Deteriorating:** hospital death; *or* SOFA (strict total where all six components are known, otherwise the total among measured components, with the number known reported) at onset + 48 h at least 2 points above the SOFA at onset; *or* vasopressor dose at onset + 48 h above the dose at onset with an absolute dose above a threshold the partner sets.
- **Improving:** alive at hospital discharge *and* SOFA at onset + 48 h at or below the SOFA at onset *and* no vasopressor at onset + 48 h.
- **Indeterminate:** everything else, including stays that leave the ICU alive before onset + 48 h (SOFA undefined after ICU discharge; these are *probably* improving and are reported as their own stratum).

Known problems to settle: deaths with treatment limitation (comfort care) are deaths of the disease plus a decision, and MIMIC-IV records code status; a 48 h window may be too early for the hepatic and platelet axis (72 h is an alternative); mortality must be read from the raw admission tables (`admissions.hospital_expire_flag` in MIMIC-IV, `patient.hospitaldischargestatus` in eICU), which the hourly features do not carry.

### 5.4 Therapy exposure as part of the description

For each group and each window (12 h before onset, 0 to 6 h, 6 to 24 h, 24 to 48 h after onset) the study should tabulate: fluid volume, vasopressor presence and norepinephrine-equivalent dose, inotrope, antibiotic start relative to onset, corticosteroid and hydrocortisone, renal replacement, invasive ventilation, transfusion, sedative and opioid, beta-blocker, antipyretic, diuretic, insulin. Without this table, no difference between deteriorating and improving patients in, say, lactate or temperature can be read.

---

## 6. What the two databases can and cannot see

| Aspect | MIMIC-IV 3.1 | eICU-CRD 2.0 | Consequence for the study |
|---|---|---|---|
| Setting | One academic centre, 2008 to 2019 | 208 hospitals, 2014 to 2015, mixed size and teaching status | Hospital-level heterogeneity exists only in eICU; MIMIC estimates carry one hospital's practice |
| Vital signs | Hourly nurse-validated values | Monitor feed aggregated from 5-minute values plus nurse charting | Variability features are not comparable; eICU hourly medians are smoother |
| Temperature | Frequent, site documented | Less frequent in many units | Fever detection sensitivity differs; use 24 h extremes and the fraction of stay-hours with any temperature |
| Labs | Frequent, differentials common | Sparser; differentials, lactate, blood gases less often | Pre-onset lab trajectories will be visible mainly in MIMIC; in eICU the *order* is the signal |
| GCS | Chart items | Nurse charting (optional table) | Coverage differs; neurological channel must be read with sedation state |
| Urine output | Hourly with catheter | Intake-output table, variable | Coverage columns essential |
| Label suspicion | Antibiotic and culture | Antibiotic only | eICU onsets earlier and looser; more empirical-treatment cases in the arrived group |
| Admission diagnosis | None at ICU admission (diagnoses are billing codes at discharge) | Free-text admission diagnosis at entry | "Admitted for sepsis" is directly readable in eICU and only inferable in MIMIC (emergency source, early antibiotics, early cultures) |
| Comorbidities | ICD codes (discharge) and text | Past-history table | Flags are "documented", not "absent" |
| Mortality | `hospital_expire_flag` | `hospitaldischargestatus` | Available in both from raw tables |

Two practical points. First, "fresh" values (measured within the last hour) must be used for every physiological comparison; carried-forward values manufacture flat trajectories and imputed values manufacture database means. Second, every comparison must be reported alongside the number of stays that *had* a fresh value in that bin, because a channel that is measured only in the worried patients will show a spurious "rise" that is really a selection effect.

---

## 7. Hypotheses written before looking

These are the expectations the study will test. Writing them down first turns a descriptive analysis into a check of our understanding. Direction is relative to the comparison group; "shared" means expected in both databases under the 10c rule (same sign and Cliff's delta at least 0.147 in both).

### 7.1 The pre-onset signal (incident 12 h before onset versus controls at matched hours since admission)

| # | Channel group | Expected | Expected lead | Shared? | Masking to stratify by |
|---|---|---|---|---|---|
| H1 | Respiratory rate (fresh), its 6 h slope | Higher and rising | 6 to 12 h, earliest vital sign | Yes | Invasive ventilation, deep sedation (`RASS`, `Med_Sedative_24h`) |
| H2 | Heart rate, shock index; diastolic pressure and pulse pressure | HR higher and rising; DBP lower, pulse pressure wider; MAP only in the last hours | 6 to 12 h; MAP 0 to 6 h | Yes | Beta-blocker, vasopressor, pacing, AF |
| H3 | Temperature | Bimodal: more fever *and* more hypothermia; the mean difference small, the tails and the 24 h range large | 0 to 12 h | Shared in the tails, possibly not in the mean | Antipyretic, steroid, RRT; age |
| H4 | Oxygenation (`O2Sat`, `SF_Ratio`, FiO2) | Lower saturation for the oxygen given; FiO2 rising | 0 to 12 h | Yes | Ventilation mode, supplemental oxygen |
| H5 | Urine output 6 h | Lower | 6 to 12 h, before creatinine | Yes where catheterised | Diuretic, fluids, catheter coverage |
| H6 | Creatinine, BUN | Slightly higher, rising (`_DeltaPrev` positive) | 0 to 6 h; lags urine | Probably MIMIC-stronger (more measured) | CKD, RRT, contrast |
| H7 | Platelets (`_DeltaBaseline`) | Falling from the stay baseline | 12 to 24 h | Yes where measured | Anticoagulant, transfusion, surgery, haemodilution |
| H8 | Lactate | Higher when measured; but mostly *measured more* | 0 to 6 h | Measurement rate shared; value MIMIC-stronger | Fluids, adrenergic drugs, liver disease |
| H9 | WBC, bands, NLR; lymphocytes | WBC and NLR higher or WBC very low; lymphocytes lower | 0 to 12 h | WBC shared; differential sparse | Steroids, chemotherapy, malignancy |
| H10 | Glucose | Higher and more variable | 6 to 12 h | Yes | Insulin, dextrose, steroid, diabetes |
| H11 | Bicarbonate, base excess, anion gap, pH | Lower bicarbonate and base excess, wider gap | 0 to 6 h | Yes where blood gas measured | Saline load, RRT, bicarbonate, ventilation (pH) |
| H12 | Bilirubin, albumin | Bilirubin slightly higher, albumin lower | 12 to 24 h, weak | Weak, MIMIC-stronger | TPN, transfusion, liver disease |
| H13 | GCS, delirium | Lower GCS, more delirium, only in unsedated patients | 6 to 12 h | Shared only in the unsedated stratum | Sedation, opioid, intubation |
| H14 | Heart-rate variability proxies | Lower variance | 12 to 24 h | Not comparable between databases (measurement artefact) | Sampling scheme, pacing, AF |
| H15 | Measurement rates (vitals, lactate, blood gas, CBC, cultures, imaging) | Sharply higher in the 6 h before onset in both databases; MIMIC baseline higher | 0 to 6 h | Shared direction, database-specific level | None (this *is* practice) |
| H16 | Baseline differences at matched hours since admission (devices, surgery, comorbidity, age, prior antibiotics) | Incident patients differ from controls from hour 1 | n/a | Partly | n/a; this is who gets sepsis, not the pre-onset signal |

### 7.2 Admitted-for-sepsis (first 6 ICU hours) versus incident (onset to onset + 6 h)

| # | Expected |
|---|---|
| H17 | Organ dysfunction is similar in kind (both groups meet the same SOFA criterion) but the admitted group has *more* cardiovascular and metabolic dysfunction (lactate, vasopressor dose, fluids) and *more* fever, consistent with the γ and δ phenotypes and with community pathogens in a host that is not yet immunosuppressed. |
| H18 | The incident group has *more* hypothermia and relative leucopenia or lymphopenia, *more* ventilation and sedation, longer device dwell, more renal and respiratory dysfunction relative to cardiovascular dysfunction, and a quieter vital-sign picture: the "blunted second hit". |
| H19 | In eICU the admitted group contains more low-severity (α-like) patients than in MIMIC-IV because the antibiotic-only label admits empirically treated patients; the proportion with lactate above 2 mmol/L or a vasopressor at onset will be lower in eICU. |

### 7.3 Deteriorating versus improving (within each septic group)

| # | Expected |
|---|---|
| H20 | At onset, deteriorating patients have higher lactate, lower platelets, lower temperature (more hypothermia), higher vasopressor dose, lower urine output and higher bilirubin; improving patients have fever with preserved pressure and lactate below 2 mmol/L (α and γ versus δ). |
| H21 | In the 12 h *before* onset, the deteriorating incident patients already show steeper slopes (respiratory rate, heart rate, platelet fall, urine fall) and a lower temperature trajectory than the improving incident patients, i.e. the pre-onset signature is strongest in the patients a warning matters most for. If this holds, "sepsis with deterioration" becomes a candidate secondary target for the warning model. |
| H22 | Therapy exposure differs between the courses (more fluid, more vasopressor, more steroid, earlier RRT in deteriorating patients), so some of H20 is treatment, not disease; the exposure table of section 5.4 is required before any of H20 is interpreted. |
| H23 | Reversible channels (temperature, heart rate, MAP, lactate, glucose) separate the courses within 24 h; slow channels (platelets, bilirubin, creatinine, lymphocytes) separate them at 48 to 72 h. |

### 7.4 Expected non-findings

- No channel will be perfectly shared: eICU will show weaker lab signals because labs are measured less, and the study must say that this is coverage, not biology.
- CRP, procalcitonin, ferritin, D-dimer, fibrinogen, bands, ScvO2 and cardiac output will have too few fresh pre-onset values for a cross-database rule in either direction; they are reported as coverage only.
- Comorbidity flags will differ between groups strongly and tell us nothing about physiology; they are reported as baseline context.

---

## 8. What this changes in the planned pathophysiology study (proposal; not applied)

The 10c section of the protocol, as drafted, has three groups (incident, arrived septic, controls), five comparisons, a cross-database rule, and fresh-only values with measurement rates. The following revisions are proposed for the partner's and candidate's decision before anything is built or changed.

1. **Four septic strata instead of one "arrived septic".** Admitted for sepsis (onset at or before hour 0), early ICU onset (hours 0 to 6), incident (hour 6 or later), and transfers (ward or other hospital) reported as a stratum within each.
2. **Course within every septic stratum.** Deteriorating, improving and indeterminate as in section 5.3, with hospital mortality read from the raw admission tables. Two added comparisons: deteriorating versus improving in the 12 h before onset (incident) and in the first 6 h (admitted), and the same at 24 and 48 h after onset.
3. **Therapy exposure tables** per stratum, course and window (section 5.4), reported next to every physiological comparison.
4. **Stratified reading of masked channels.** Respiratory rate by invasive ventilation; heart rate by beta-blocker and rhythm; MAP by vasopressor (and the dose reported instead); temperature by antipyretic, steroid and age band; GCS by sedation (RASS at or above −2 and no sedative in 24 h); urine output by diuretic and catheter coverage; WBC and lymphocytes by steroid and chemotherapy.
5. **Tails, not only medians, for temperature and glucose:** the fraction of stays with a 24 h maximum above 38.3 °C, a minimum below 36 °C, and both.
6. **Measurement-rate tables as a first-class output,** with the explicit statement, per channel, whether a cross-database difference is physiological or a measurement or coverage artefact (section 6).
7. **Hypotheses H1 to H23 registered in the protocol before the notebook runs,** each reported as supported, not supported or not testable (coverage), so that the study is a test of our understanding and not a search.
8. **A question for the partner on the prediction target.** If H21 holds, should stage 2 carry a secondary target, "sepsis onset followed by deterioration", alongside the primary onset target? The alarm budget and the utility weights from the consultants would then be set for the patients whose course a warning can change.

What this proposal does *not* change: the stage-1b plan and its decision rules, the stage-2 arms already decided, the sealed test and holdout, the 6-hour horizon, the YAIB label. The all-comers cohort for stage 2 (10c.2, item 1) still stands as proposed, but its implementation should wait for the study's result on H17 to H19, because those hypotheses decide whether the admitted-for-sepsis hours help the model learn physiology or teach it to recognise resuscitation.

---

## 9. Questions for the partner and the candidate

1. Are the operational definitions of deteriorating and improving (section 5.3) acceptable, and is 48 h or 72 h the right horizon?
2. Should deaths under treatment limitation be counted as deteriorating, excluded, or reported separately?
3. Is the four-stratum split (section 8, item 1) right, or should transfers be merged with incident?
4. Which of H1 to H23 do you disagree with, and what would you expect instead?
5. Is the sedation threshold for reading GCS (RASS at or above −2, no sedative in 24 h) clinically sensible?
6. Do you want the secondary target "sepsis with deterioration" considered for stage 2 if H21 holds?
7. Is there physiology you expect in ICU-acquired sepsis that this document misses (for example, gut-origin sepsis after enteral feeding failure, or fungal sepsis after prolonged antibiotics)?
8. Should the study report Seymour-like phenotype assignment at onset (lactate, vasopressor, bilirubin, temperature, age, creatinine) as a descriptive stratum?

When these are answered I will revise section 10c of the protocol to match, then rebuild the pathophysiology notebook, on your "go".

---

## 10. References

Papers I could check during this work (abstract or full text), with links:

- Ahmad S et al. Continuous multi-parameter heart rate variability analysis heralds onset of sepsis in adults. PLoS ONE 2009. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2721415/
- Bravi A et al. Monitoring and identification of sepsis development through a composite measure of heart rate variability. PLoS ONE 2012. https://ruor.uottawa.ca/items/d465fd23-785c-4d0c-8ec7-03962320e0e9/full
- Bhavani SV et al. Development and validation of novel sepsis subphenotypes using trajectories of vital signs. Intensive Care Med 2022. https://link.springer.com/content/pdf/10.1007/s00134-022-06890-z.pdf
- Platelet count decline preceding other signs of sepsis in burn injury (small series). Arch Surg. https://jamanetwork.com/journals/jamasurgery/article-abstract/595582
- Kushimoto S et al. The impact of body temperature abnormalities on the disease severity and outcome in patients with severe sepsis. Crit Care 2013. https://ccforum.biomedcentral.com/track/pdf/10.1186/cc13106
- Kushimoto S et al. Body temperature and mortality by age in sepsis. Crit Care 2020. https://doaj.org/article/eb8bb58aa86b4e5bb69e1a4442d4e307
- Lauritsen SM et al. Early detection of sepsis utilizing deep learning on electronic health record event sequences. 2019. https://arxiv.org/pdf/1906.02956
- Markwart R et al. Epidemiology and burden of sepsis acquired in hospitals and intensive care units: a systematic review and meta-analysis. Intensive Care Med 2020. https://pubmed.ncbi.nlm.nih.gov/32591853/
- Moss TJ et al. Signatures of subacute potentially catastrophic illness in the ICU. Crit Care Med 2016. https://pubmed.ncbi.nlm.nih.gov/27452809/
- Machine learning models for analysis of vital signs dynamics: a case for sepsis onset prediction. J Healthc Eng 2019. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6925691/
- Platelet decline and outcome in sepsis and septic shock. Platelets 2023. https://www.aminer.cn/pub/645bdf63f11ef10fc6370b9b/diagnostic-and-prognostic-role-of-platelets-in-patients-with-sepsis-and-septic
- Relias Media. Beta blockers may mask symptoms in septic elders. https://reliasmedia.com/articles/19497-beta-blockers-may-mask-symptoms-in-septic-elders
- Sepsis: inflammation is a necessary evil. Front Cell Dev Biol 2019. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6596337/
- Sepsis-induced immunoparalysis: mechanisms, markers and treatment options (Pickkers group). https://researchgate.net/profile/Peter-Pickkers/publication/262812714_Sepsis-induced_immunoparalysis_Mechanisms_markers_and_treatment_options/links/57b18cc508ae15c76cbad589/Sepsis-induced-immunoparalysis-Mechanisms-markers-and-treatment-options.pdf
- Lymphopenia in sepsis: narrative review. Crit Care 2024. https://ccforum.biomedcentral.com/counter/pdf/10.1186/s13054-024-05099-4.pdf
- Sepsis-induced T cell immunoparalysis. Front Immunol 2022. https://www.frontiersin.org/articles/10.3389/fimmu.2022.891024/full
- Seymour CW et al. Derivation, validation, and potential treatment implications of novel clinical phenotypes for sepsis. JAMA 2019. https://jamanetwork.com/journals/jama/fullarticle/2733996
- Wiewel MA et al. Risk factors, host response and outcome of hypothermic sepsis. Crit Care 2016. https://doi.org/10.1186/s13054-016-1510-3

Cited from memory and marked *[to check]* in the text: Singer et al. JAMA 2016 (Sepsis-3); Rhee et al. Crit Care Med 2019 (hospital-onset sepsis); Ferreira et al. JAMA 2001 (serial SOFA); Nguyen et al. Crit Care Med 2004 (lactate clearance); Drewry et al. Shock 2014 (persistent lymphopenia); Hotchkiss et al. Nat Rev Immunol 2013 (sepsis-induced immunosuppression); Gofton and Young, Nat Rev Neurol 2012 (sepsis-associated encephalopathy).
