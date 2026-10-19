// RD6 six-monthly progress report, April to October 2026, as a Word document.
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, AlignmentType,
  BorderStyle, ShadingType, LevelFormat, PageBreak, TableLayoutType, VerticalAlign,
} = require('docx');

const OUT = path.join(__dirname, 'RD6_Progress_Report_Elrggal_Oct2026.docx');
const NAVY = '14213D', TEAL = '0E7C86', GREY = '5C677D', TINT = 'EEF3F7', LINE = 'D5DCE4';
const FONT = 'Calibri';

// ---------- helpers ----------
const P = (text, o = {}) => new Paragraph({
  alignment: o.align || AlignmentType.LEFT, spacing: { after: o.after == null ? 120 : o.after, before: o.before || 0, line: 276 },
  children: Array.isArray(text) ? text : [new TextRun({ text, bold: !!o.bold, italics: !!o.italic, size: o.size || 22, color: o.color || '000000', font: FONT })],
});
const R = (text, o = {}) => new TextRun({ text, bold: !!o.bold, italics: !!o.italic, size: o.size || 22, color: o.color || '000000', font: FONT });
const H1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 160 }, children: [new TextRun({ text, font: FONT })] });
const H2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun({ text, font: FONT })] });
const H3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 }, children: [new TextRun({ text, font: FONT })] });
const bullet = (text, level = 0) => new Paragraph({ numbering: { reference: 'bullets', level }, spacing: { after: 80, line: 276 }, children: Array.isArray(text) ? text : [R(text)] });
const numbered = (text, ref) => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 100, line: 276 }, children: Array.isArray(text) ? text : [R(text)] });
const border = { style: BorderStyle.SINGLE, size: 4, color: LINE };
const borders = { top: border, bottom: border, left: border, right: border };
function tcell(text, width, o = {}) {
  const paras = (Array.isArray(text) ? text : [text]).map((t) => new Paragraph({ spacing: { after: 40, line: 260 }, children: [new TextRun({ text: t, bold: !!o.bold, size: o.size || 20, color: o.color || '000000', font: FONT })] }));
  return new TableCell({ width: { size: width, type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER, margins: { top: 60, bottom: 60, left: 100, right: 100 }, shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: 'auto' } : undefined, children: paras });
}
function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED,
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: headers.map((h, i) => tcell(h, widths[i], { bold: true, fill: NAVY, color: 'FFFFFF' })) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((c, i) => tcell(c, widths[i], { fill: ri % 2 ? TINT : undefined, bold: i === 0 && !!r.boldFirst })) })),
    ],
  });
}
const gap = (after = 160) => new Paragraph({ spacing: { after }, children: [] });

// ---------- content ----------
const TW = 9000; // text width in DXA for A4 with 2.5 cm margins (approx 9,026)
const children = [];

// Title block
children.push(P('EDINBURGH NAPIER UNIVERSITY', { bold: true, size: 28, color: NAVY, align: AlignmentType.CENTER, after: 60 }));
children.push(P('School of Computing, Engineering and the Built Environment', { size: 24, color: GREY, align: AlignmentType.CENTER, after: 240 }));
children.push(P('PhD PROGRESS REPORT - RD6', { bold: true, size: 32, color: NAVY, align: AlignmentType.CENTER, after: 80 }));
children.push(P('April 2026 - October 2026', { size: 24, align: AlignmentType.CENTER, after: 320 }));
children.push(P('Thesis Title:', { bold: true, after: 60 }));
children.push(P('Development of Novel Artificial Intelligence Models for Early Detection and Prediction of Infectious Diseases with a Focus on Sepsis', { bold: true, size: 24, color: NAVY, after: 240 }));
children.push(table(['Field', 'Detail'], [
  ['Candidate', 'Mahmoud Essam Elrggal'],
  ['Director of Studies', 'Prof. Ahmed Al Dubai'],
  ['Second Supervisor', 'Dr Kia Dashtipour'],
  ['School', 'School of Computing, Engineering and the Built Environment'],
  ['University', 'Edinburgh Napier University'],
  ['Reporting period', 'April 2026 - October 2026'],
  ['Report type', 'RD6 - Six-Monthly Progress Review'],
  ['Status of results in this report', 'Preliminary, development-split results on 10,000-stay samples; the full-cohort results are being prepared for journal submission; the sealed holdout has not been opened.'],
], [2600, 6400]));
children.push(gap(240));

// 1 Introduction
children.push(H1('1. Introduction'));
children.push(P('Sepsis, a dysregulated host response to infection that leads to organ dysfunction, affects about 49 million people a year and causes about 11 million deaths. Each hour of delay in antibiotic treatment raises mortality by roughly 4 to 8 per cent, yet the clinical definition (Sepsis-3: suspected infection plus a rise of at least two points on the SOFA organ-failure score) is met only once organ damage has begun. An early warning that arrives hours before the definition is met, and that clinicians trust enough to act on, remains the unmet need this PhD addresses.'));
children.push(P('Published sepsis prediction models report excellent discrimination on their own data and fail where it matters. The winning entry of the PhysioNet 2019 Challenge scored a normalised utility of 0.43 on new patients from the two hospitals it trained on and -0.12 on a hidden third hospital, worse than never alarming (overall official score 0.36; Reyna et al., 2020; Morrill et al., 2020). The Epic Sepsis Model, deployed in hundreds of US hospitals, achieved an AUROC of 0.63 in independent validation against a vendor claim of 0.76 to 0.83, missing 67 per cent of sepsis patients while alerting on 18 per cent of all admissions (Wong et al., 2021). Three causes recur: information from the future leaks into training; models are scored by ranking rather than by whether an alarm would help; and every study defines sepsis its own way.'));
children.push(P('This reporting period therefore re-oriented the programme. An audit of the candidate\'s own earlier pipeline found look-ahead leakage; those models were retired and their results are no longer reported. The work moved from the challenge\'s prepared tables to two raw ICU databases, MIMIC-IV 3.1 and eICU-CRD 2.0, with one shared Sepsis-3 definition, strict hour-by-hour causality, a clinician-defined predictor set, and evaluation by clinical utility with a sealed holdout. The research design became mixed-methods: the quantitative modelling now under way, a qualitative study with the healthcare professionals who would receive the alert (now nearly complete), and, as the future direction, a prospective test on hospital patients.'));

// 2 Aim and objectives
children.push(H1('2. Research Aim and Objectives'));
children.push(P('The overarching aim is unchanged: to develop and evaluate novel AI models that enable early, accurate and interpretable detection and prediction of infectious diseases, with an emphasis on sepsis in the ICU. The central research question, refined this period, is:'));
children.push(P('Using only the information a clinician could have seen at each hour, can a model warn of sepsis six hours ahead with positive clinical utility, and does that utility survive transfer to a hospital system it has never seen?', { bold: true, italic: true, color: NAVY }));
children.push(H2('2.1 Objectives'));
[
  'Build a causal, cross-database pipeline: one Sepsis-3 definition applied identically to MIMIC-IV and eICU, every value used only from the hour it was recorded, hours after onset excluded, and a 20 per cent patient holdout sealed until the protocol is frozen.',
  'Define the predictor set from the bedside: the full clinical picture (659 predictors), with antibiotics and cultures that define the label excluded, prophylactic antibiotics separated by a guideline rule, and clinician-suspicion proxies declared and tested in sensitivity analyses.',
  'Evaluate architectures as hypotheses, including the candidate\'s OSTA-Transformer, against the same model without organ structure, simpler sequence models, the PhysioNet winner\'s approach and self-supervised pretraining, with decision rules fixed before results exist.',
  'Judge models by what would help patients: normalised utility, sensitivity at a fixed false-alarm burden, warning time, calibration and transfer between databases, with patient-level confidence intervals.',
  'Conduct a qualitative study (online interviews and round-table discussions with 20 infectious disease and critical care consultants from different hospitals) on whether they would trust and act on the alert, what explanation they need, and what false-alarm rate they would accept (in progress, nearly complete).',
  'Prepare a prospective, initially silent, test of the model on hospital patients, and disseminate the work through peer-reviewed publication.',
].forEach((t) => children.push(numbered(t, 'objectives')));
children.push(H2('2.2 Research questions'));
children.push(bullet([R('RQ1 Predictors. ', { bold: true }), R('Which information known at hour t carries the signal: vital signs and laboratory values alone, or also treatments, devices, admission context and comorbidity that no public model uses?')]));
children.push(bullet([R('RQ2 Architecture. ', { bold: true }), R('Once causality is enforced, does structuring the model around organ systems add anything over simpler sequence models?')]));
children.push(bullet([R('RQ3 Transfer and trust. ', { bold: true }), R('Does positive utility in one ICU database survive in another, and what would make the clinicians who receive the alarm act on it?')]));

// 3 Methodology
children.push(H1('3. Research Methodology'));
children.push(H2('3.1 Mixed-methods design'));
children.push(table(['Phase', 'Method', 'Output'], [
  ['Phase 1 - Quantitative (in progress)', 'Retrospective modelling on MIMIC-IV and eICU: one label definition, causal features, prespecified architecture and loss comparison, utility-based evaluation, transfer between databases, sealed holdout opened once.', 'A warning model with measured utility and an alarm policy.'],
  ['Phase 2 - Qualitative (in progress, nearly complete)', 'Online semi-structured interviews and round-table discussions with 20 infectious disease and critical care consultants from different hospitals on trust in and use of an AI sepsis alert: whether they would act on it, the explanation they need and the alarm burden they accept.', 'The false-alarm budget, the explanation (overall risk or risk per organ) and the trust conditions the model must meet.'],
  ['Phase 3 - Prospective (future direction)', 'Silent-mode run on live ICU data with alarms logged but not shown, compared with outcomes; then a clinician-facing pilot. Requires ethics approval, a data-governance agreement and a clinical partner.', 'Evidence from real patients, in real time, in a hospital the model never trained on.'],
], [2300, 4300, 2400]));
children.push(gap());
children.push(P('The design is mixed because an alarm that clinicians do not trust saves nobody: the qualitative phase sets the operating constraints that the quantitative model must satisfy before any prospective use.'));

children.push(H2('3.2 Data sources'));
children.push(table(['Database', 'Setting', 'Candidate ICU stays', 'Used this period'], [
  ['MIMIC-IV 3.1', 'Beth Israel Deaconess Medical Center, Boston (one academic centre)', 'about 94,000', 'fixed random sample of 10,000 stays; 8,795 after benchmark exclusions'],
  ['eICU-CRD 2.0', 'about 200 US hospitals (Philips eICU programme)', 'about 201,000', 'fixed random sample of 10,000 stays; 5,710 after benchmark exclusions'],
  ['PhysioNet 2019', 'two US hospitals, challenge-prepared hourly tables', '40,336 patients', 'causal re-evaluation of the earlier architectures only'],
], [1700, 3000, 1800, 2500]));
children.push(gap());
children.push(P('Both raw databases are accessed under PhysioNet credentialing. Patient-level data never leave the analysis environment; only aggregate results are reported.'));

children.push(H2('3.3 Labels, cohorts and splits'));
children.push(bullet('Sepsis-3 onset is derived with the published Yet Another ICU Benchmark (YAIB) pipeline on the ricu concept library, identically for both databases: suspected infection (an antibiotic order and a culture within the Seymour window in MIMIC-IV; antibiotics only in eICU, where cultures are not reliably recorded) plus a SOFA rise of at least two points.'));
children.push(bullet('The prediction task is hourly: does onset fall within the next six hours? Hours after onset are excluded from training and scoring; stays are followed for up to 120 hours.'));
children.push(bullet('20 per cent of patients in each database are sealed as the final holdout by a deterministic patient hash. The remaining 80 per cent form the development set, split by patient into training, validation, calibration and test. No threshold, calibration or model choice ever touches the holdout.'));
children.push(bullet('The 10,000-stay samples are fixed random draws, identical across every run this period, so differences between runs are due to the methods.'));

children.push(H2('3.4 Causality and predictors'));
children.push(P('Every value is used only from the hour it was recorded in the system (store time where available), expires after 24 hours (no expiry for weight and Glasgow Coma Scale components), and is accompanied by a measured-or-not flag and an age channel. The 659 predictors (a few, such as prophylaxis and earlier-admission history, are recorded in MIMIC-IV only and are missing by design in eICU) were defined by the candidate from clinical practice and fall into the following groups:'));
children.push(table(['Group', 'Content'], [
  ['Vital signs and monitoring', 'heart rate, cuff and arterial blood pressures, respiratory rate, oxygen saturation, temperature, end-tidal CO2, central venous pressure, cardiac output, pain and sedation scores'],
  ['Laboratory and blood gas', 'chemistry, haematology with differential, coagulation, lactate, procalcitonin, troponin, BNP, ferritin, D-dimer, amylase, lipase, ammonia, urinalysis, blood gases'],
  ['Scores and derived', 'SOFA (total and per organ), qSOFA, NEWS2, shock index, P/F and S/F ratios, neutrophil-lymphocyte ratio, BMI, changes against the previous value and the baseline, 24-hour extremes and trends'],
  ['Organ support', 'vasopressor dose in noradrenaline equivalents, ventilation mode and settings, oxygen flow, airway status, renal replacement therapy, urine output rate and KDIGO AKI stage'],
  ['Fluids, drugs and devices', 'crystalloids and transfusions, nutrition route, central and arterial lines, urinary catheters, drains; corticosteroids, immunosuppressants, chemotherapy, sedatives, opioids, diuretics, antipyretics'],
  ['Context and history', 'admission source and ICU type, hours in hospital before ICU, prior admissions, prior positive cultures and antibiotics in earlier admissions, 17 comorbidity flags, infection-related phenotypes, imaging orders'],
  ['Prophylactic antibiotics (MIMIC-IV)', 'surgical prophylaxis identified by agent, perioperative timing, duration of 24 hours or less (48 for cardiac surgery), no culture in the suspicion window and no escalation within 72 hours (ASHP/IDSA/SIS/SHEA 2013; Surviving Sepsis Campaign 2021); medical prophylaxis by agent and dose pattern'],
  ['Never used as predictors', 'antibiotics and cultures that define suspected infection; race, ethnicity and insurance (reserved for a planned fairness analysis); anything recorded after the prediction hour'],
], [2600, 6400]));
children.push(gap());
children.push(P('Two inputs are flagged as clinician-suspicion proxies, stress-dose hydrocortisone and imaging orders, because they often encode that the team already suspects sepsis. They are kept, declared, and every result is reported with and without them.'));

children.push(H2('3.5 Models and the prespecified comparison'));
children.push(bullet('Kept from earlier runs: OSTA-Transformer (organ-system-aware temporal attention with cross-organ attention and per-organ risk), output fusion, CNN-Transformer, logistic regression and boosted trees.'));
children.push(bullet('Literature benchmark: path signatures with boosted trees, following the approach of the PhysioNet 2019 winner (signature features of the vital-sign trajectories, then gradient boosting) on the same hours and predictors. It is the winner\'s approach, not a replication of its full pipeline.'));
children.push(bullet('New supervised models: OSTA without organ grouping (the ablation that decides whether organ structure is kept), GRU-D, a causal temporal CNN, a CNN encoder with an OSTA head, and event attention with an OSTA head.'));
children.push(bullet('Self-supervised: a per-channel causal CNN encoder pretrained on up to 75,000 unlabelled stays per database (next-value forecasting, measured-within-six-hours, SOFA organ components and organ worsening at 6, 12 and 24 hours), fine-tuned with OSTA, flat and discrete-time survival heads; site-specific and pooled encoders.'));
children.push(bullet('Losses: utility-weighted cross-entropy (primary), plain cross-entropy and temporal label smoothing, chosen by the rank-average of validation utility and AUPRC.'));
children.push(bullet('Decision rules written before any result: organ structure is kept only if OSTA beats its flat counterpart on validation; the shortlist for the full cohort is the top two or three new models plus the baselines; the full cohort uses three seeds.'));

children.push(H2('3.6 Evaluation'));
children.push(P('The principal panel is the PhysioNet normalised utility (official scorer, unchanged), hourly AUROC and AUPRC, sensitivity at a budget of 0.5 false alarms per patient-day, median warning time before onset, false alarms per patient-day, and calibration (Brier score, calibration slope). Additions this period: warning time relative to the first antibiotic order, transfer rows (each database\'s model scored on the other\'s development patients), a conformal alarm policy with abstention on out-of-distribution hours, a trajectory-rich subset, and the no-proxy sensitivity analysis. All intervals are patient-cluster bootstraps; paired comparisons against OSTA use the same bootstrap.'));

children.push(H2('3.7 Engineering and reproducibility'));
children.push(P('The pipeline is a set of self-contained Colab notebooks with all analysis code embedded and verified by SHA-256 checksums, 212 automated engineering checks (including future-perturbation invariance tests for every model), resumable stages, and a synthetic-data fixture that runs the whole protocol end to end. Nothing calls an external AI service and patient data never leave the environment. Compute this period was Google Colab with an A100 GPU and high-memory runtimes.'));

// 4 Progress
children.push(H1('4. Research Progress (April - October 2026)'));
children.push(H2('4.1 Leakage audit and retirement of the earlier models'));
children.push(P('A line-by-line audit of the PhysioNet pipeline used for the models described in the March 2026 report found three kinds of look-ahead leakage: hours after onset were labelled positive, measurements were carried forward from the time they were taken rather than the time they became available, and treatments that define the label were among the inputs. Those models and their reported metrics have been withdrawn and are not cited in this report; the two manuscripts based on them were withheld from submission.'));
children.push(P('Rebuilt causally, the OSTA-Transformer on the PhysioNet 2019 test set (three-seed ensemble) achieves a patient-level AUROC of 0.81, an hourly AUROC of 0.80 and a normalised utility of 0.22 (0.30 at the conformal operating point, sensitivity 0.70, specificity 0.72). With 1.6 per cent of hours positive, these are the honest baseline figures from which all later work is measured. This finding is itself a contribution: it demonstrates how far leakage inflates published scores and defines the audit that the new pipeline passes by construction.'));

children.push(H2('4.2 The causal cross-database pipeline'));
children.push(P('Sepsis-3 labels and cohorts were extracted for both raw databases with the benchmark pipeline, including a repair of a defect in the pinned benchmark code that halted eICU extraction. The feature pipeline passed through five versions during the period, each adding predictor classes identified from clinical practice (comorbidity and admission context, devices and drug exposures, vasopressor dose, full SOFA and lab deltas, prophylactic antibiotics), to the current 659 predictors with masks and ages. All stages are keyed and resumable, and the raw-table scans are shared between runs.'));

children.push(H2('4.3 Extraction audit'));
children.push(P('A coverage audit against the raw tables showed that much of the apparent transfer problem lies in how data are charted. Values that most published pipelines read from the periodic monitoring tables were, in eICU, largely in the nurses\' charting table; urine output in MIMIC-IV became a rate per kilogram per hour only once each record was tied to the interval it covered. Coverage after the audit (share of patient-hours with a usable value):'));
children.push(table(['Channel', 'Before audit', 'After audit'], [
  ['eICU temperature', '5 %', '94 %'],
  ['eICU blood pressure (cuff and arterial)', '21 %', '99.5 %'],
  ['eICU weight', '6 %', '96 %'],
  ['eICU Glasgow Coma Scale', '62 %', '83 %'],
  ['MIMIC-IV urine output rate', '9 %', '44 %'],
  ['MIMIC-IV Glasgow Coma Scale', '66 %', '78 %'],
], [4500, 2250, 2250]));
children.push(gap());

children.push(H2('4.4 Preliminary results on the development split'));
children.push(P('The following are preliminary results from the prespecified comparison on the MIMIC-IV development test split of the 10,000-stay sample (one run). Every model was scored on identical hours with the official PhysioNet utility scorer. The sealed holdout has not been opened and nothing was tuned on test data. Full results will appear in the manuscript in preparation.'));
children.push(table(['Measure', 'MIMIC-IV development test split'], [
  ['Test split', '1,422 stays, 63,488 hours, 71 sepsis events; 0.65 % of hours positive'],
  ['Models compared', '21: sixteen architectures, loss comparators (cross-entropy and time-to-onset weighted) and a mean ensemble'],
  ['Normalised utility', 'all 21 models above zero, every 95 % CI above zero; range 0.08 to 0.29'],
  ['OSTA-Transformer', '0.23 (95 % CI 0.13 to 0.34)'],
  ['Winner\'s approach (signatures + boosted trees) rebuilt in this pipeline', '0.15 (95 % CI 0.06 to 0.22)'],
  ['Highest point estimates', 'self-supervised CNN encoder with OSTA head 0.29 (0.17 to 0.39); CNN with OSTA head 0.28; mean ensemble 0.28'],
  ['Model chosen by the validation rule', 'GRU-D, 0.19 (0.08 to 0.29)'],
  ['Logistic regression', '0.08 (0.01 to 0.16)'],
  ['Hourly AUROC', '0.72 to 0.84 across models'],
  ['Reference points', 'PhysioNet 2019 winner: 0.43 on new patients from its training hospitals, -0.12 on the hidden hospital; our causal OSTA on PhysioNet: 0.22'],
], [3200, 5800]));
children.push(gap());
children.push(P('On a database built from raw tables with every hour scored causally, every model keeps a positive utility, including the competition winner\'s approach. These are internal results: the counterpart of the winner\'s 0.43 on its own hospitals, one of which (Beth Israel Deaconess, hospital system A of the challenge) is also the MIMIC-IV hospital. The counterpart of the winner\'s -0.12 on an unseen hospital is the sealed cross-database holdout, which has not been opened. The architectures differ more in point estimate than their overlapping intervals can support at this sample size. Transfer is the open problem: MIMIC-IV models scored on eICU development patients give utilities of -0.03 to 0.04 with intervals that include zero (hourly AUROC 0.58 to 0.68). eICU has the weaker antibiotic-only label and is the focus of the native eICU results (running at the time of writing), the full cohort, leave-hospital-out evaluation and label harmonisation.'));

children.push(H2('4.5 Overfitting and the prespecified decisions'));
children.push(P('Training records show that every rich-feature neural model reaches its best validation score within one to three epochs while the training loss keeps falling: a training split contains about 175 septic stays, too few for 300 to 650 predictors. The validation split is also too small to rank models reliably: OSTA and OSTA without organ grouping tie on test (0.23 each) but score 0.12 and 0.28 on validation, and the validation leaders (GRU-D 0.29, TCN 0.29) are mid-table on test.'));
children.push(P('The decision rules fixed before any result were applied on validation only. Organ structure is not supported at this sample size: OSTA did not beat its flat counterpart on validation, and this is reported as found. The loss comparison is undecided (cross-entropy ranked first for OSTA, the utility-weighted loss for the self-supervised model, the time-to-onset loss last for both). The shortlist for the full cohort is GRU-D, the temporal CNN and flat OSTA, plus the baselines and the winner\'s method. One declared deviation was recorded before the full-cohort run: the self-supervised CNN with an OSTA head had the highest test point estimate (0.29) without being chosen on validation, so it is added together with its flat twin as an exploratory pair, labelled as such, with the primary conclusions drawn from the rule-chosen models only; the pair also tests the organ question a second time at scale. The next lever is data: the full cohort has about nine times more sepsis cases and runs with three seeds.'));



children.push(H2('4.6 How the models evolved: why each was built and how they differ'));
children.push(P('The models in this project were not chosen at once. They were built in three stages, and each stage was triggered by a finding from the one before. This section explains what led to each model, how it differs from its predecessors, and what became of it. Table 4 lists every model.'));
children.push(H3('Stage 1, earlier work on PhysioNet 2019: from a general architecture to an organ-structured one'));
children.push(P('The first model was a CNN-Transformer: convolutional layers capture short local trends in the hourly vital signs and laboratory values, and transformer attention (Vaswani et al., 2017) links them across the whole stay. It treats every variable alike and offers no clinical explanation. The OSTA-Transformer was proposed to address that. Clinicians assess sepsis organ by organ, as the SOFA score does (Vincent et al., 1996), so OSTA groups the predictors by organ system, reads each organ over time with its own attention, lets the organs attend to each other, and outputs a sepsis risk together with a risk per organ that a clinician can read. It was trained with a purpose-built loss: focal loss for the rare positive hours (Lin et al., 2017), time weights that emphasise the hours nearest onset, and two organ terms that encourage the per-organ risks to agree with the overall risk and to stay diverse. The leakage audit (Section 4.1; Kapoor and Narayanan, 2023) then showed that both models had been trained with information from the future. Both were withdrawn, and OSTA was rebuilt causally, giving the honest PhysioNet baseline: hourly AUROC 0.80, patient AUROC 0.81 and normalised utility 0.22.'));
children.push(H3('Stage 2, V10 on MIMIC-IV and eICU: can independent organ evidence guide OSTA?'));
children.push(P('Moving to the raw databases raised a design question. OSTA learns how much each organ matters only from the sepsis labels. A bank of small per-organ "observer" networks, each trained on a separate group of patients (the observer-fit split) to estimate risk from one organ\'s measurements, could act like specialty consultations and give OSTA independent evidence. Four ways of using that evidence were compared on identical hours, and the protocol stated in advance that none was to be assumed to win: observer features (the observers\' outputs as extra inputs), output fusion (added to OSTA\'s output through a learned weight), gated attention guidance (the observers steer OSTA\'s cross-organ attention, with learned gates deciding when to trust them), and ungated guidance (the same steering always on, as a control for the gate). Two controls ran alongside: the same models on raw values only, to test whether feature engineering adds anything, and OSTA trained on the observers\' patients as well, to test whether any gain from observers merely reflects extra labelled patients. When the purpose-built OSTA loss was found to have been replaced by plain cross-entropy in the new code, it was restored for fidelity and compared directly.'));
children.push(P('The findings were consistent. No integration beat OSTA: over three seeds the gated minus OSTA AUPRC difference was +0.002 (95 % CI -0.001 to 0.005), and the ungated control was lower than the gated arm. Output fusion was the strongest of the family. Raw values matched engineered features on MIMIC-IV, extra labelled patients did not help, and the restored OSTA loss performed no better than cross-entropy. The training records explained why the variants could not separate: every rich-feature neural model reached its best validation score within one to three epochs, so the chosen checkpoint was close to the shared starting point. The sample, not the architecture, was the limit.'));
children.push(H3('Stage 3, V11: test the idea, learn from the literature, use scarce labels better'));
children.push(P('Stage 3 was designed from those findings. First, the organ hypothesis is tested directly: flat OSTA is the same model with all predictors in one group, and organ structure is kept only if OSTA beats it on validation. Second, models built for irregular ICU data in the sepsis literature (Moor et al., 2021) were added on identical hours: GRU-D, which lets stale measurements decay towards normal (Che et al., 2018); a causal temporal convolutional network (Bai et al., 2018); and the PhysioNet 2019 winner\'s method, path signatures with boosted trees (Morrill et al., 2020). Third, because labelled sepsis cases are scarce, the self-supervised models first learn physiology from unlabelled stays by forecasting values and organ scores (Yèche et al., 2021), a per-channel encoder reads each signal with its own measurement pattern, event attention uses only fresh measurements (Horn et al., 2020), and a discrete-time hazard head uses when onset happens rather than only whether (Gensheimer and Narasimhan, 2019). Finally, the training loss was aligned with the clinical score: the utility-weighted loss weights each hour by what an alarm there is worth, compared against plain cross-entropy and temporal label smoothing (Yèche et al., 2023). The observer features, gated and ungated guidance, the extra-label control and the original OSTA loss were retired; output fusion, the CNN-Transformer, OSTA and the two baselines were kept. The preliminary outcome is in Sections 4.4 and 4.5: all 21 models have positive utility on MIMIC-IV, organ structure is not supported at this sample size, and the full cohort will rank the shortlisted models.'));
children.push(P('Table 4. Every model in the project: what led to it, how it differs, and its status.', { bold: true, after: 80 }));
children.push(table(['Model', 'Stage', 'What led to it', 'How it differs', 'Status'], [
  ['CNN-Transformer', 'Stage 1', 'First architecture: local trends plus long-range attention', 'Treats all variables alike; no clinical structure', 'Leaky version withdrawn; causal version kept as a comparator'],
  ['OSTA-Transformer', 'Stage 1', 'Need for clinical structure and explanation', 'Organ groups, cross-organ attention, risk per organ, purpose-built loss', 'Leaky version withdrawn; causal rebuild is the PhysioNet baseline and a V11 arm'],
  ['Observer features', 'Stage 2', 'Give OSTA independent per-organ evidence', 'Observer outputs as extra inputs', 'No gain; retired'],
  ['Output fusion', 'Stage 2', 'The same evidence without changing OSTA', 'Observer outputs added at the output', 'Strongest of the family; kept'],
  ['Gated attention guidance', 'Stage 2', 'Let the evidence steer which organs OSTA attends to', 'Learned gates on cross-organ attention', 'Equal to OSTA; retired'],
  ['Ungated attention guidance', 'Stage 2', 'Control for the gate', 'Guidance always on', 'Lower than gated; retired'],
  ['Raw-value control', 'Stage 2', 'Does feature engineering add anything?', 'Raw values, masks and ages only', 'Matched engineered features on MIMIC-IV; kept as a control'],
  ['Extra-label control', 'Stage 2', 'Is an observer gain only extra labels?', 'OSTA trained on the observers\' patients too', 'No gain; retired'],
  ['Original OSTA loss', 'Stage 2', 'Fidelity to the original OSTA', 'Focal loss, time weights, organ terms', 'No gain over cross-entropy; retired'],
  ['Logistic regression', 'All', 'Transparent baseline', 'Linear, one hour at a time', 'Kept'],
  ['Boosted trees', 'All', 'Strong tabular baseline (Friedman, 2001)', 'Non-linear, one hour at a time', 'Kept'],
  ['Flat OSTA', 'Stage 3', 'Test the organ hypothesis directly', 'OSTA without organ grouping', 'Beat OSTA on validation; shortlisted'],
  ['GRU-D', 'Stage 3', 'Built for irregular, stale ICU data', 'Recurrent; learned decay of old values', 'Shortlisted'],
  ['Temporal CNN', 'Stage 3', 'Common in the sepsis literature', 'Causal convolutions; fixed look-back', 'Shortlisted'],
  ['Signatures + boosted trees', 'Stage 3', 'Benchmark against the published winner', 'Trajectory summaries, then trees', 'Kept as the benchmark'],
  ['CNN to OSTA', 'Stage 3', 'Read each signal on its own terms', 'Per-channel encoder before OSTA', 'Supervised control for pretraining'],
  ['Event OSTA', 'Stage 3', 'Use real measurements, not carried values', 'Attention to fresh vital signs only', 'Not shortlisted'],
  ['Self-supervised CNN to OSTA and flat twin', 'Stage 3', 'Few labelled sepsis cases', 'Encoder pretrained without labels', 'Added to the full cohort as declared exploratory pair'],
  ['Pooled-encoder twins', 'Stage 3', 'Adaptation across hospital systems', 'Pretrained on both databases', 'Not shortlisted'],
  ['Hazard head', 'Stage 3', 'Use the timing of onset', 'Survival curve at 1 to 24 h', 'Not shortlisted'],
  ['Mean ensemble', 'Stage 3', 'Average out single-model errors', 'Mean of OSTA, CNN-Transformer and the self-supervised model', 'Secondary analysis'],
], [1750, 1000, 2150, 2200, 1900]));
children.push(gap());

children.push(H2('4.7 Publications and dissemination'));
children.push(P('Three manuscripts were submitted during the period (Section 5). The main study on MIMIC-IV and eICU is being written up for submission in 2027 once the full-cohort and sealed-holdout results are available. The candidate presents the work at the SCEBE Research Degree Conference on 20 October 2026 (15-minute talk and questions).'));

children.push(H2('4.8 Deviations from the March 2026 plan'));
children.push(table(['Planned in March 2026', 'What happened', 'Reason'], [
  ['Submit the CNN-Transformer paper (Apr-May) and the OSTA paper (May-Jun)', 'Withheld', 'leakage audit; both architectures are being re-evaluated causally in the current comparison'],
  ['Respond to PLOS ONE reviewer feedback on the AMR review', 'Revised and submitted to the International Journal of Antimicrobial Agents (9 Oct 2026)', 'change of venue after revision'],
  ['External validation of OSTA on MIMIC-IV (Jun-Aug)', 'Became the core programme: MIMIC-IV and eICU, one label, causal pipeline, utility evaluation', 'validation on prepared data would have inherited the leakage'],
  ['Real-time deployment feasibility', 'Deferred to the prospective phase', 'depends on the full-cohort model and the clinician study'],
  ['Clinical stakeholder study with ICU clinicians', 'Now the qualitative phase of a mixed-methods design; in progress and nearly complete', 'its findings set the alarm policy before the holdout is opened'],
  ['Conference presentation', 'SCEBE Research Degree Conference, 20 Oct 2026', 'as planned'],
], [2900, 3300, 2800]));
children.push(gap());

// 5 Publications
children.push(H1('5. Publications Summary'));
children.push(table(['#', 'Title', 'Journal', 'Submitted', 'Status'], [
  ['1', 'Artificial Intelligence in the Diagnosis of Antimicrobial Resistance: Rapid Diagnostics and Imaging Innovations (narrative review)', 'International Journal of Antimicrobial Agents', '9 Oct 2026', 'Technical check'],
  ['2', 'Temporal Patterns and Predictors of Sepsis Onset in ICU Patients: A Retrospective Cohort Study Using PhysioNet Data', 'Frontiers in Medicine', '23 Sep 2026', 'Editorial assignment'],
  ['3', 'Diagnostic Applications of Infrared Thermography Across Infectious Diseases: A Systematic Review with a Subgroup Meta-Analysis', 'JMIR', '18 Jul 2026', 'In review'],
  ['4', 'Early sepsis warning on MIMIC-IV and eICU: causal predictors, clinical utility and transfer (main study)', 'target: critical care informatics journal', 'planned 2027', 'In preparation'],
], [500, 3900, 2000, 1300, 1300]));
children.push(gap());
children.push(P('The cohort study (manuscript 2; 27,101 ICU admissions, 8 per cent sepsis, median onset 100 hours) is the statistical companion to the modelling work: Cox models with a six-hour backshifted label identify early predictors that the deep models then use.'));

// 6 Professional development
children.push(H1('6. Professional Development'));
children.push(table(['Activity', 'Status', 'Relevance to the PhD'], [
  ['Harvard PPCR: Clinical Trials Design, Implementation and Analysis (nine-month programme)', 'Completed, February 2026', 'informs the alarm-policy study, the qualitative phase and the design of the prospective test'],
  ['Iowa State University: Machine Learning Programme', 'Completed, December 2025', 'theoretical grounding for the architecture comparison and model selection'],
  ['DataCamp Python Data Science Career Track', 'In progress since September 2025', 'data engineering for the raw-database pipeline'],
  ['PhysioNet credentialed access to MIMIC-IV 3.1 and eICU-CRD 2.0', 'Held', 'all empirical work this period'],
  ['SCEBE Research Degree Conference, 15-minute presentation', '20 October 2026', 'presentation skills; feedback on model selection and the clinician study design'],
], [3600, 1900, 3500]));
children.push(gap());
children.push(P('Skills developed this period: large-scale extraction from raw ICU databases (DuckDB over multi-gigabyte tables; item dictionaries and unit audits), the ricu and YAIB benchmark tooling, causal and availability-aware feature design, utility-based evaluation and the official PhysioNet scorer, prespecified analysis protocols with sealed holdouts, reproducible notebook engineering with automated checks, and GPU training on cloud runtimes. The candidate also led the clinical specification of the predictor set, the antibiotic classification rule and the proxy analysis, where the candidate\'s clinical training directly shaped the method.'));

// 7 Plan
children.push(H1('7. Plan for the Next Six Months (November 2026 - April 2027)'));
children.push(table(['When', 'Objective', 'Deliverable'], [
  ['Oct - Nov 2026', 'Complete the sixteen-model comparison; apply the prespecified validation rules (loss, organ structure, shortlist)', 'shortlist and rules recorded; comparison section of the manuscript'],
  ['Nov - Dec 2026', 'Full cohort (about 94,000 MIMIC-IV and 201,000 eICU stays), three seeds; leave-hospital-out evaluation across eICU hospitals; pooled multi-site training; label-harmonisation sensitivity (antibiotic-only suspicion on MIMIC-IV)', 'full-cohort development results; compute plan (Colab or a dedicated cloud machine)'],
  ['Jan 2027', 'Freeze the protocol; open the sealed holdout once; fix the alarm policy (sensitivity against false alarms per patient-day); subgroup fairness analysis', 'holdout results; alarm policy; manuscript draft'],
  ['Nov - Dec 2026', 'Complete the qualitative study (20 consultants) and its thematic analysis', 'findings on trust, explanation and alarm burden; input to the alarm policy'],
  ['Feb - Apr 2027', 'Radiology reports as predictors (MIMIC-IV notes, rule-based findings with local text models; no external services)', 'ablation with and without notes'],
  ['From mid-2027', 'Future direction: prepare the silent prospective test on hospital patients (clinical partner, data-governance agreement, ethics)', 'protocol for the prospective phase; submission of the main study'],
], [1700, 4500, 2800]));
children.push(gap());
children.push(H2('7.1 Risks and mitigations'));
children.push(bullet([R('Compute time. ', { bold: true }), R('The full cohort is about nine times the current sample; Colab runs of 12 to 16 hours per experiment are at the limit. Mitigation: a dedicated cloud GPU machine for the full-cohort runs, with the same resumable pipeline.')]));
children.push(bullet([R('Label heterogeneity. ', { bold: true }), R('eICU\'s antibiotic-only suspicion is weaker than MIMIC-IV\'s. Mitigation: report transfer under both definitions and a harmonised antibiotic-only sensitivity analysis.')]));
children.push(bullet([R('Small-sample overfitting. ', { bold: true }), R('Mitigation: scale, self-supervised pretraining, three seeds, and a shortlist chosen on validation rather than test; the full cohort also gives a validation split large enough to rank models.')]));
children.push(bullet([R('Ethics lead time for the prospective phase. ', { bold: true }), R('Mitigation: start the ethics and data-governance applications in early 2027 and build on contacts made during the qualitative study to secure a clinical partner.')]));


// 8 Conclusion
children.push(H1('8. Conclusion'));
children.push(P('The period turned a set of promising but leaky results into an honest, transferable research programme. The candidate audited and retired the earlier models, built a causal pipeline across two raw ICU databases with one shared definition of sepsis and a clinician-defined predictor set, moved evaluation to clinical utility with a sealed holdout, and produced preliminary evidence that, on identical MIMIC-IV hours, all 21 models compared, including the competition winner\'s own method, keep a positive utility, while transfer to a second hospital system remains the open problem. Three manuscripts were submitted. The next period scales the evaluation to the full cohort, opens the holdout once, brings in the clinicians who would receive the alarm, and prepares the prospective test on hospital patients that the whole programme points towards.'));


// 9 References
children.push(H1('9. References'));
children.push(P('Bai S, Kolter JZ, Koltun V. An empirical evaluation of generic convolutional and recurrent networks for sequence modeling. arXiv:1803.01271. 2018.', { size: 20, after: 80 }));
children.push(P('Che Z, Purushotham S, Cho K, Sontag D, Liu Y. Recurrent neural networks for multivariate time series with missing values. Sci Rep. 2018;8:6085.', { size: 20, after: 80 }));
children.push(P('Friedman JH. Greedy function approximation: a gradient boosting machine. Ann Stat. 2001;29:1189-1232.', { size: 20, after: 80 }));
children.push(P('Gensheimer MF, Narasimhan B. A scalable discrete-time survival model for neural networks. PeerJ. 2019;7:e6257.', { size: 20, after: 80 }));
children.push(P('Horn M, Moor M, Bock C, Rieck B, Borgwardt K. Set functions for time series. International Conference on Machine Learning (ICML). 2020.', { size: 20, after: 80 }));
children.push(P('Kapoor S, Narayanan A. Leakage and the reproducibility crisis in machine-learning-based science. Patterns. 2023;4:100804.', { size: 20, after: 80 }));
children.push(P('Lin TY, Goyal P, Girshick R, He K, Dollar P. Focal loss for dense object detection. IEEE International Conference on Computer Vision (ICCV). 2017.', { size: 20, after: 80 }));
children.push(P('Moor M, Rieck B, Horn M, Jutzeler CR, Borgwardt K. Early prediction of sepsis in the ICU using machine learning: a systematic review. Front Med. 2021;8:607952.', { size: 20, after: 80 }));
children.push(P('Morrill JH, Kormilitzin A, Nevado-Holgado AJ, et al. Utilization of the signature method to identify the early onset of sepsis from multivariate physiological time series in critical care monitoring. Crit Care Med. 2020;48:e976-e981.', { size: 20, after: 80 }));
children.push(P('Reyna MA, Josef CS, Jeter R, et al. Early prediction of sepsis from clinical data: the PhysioNet/Computing in Cardiology Challenge 2019. Crit Care Med. 2020;48:210-217.', { size: 20, after: 80 }));
children.push(P('Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. Advances in Neural Information Processing Systems (NeurIPS). 2017.', { size: 20, after: 80 }));
children.push(P('Vincent JL, Moreno R, Takala J, et al. The SOFA (Sepsis-related Organ Failure Assessment) score to describe organ dysfunction/failure. Intensive Care Med. 1996;22:707-710.', { size: 20, after: 80 }));
children.push(P('Wong A, Otles E, Donnelly JP, et al. External validation of a widely implemented proprietary sepsis prediction model in hospitalized patients. JAMA Intern Med. 2021;181:1065-1070.', { size: 20, after: 80 }));
children.push(P('Yeche H, Dresdner G, Locatello F, Huser M, Ratsch G. Neighborhood contrastive learning applied to online patient monitoring. International Conference on Machine Learning (ICML). 2021.', { size: 20, after: 80 }));
children.push(P('Yeche H, Pace A, Ratsch G, Kuznetsova R. Temporal label smoothing for early event prediction. International Conference on Machine Learning (ICML). 2023.', { size: 20, after: 80 }));

// ---------- document ----------
const { Header, Footer, PageNumber } = require('docx');
const STYLES = {
  default: { document: { run: { font: FONT, size: 22 } } },
  paragraphStyles: [
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 30, bold: true, color: NAVY, font: FONT }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 25, bold: true, color: TEAL, font: FONT }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 23, bold: true, color: NAVY, font: FONT }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
  ],
};
const doc = new Document({
  creator: 'Mahmoud Essam Elrggal',
  title: 'RD6 Progress Report, April to October 2026',
  styles: STYLES,
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
      { reference: 'objectives', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { margin: { top: 1418, bottom: 1418, left: 1418, right: 1418 } } },
    headers: { default: new Header({ children: [P('Mahmoud Essam Elrggal  |  RD6 Progress Report  |  April - October 2026', { size: 18, color: GREY, align: AlignmentType.RIGHT, after: 0 })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ['Page ', PageNumber.CURRENT, ' of ', PageNumber.TOTAL_PAGES], size: 18, color: GREY, font: FONT })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log('written', OUT, buf.length, 'bytes'); });
