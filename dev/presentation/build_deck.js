// SCEBE Research Degree Conference 2026 deck: Mahmoud Essam Elrggal, 15 min + 5 min questions.
const pptxgen = require('pptxgenjs');
const path = require('path');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const sharp = require('sharp');
const fa = require('react-icons/fa');
const { applyTheme } = require('/root/.claude/skills/synced/d91fe1c6-8d49-4422-b8c8-6dd15fde630e_6b953dd5-185b-425b-91bb-1cf229fc0818/pptx/scripts/apply_theme.js');

const OUT = path.join(__dirname, 'Elrggal_Mahmoud_SCEBE2026.pptx');

const THEME = {
  name: 'SepsisWarning2026',
  headFontFace: 'Cambria',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '14213D', lt1: 'FFFFFF', dk2: '0F2F4A', lt2: 'EEF3F7',
    accent1: '0E7C86', accent2: '2A78D6', accent3: 'EB6834', accent4: '1BAF7A', accent5: '5C677D', accent6: 'E8A33D',
    hlink: '0E7C86', folHlink: '5C677D',
  },
};
const NAVY = '14213D', TEAL = '0E7C86', BLUE = '2A78D6', ORANGE = 'EB6834', AQUA = '1BAF7A', GREY = '5C677D', TINT = 'EEF3F7', WHITE = 'FFFFFF', DKNAVY = '0F2F4A', LINE = 'D5DCE4';

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = 'Mahmoud Essam Elrggal';
pres.title = 'Can a sepsis warning stay useful in a hospital it has never seen?';
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, M = 0.6;
const FOOT = 'Mahmoud Essam Elrggal  |  SCEBE Research Degree Conference, 20 October 2026';

async function icon(Name, color, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(fa[Name], { color: '#' + color, size: px }));
  const buf = await sharp(Buffer.from(svg)).resize(px, px).png().toBuffer();
  return 'image/png;base64,' + buf.toString('base64');
}

// ---------- layouts ----------
pres.defineSlideMaster({
  title: 'TITLE_DARK', background: { color: NAVY },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 1.55, w: W - 2 * M, h: 2.2, fontSize: 36, bold: true, color: WHITE, valign: 'middle', margin: 0 } } },
    { placeholder: { options: { name: 'body', type: 'body', x: M, y: 3.95, w: W - 2 * M, h: 2.9, fontSize: 16, color: WHITE, valign: 'top', margin: 0 } } },
  ],
});
pres.defineSlideMaster({
  title: 'CONTENT', background: { color: WHITE },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.32, w: W - 2 * M, h: 1.05, fontSize: 26, bold: true, color: NAVY, valign: 'middle', margin: 0 } } },
    { text: { text: FOOT, options: { x: M, y: H - 0.42, w: 9.5, h: 0.3, fontSize: 9, color: GREY, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.8, y: H - 0.44, w: 0.8, h: 0.3, fontSize: 11, color: NAVY, align: 'right', bold: true },
});
pres.defineSlideMaster({
  title: 'BACKUP', background: { color: WHITE },
  objects: [
    { text: { text: 'BACKUP', options: { x: W - M - 1.2, y: 0.22, w: 1.2, h: 0.3, fontSize: 10, bold: true, color: TEAL, align: 'right', margin: 0 } } },
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.32, w: W - 2 * M - 1.3, h: 1.05, fontSize: 26, bold: true, color: NAVY, valign: 'middle', margin: 0 } } },
    { text: { text: FOOT, options: { x: M, y: H - 0.42, w: 9.5, h: 0.3, fontSize: 9, color: GREY, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.8, y: H - 0.44, w: 0.8, h: 0.3, fontSize: 11, color: NAVY, align: 'right', bold: true },
});
pres.defineSlideMaster({
  title: 'CLOSING_DARK', background: { color: NAVY },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.4, w: W - 2 * M, h: 1.0, fontSize: 30, bold: true, color: WHITE, valign: 'middle', margin: 0 } } },
    { text: { text: FOOT, options: { x: M, y: H - 0.42, w: 9.5, h: 0.3, fontSize: 9, color: 'B8C4D2', margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.8, y: H - 0.44, w: 0.8, h: 0.3, fontSize: 11, color: WHITE, align: 'right', bold: true },
});

// ---------- helpers ----------
function card(slide, x, y, w, h, opts = {}) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: opts.fill || TINT }, line: { color: opts.line || (opts.fill || TINT), width: 0.75 }, objectName: opts.name || 'card' });
}
function text(slide, str, x, y, w, h, o = {}) {
  slide.addText(str, { x, y, w, h, isTextBox: true, margin: 0, fontSize: o.fontSize || 14, color: o.color || NAVY, bold: !!o.bold, italic: !!o.italic, align: o.align || 'left', valign: o.valign || 'top', fontFace: o.fontFace, lineSpacingMultiple: o.lsm, objectName: o.name || 'text', paraSpaceAfter: o.psa });
}
function bullets(slide, items, x, y, w, h, o = {}) {
  const runs = items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1, paraSpaceAfter: o.psa == null ? 6 : o.psa } }));
  slide.addText(runs, { x, y, w, h, isTextBox: true, margin: 0, fontSize: o.fontSize || 14, color: o.color || NAVY, valign: o.valign || 'top', objectName: o.name || 'bullets' });
}
function stat(slide, x, y, w, h, big, label, o = {}) {
  card(slide, x, y, w, h, { fill: o.fill || TINT, name: 'stat card' });
  text(slide, big, x + 0.2, y + 0.15, w - 0.4, h * 0.5, { fontSize: o.bigSize || 34, bold: true, color: o.color || TEAL, fontFace: 'Cambria', valign: 'middle', name: 'stat number' });
  text(slide, label, x + 0.2, y + h * 0.5 + 0.12, w - 0.4, h * 0.5 - 0.25, { fontSize: o.labelSize || 12, color: o.labelColor || NAVY, valign: 'top', name: 'stat label' });
}
function arrow(slide, x1, y1, x2, y2, color = GREY, width = 1.5) {
  const x = Math.min(x1, x2), y = Math.min(y1, y2), w = Math.abs(x2 - x1), h = Math.abs(y2 - y1);
  slide.addShape(pres.ShapeType.line, { x, y, w: w || 0.001, h: h || 0.001, line: { color, width, endArrowType: 'triangle' }, flipH: x2 < x1, flipV: y2 < y1, objectName: 'arrow' });
}
function iconCircle(slide, data, x, y, d = 0.62, fill = TEAL) {
  slide.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: 'icon circle' });
  slide.addImage({ data, x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52, objectName: 'icon' });
}
function source(slide, str, dark = false) {
  text(slide, str, M, H - 0.78, W - 2 * M, 0.3, { fontSize: 9, color: dark ? 'B8C4D2' : GREY, italic: true, name: 'sources' });
}

(async () => {
  const ICON = {
    heart: await icon('FaHeartbeat', WHITE), clock: await icon('FaClock', WHITE), hospital: await icon('FaHospital', WHITE),
    db: await icon('FaDatabase', WHITE), question: await icon('FaQuestion', WHITE), search: await icon('FaSearch', WHITE),
    lock: await icon('FaLock', WHITE), scale: await icon('FaBalanceScale', WHITE), route: await icon('FaRoute', WHITE),
    pills: await icon('FaPills', WHITE), flask: await icon('FaFlask', WHITE), chart: await icon('FaChartLine', WHITE),
    users: await icon('FaUsers', WHITE), check: await icon('FaCheck', WHITE), cog: await icon('FaCogs', WHITE),
    comment: await icon('FaComments', WHITE), book: await icon('FaBookOpen', WHITE), eye: await icon('FaEyeSlash', WHITE),
    exchange: await icon('FaExchangeAlt', WHITE), stop: await icon('FaBan', WHITE),
  };

  // ================= 1. TITLE =================
  pres.addSection({ title: 'Context and problem' });
  let s = pres.addSlide({ masterName: 'TITLE_DARK', sectionTitle: 'Context and problem' });
  text(s, 'SCEBE RESEARCH DEGREE CONFERENCE  |  20 OCTOBER 2026  |  MERCHISTON CAMPUS', M, 0.75, W - 2 * M, 0.35, { fontSize: 12, color: 'B8C4D2', bold: true, name: 'event line' });
  s.addText('Can a sepsis warning built only from what clinicians knew at the time stay useful in a hospital it has never seen?', { placeholder: 'title' });
  s.addText([
    { text: 'PhD: Development of Novel AI Models for Early Detection and Prediction of Infectious Diseases, with a Focus on Sepsis', options: { fontSize: 16, italic: true, color: 'B8C4D2', breakLine: true, paraSpaceAfter: 14 } },
    { text: 'Mahmoud Essam Elrggal', options: { fontSize: 20, bold: true, breakLine: true } },
    { text: 'Pharmacist  |  PhD candidate, School of Computing, Engineering and the Built Environment, Edinburgh Napier University', options: { fontSize: 14, breakLine: true, paraSpaceAfter: 10 } },
    { text: 'Director of Studies: Prof. Ahmed Al Dubai', options: { fontSize: 14 } },
  ], { placeholder: 'body' });
  s.addNotes('30 s. I am a pharmacist working on AI for sepsis. One sentence of wider context: sepsis is the most common way an infection kills in hospital, and the whole point of my project is a warning that arrives early enough to act on. The title is the question the whole talk answers.');

  // ================= 2. SEPSIS PRIMER =================
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Context and problem' });
  s.addText('Sepsis kills about 11 million people a year, and the hours before antibiotics decide who survives', { placeholder: 'title' });
  stat(s, M, 1.55, 2.6, 1.45, '49 M', 'cases of sepsis each year worldwide');
  stat(s, M + 2.75, 1.55, 2.6, 1.45, '11 M', 'deaths each year, 1 in 5 of all deaths');
  stat(s, M + 5.5, 1.55, 2.6, 1.45, '+4 to 8 %', 'higher mortality for every hour antibiotics are delayed');
  // definition card
  card(s, M + 8.35, 1.55, W - 2 * M - 8.35, 1.45, { fill: NAVY, name: 'definition card' });
  text(s, 'Sepsis-3 definition', M + 8.55, 1.65, 3.4, 0.3, { fontSize: 12, bold: true, color: 'B8C4D2' });
  text(s, 'A suspected infection plus new organ dysfunction: a rise of 2 or more points on the SOFA organ-failure score. "Onset" is the hour both are met.', M + 8.55, 1.95, W - 2 * M - 8.75, 1.0, { fontSize: 12.5, color: WHITE });
  // timeline
  const ty = 4.05, tx0 = M + 1.1, tx1 = W - M - 1.1;
  s.addShape(pres.ShapeType.line, { x: tx0, y: ty, w: tx1 - tx0, h: 0.001, line: { color: LINE, width: 3 }, objectName: 'timeline' });
  const steps = [
    ['Infection starts', 'often unnoticed', GREY],
    ['Physiology drifts', 'heart rate, breathing, labs change hour by hour', TEAL],
    ['Our warning target', '6 hours before onset', BLUE],
    ['Sepsis onset', 'organ dysfunction meets the definition', ORANGE],
    ['Recognition and antibiotics', 'the clock the mortality figures run on', NAVY],
  ];
  steps.forEach((st, i) => {
    const cx = tx0 + (tx1 - tx0) * i / (steps.length - 1);
    s.addShape(pres.ShapeType.ellipse, { x: cx - 0.17, y: ty - 0.17, w: 0.34, h: 0.34, fill: { color: st[2] }, line: { color: WHITE, width: 2 }, objectName: 'timeline point' });
    text(s, st[0], cx - 1.25, ty + 0.32, 2.5, 0.35, { fontSize: 13, bold: true, align: 'center', color: st[2] === GREY ? NAVY : st[2] });
    text(s, st[1], cx - 1.25, ty + 0.66, 2.5, 0.7, { fontSize: 11.5, align: 'center', color: GREY });
  });
  // pharmacist note
  card(s, M, 5.65, W - 2 * M, 0.95, { fill: TINT, name: 'pharmacist note' });
  iconCircle(s, ICON.pills, M + 0.18, 5.82, 0.6, TEAL);
  text(s, 'The pharmacist\'s view: early antibiotics save lives, but antibiotics "just in case" for everyone breed resistance. A warning is only useful if it is right often enough to act on, and early enough to matter.', M + 0.95, 5.72, W - 2 * M - 1.15, 0.85, { fontSize: 13.5, valign: 'middle' });
  source(s, 'Rudd et al., Lancet 2020 (global burden); Singer et al., JAMA 2016 (Sepsis-3); Kumar et al., Crit Care Med 2006 and Seymour et al., NEJM 2017 (hourly delay and mortality).');
  s.addNotes('1.5 min. Context slide for engineers. Define the three words I will keep using: onset, SOFA, and the six-hour horizon. Explain why the warning must come before onset: by the time the definition is met the organ damage has started. The pharmacist point: this is not about giving antibiotics to everyone earlier, because that drives resistance, which is my other research line; it is about the right patients, early.');

  // ================= 3. THE GAP =================
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Context and problem' });
  s.addText('Published sepsis AI scores well on its own data and fails where it matters: the next hospital', { placeholder: 'title' });
  // two evidence cards
  card(s, M, 1.55, 5.95, 2.55, { fill: TINT, name: 'evidence card 1' });
  text(s, 'PhysioNet 2019 Challenge: 104 teams, one scoring rule', M + 0.25, 1.68, 5.5, 0.35, { fontSize: 14, bold: true });
  text(s, '0.36', M + 0.25, 2.1, 1.7, 0.8, { fontSize: 38, bold: true, color: ORANGE, fontFace: 'Cambria', valign: 'middle' });
  text(s, 'winning utility on the two hospitals in training', M + 0.25, 2.9, 2.4, 0.6, { fontSize: 11.5, color: GREY });
  text(s, '-0.12', M + 3.0, 2.1, 1.7, 0.8, { fontSize: 38, bold: true, color: ORANGE, fontFace: 'Cambria', valign: 'middle' });
  text(s, 'same model on the hidden third hospital: worse than no alarm at all', M + 3.0, 2.9, 2.75, 0.8, { fontSize: 11.5, color: GREY });
  text(s, 'Utility: the challenge score that rewards an alarm 6 h before onset and penalises false alarms (0 = never alarming).', M + 0.25, 3.55, 5.5, 0.5, { fontSize: 10.5, italic: true, color: GREY });

  card(s, M + 6.15, 1.55, W - 2 * M - 6.15, 2.55, { fill: TINT, name: 'evidence card 2' });
  text(s, 'Epic Sepsis Model: deployed in hundreds of US hospitals', M + 6.4, 1.68, 5.6, 0.35, { fontSize: 14, bold: true });
  text(s, '0.63', M + 6.4, 2.1, 1.7, 0.8, { fontSize: 38, bold: true, color: ORANGE, fontFace: 'Cambria', valign: 'middle' });
  text(s, 'AUROC in independent validation, against 0.76 to 0.83 claimed by the vendor', M + 6.4, 2.9, 2.6, 0.8, { fontSize: 11.5, color: GREY });
  text(s, '67 %', M + 9.35, 2.1, 1.7, 0.8, { fontSize: 38, bold: true, color: ORANGE, fontFace: 'Cambria', valign: 'middle' });
  text(s, 'of sepsis patients missed, while alerting on 18 % of all admissions', M + 9.35, 2.9, 2.6, 0.8, { fontSize: 11.5, color: GREY });
  text(s, 'A systematic review of 28 models reports AUROC 0.68 to 0.99; almost none were tested prospectively.', M + 6.4, 3.55, 5.6, 0.5, { fontSize: 10.5, italic: true, color: GREY });

  text(s, 'Three things the literature rarely controls', M, 4.35, 8, 0.35, { fontSize: 15, bold: true });
  const reasons = [
    [ICON.eye, 'Future information leaks into training', 'hours after onset labelled positive; values used before they were recorded; treatments that define the label used as inputs'],
    [ICON.chart, 'Scored by ranking, not by whether an alarm helps', 'AUROC on one split of one database; no cost for false alarms, no credit for warning time'],
    [ICON.exchange, 'Each study defines sepsis its own way', 'results cannot be compared, and a model tuned to one definition fails under another'],
  ];
  reasons.forEach((r, i) => {
    const x = M + i * 4.1;
    iconCircle(s, r[0], x, 4.85, 0.6, NAVY);
    text(s, r[1], x + 0.75, 4.82, 3.2, 0.5, { fontSize: 13, bold: true });
    text(s, r[2], x + 0.75, 5.3, 3.2, 1.1, { fontSize: 11.5, color: GREY });
  });
  source(s, 'Reyna et al., Crit Care Med 2020 (challenge results); Wong et al., JAMA Intern Med 2021 (Epic external validation); Fleuren et al., Intensive Care Med 2020 (review).');
  s.addNotes('1.5 min. This is the gap. The best entry of the largest public competition went negative on a hospital it had not seen. The most widely deployed commercial model missed two thirds of sepsis in an independent test. The three reasons at the bottom are the ones my project is built to control; I will show that we have been bitten by the first one ourselves.');

  // ================= 4. THE QUESTION =================
  pres.addSection({ title: 'Aims and approach' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Aims and approach' });
  s.addText('The question the literature has not asked', { placeholder: 'title' });
  card(s, M, 1.5, W - 2 * M, 1.5, { fill: NAVY, name: 'question card' });
  iconCircle(s, ICON.question, M + 0.25, 1.93, 0.65, TEAL);
  text(s, 'Using only the information a clinician could have seen at each hour, can a model warn of sepsis six hours ahead with positive clinical utility, and does that utility survive transfer to a hospital system it has never seen?', M + 1.1, 1.62, W - 2 * M - 1.35, 1.28, { fontSize: 17, bold: true, color: WHITE, valign: 'middle' });
  // asked before vs we ask
  card(s, M, 3.2, 5.9, 1.35, { fill: TINT, name: 'asked before' });
  text(s, 'What has been asked', M + 0.25, 3.3, 5.4, 0.35, { fontSize: 12.5, bold: true, color: ORANGE });
  text(s, 'How high can the AUROC go on one prepared dataset, with one team\'s label definition and whatever inputs were available?', M + 0.25, 3.65, 5.4, 0.85, { fontSize: 13 });
  card(s, M + 6.1, 3.2, W - 2 * M - 6.1, 1.35, { fill: TINT, name: 'we ask' });
  text(s, 'What this project asks', M + 6.35, 3.3, 5.6, 0.35, { fontSize: 12.5, bold: true, color: BLUE });
  text(s, 'Would the alarm have helped this patient, at an acceptable false-alarm burden, and would it still help in the next hospital, under one shared definition of sepsis?', M + 6.35, 3.65, 5.6, 0.85, { fontSize: 13 });
  // RQs
  const rqs = [
    ['RQ1  Predictors', 'Which information known at hour t carries the signal: vital signs and laboratory values alone, or also treatments, devices, admission context and comorbidity that no public model uses?'],
    ['RQ2  Architecture', 'Once causality is enforced, does structuring the model around organ systems add anything over simpler sequence models? A hypothesis to test, not an assumption.'],
    ['RQ3  Transfer and alarm policy', 'Does positive utility in one ICU database survive in another, and which alarm policy gives the most patients helped per false alarm?'],
  ];
  rqs.forEach((r, i) => {
    const x = M + i * 4.1;
    card(s, x, 4.75, 3.9, 1.85, { fill: WHITE, line: LINE, name: 'rq card' });
    text(s, r[0], x + 0.2, 4.85, 3.5, 0.35, { fontSize: 13, bold: true, color: TEAL });
    text(s, r[1], x + 0.2, 5.2, 3.5, 1.35, { fontSize: 12 });
  });
  s.addNotes('1.5 min. Read the question slowly; it is the one thing to remember. The contrast box explains why it is new: the field optimises a ranking score on one dataset; we ask about the alarm and about transfer. Three research questions follow from it: predictors, architecture, transfer.');

  // ================= 5. WHY THIS WAY =================
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Aims and approach' });
  s.addText('Why this way: six choices that go against common practice', { placeholder: 'title' });
  const hdr = (t) => ({ text: t, options: { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: 12, valign: 'middle' } });
  const cell = (t, o = {}) => ({ text: t, options: { fontSize: 11, color: NAVY, valign: 'middle', ...o } });
  const rows = [
    [hdr('Common practice'), hdr('This project'), hdr('Why')],
    [cell('Challenge-prepared tables: PhysioNet 2019, 40 variables, two hospitals'), cell('Raw MIMIC-IV 3.1 (one US academic centre, about 94,000 ICU stays) and eICU-CRD 2.0 (about 200 US hospitals, about 201,000 stays)', { bold: true }), cell('Different hospitals and charting systems make the transfer test real')],
    [cell('Each study defines sepsis its own way'), cell('One Sepsis-3 definition applied identically to both databases (YAIB / ricu, Seymour suspicion window)', { bold: true }), cell('Results are comparable across databases and with the benchmark literature')],
    [cell('Values carried forward; hours after onset labelled positive'), cell('Strict causality: each value used only from the hour it was recorded, expires after 24 h, with "measured?" and "how old?" channels; hours after onset excluded', { bold: true }), cell('No information from the future reaches the model')],
    [cell('40 to 125 variables'), cell('655 clinician-defined predictors: vitals, labs, blood gases, SOFA / qSOFA / NEWS2, ventilation, vasopressor dose, fluids, urine output, devices, drug exposures, imaging orders, admission context, comorbidities', { bold: true }), cell('The whole clinical picture, defined by someone who has treated these patients')],
    [cell('Antibiotics used as predictors'), cell('Antibiotics and cultures that define the label are excluded; prophylactic antibiotics are separated by a guideline rule and kept', { bold: true }), cell('Avoids predicting the label from itself')],
    [cell('AUROC on one split'), cell('Utility, sensitivity at 0.5 or fewer false alarms per patient-day, warning time, calibration; 20 % of patients sealed and opened once', { bold: true }), cell('Measures what would help patients, and cannot be tuned to the test')],
  ];
  s.addTable(rows, { x: M, y: 1.5, w: W - 2 * M, colW: [3.2, 5.6, 3.33], rowH: [0.38, 0.72, 0.6, 0.78, 0.9, 0.62, 0.72], border: { type: 'solid', color: LINE, pt: 0.75 }, fontFace: 'Calibri', margin: 0.06, objectName: 'choices table' });
  source(s, 'Key literature shaping these choices: Reyna 2020 (utility score); Seymour 2016 (suspicion window); van de Water 2024 (YAIB benchmark); Moor et al., eClinicalMedicine 2023 (training across sites improves transfer).');
  s.addNotes('2 min. One row per choice; the middle column is what we do, the right column is why. Spend most time on rows 3 and 5: causality and the exclusion of label-defining antibiotics are what most published models get wrong, and row 4 is where being a clinician matters: the predictor list was written from the bedside, not from what happened to be in a table.');

  // ================= 6. MODELS =================
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Aims and approach' });
  s.addText('Organ-structured attention is a hypothesis we test, not an assumption', { placeholder: 'title' });
  // OSTA diagram (left)
  text(s, 'OSTA: organ-system-aware temporal attention (my architecture)', M, 1.5, 6.3, 0.35, { fontSize: 13.5, bold: true, color: TEAL });
  const organs = ['Respiratory', 'Cardiovascular', 'Renal', 'Hepatic', 'Coagulation', 'Neurological', 'Infection, treatment, context'];
  const ox = M, oy = 1.95, oh = 0.42, og = 0.1;
  organs.forEach((o, i) => {
    const y = oy + i * (oh + og);
    s.addShape(pres.ShapeType.roundRect, { x: ox, y, w: 2.1, h: oh, rectRadius: 0.06, fill: { color: TINT }, line: { color: LINE, width: 0.75 }, objectName: 'organ box' });
    text(s, o, ox + 0.1, y, 1.95, oh, { fontSize: 11, valign: 'middle' });
    arrow(s, ox + 2.1, y + oh / 2, ox + 2.45, y + oh / 2, GREY, 1);
    s.addShape(pres.ShapeType.roundRect, { x: ox + 2.45, y, w: 1.35, h: oh, rectRadius: 0.06, fill: { color: 'D6EEF0' }, line: { color: TEAL, width: 0.75 }, objectName: 'organ attention' });
    text(s, 'attention over hours', ox + 2.5, y, 1.25, oh, { fontSize: 9.5, valign: 'middle', align: 'center', color: TEAL });
  });
  const midY = oy + (organs.length * (oh + og) - og) / 2;
  arrow(s, ox + 3.8, midY, ox + 4.15, midY, GREY, 1.5);
  s.addShape(pres.ShapeType.roundRect, { x: ox + 4.15, y: midY - 0.75, w: 1.05, h: 1.5, rectRadius: 0.06, fill: { color: TEAL }, line: { color: TEAL, width: 0 }, objectName: 'cross organ' });
  text(s, 'cross-organ attention', ox + 4.2, midY - 0.75, 0.95, 1.5, { fontSize: 10.5, bold: true, color: WHITE, align: 'center', valign: 'middle' });
  arrow(s, ox + 5.2, midY, ox + 5.5, midY, GREY, 1.5);
  s.addShape(pres.ShapeType.roundRect, { x: ox + 5.5, y: midY - 0.75, w: 1.0, h: 1.5, rectRadius: 0.06, fill: { color: NAVY }, line: { color: NAVY, width: 0 }, objectName: 'osta output' });
  text(s, 'risk in the next 6 h, plus a risk per organ', ox + 5.55, midY - 0.75, 0.9, 1.5, { fontSize: 10, bold: true, color: WHITE, align: 'center', valign: 'middle' });
  text(s, 'Each organ group is read by its own attention module, then the groups exchange information, mirroring how an ICU team reasons. Output: one overall risk and a risk per organ, so a warning can say which system is failing.', M, 5.75, 6.5, 0.9, { fontSize: 11.5, color: GREY });

  // CNN-Transformer (right)
  const rx = M + 7.0;
  text(s, 'CNN-Transformer (my earlier architecture)', rx, 1.5, 5.3, 0.35, { fontSize: 13.5, bold: true, color: BLUE });
  const stages = [['hourly inputs', TINT, NAVY], ['causal convolutions: patterns over 1 to 12 h', 'DCE6F7', BLUE], ['attention over the whole stay', 'DCE6F7', BLUE], ['risk in the next 6 h', NAVY, WHITE]];
  stages.forEach((st, i) => {
    const y = 1.95 + i * 0.78;
    s.addShape(pres.ShapeType.roundRect, { x: rx, y, w: 5.3, h: 0.5, rectRadius: 0.06, fill: { color: st[1] }, line: { color: st[1] === TINT ? LINE : st[1], width: 0.75 }, objectName: 'cnn stage' });
    text(s, st[0], rx + 0.15, y, 5.0, 0.5, { fontSize: 12, valign: 'middle', align: 'center', color: st[2], bold: i === 3 });
    if (i < stages.length - 1) arrow(s, rx + 2.65, y + 0.5, rx + 2.65, y + 0.78, GREY, 1);
  });
  card(s, rx, 5.15, 5.3, 1.5, { fill: TINT, name: 'comparison card' });
  text(s, 'Compared on identical hours, decision rules fixed in advance', rx + 0.2, 5.22, 5.0, 0.3, { fontSize: 12, bold: true });
  text(s, 'OSTA with and without organ grouping (the ablation that decides), GRU-D, temporal CNN, logistic regression, boosted trees, the challenge winner\'s method (path signatures + boosted trees), and self-supervised pretraining on 150,000 unlabelled stays. Organ structure is kept only if it beats the flat model on the validation split.', rx + 0.2, 5.52, 5.0, 1.1, { fontSize: 11 });
  s.addNotes('1.5 min. Two diagrams, one message: OSTA is the architecture I proposed, and the honest way to defend it is to run the same model without the organ grouping on the same hours. Mention that the challenge winner\'s method is in the comparison as a benchmark, and that the decision rules were written before the results existed.');

  // ================= 7. LEAKAGE RESULT =================
  pres.addSection({ title: 'Results and progress' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results and progress' });
  s.addText('First result: removing information from the future is the biggest single correction', { placeholder: 'title' });
  card(s, M, 1.5, 5.6, 4.95, { fill: TINT, name: 'leak card' });
  iconCircle(s, ICON.search, M + 0.25, 1.7, 0.6, ORANGE);
  text(s, 'What an audit of our own pipeline found', M + 1.0, 1.72, 4.4, 0.55, { fontSize: 14, bold: true, valign: 'middle' });
  bullets(s, [
    'Hours after sepsis onset were labelled positive, so the model learnt to recognise sepsis that had already started.',
    'Measurements were carried forward from the time they were taken, not from the time they were available.',
    'Treatments that are part of the label (antibiotics, cultures) were present among the inputs.',
    'Earlier versions of our models were trained this way; they were retired and are not reported.',
  ], M + 0.25, 2.45, 5.1, 3.0, { fontSize: 12.5, psa: 8 });
  text(s, 'Numbers in the 0.9s in the literature should be read with this in mind.', M + 0.25, 5.6, 5.1, 0.7, { fontSize: 12.5, italic: true, color: NAVY, bold: true });
  // right: causal result
  text(s, 'Rebuilt causally: OSTA on the PhysioNet 2019 test set (3-seed ensemble)', M + 5.85, 1.5, W - 2 * M - 5.85, 0.4, { fontSize: 13.5, bold: true, color: TEAL });
  stat(s, M + 5.85, 2.0, 2.0, 1.5, '0.81', 'patient-level AUROC', { color: BLUE });
  stat(s, M + 7.99, 2.0, 2.0, 1.5, '0.80', 'hourly AUROC', { color: BLUE });
  stat(s, M + 10.13, 2.0, 2.0, 1.5, '0.22', 'normalised utility (0.30 at the conformal threshold)', { color: BLUE, labelSize: 11 });
  card(s, M + 5.85, 3.75, W - 2 * M - 5.85, 2.7, { fill: WHITE, line: LINE, name: 'reading card' });
  text(s, 'How to read these numbers', M + 6.05, 3.85, 6, 0.35, { fontSize: 13, bold: true });
  bullets(s, [
    'Positive hours are 1.6 % of all hours: ranking scores look modest even for a useful model.',
    'Utility 0.22 means the alarms are worth about a fifth of a perfect alarm system, after paying for false alarms; at the conformal threshold (sensitivity 0.70, specificity 0.72) it is 0.30. The challenge winner scored 0.36 in-sample and below zero out of sample.',
    'This is the honest starting point from which every later number is measured.',
  ], M + 6.05, 4.25, W - 2 * M - 6.3, 2.15, { fontSize: 12, psa: 6 });
  s.addNotes('1.5 min. Be direct: we found leakage in our own earlier models and retired them. The causal version scores lower and is the one we stand behind. Explain the utility number in words, because most of the room will not have met it.');

  // ================= 8. COVERAGE =================
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results and progress' });
  s.addText('Making two raw databases speak the same language was most of the work', { placeholder: 'title' });
  s.addChart(pres.ChartType.bar, [
    { name: 'Before the extraction audit', labels: ['eICU temperature', 'eICU blood pressure', 'eICU weight', 'eICU GCS', 'MIMIC-IV urine rate', 'MIMIC-IV GCS'], values: [5, 21, 6, 62, 9, 66] },
    { name: 'After', labels: ['eICU temperature', 'eICU blood pressure', 'eICU weight', 'eICU GCS', 'MIMIC-IV urine rate', 'MIMIC-IV GCS'], values: [94, 99.5, 96, 83, 44, 78] },
  ], {
    x: M, y: 1.5, w: 7.6, h: 4.9, barDir: 'col', barGrouping: 'clustered', barGapWidthPct: 60,
    chartColors: [ORANGE, BLUE], showTitle: true, title: 'Share of patient-hours with a usable value (%)', titleFontSize: 13, titleColor: NAVY, titleFontFace: '+mn-lt',
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 10, dataLabelColor: NAVY, dataLabelFontFace: '+mn-lt', dataLabelFormatCode: '0',
    valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 25, valAxisLabelFontSize: 10, valAxisLabelColor: GREY, valAxisLabelFontFace: '+mn-lt',
    catAxisLabelFontSize: 10.5, catAxisLabelColor: NAVY, catAxisLabelFontFace: '+mn-lt', valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: 'none' },
    showLegend: true, legendPos: 'b', legendFontSize: 11, legendColor: NAVY, legendFontFace: '+mn-lt', objectName: 'coverage chart',
  });
  card(s, M + 7.85, 1.5, W - 2 * M - 7.85, 4.9, { fill: TINT, name: 'coverage notes' });
  text(s, 'What the audit changed', M + 8.05, 1.62, 4, 0.35, { fontSize: 14, bold: true });
  bullets(s, [
    'Samples of 10,000 ICU stays per database: 8,795 MIMIC-IV and 5,710 eICU stays after the benchmark\'s exclusions.',
    '76 raw measurement channels mapped item by item, with every mapping checked against row counts and a unit audit.',
    'eICU nurse-charted vitals, cuff pressures and weights were in different tables from the ones most pipelines read.',
    'Urine output became a rate per kg only once each record was tied to the interval it covered.',
    'Nothing here is a model change; it is where the transfer problem actually lives.',
  ], M + 8.05, 2.05, W - 2 * M - 8.25, 4.2, { fontSize: 12, psa: 7 });
  s.addNotes('1 min. The chart is coverage, not performance: the fraction of patient-hours where a value exists. Before the audit a third of eICU had no temperature at all. The message: the transfer problem is largely a data-representation problem, and that is where a clinician reading the raw tables earns their keep.');

  // ================= 9. UTILITY RESULT =================
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results and progress' });
  s.addText('On MIMIC-IV the warning has positive utility, where the challenge winner collapsed on an unseen hospital', { placeholder: 'title' });
  const labs = ['Challenge winner, hospitals in training', 'Challenge winner, hidden third hospital', 'Our causal OSTA, PhysioNet test', 'Our best model, MIMIC-IV development test'];
  s.addChart(pres.ChartType.bar, [
    { name: 'Normalised utility', labels: labs, values: [0.36, -0.12, 0.22, 0.18] },
  ], {
    x: M, y: 1.5, w: 7.3, h: 4.6, barDir: 'bar', barGrouping: 'clustered', barGapWidthPct: 45,
    chartColors: [ORANGE, ORANGE, BLUE, BLUE], showTitle: true, title: 'Normalised utility (1 = perfect alarms, 0 = never alarming, below 0 = worse than silence)', titleFontSize: 12, titleColor: NAVY, titleFontFace: '+mn-lt',
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 11, dataLabelColor: NAVY, dataLabelFontBold: true, dataLabelFontFace: '+mn-lt', dataLabelFormatCode: '0.00',
    valAxisMinVal: -0.2, valAxisMaxVal: 0.5, valAxisMajorUnit: 0.1, valAxisLabelFontSize: 10, valAxisLabelColor: GREY, valAxisLabelFontFace: '+mn-lt', valAxisLabelFormatCode: '0.0',
    catAxisLabelFontSize: 11, catAxisLabelColor: NAVY, catAxisLabelFontFace: '+mn-lt', catAxisOrientation: 'maxMin', catAxisLabelPos: 'low', valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: 'none' },
    showLegend: false, objectName: 'utility chart',
  });
  // manual legend (two swatches)
  s.addShape(pres.ShapeType.rect, { x: M + 0.3, y: 6.2, w: 0.28, h: 0.2, fill: { color: ORANGE }, line: { color: ORANGE, width: 0 }, objectName: 'legend swatch' });
  text(s, 'Published challenge entry (Reyna et al. 2020)', M + 0.68, 6.14, 3.3, 0.32, { fontSize: 11, valign: 'middle' });
  s.addShape(pres.ShapeType.rect, { x: M + 4.1, y: 6.2, w: 0.28, h: 0.2, fill: { color: BLUE }, line: { color: BLUE, width: 0 }, objectName: 'legend swatch' });
  text(s, 'This project (causal evaluation)', M + 4.48, 6.14, 2.8, 0.32, { fontSize: 11, valign: 'middle' });
  card(s, M + 7.55, 1.5, W - 2 * M - 7.55, 4.9, { fill: TINT, name: 'mimic panel' });
  text(s, 'MIMIC-IV development test split', M + 7.75, 1.6, 4.3, 0.35, { fontSize: 14, bold: true });
  text(s, '1,422 stays, 63,488 hours, 71 sepsis events; 0.65 % of hours are positive', M + 7.75, 1.95, 4.3, 0.5, { fontSize: 11.5, color: GREY });
  stat(s, M + 7.75, 2.5, 2.05, 1.25, '0.81', 'hourly AUROC, 3 seeds (SD 0.01)', { fill: WHITE, color: BLUE, bigSize: 28, labelSize: 10.5 });
  stat(s, M + 9.95, 2.5, 2.0, 1.25, '5 h', 'median warning before onset', { fill: WHITE, color: BLUE, bigSize: 28, labelSize: 10.5 });
  stat(s, M + 7.75, 3.9, 2.05, 1.25, '1 in 2', 'sepsis events caught at 0.5 false alarms per patient-day', { fill: WHITE, color: BLUE, bigSize: 28, labelSize: 10.5 });
  stat(s, M + 9.95, 3.9, 2.0, 1.25, '0.18', 'utility, 95 % CI 0.08 to 0.27', { fill: WHITE, color: BLUE, bigSize: 28, labelSize: 10.5 });
  text(s, 'Development split of a 10,000-stay sample, 1 to 3 seeds. The sealed 20 % holdout has not been opened. Our run of the winner\'s own method on MIMIC-IV is in progress.', M + 7.75, 5.3, W - 2 * M - 7.95, 1.0, { fontSize: 10.5, italic: true, color: GREY });
  s.addNotes('1.5 min. The chart is the slide. Orange is the published competition result; blue is ours. The point is not that 0.18 is high; it is that it is positive on a database the model was built from raw tables, with every hour scored causally, whereas the best competition entry went negative the moment it left its training hospitals. State the caveats on the right out loud: development split, small sample, holdout still sealed.');

  // ================= 10. OVERFITTING / SCALE =================
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Results and progress' });
  s.addText('On 10,000 stays every architecture overfits within three epochs: the next lever is scale, not a new model', { placeholder: 'title' });
  card(s, M, 1.5, 6.0, 4.9, { fill: TINT, name: 'evidence card' });
  text(s, 'What the training records show', M + 0.2, 1.62, 5.6, 0.35, { fontSize: 14, bold: true });
  const ev = [
    ['1 to 3', 'epochs to the best validation score for every rich-feature neural model, while training loss keeps falling'],
    ['175', 'septic stays in a training split: too few for 300 to 600 predictors'],
    ['0.80 to 0.81', 'AUROC for OSTA, CNN-Transformer, output fusion and gated variants: differences smaller than seed noise (SD 0.012)'],
    ['= 0', 'difference between OSTA with and without attention gates: the checkpoint is the first epoch either way'],
  ];
  ev.forEach((e, i) => {
    const y = 2.1 + i * 1.05;
    text(s, e[0], M + 0.2, y, 1.6, 0.8, { fontSize: 22, bold: true, color: ORANGE, fontFace: 'Cambria', valign: 'middle' });
    text(s, e[1], M + 1.9, y, 3.9, 0.95, { fontSize: 12, valign: 'middle' });
  });
  card(s, M + 6.25, 1.5, W - 2 * M - 6.25, 4.9, { fill: WHITE, line: LINE, name: 'response card' });
  text(s, 'What this changes', M + 6.45, 1.62, 5.5, 0.35, { fontSize: 14, bold: true });
  const resp = [
    [ICON.db, 'Full cohort', 'about 94,000 MIMIC-IV and 201,000 eICU stays: roughly nine times more sepsis cases than the samples used so far, three seeds'],
    [ICON.cog, 'Self-supervised pretraining', 'the encoder first learns from up to 150,000 unlabelled stays to forecast the next value and organ worsening, without sepsis labels'],
    [ICON.scale, 'Loss chosen by utility', 'utility-weighted training against plain and time-smoothed losses, selected on the validation split by a rule written in advance'],
    [ICON.route, 'Running now', 'sixteen architectures, the organ-structure ablation and the challenge winner\'s method, on identical hours'],
  ];
  resp.forEach((r, i) => {
    const y = 2.1 + i * 1.05;
    iconCircle(s, r[0], M + 6.45, y + 0.12, 0.58, TEAL);
    text(s, r[1], M + 7.2, y, 4.7, 0.32, { fontSize: 12.5, bold: true });
    text(s, r[2], M + 7.2, y + 0.32, 4.7, 0.7, { fontSize: 11, color: GREY });
  });
  s.addNotes('1.5 min. The honest reading of the architecture comparison so far: on ten thousand stays, nothing separates the models, because they all memorise 175 septic patients within a couple of epochs. So the next lever is data: the full cohort, and pretraining on unlabelled stays. The sixteen-model comparison is running this week; architecture is being treated as a hypothesis, not a result.');

  // ================= 11. CONTRIBUTION + NEXT =================
  pres.addSection({ title: 'Contribution and next steps' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Contribution and next steps' });
  s.addText('The contribution is an honest, transferable test of sepsis warnings; the next step is scale and the sealed holdout', { placeholder: 'title' });
  text(s, 'Contribution so far', M, 1.5, 6, 0.35, { fontSize: 14, bold: true, color: TEAL });
  const contrib = [
    [ICON.lock, 'A causal, cross-database pipeline', 'one Sepsis-3 definition on two raw ICU databases, every value used from the hour it was known, 655 clinician-defined predictors, antibiotics handled by rule'],
    [ICON.scale, 'Evaluation by what helps patients', 'utility, false alarms per patient-day and warning time with patient-level confidence intervals; a 20 % holdout sealed until the protocol is frozen'],
    [ICON.search, 'Three findings', 'leakage inflates published scores; data coverage drives transfer more than architecture; models overfit small samples within epochs'],
    [ICON.book, 'Three manuscripts submitted in 2026', 'AI in antimicrobial-resistance diagnostics (Int J Antimicrob Agents, Oct); temporal patterns and predictors of sepsis onset, 27,101 ICU admissions (Frontiers in Medicine, Sep); infrared thermography in infectious disease, systematic review with meta-analysis (JMIR, Jul)'],
  ];
  contrib.forEach((c, i) => {
    const y = 1.95 + i * 1.12;
    iconCircle(s, c[0], M, y + 0.08, 0.58, NAVY);
    text(s, c[1], M + 0.75, y, 5.3, 0.32, { fontSize: 12.5, bold: true });
    text(s, c[2], M + 0.75, y + 0.32, 5.3, 0.8, { fontSize: 10.5, color: GREY });
  });
  text(s, 'Next six months', M + 6.6, 1.5, 5.5, 0.35, { fontSize: 14, bold: true, color: TEAL });
  const plan = [
    ['Oct to Nov 2026', 'Sixteen-model comparison on identical hours; shortlist by the prespecified validation rule'],
    ['Nov to Dec 2026', 'Full cohort, three seeds; leave-hospital-out evaluation across eICU\'s hospitals; pooled multi-site training'],
    ['Jan 2027', 'Freeze the protocol, open the sealed holdout once; alarm-policy study (sensitivity against false alarms per patient-day)'],
    ['Feb to Mar 2027', 'Radiology reports as predictors (MIMIC-IV notes), fairness analysis by subgroup, manuscript of the main study'],
  ];
  plan.forEach((p, i) => {
    const y = 1.95 + i * 1.12;
    s.addShape(pres.ShapeType.roundRect, { x: M + 6.6, y: y + 0.05, w: 1.55, h: 0.5, rectRadius: 0.06, fill: { color: TEAL }, line: { color: TEAL, width: 0 }, objectName: 'plan date' });
    text(s, p[0], M + 6.65, y + 0.05, 1.45, 0.5, { fontSize: 10.5, bold: true, color: WHITE, align: 'center', valign: 'middle' });
    text(s, p[1], M + 8.35, y, W - M - 8.35, 0.95, { fontSize: 11.5, valign: 'top' });
    if (i < plan.length - 1) s.addShape(pres.ShapeType.line, { x: M + 7.37, y: y + 0.6, w: 0.001, h: 0.5, line: { color: LINE, width: 1.5 }, objectName: 'plan connector' });
  });
  s.addNotes('2 min. Contribution first, then plan. The contribution is methodological as much as it is a model: the pipeline and the evaluation are what make any later result believable. The plan is sequenced so that the holdout is opened exactly once, after the protocol is frozen.');

  // ================= 12. INPUT =================
  pres.addSection({ title: 'Where I would like your input' });
  s = pres.addSlide({ masterName: 'CLOSING_DARK', sectionTitle: 'Where I would like your input' });
  s.addText('Where I would like your input', { placeholder: 'title' });
  const qs = [
    [ICON.scale, 'Which score should pick the model when they disagree?', 'Utility rewards an alarm six hours before onset and charges for every false-alarm hour; AUROC rewards ranking. On our data they already rank models differently. How much sensitivity would you trade to halve false alarms per patient-day, and should that trade-off be fixed before or after seeing the holdout?'],
    [ICON.exchange, 'How should sepsis be defined across databases?', 'In MIMIC-IV suspicion needs an antibiotic and a culture; eICU records antibiotics only, so its label is weaker. Harmonise both to the weaker definition, keep each database\'s best definition and report transfer under each, or model the two as different targets?'],
  ];
  qs.forEach((q, i) => {
    const y = 1.7 + i * 2.45;
    s.addShape(pres.ShapeType.roundRect, { x: M, y, w: W - 2 * M, h: 2.2, rectRadius: 0.08, fill: { color: DKNAVY }, line: { color: '2A4A6B', width: 0.75 }, objectName: 'question card' });
    iconCircle(s, q[0], M + 0.3, y + 0.35, 0.7, TEAL);
    text(s, q[1], M + 1.3, y + 0.25, W - 2 * M - 1.6, 0.5, { fontSize: 17, bold: true, color: WHITE, valign: 'middle' });
    text(s, q[2], M + 1.3, y + 0.8, W - 2 * M - 1.6, 1.3, { fontSize: 13, color: 'D7E0EA' });
  });
  text(s, 'Thank you. Backup slides follow: glossary, the utility score, predictor catalogue, cohort, the running comparison, and the RD6 supplement.', M, 6.65, W - 2 * M, 0.35, { fontSize: 11, italic: true, color: 'B8C4D2' });
  s.addNotes('1 min. Two concrete questions. The first is about evaluation: which score decides. The second is about labels: it is the problem that decides whether cross-database results mean anything. Then thank the audience and stop; backups are ready for questions.');

  // ================= BACKUPS =================
  pres.addSection({ title: 'Backup' });
  // B1 glossary
  s = pres.addSlide({ masterName: 'BACKUP', sectionTitle: 'Backup' });
  s.addText('Glossary: the clinical terms used in this talk', { placeholder: 'title' });
  const gl = [
    ['Sepsis-3', 'Life-threatening organ dysfunction caused by a dysregulated response to infection (Singer et al. 2016). Operationalised as suspected infection plus a SOFA rise of 2 or more points.'],
    ['SOFA', 'Sequential Organ Failure Assessment: 0 to 4 points for each of six organ systems (respiratory, cardiovascular, renal, hepatic, coagulation, neurological).'],
    ['Suspected infection', 'An antibiotic order and a culture within a 72 h / 24 h window of each other (Seymour et al. 2016). eICU has antibiotics only.'],
    ['Onset and horizon', 'Onset is the first hour both criteria are met. The model is asked, every hour, whether onset falls within the next 6 hours.'],
    ['qSOFA and NEWS2', 'Bedside screening scores built from vital signs and mental state; used here as predictors, never as the label.'],
    ['Utility score', 'PhysioNet 2019 scoring rule: reward for alarms from 12 h before to 3 h after onset, penalty for false-alarm hours and for missed sepsis, normalised so that 1 is perfect and 0 is never alarming.'],
    ['False alarms per patient-day', 'How often the alarm fires on patients who do not develop sepsis, expressed per 24 h of monitoring; 0.5 is the budget used in this project.'],
    ['Causal (availability-aware)', 'Each value is used only from the hour it was recorded in the system, with a measured-or-not flag and its age; no hour after onset is used for training or scoring.'],
  ];
  gl.forEach((g, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.1, y = 1.55 + row * 1.25;
    text(s, g[0], x, y, 1.75, 1.1, { fontSize: 12.5, bold: true, color: TEAL });
    text(s, g[1], x + 1.8, y, 4.2, 1.15, { fontSize: 11 });
  });

  // B2 utility score
  s = pres.addSlide({ masterName: 'BACKUP', sectionTitle: 'Backup' });
  s.addText('The utility score: what an alarm is worth, hour by hour', { placeholder: 'title' });
  s.addChart(pres.ChartType.line, [
    { name: 'Reward for an alarm (true positive)', labels: ['-14', '-12', '-10', '-8', '-6', '-4', '-2', '0', '+1', '+3'], values: [0, 0, 0.33, 0.67, 1, 0.78, 0.56, 0.33, 0.22, 0] },
    { name: 'Penalty for silence (false negative)', labels: ['-14', '-12', '-10', '-8', '-6', '-4', '-2', '0', '+1', '+3'], values: [0, 0, 0, 0, 0, -0.44, -0.89, -1.33, -1.56, -2] },
  ], {
    x: M, y: 1.5, w: 7.6, h: 4.9, lineSize: 2.5, lineDataSymbol: 'none', chartColors: [BLUE, ORANGE], showTitle: true, title: 'Hours relative to sepsis onset (negative = before onset)', titleFontSize: 12, titleColor: NAVY, titleFontFace: '+mn-lt',
    valAxisMinVal: -2, valAxisMaxVal: 1, valAxisMajorUnit: 0.5, valAxisLabelFontSize: 10, valAxisLabelColor: GREY, valAxisLabelFontFace: '+mn-lt', catAxisLabelFontSize: 10, catAxisLabelColor: GREY, catAxisLabelFontFace: '+mn-lt',
    valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: 'none' }, showLegend: true, legendPos: 'b', legendFontSize: 11, legendColor: NAVY, legendFontFace: '+mn-lt', objectName: 'utility curve',
  });
  card(s, M + 7.85, 1.5, W - 2 * M - 7.85, 4.9, { fill: TINT, name: 'utility notes' });
  text(s, 'Reading the score', M + 8.05, 1.62, 4, 0.35, { fontSize: 14, bold: true });
  bullets(s, [
    'An alarm earns most when raised 6 h before onset; alarms earlier than 12 h earn nothing.',
    'Every false-alarm hour on a patient who never develops sepsis costs 0.05.',
    'Silence after onset is penalised up to 2 points per hour by 3 h after onset.',
    'Normalised utility = (score - score of never alarming) / (perfect score - score of never alarming).',
    'It rewards timing and punishes alert fatigue: the two things a bedside system is judged on.',
    'Official scorer code used unchanged; alarms evaluated hourly on the first 120 h of each stay.',
  ], M + 8.05, 2.05, W - 2 * M - 8.25, 4.2, { fontSize: 11.5, psa: 6 });

  // B3 predictor catalogue
  s = pres.addSlide({ masterName: 'BACKUP', sectionTitle: 'Backup' });
  s.addText('The 655 predictors: the whole clinical picture, each with a measured flag and an age', { placeholder: 'title' });
  const cats = [
    ['Vital signs and monitoring', 'heart rate, blood pressures (cuff and arterial), respiratory rate, oxygen saturation, temperature, end-tidal CO2, central venous pressure, cardiac output, pain and sedation scores'],
    ['Laboratory and blood gas', 'full chemistry, haematology with differential, coagulation, lactate, procalcitonin, troponin, BNP, ferritin, D-dimer, amylase, lipase, ammonia, urinalysis, blood gases'],
    ['Scores and derived', 'SOFA (full and per organ), qSOFA, NEWS2, shock index, P/F and S/F ratios, neutrophil-lymphocyte ratio, BMI, changes against the previous value and the baseline, 24 h extremes and trends'],
    ['Organ support', 'vasopressor dose in noradrenaline equivalents, ventilation mode and settings, oxygen flow, airway status, renal replacement therapy, urine output rate and AKI stage'],
    ['Fluids, drugs and devices', 'crystalloids and transfusions, nutrition route, central and arterial lines, urinary catheters, drains; corticosteroids, immunosuppressants, chemotherapy, sedatives, opioids, diuretics, antipyretics'],
    ['Context and history', 'admission source and ICU type, hours in hospital before ICU, prior admissions, prior positive cultures and antibiotics in earlier admissions, 17 comorbidity flags, infection-related phenotypes, imaging orders'],
    ['Prophylactic antibiotics (MIMIC-IV)', 'surgical prophylaxis by agent, perioperative timing, duration and the absence of cultures or escalation; medical prophylaxis by agent and dose pattern'],
    ['Never used as predictors', 'antibiotics and cultures that define suspected infection; race, ethnicity and insurance (fairness analysis only); anything recorded after the prediction hour'],
  ];
  cats.forEach((c, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.1, y = 1.55 + row * 1.25;
    card(s, x, y, 5.95, 1.12, { fill: i === 7 ? 'FBE9E1' : TINT, name: 'predictor card' });
    text(s, c[0], x + 0.15, y + 0.08, 5.65, 0.3, { fontSize: 12, bold: true, color: i === 7 ? ORANGE : TEAL });
    text(s, c[1], x + 0.15, y + 0.38, 5.65, 0.72, { fontSize: 10.5 });
  });

  // B4 cohort
  s = pres.addSlide({ masterName: 'BACKUP', sectionTitle: 'Backup' });
  s.addText('Cohorts, splits and the sealed holdout', { placeholder: 'title' });
  const crow = [
    [hdr('Database'), hdr('Candidate ICU stays'), hdr('Sample used so far'), hdr('After benchmark exclusions'), hdr('Sealed holdout'), hdr('Development use')],
    [cell('MIMIC-IV 3.1 (BIDMC, Boston)', { bold: true }), cell('about 94,000'), cell('10,000'), cell('8,795 stays'), cell('20 % of patients by deterministic hash'), cell('train / validation / calibration / test, grouped by patient')],
    [cell('eICU-CRD 2.0 (about 200 US hospitals)', { bold: true }), cell('about 201,000'), cell('10,000'), cell('5,710 stays'), cell('20 % of patients by deterministic hash'), cell('same, with hospital identifiers kept for leave-hospital-out')],
  ];
  s.addTable(crow, { x: M, y: 1.55, w: W - 2 * M, colW: [2.6, 1.8, 1.7, 2.0, 2.0, 2.03], rowH: [0.4, 0.75, 0.75], border: { type: 'solid', color: LINE, pt: 0.75 }, fontFace: 'Calibri', margin: 0.06, objectName: 'cohort table' });
  bullets(s, [
    'Labels: Sepsis-3 via the YAIB benchmark (ricu), onset within the next 6 h; hours after onset excluded; stays followed for up to 120 h.',
    'Exclusions follow the benchmark (age, stay length, missing core data); the 10,000-stay samples are fixed random draws, identical across all runs so far.',
    'The holdout is released only once, after the full-cohort protocol is frozen; no threshold, calibration or model choice ever touches it.',
    'Transfer rows: each database\'s model is also scored on the other database\'s development patients.',
    'Unlabelled pretraining corpus: up to 75,000 stays per database that are not in the labelled cohort and not in the holdout.',
  ], M, 4.05, W - 2 * M, 2.6, { fontSize: 12.5, psa: 8 });

  // B5 running comparison
  s = pres.addSlide({ masterName: 'BACKUP', sectionTitle: 'Backup' });
  s.addText('The comparison running now: sixteen models, three losses, rules fixed in advance', { placeholder: 'title' });
  const arow = [
    [hdr('Group'), hdr('Models'), hdr('Purpose')],
    [cell('Kept from earlier runs', { bold: true }), cell('OSTA, output fusion, CNN-Transformer, logistic regression, boosted trees'), cell('continuity with the 10,000-stay results')],
    [cell('Literature benchmark', { bold: true }), cell('path signatures + boosted trees (PhysioNet 2019 winner\'s method)'), cell('direct replication of the winner on our data')],
    [cell('New supervised', { bold: true }), cell('flat OSTA (same model, no organ grouping), GRU-D, causal temporal CNN, CNN encoder + OSTA head, event attention + OSTA head'), cell('organ-structure ablation; irregular-sampling models from the literature')],
    [cell('Self-supervised', { bold: true }), cell('CNN encoder pretrained on unlabelled stays (next value, measured-within-6 h, SOFA components and organ worsening at 6/12/24 h), fine-tuned with OSTA, flat and survival (hazard) heads; site and pooled encoders'), cell('label-free learning from 150,000 stays; survival framing of the horizon')],
    [cell('Losses', { bold: true }), cell('utility-weighted cross-entropy (primary), plain cross-entropy, temporal label smoothing'), cell('chosen by validation utility + AUPRC rank-average')],
    [cell('Decision rules', { bold: true }), cell('organ structure kept only if OSTA beats flat OSTA on validation; shortlist = top 2 to 3 new models + baselines; full cohort with 3 seeds'), cell('no choice is made on test data')],
  ];
  s.addTable(arow, { x: M, y: 1.55, w: W - 2 * M, colW: [2.2, 6.3, 3.63], rowH: [0.38, 0.55, 0.55, 0.75, 1.05, 0.55, 0.75], border: { type: 'solid', color: LINE, pt: 0.75 }, fontFace: 'Calibri', margin: 0.06, objectName: 'arms table' });
  text(s, 'Evaluation additions in this run: warning time relative to the first antibiotic order, transfer to the other database, a conformal alarm policy with abstention on out-of-distribution hours, and a sensitivity analysis without clinician-suspicion proxies (hydrocortisone, imaging orders, prophylaxis).', M, 6.2, W - 2 * M, 0.6, { fontSize: 11, italic: true, color: GREY });

  // B6 publications (RD6 supplement)
  s = pres.addSlide({ masterName: 'BACKUP', sectionTitle: 'Backup' });
  s.addText('RD6 supplement: publications and outputs, October 2025 to October 2026', { placeholder: 'title' });
  const prow = [
    [hdr('Manuscript'), hdr('Journal'), hdr('Submitted'), hdr('Status')],
    [cell('Artificial Intelligence in the Diagnosis of Antimicrobial Resistance: Rapid Diagnostics and Imaging Innovations (narrative review)', { bold: true }), cell('International Journal of Antimicrobial Agents'), cell('9 Oct 2026'), cell('Technical check')],
    [cell('Temporal Patterns and Predictors of Sepsis Onset in ICU Patients: A Retrospective Cohort Study Using PhysioNet Data', { bold: true }), cell('Frontiers in Medicine'), cell('23 Sep 2026'), cell('Editorial assignment')],
    [cell('Diagnostic Applications of Infrared Thermography Across Infectious Diseases: A Systematic Review with a Subgroup Meta-Analysis', { bold: true }), cell('JMIR'), cell('18 Jul 2026'), cell('In review')],
    [cell('Early sepsis warning on MIMIC-IV and eICU: causal predictors, utility and transfer (main study)', { bold: true }), cell('target: critical care informatics journal'), cell('planned 2027'), cell('full-cohort run and sealed-holdout evaluation pending')],
  ];
  s.addTable(prow, { x: M, y: 1.55, w: W - 2 * M, colW: [6.0, 2.6, 1.5, 2.03], rowH: [0.38, 0.8, 0.8, 0.8, 0.8], border: { type: 'solid', color: LINE, pt: 0.75 }, fontFace: 'Calibri', margin: 0.06, objectName: 'publications table' });
  bullets(s, [
    'The cohort study (27,101 ICU admissions, 8 % sepsis, median onset 100 h) is the statistical companion to the modelling work: Cox models with a 6 h backshifted label identify early predictors that the deep models then use.',
    'The CNN-Transformer and OSTA manuscripts drafted in early 2026 were withheld after the leakage audit; both architectures are being re-evaluated causally in the current comparison.',
  ], M, 5.3, W - 2 * M, 1.2, { fontSize: 11.5, psa: 6 });

  // B7 professional development + plan (RD6 supplement)
  s = pres.addSlide({ masterName: 'BACKUP', sectionTitle: 'Backup' });
  s.addText('RD6 supplement: training completed and the plan to March 2027', { placeholder: 'title' });
  text(s, 'Training and professional development', M, 1.5, 6, 0.35, { fontSize: 14, bold: true, color: TEAL });
  const pd = [
    ['Harvard PPCR: Clinical Trials Design, Implementation and Analysis', 'completed, March 2025 to February 2026; informs the validation and alarm-policy study design'],
    ['Iowa State University: Machine Learning Programme', 'completed, October to December 2025'],
    ['DataCamp Python Data Science Career Track', 'in progress since September 2025'],
    ['Research data and compute', 'PhysioNet credentialed access to MIMIC-IV 3.1 and eICU-CRD 2.0; reproducible notebook pipeline with 212 automated engineering checks'],
  ];
  pd.forEach((p, i) => {
    const y = 1.95 + i * 1.05;
    iconCircle(s, ICON.check, M, y + 0.1, 0.55, TEAL);
    text(s, p[0], M + 0.72, y, 5.3, 0.32, { fontSize: 12, bold: true });
    text(s, p[1], M + 0.72, y + 0.32, 5.3, 0.7, { fontSize: 10.5, color: GREY });
  });
  text(s, 'What happened to the March 2026 plan', M + 6.6, 1.5, 5.6, 0.35, { fontSize: 14, bold: true, color: TEAL });
  const mp = [
    ['MIMIC-IV external validation', 'became the core of the programme, extended to eICU with one shared label definition'],
    ['Submit the CNN-Transformer and OSTA papers', 'paused after the leakage audit; both models are in the causal comparison instead'],
    ['AMR review', 'revised and submitted to the International Journal of Antimicrobial Agents'],
    ['Present at a conference', 'this conference; the RD6 review follows'],
    ['Clinical stakeholder study', 'moved after the full-cohort results, with the alarm-policy study'],
  ];
  mp.forEach((p, i) => {
    const y = 1.95 + i * 0.85;
    text(s, p[0], M + 6.6, y, 2.4, 0.8, { fontSize: 11.5, bold: true });
    text(s, p[1], M + 9.1, y, W - M - 9.1, 0.8, { fontSize: 11, color: GREY });
  });

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log('written', OUT);
})().catch(e => { console.error(e); process.exit(1); });
