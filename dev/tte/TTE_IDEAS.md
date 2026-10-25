# Target trial emulation in MIMIC-IV 3.1 and eICU-CRD 2.0: paper ideas

Prepared 25 Oct 2026 as a side project to the sepsis PhD. The harmonised extraction built for the sepsis work (one clock, one unit, one concept per channel, values usable from the hour they became available) is exactly what an emulation needs for time-varying confounding, so most of the cost is already paid.

## Why target trial emulation here

Hernán and Robins' framework asks, for a causal question, "what randomised trial would answer it?", writes that trial's protocol (eligibility, treatment strategies, assignment, time zero, outcome, follow-up, causal contrast, analysis plan), and then emulates each component with observational data. Its main value in ICU data is that it forces time zero to coincide with eligibility and strategy assignment, which removes immortal-time bias, the error behind most "early treatment saves lives" observational papers. Two features of these databases matter: MIMIC-IV has real timestamps and hospital-wide tables (one centre); eICU has 208 hospitals with minute offsets and coarser treatment records (many centres, so practice variation can be used as an instrument and hospital can be a cluster).

## The strongest single paper: benchmarking emulations against published ICU trials

Emulate five to six completed ICU randomised trials in both databases and report how close the emulated effects come to the trials' estimates. This is the RCT-DUPLICATE design (Franklin, Wang, Schneeweiss) brought to ICU data, which has not been done across two open databases with time-varying treatment. Each emulation is a chapter; the agreement table is the result. It is publishable whether or not the emulations agree, because disagreement with a known trial is informative about the data, and it gives every later question a calibrated method.

Trials to emulate (all with time-stamped exposures in both databases): SMART (balanced crystalloid vs saline), ADRENAL (hydrocortisone in septic shock), SPICE III (dexmedetomidine-based sedation), PEPTIC or REVISE (PPI vs H2RA), TRICC/TRISS (transfusion threshold), STARRT-AKI (RRT timing). CENSER (early norepinephrine) is the seventh if a hypotension time zero can be built from the harmonised vital signs.

Target journals: Intensive Care Medicine, Critical Care Medicine, American Journal of Epidemiology (methods emphasis), JAMIA (data emphasis).

## Candidate questions (each is also a stand-alone paper)

Feasibility counts for all eight come from `TTE_Feasibility_MIMIC_eICU.ipynb`. The proxies there are simple; the protocols below are the real definitions.

### Q1. Early versus delayed vasopressor start
- **Eligibility:** adults, first ICU admission, new hypotension (MAP < 65 mmHg on two readings within 1 h) with no vasopressor yet.
- **Strategies:** A, start norepinephrine within 1 h of the first qualifying MAP; B, no vasopressor in the first hour, fluids allowed, vasopressor at any later time.
- **Time zero:** the first qualifying MAP. **Outcome:** 28-day mortality (MIMIC-IV has date of death; eICU hospital death only). **Follow-up:** 28 days or discharge.
- **Analysis:** cloning, censoring and inverse-probability weighting (each eligible patient is cloned into both strategies and censored when their observed treatment deviates); weights from pooled logistic models on hourly covariates (MAP, lactate, fluids given, SOFA components).
- **Trial it emulates:** CENSER (2019) found earlier shock control with early norepinephrine. **Notes:** confounding by indication is severe; the emulation stands or falls on hourly lactate and fluid data, both present in the harmonised stage.

### Q2. Balanced crystalloid versus saline
- **Eligibility:** adults at ICU admission with no crystalloid yet given in the ICU.
- **Strategies:** A, lactated Ringer or Plasma-Lyte as the first and continued crystalloid for 7 days; B, 0.9 % saline. Mixed use is a deviation (censor).
- **Time zero:** ICU admission. **Outcomes:** hospital death; MAKE30 (death, new RRT, persistent creatinine rise) where creatinine allows.
- **Analysis:** clone-censor-weight; per-protocol effect of sustained fluid type. **Emulates:** SMART (2018), BaSICS (2021), PLUS (2022). **Notes:** in eICU fluid type comes from the infusion and intake tables and is incomplete at many hospitals; report per-hospital completeness and restrict to hospitals where fluids are charted.

### Q3. Hydrocortisone in vasopressor-dependent shock
- **Eligibility:** vasopressor started in the last 24 h, no corticosteroid in the previous 72 h.
- **Strategies:** A, IV hydrocortisone 200 mg/day started within 24 h of the first vasopressor and continued 7 days or until shock reversal; B, no hydrocortisone.
- **Time zero:** first vasopressor. **Outcome:** 28-day or hospital death; shock reversal (vasopressor-free at 7 days) as secondary.
- **Analysis:** sequential trials (one emulated trial per hour of eligibility, pooled) because the decision can be taken at any hour; IPW for treatment and censoring. **Emulates:** ADRENAL (2018), APROCCHSS (2018).

### Q4. Dexmedetomidine versus propofol as the first sedative
- **Eligibility:** invasive ventilation started in the last 12 h, no sedative infusion yet.
- **Strategies:** A, dexmedetomidine as the primary sedative; B, propofol. **Time zero:** first sedative start within 12 h of intubation.
- **Outcomes:** hospital death; ventilator-free days to day 28; delirium where CAM-ICU is charted (MIMIC-IV chartevents).
- **Analysis:** clone-censor-weight with censoring at switch; propensity for the first choice from pre-intubation covariates. **Emulates:** SPICE III (2019), MENDS2 (2021).

### Q5. PPI versus H2RA for stress-ulcer prophylaxis
- **Eligibility:** invasive ventilation, no acid suppression in the previous 24 h, no active GI bleeding.
- **Strategies:** A, PPI started within 24 h of ventilation; B, H2RA. (A third strategy, no prophylaxis, for REVISE.)
- **Outcomes:** clinically important GI bleeding (MIMIC-IV: transfusion plus endoscopy or bleeding diagnosis codes; eICU: diagnosis strings), hospital death, pneumonia and C. difficile as safety outcomes.
- **Analysis:** per-protocol with censoring at crossover; competing risk of death. **Emulates:** PEPTIC (2020), SUP-ICU (2018), REVISE (2024).

### Q6. Restrictive versus liberal transfusion threshold
- **Eligibility:** haemoglobin below 9 g/dL in the ICU, no transfusion in the previous 24 h, no active bleeding.
- **Strategies:** A, transfuse only when haemoglobin falls below 7; B, transfuse when below 9. These are dynamic strategies, so the emulation uses the grace-period version of cloning: a patient follows A while they are not transfused above 7, and so on.
- **Time zero:** first haemoglobin below 9. **Outcome:** hospital death, 90-day death in MIMIC-IV.
- **Emulates:** TRICC (1999), TRISS (2014). **Notes:** the cleanest dynamic-regime example in the set; a methods paper on its own.

### Q7. Early versus delayed renal replacement therapy
- **Eligibility:** KDIGO stage 2 or 3 AKI (creatinine doubling or urine output criteria from the harmonised hourly urine rate) without an emergency indication (potassium above 6, severe acidosis, overload with hypoxaemia).
- **Strategies:** A, RRT within 12 h of stage 2; B, RRT only on an emergency indication or after 72 h.
- **Time zero:** stage 2 met. **Outcome:** 90-day death (MIMIC-IV), hospital death (eICU); RRT dependence at discharge.
- **Analysis:** sequential trials with IPW. **Emulates:** STARRT-AKI (2020), AKIKI (2016), IDEAL-ICU (2018). **Notes:** the urine-output criterion is only possible because the harmonised stage already has an hourly urine rate per kilogram.

### Q8. Antibiotic timing after the first culture
- **Eligibility:** first blood culture drawn in the ICU (microbiologyevents in MIMIC-IV, microLab in eICU), no IV antibiotic in the previous 24 h.
- **Strategies:** A, IV antibiotic within 1 h of the culture; B, within 1 to 6 h. **Time zero:** culture draw.
- **Outcome:** hospital death. **Analysis:** clone-censor-weight, the textbook immortal-time case. **Emulates:** no trial; the Surviving Sepsis 1-hour bundle rests on observational timing studies that mostly did not handle immortal time. A clean emulation that either supports or weakens that evidence is a paper in itself, and it reuses the sepsis project's suspicion-of-infection machinery.

## Two eICU-specific ideas

- **Hospital preference as an instrument.** For Q2, Q4 and Q5 the hospital's prevailing choice (share of patients given the A strategy in the previous year) is a candidate instrument. Report the instrument's strength and the exclusion-restriction argument; compare the IV estimate with the IPW estimate.
- **Transportability.** Estimate the effect in MIMIC-IV, transport it to the eICU population with inverse-odds weights, and compare with the eICU estimate. This is the causal-inference counterpart of the sepsis project's transfer question.

## What every paper needs

- A written protocol (the seven components) before any outcome is looked at, deposited on OSF.
- Negative-control outcomes and exposures to detect residual confounding.
- Quantitative bias analysis for unmeasured confounding (E-values at least).
- The TARGET reporting guideline for emulations (2025), STROBE as the base.
- Cell counts below 11 never leave the runtime; no patient-level data in any document or chat.

## Suggested order

1. Run the feasibility notebook; drop anything *underpowered* in both databases.
2. Write the benchmarking paper's protocol with the five or six trial emulations that survive.
3. Q8 and Q6 as the two stand-alone methods papers (immortal time; dynamic regimes).
4. The eICU transportability paper once the benchmark emulations exist in both databases.
