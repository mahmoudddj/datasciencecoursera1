# Early warning of ICU-acquired sepsis: three questions for the ICU consultants

**Purpose.** We are building and testing a model that warns of sepsis developing in patients already in the ICU, using two public databases (one US academic centre; 200 US hospitals). Before we fix the study design we need three clinical judgements that the data cannot make for us. Each page gives our proposed default, the fact from our own data that prompted it, and three boxes. Please tick one box per page and add a line if you change the default. It should take about ten minutes.

---

## Page 1. A warning that comes after the first antibiotic

**What we found.** In both databases the first antibiotic for the septic episode was ordered a median of 7 hours *before* the hour at which the formal Sepsis-3 definition is met (antibiotics plus a rise of 2 in the organ-failure score). In roughly half of the patients, a model that warns "six hours before Sepsis-3" is therefore warning after the clinician has already started treatment.

**Our proposed default.** A warning that fires after the first antibiotic has been ordered is recorded but earns no credit in the main results. The main results report how many patients were warned *before* the antibiotic and by how many hours. Warnings after the antibiotic are reported separately.

**The question.** Does a warning that arrives after you have already started antibiotics have any clinical value to you, for example as a prompt to review the antibiotic choice, to escalate monitoring, or to involve a senior colleague?

- [ ] **Agree with the default.** Count only warnings before the antibiotic.
- [ ] **Change to:** warnings after the antibiotic also have value, for the following use: ______________________________
- [ ] **Cannot say.**

---

## Page 2. What "getting worse" means after sepsis has started

**What we found.** To study which patients deteriorate after sepsis is recognised, we need a rule that reads the record at a fixed time after onset. We read it at 48 hours and again at 72 hours; the two readings agreed in 98 % of 700 patients, so the horizon is not where the rule is sensitive. The two points where it is sensitive are the vasopressor threshold and how deaths under treatment limitation are counted.

**Our proposed default.** At 48 hours after onset a patient is *deteriorating* if any of the following holds: death in hospital; a rise of at least 2 points in the sum of organ-failure (SOFA) components, comparing the same components at onset and at 48 hours; or vasopressor escalation to at least 0.1 micrograms per kilogram per minute of norepinephrine-equivalent above the dose at onset. A patient is *improving* if alive at discharge, with no such rise and no vasopressor at 48 hours. A patient who leaves the ICU alive before 48 hours is counted as improving and reported separately. 72 hours is reported as a sensitivity check.

**The questions.**

(a) Is this the course definition you recognise?

- [ ] **Agree with the default.**
- [ ] **Change to:** ______________________________
- [ ] **Cannot say.**

(b) Vasopressor threshold: is 0.1 norepinephrine-equivalent the right level to call escalation?

- [ ] **Agree.**
- [ ] **Change to:** ______ micrograms per kilogram per minute.
- [ ] **Cannot say.**

(c) Deaths under treatment limitation (comfort care, do-not-escalate): should they count as deterioration, be excluded, or be reported separately?

- [ ] **Count as deterioration** (default).
- [ ] **Report separately.**
- [ ] **Exclude.**

---

## Page 3. How the alarm threshold should be set

**What we found.** A probability threshold tuned in one hospital lands in the wrong place in another: in our transfer tests some models fell silent, and the published experience is that fixed-score alarms drift with the case mix (one vendor model alerted on 18 % of all inpatients at its fixed score). A threshold set as a *workload*, a fixed fraction of patient-hours that alarm, holds the alarm burden constant by construction; the price is that it does not change when the true rate of sepsis changes. In our development runs the chosen policy produced about one false alarm per three patient-days and caught about half of the events, with a median warning of four hours.

**Our proposed default.** The threshold is set as a workload, a fixed fraction of patient-hours, carried between hospitals, with two consecutive hours above it required before an alarm fires.

**The questions.**

(a) Should the threshold be set as a workload or as a probability?

- [ ] **Workload** (default).
- [ ] **Probability.**
- [ ] **Cannot say.**

(b) What alarm burden would you accept from such a system on your unit?

- [ ] Up to **1** false alarm per 10 patients per day.
- [ ] Up to **3** false alarms per 10 patients per day.
- [ ] Up to **5** false alarms per 10 patients per day (about our current budget).
- [ ] Other: ______ per 10 patients per day.

(c) Should that burden be the same on a surgical and a medical unit?

- [ ] **Same** (default).
- [ ] **Different:** surgical ______, medical ______ per 10 patients per day.
- [ ] **Cannot say.**

---

**Optional.** Your unit type and years in intensive care: ______________________________. Anything else we should know before we fix the design: ______________________________.

Thank you. The answers set three numbers in the study protocol before it is frozen and registered; your names are not recorded.
