// SCEBE 2026 deck v2: editorial clinical style, Arial, crimson accent, every claim referenced.
const pptxgen = require('pptxgenjs');
const path = require('path');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const sharp = require('sharp');
const fa = require('react-icons/fa');
const gi = require('react-icons/gi');
const { applyTheme } = require('/root/.claude/skills/synced/d91fe1c6-8d49-4422-b8c8-6dd15fde630e_6b953dd5-185b-425b-91bb-1cf229fc0818/pptx/scripts/apply_theme.js');

const OUT = path.join(__dirname, 'Elrggal_Mahmoud_SCEBE2026.pptx');
const SECOND_SUPERVISOR = process.env.SECOND_SUPERVISOR || 'Kia';

const INK = '1B1B1B', RED = 'C8102E', GREY = '5E5E5E', MID = '8C8C8C', LIGHT = 'F2F2F2', RULE = 'BDBDBD', WHITE = 'FFFFFF', PINK = 'FBE3E6';
const THEME = { name: 'ClinicalEditorial', headFontFace: 'Arial', bodyFontFace: 'Arial',
  colors: { dk1: INK, lt1: WHITE, dk2: '3A3A3A', lt2: LIGHT, accent1: RED, accent2: '3A3A3A', accent3: MID, accent4: '1F4E9A', accent5: '7A1020', accent6: 'D9A400', hlink: RED, folHlink: GREY } };

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.theme = { headFontFace: 'Arial', bodyFontFace: 'Arial' };
pres.author = 'Mahmoud Essam Elrggal';
pres.title = 'Development of Novel AI Models for Early Detection and Prediction of Infectious Diseases, with a Focus on Sepsis';
const W = 13.333, H = 7.5, M = 0.6, CW = W - 2 * M;
const FOOT = 'Mahmoud Essam Elrggal  |  SCEBE Research Degree Conference 2026';

// ---------- references (numbered by first citation) ----------
const REF = {
  rudd: 'Rudd KE, Johnson SC, Agesa KM, et al. Global, regional, and national sepsis incidence and mortality, 1990-2017: analysis for the Global Burden of Disease Study. Lancet. 2020;395:200-211.',
  murray: 'Antimicrobial Resistance Collaborators. Global burden of bacterial antimicrobial resistance in 2019: a systematic analysis. Lancet. 2022;399:629-655.',
  timbrook: 'Timbrook TT, Morton JB, McConeghy KW, et al. The effect of molecular rapid diagnostic testing on clinical outcomes in bloodstream infections: a systematic review and meta-analysis. Clin Infect Dis. 2017;64:15-23.',
  adams: 'Adams R, Henry KE, Sridharan A, et al. Prospective, multi-site study of patient outcomes after implementation of the TREWS machine learning-based early warning system for sepsis. Nat Med. 2022;28:1455-1460.',
  amr: 'Elrggal ME, et al. Artificial intelligence in the diagnosis of antimicrobial resistance: rapid diagnostics and imaging innovations. Submitted, Int J Antimicrob Agents, 2026.',
  singer: 'Singer M, Deutschman CS, Seymour CW, et al. The Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3). JAMA. 2016;315:801-810.',
  vincent: 'Vincent JL, Moreno R, Takala J, et al. The SOFA (Sepsis-related Organ Failure Assessment) score to describe organ dysfunction/failure. Intensive Care Med. 1996;22:707-710.',
  liu: 'Liu V, Escobar GJ, Greene JD, et al. Hospital deaths in patients with sepsis from 2 independent cohorts. JAMA. 2014;312:90-92.',
  seymour17: 'Seymour CW, Gesten F, Prescott HC, et al. Time to treatment and mortality during mandated emergency care for sepsis. N Engl J Med. 2017;376:2235-2244.',
  kumar: 'Kumar A, Roberts D, Wood KE, et al. Duration of hypotension before initiation of effective antimicrobial therapy is the critical determinant of survival in human septic shock. Crit Care Med. 2006;34:1589-1596.',
  churpek: 'Churpek MM, Snyder A, Han X, et al. Quick SOFA, SIRS, and early warning scores for detecting clinical deterioration in infected patients outside the ICU. Am J Respir Crit Care Med. 2017;195:906-911.',
  yu: 'Yu AC, Mohajer B, Eng J. External validation of deep learning algorithms for radiologic diagnosis: a systematic review. Radiol Artif Intell. 2022;4:e210064.',
  kwong: 'Kwong JCC, Erdman L, Khondker A, et al. The silent trial: the bridge between bench-to-bedside clinical AI applications. Front Digit Health. 2022;4:929508.',
  nagendran: 'Nagendran M, Chen Y, Lovejoy CA, et al. Artificial intelligence versus clinicians: systematic review of design, reporting standards, and claims of deep learning studies. BMJ. 2020;368:m689.',
  reyna: 'Reyna MA, Josef CS, Jeter R, et al. Early prediction of sepsis from clinical data: the PhysioNet/Computing in Cardiology Challenge 2019. Crit Care Med. 2020;48:210-217.',
  agniel: 'Agniel D, Kohane IS, Weber GM. Biases in electronic health record data due to processes within the healthcare system: retrospective observational study. BMJ. 2018;361:k1479.',
  zech: 'Zech JR, Badgeley MA, Liu M, et al. Variable generalization performance of a deep learning model to detect pneumonia in chest radiographs: a cross-sectional study. PLoS Med. 2018;15:e1002683.',
  kapoor: 'Kapoor S, Narayanan A. Leakage and the reproducibility crisis in machine-learning-based science. Patterns. 2023;4:100804.',
  shah: 'Shah NH, Milstein A, Bagley SC. Making machine learning models clinically useful. JAMA. 2019;322:1351-1352.',
  kelly: 'Kelly CJ, Karthikesalingam A, Suleyman M, Corrado G, King D. Key challenges for delivering clinical impact with artificial intelligence. BMC Med. 2019;17:195.',
  morrill: 'Morrill JH, Kormilitzin A, Nevado-Holgado AJ, et al. Utilization of the signature method to identify the early onset of sepsis from multivariate physiological time series in critical care monitoring. Crit Care Med. 2020;48:e976-e981.',
  wong: 'Wong A, Otles E, Donnelly JP, et al. External validation of a widely implemented proprietary sepsis prediction model in hospitalized patients. JAMA Intern Med. 2021;181:1065-1070.',
  fleuren: 'Fleuren LM, Klausch TLT, Zwager CL, et al. Machine learning for the prediction of sepsis: a systematic review and meta-analysis of diagnostic test accuracy. Intensive Care Med. 2020;46:383-400.',
  moor21: 'Moor M, Rieck B, Horn M, Jutzeler CR, Borgwardt K. Early prediction of sepsis in the ICU using machine learning: a systematic review. Front Med. 2021;8:607952.',
  tschandl: 'Tschandl P, Rinner C, Apalla Z, et al. Human-computer collaboration for skin cancer recognition. Nat Med. 2020;26:1229-1234.',
  henrynpj: 'Henry KE, Kornfield R, Sridharan A, et al. Human-machine teaming is key to AI adoption: clinicians\' experiences with a deployed machine learning system. NPJ Digit Med. 2022;5:97.',
  wiens: 'Wiens J, Saria S, Sendak M, et al. Do no harm: a roadmap for responsible machine learning for health care. Nat Med. 2019;25:1337-1340.',
  bratzler: 'Bratzler DW, Dellinger EP, Olsen KM, et al. Clinical practice guidelines for antimicrobial prophylaxis in surgery. Am J Health Syst Pharm. 2013;70:195-283.',
  evans: 'Evans L, Rhodes A, Alhazzani W, et al. Surviving Sepsis Campaign: international guidelines for management of sepsis and septic shock 2021. Intensive Care Med. 2021;47:1181-1247.',
  johnson: 'Johnson AEW, Bulgarelli L, Shen L, et al. MIMIC-IV, a freely accessible electronic health record dataset. Sci Data. 2023;10:1.',
  pollard: 'Pollard TJ, Johnson AEW, Raffa JD, et al. The eICU Collaborative Research Database, a freely available multi-center database for critical care research. Sci Data. 2018;5:180178.',
  goldberger: 'Goldberger AL, Amaral LAN, Glass L, et al. PhysioBank, PhysioToolkit, and PhysioNet: components of a new research resource for complex physiologic signals. Circulation. 2000;101:e215-e220.',
  yaib: 'van de Water R, Schmidt HNA, Elbers PWG, et al. Yet Another ICU Benchmark: a flexible multi-center framework for clinical machine learning. ICLR 2024.',
  ricu: 'Bennett N, Plecko D, Ukor IF, Meinshausen N, Buhlmann P. ricu: R\'s interface to intensive care data. GigaScience. 2023;12.',
  seymour16: 'Seymour CW, Liu VX, Iwashyna TJ, et al. Assessment of clinical criteria for sepsis (Sepsis-3). JAMA. 2016;315:762-774.',
  vaswani: 'Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. Advances in Neural Information Processing Systems (NeurIPS). 2017.',
  che: 'Che Z, Purushotham S, Cho K, Sontag D, Liu Y. Recurrent neural networks for multivariate time series with missing values. Sci Rep. 2018;8:6085.',
  bai: 'Bai S, Kolter JZ, Koltun V. An empirical evaluation of generic convolutional and recurrent networks for sequence modeling. arXiv:1803.01271. 2018.',
  yeche23: 'Yeche H, Pace A, Ratsch G, Kuznetsova R. Temporal label smoothing for early event prediction. International Conference on Machine Learning (ICML). 2023.',
  yeche21: 'Yeche H, Dresdner G, Locatello F, Huser M, Ratsch G. Neighborhood contrastive learning applied to online patient monitoring. International Conference on Machine Learning (ICML). 2021.',
  thiswork: 'Elrggal ME, et al. Early sepsis warning on MIMIC-IV and eICU: preliminary development-split results, October 2026. Unpublished; manuscript in preparation.',
  temporal: 'Elrggal ME, et al. Temporal patterns and predictors of sepsis onset in ICU patients: a retrospective cohort study using PhysioNet data. Submitted, Front Med, 2026.',
  thermo: 'Elrggal ME, et al. Diagnostic applications of infrared thermography across infectious diseases: a systematic review with a subgroup meta-analysis. Submitted, JMIR, 2026.',
  kdigo: 'Kidney Disease: Improving Global Outcomes (KDIGO) AKI Work Group. KDIGO clinical practice guideline for acute kidney injury. Kidney Int Suppl. 2012;2:1-138.',
  rcp: 'Royal College of Physicians. National Early Warning Score (NEWS) 2: standardising the assessment of acute-illness severity in the NHS. London: RCP; 2017.',
};
const SHORT = {};
for (const [k, v] of Object.entries(REF)) {
  const parts = v.split('. ');
  const surname = parts[0].split(' ')[0].replace(/,$/, '');
  const yr = (v.match(/(19|20)\d\d/g) || ['']).slice(-1)[0];
  const journal = (parts[2] || '').replace(/\s*(19|20)\d\d.*$/, '').replace(/;.*$/, '').trim();
  SHORT[k] = `${surname} et al., ${journal} ${yr}`;
}
SHORT.amr = 'Elrggal et al., submitted 2026'; SHORT.temporal = 'Elrggal et al., submitted 2026'; SHORT.thermo = 'Elrggal et al., submitted 2026';
SHORT.thiswork = 'This work, preliminary, unpublished'; SHORT.murray = 'AMR Collaborators, Lancet 2022'; SHORT.kdigo = 'KDIGO 2012'; SHORT.rcp = 'Royal College of Physicians 2017';
SHORT.yaib = 'van de Water et al., ICLR 2024'; SHORT.vaswani = 'Vaswani et al., NeurIPS 2017'; SHORT.bai = 'Bai et al., arXiv 2018'; SHORT.yeche23 = 'Yeche et al., ICML 2023'; SHORT.yeche21 = 'Yeche et al., ICML 2021';
const ORDER = []; let cur = null;
function c(...keys) {
  const nums = keys.map((k) => { if (!REF[k]) throw new Error('missing ref ' + k); if (!ORDER.includes(k)) ORDER.push(k); if (cur) cur.add(k); return ORDER.indexOf(k) + 1; });
  return '[' + nums.join(', ') + ']';
}
function refFooter(slide, dark = false) {
  if (!cur || !cur.size) return;
  const items = [...cur].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b)).map((k) => `[${ORDER.indexOf(k) + 1}] ${SHORT[k]}`);
  slide.addText(items.join('   '), { x: M, y: 6.5, w: CW - 1.0, h: 0.5, isTextBox: true, margin: 0, fontSize: 9.5, color: dark ? 'F3C6CC' : GREY, valign: 'bottom', objectName: 'references' });
}

async function icon(lib, name, color = WHITE, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(lib[name], { color: '#' + color, size: px }));
  return 'image/png;base64,' + (await sharp(Buffer.from(svg)).resize(px, px).png().toBuffer()).toString('base64');
}

// ---------- layouts ----------
pres.defineSlideMaster({ title: 'CONTENT', background: { color: WHITE }, objects: [
  { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.6, w: CW, h: 0.95, fontSize: 26, bold: true, color: INK, align: 'left', valign: 'top', margin: 0, fontFace: 'Arial' } } },
  { text: { text: FOOT, options: { x: M, y: 7.08, w: 8, h: 0.25, fontSize: 9, color: MID, margin: 0 } } },
], slideNumber: { x: W - M - 0.8, y: 7.04, w: 0.8, h: 0.3, fontSize: 12, color: RED, bold: true, align: 'right' } });
pres.defineSlideMaster({ title: 'BACKUP', background: { color: WHITE }, objects: [
  { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.6, w: CW, h: 0.95, fontSize: 24, bold: true, color: INK, align: 'left', valign: 'top', margin: 0, fontFace: 'Arial' } } },
  { text: { text: FOOT, options: { x: M, y: 7.08, w: 8, h: 0.25, fontSize: 9, color: MID, margin: 0 } } },
], slideNumber: { x: W - M - 0.8, y: 7.04, w: 0.8, h: 0.3, fontSize: 12, color: RED, bold: true, align: 'right' } });
pres.defineSlideMaster({ title: 'TITLE', background: { color: WHITE }, objects: [] });
pres.defineSlideMaster({ title: 'CLOSING', background: { color: RED }, objects: [
  { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.6, w: CW, h: 0.95, fontSize: 30, bold: true, color: WHITE, align: 'left', valign: 'top', margin: 0, fontFace: 'Arial' } } },
  { text: { text: FOOT, options: { x: M, y: 7.08, w: 8, h: 0.25, fontSize: 9, color: 'F3C6CC', margin: 0 } } },
], slideNumber: { x: W - M - 0.8, y: 7.04, w: 0.8, h: 0.3, fontSize: 12, color: WHITE, bold: true, align: 'right' } });

// ---------- helpers ----------
function T(s, str, x, y, w, h, o = {}) {
  s.addText(str, { x, y, w, h, isTextBox: true, margin: o.margin == null ? 0 : o.margin, fontSize: o.size || 14, color: o.color || INK, bold: !!o.bold, italic: !!o.italic, align: o.align || 'left', valign: o.valign || 'top', objectName: o.name || 'text', paraSpaceAfter: o.psa, lineSpacingMultiple: o.lsm });
}
function rich(s, runs, x, y, w, h, o = {}) {
  s.addText(runs.map((r, i) => ({ text: r[0], options: { bold: !!(r[1] && r[1].bold), color: (r[1] && r[1].color) || o.color || INK, fontSize: (r[1] && r[1].size) || o.size || 14, breakLine: !!(r[1] && r[1].br) && i < runs.length - 1, italic: !!(r[1] && r[1].italic) } })),
    { x, y, w, h, isTextBox: true, margin: 0, valign: o.valign || 'top', objectName: o.name || 'rich text', paraSpaceAfter: o.psa == null ? 4 : o.psa });
}
function list(s, items, x, y, w, h, o = {}) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 16 }, breakLine: i < items.length - 1, paraSpaceAfter: o.psa == null ? 8 : o.psa } })),
    { x, y, w, h, isTextBox: true, margin: 0, fontSize: o.size || 14, color: o.color || INK, valign: 'top', objectName: o.name || 'list' });
}
function box(s, x, y, w, h, o = {}) {
  s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: o.fill || WHITE }, line: { color: o.line || INK, width: o.lw == null ? 1 : o.lw }, objectName: o.name || 'box' });
}
function tile(s, data, x, y, d = 0.6, fill = RED) {
  s.addShape(pres.ShapeType.rect, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: 'icon tile' });
  s.addImage({ data, x: x + d * 0.2, y: y + d * 0.2, w: d * 0.6, h: d * 0.6, objectName: 'icon' });
}
function arrow(s, x1, y1, x2, y2, color = INK, width = 1.5) {
  s.addShape(pres.ShapeType.line, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001, line: { color, width, endArrowType: 'triangle' }, flipH: x2 < x1, flipV: y2 < y1, objectName: 'arrow' });
}
function label(s, str, dark = false) { T(s, str, M, 0.26, 8, 0.3, { size: 11, bold: true, color: dark ? WHITE : RED, name: 'section label' }); }
function prelim(s) {
  s.addShape(pres.ShapeType.rect, { x: W - M - 4.6, y: 0.24, w: 4.6, h: 0.32, fill: { color: PINK }, line: { color: PINK, width: 0 }, objectName: 'preliminary tag' });
  T(s, 'PRELIMINARY  |  full results in the manuscript in preparation', W - M - 4.55, 0.24, 4.5, 0.32, { size: 10, bold: true, color: RED, align: 'center', valign: 'middle' });
}
function slide(master, section, sectionTitle) { cur = new Set(); const s = pres.addSlide({ masterName: master, sectionTitle }); if (section) label(s, section, master === 'CLOSING'); return s; }
const th = (t) => ({ text: t, options: { bold: true, color: WHITE, fill: { color: INK }, fontSize: 12, valign: 'middle' } });
const td = (t, o = {}) => ({ text: t, options: { fontSize: 11.5, color: INK, valign: 'middle', ...o } });

(async () => {
  const I = {
    virus: await icon(fa, 'FaVirus'), pill: await icon(fa, 'FaPills'), micro: await icon(fa, 'FaMicroscope'), bell: await icon(fa, 'FaBell'),
    lungs: await icon(gi, 'GiLungs'), heart: await icon(gi, 'GiHeartOrgan'), kidney: await icon(gi, 'GiKidneys'), liver: await icon(gi, 'GiLiver'), drop: await icon(gi, 'GiDrop'), brain: await icon(gi, 'GiBrain'),
    db: await icon(fa, 'FaDatabase'), users: await icon(fa, 'FaUserMd'), hospital: await icon(fa, 'FaHospital'), search: await icon(fa, 'FaSearch'), chart: await icon(fa, 'FaChartLine'),
    globe: await icon(fa, 'FaGlobeEurope'), clock: await icon(fa, 'FaStopwatch'), xray: await icon(fa, 'FaXRay'), scale: await icon(fa, 'FaBalanceScale'), exchange: await icon(fa, 'FaExchangeAlt'),
    lock: await icon(fa, 'FaLock'), book: await icon(fa, 'FaBookOpen'), comments: await icon(fa, 'FaComments'), heartbeat: await icon(fa, 'FaHeartbeat', WHITE), check: await icon(fa, 'FaCheck'),
  };

  // ===== 1 TITLE =====
  pres.addSection({ title: 'Context' });
  cur = new Set();
  let s = pres.addSlide({ masterName: 'TITLE', sectionTitle: 'Context' });
  s.addShape(pres.ShapeType.rect, { x: W - 3.6, y: 0, w: 3.6, h: H, fill: { color: RED }, line: { color: RED, width: 0 }, objectName: 'title panel' });
  s.addImage({ data: I.heartbeat, x: W - 2.55, y: 1.0, w: 1.5, h: 1.5, objectName: 'title icon' });
  T(s, 'SCEBE Research Degree Conference 2026', W - 3.3, 3.0, 3.0, 0.8, { size: 16, bold: true, color: WHITE });
  T(s, '20 October 2026\nMerchiston Campus\nEdinburgh Napier University', W - 3.3, 3.85, 3.0, 1.2, { size: 14, color: WHITE });
  T(s, 'Development of Novel AI Models for Early Detection and Prediction of Infectious Diseases, with a Focus on Sepsis', M, 1.0, W - 3.6 - M - 0.5, 2.3, { size: 32, bold: true, color: INK, valign: 'bottom', name: 'main title' });
  T(s, 'Can a sepsis warning stay useful in a hospital it has never seen?', M, 3.45, W - 3.6 - M - 0.5, 0.6, { size: 20, bold: true, color: RED, name: 'subtitle' });
  rich(s, [
    ['Mahmoud Essam Elrggal', { bold: true, size: 18, br: true }],
    ['PhD candidate, School of Computing, Engineering and the Built Environment, Edinburgh Napier University', { size: 14, br: true }],
    [' ', { size: 8, br: true }],
    ['Director of Studies: Prof. Ahmed Al Dubai', { size: 14, br: true }],
    ['Second Supervisor: ' + SECOND_SUPERVISOR, { size: 14 }],
  ], M, 4.5, W - 3.6 - M - 0.5, 1.8, { psa: 2 });
  s.addNotes('1 min. Introduce yourself in one sentence as a healthcare professional and PhD candidate. Read the subtitle question: it is what the whole talk answers.');

  // ===== 2 INFECTIOUS DISEASE =====
  s = slide('CONTENT', 'CONTEXT', 'Context');
  s.addText('Detecting infection early saves lives and saves antibiotics', { placeholder: 'title' });
  const ids = [
    [I.globe, '11 M', 'sepsis deaths a year: 1 in 5 deaths worldwide ' + c('rudd')],
    [I.pill, '1.27 M', 'deaths in 2019 caused directly by antibiotic-resistant bacteria; 4.95 M associated ' + c('murray')],
    [I.micro, 'OR 0.66', 'odds of death with rapid diagnosis of bloodstream infection; effective therapy about 5 h sooner ' + c('timbrook')],
    [I.bell, '-18.7 %', 'relative in-hospital mortality when a sepsis AI alert was confirmed by clinicians within 3 h ' + c('adams')],
  ];
  ids.forEach((d, i) => {
    const x = M + i * 3.07;
    tile(s, d[0], x, 1.75, 0.6);
    T(s, d[1], x, 2.45, 2.9, 0.7, { size: 34, bold: true, color: RED });
    T(s, d[2], x, 3.15, 2.85, 1.3, { size: 13.5 });
  });
  // pathway figure
  const py = 5.0, steps = ['Infection begins', 'Body starts to change', 'Clinician recognises', 'Microbiology result (48-72 h)', 'Targeted treatment'];
  const sw = 2.25, gap = 0.22;
  steps.forEach((t, i) => {
    const x = M + i * (sw + gap);
    box(s, x, py, sw, 0.62, { fill: i === 1 || i === 2 ? PINK : LIGHT, line: i === 1 || i === 2 ? RED : RULE });
    T(s, t, x + 0.08, py, sw - 0.16, 0.62, { size: 13, bold: true, align: 'center', valign: 'middle' });
    if (i < steps.length - 1) arrow(s, x + sw, py + 0.31, x + sw + gap, py + 0.31, INK, 1.25);
  });
  T(s, 'AI prediction moves recognition earlier', M + sw + gap, py + 0.7, 2 * sw + gap, 0.35, { size: 13, bold: true, color: RED, align: 'center' });
  T(s, 'AI rapid diagnostics shorten this step ' + c('amr'), M + 3 * (sw + gap), py + 0.7, sw, 0.6, { size: 12, color: GREY, align: 'center' });
  T(s, 'The infection pathway', M, py - 0.42, 4, 0.35, { size: 13, bold: true, color: GREY });
  refFooter(s);
  s.addNotes('1 min. Four numbers: the burden of sepsis, the burden of resistance, and two pieces of evidence that acting earlier helps: rapid diagnostics with stewardship, and a sepsis AI alert that clinicians acted on. The pathway shows where AI helps: earlier recognition (my project) and faster diagnosis (my review).');

  // ===== 3 SEPSIS =====
  s = slide('CONTENT', 'CONTEXT', 'Context');
  s.addText('Sepsis is an infection that makes the body\'s own organs fail', { placeholder: 'title' });
  T(s, 'Sepsis-3: life-threatening organ dysfunction caused by a dysregulated host response to infection ' + c('singer'), M, 1.6, 6.3, 0.75, { size: 15, bold: true });
  T(s, 'Organ failure is measured by the SOFA score: 0 to 4 points for each organ system ' + c('vincent'), M, 2.4, 6.3, 0.5, { size: 13, color: GREY });
  const organs = [[I.lungs, 'Lungs', 'oxygen ratio PaO2/FiO2'], [I.heart, 'Circulation', 'blood pressure, vasopressors'], [I.kidney, 'Kidneys', 'creatinine, urine output'],
    [I.liver, 'Liver', 'bilirubin'], [I.drop, 'Clotting', 'platelets'], [I.brain, 'Brain', 'Glasgow Coma Scale']];
  organs.forEach((o, i) => {
    const col = i % 3, row = Math.floor(i / 3), x = M + col * 2.12, y = 3.05 + row * 1.6;
    tile(s, o[0], x, y, 0.7);
    T(s, o[1], x + 0.8, y, 1.25, 0.35, { size: 14, bold: true });
    T(s, o[2], x + 0.8, y + 0.35, 1.25, 0.9, { size: 12, color: GREY });
  });
  box(s, 7.3, 1.6, W - M - 7.3, 4.75, { fill: LIGHT, line: LIGHT });
  T(s, 'Why it is hard', 7.5, 1.72, 5, 0.35, { size: 15, bold: true, color: RED });
  list(s, [
    'Sepsis contributes to between one in two and one in three hospital deaths ' + c('liu') + '.',
    'Each hour of delay to antibiotics raises the odds of death by about 4 % ' + c('seymour17') + '; in septic shock survival falls by 7.6 % per hour ' + c('kumar') + '.',
    'Early signs are non-specific: fever, a fast heart rate and fast breathing are common in many ICU patients.',
    'Bedside screening scores such as qSOFA and SIRS detect deterioration less accurately than early-warning scores ' + c('churpek') + '.',
  ], 7.5, 2.15, W - M - 7.7, 4.1, { size: 14, psa: 10 });
  refFooter(s);
  s.addNotes('1 min. Define sepsis as infection plus organ failure, and SOFA as the organ scoring system, pointing at the six organs. Then: it is common, time-critical, and hard to recognise early, which is why prediction matters.');

  // ===== 4 CLINICAL AI LITERATURE =====
  s = slide('CONTENT', 'WHAT THE MEDICAL LITERATURE SHOWS', 'Context');
  s.addText('Clinical AI often excels in development and fails in practice', { placeholder: 'title' });
  const probs = [
    [I.hospital, 'It fails on new data', '81 % of 86 deep-learning algorithms performed worse on external data ' + c('yu') + '. A model fell from AUC 0.90 to 0.50 when run silently on new patients ' + c('kwong') + '. Of 81 deep-learning studies, 9 were prospective and 6 tested in real clinical settings ' + c('nagendran') + '.'],
    [I.search, 'It sees a narrow picture', 'The most used sepsis benchmark gives models 40 hourly variables ' + c('reyna') + '; treatments, devices and history are usually left out.'],
    [I.users, 'It learns the care process, not the patient', 'Whether a laboratory test was ordered predicted survival for 86 % of 272 tests; the timing of the order beat the result itself for 68 % ' + c('agniel') + '. A pneumonia model learned which hospital took the X-ray ' + c('zech') + '.'],
    [I.chart, 'It is judged by numbers, not clinical meaning', 'Data leakage inflates results in at least 17 scientific fields ' + c('kapoor') + '. Usefulness depends on the action a prediction triggers, not on AUROC alone ' + c('shah', 'kelly') + '.'],
  ];
  probs.forEach((p, i) => {
    const col = i % 2, row = Math.floor(i / 2), x = M + col * 6.15, y = 1.7 + row * 2.4;
    box(s, x, y, 5.95, 2.2, { line: RULE });
    tile(s, p[0], x + 0.2, y + 0.2, 0.55);
    T(s, p[1], x + 0.95, y + 0.2, 4.85, 0.55, { size: 16, bold: true, valign: 'middle' });
    T(s, p[2], x + 0.2, y + 0.9, 5.55, 1.25, { size: 13 });
  });
  refFooter(s);
  s.addNotes('1 min. The general lesson from medical AI, before sepsis: models fail on new data, see only part of the patient, learn how care is delivered rather than the disease, and are judged by numbers rather than by what a clinician would do with them.');

  // ===== 5 SEPSIS AI =====
  s = slide('CONTENT', 'WHAT THE MEDICAL LITERATURE SHOWS', 'Context');
  s.addText('Sepsis AI follows the same pattern', { placeholder: 'title' });
  box(s, M, 1.7, 5.95, 2.65, { line: RULE });
  T(s, 'PhysioNet 2019 Challenge: 104 teams ' + c('reyna'), M + 0.2, 1.82, 5.6, 0.4, { size: 15, bold: true });
  T(s, '0.43', M + 0.2, 2.3, 2.2, 0.8, { size: 44, bold: true, color: INK });
  T(s, 'winner\'s utility on new patients from its two training hospitals', M + 0.2, 3.1, 2.4, 0.9, { size: 12.5, color: GREY });
  arrow(s, M + 2.55, 2.7, M + 3.15, 2.7, RED, 2.5);
  T(s, '-0.12', M + 3.3, 2.3, 2.4, 0.8, { size: 44, bold: true, color: RED });
  T(s, 'on a third hospital it had never seen: worse than no alarm ' + c('morrill'), M + 3.3, 3.1, 2.5, 0.9, { size: 12.5, color: GREY });
  box(s, M + 6.15, 1.7, 5.95, 2.65, { line: RULE });
  T(s, 'Epic Sepsis Model, widely deployed ' + c('wong'), M + 6.35, 1.82, 5.6, 0.4, { size: 15, bold: true });
  T(s, '0.63', M + 6.35, 2.3, 2.3, 0.8, { size: 44, bold: true, color: RED });
  T(s, 'AUROC in independent validation (vendor: 0.76 to 0.83)', M + 6.35, 3.1, 2.5, 0.9, { size: 12.5, color: GREY });
  T(s, '67 %', M + 9.2, 2.3, 2.6, 0.8, { size: 44, bold: true, color: RED });
  T(s, 'of sepsis cases missed while alerting on 18 % of all admissions', M + 9.2, 3.1, 2.7, 0.9, { size: 12.5, color: GREY });
  box(s, M, 4.55, CW, 1.75, { fill: LIGHT, line: LIGHT });
  rich(s, [
    ['Across the field: ', { bold: true }], ['28 sepsis models reported AUROC from 0.68 to 0.99, with almost no prospective testing ' + c('fleuren') + '. ', {}],
    ['Studies use different definitions and implementations of sepsis, so results cannot be compared ' + c('moor21') + '. ', {}],
    ['The same three causes recur: information from the future, a narrow set of inputs, and scores that do not reflect whether an alarm would help.', { bold: true }],
  ], M + 0.25, 4.7, CW - 0.5, 1.5, { size: 14 });
  refFooter(s);
  s.addNotes('1 min. Two concrete failures: the best entry of the largest public competition, and the most deployed commercial model. Utility is the challenge score that rewards an alarm before sepsis and charges for false alarms; zero means never alarming. Then the field-wide picture.');

  // ===== 6 QUESTION =====
  pres.addSection({ title: 'Question and approach' });
  s = slide('CONTENT', 'RESEARCH QUESTION', 'Question and approach');
  s.addText('The question this research asks', { placeholder: 'title' });
  box(s, M, 1.65, CW, 1.45, { fill: RED, line: RED });
  T(s, 'Using only what a clinician could have known at each hour, can a model warn of sepsis hours before onset with positive clinical utility, and does that utility hold in a hospital system it has never seen?', M + 0.3, 1.65, CW - 0.6, 1.45, { size: 19, bold: true, color: WHITE, valign: 'middle' });
  box(s, M, 3.3, 5.95, 1.3, { line: RULE });
  T(s, 'What has mostly been asked', M + 0.2, 3.4, 5.5, 0.35, { size: 13, bold: true, color: GREY });
  T(s, 'How high can AUROC go on one prepared dataset, with one team\'s sepsis definition ' + c('fleuren', 'moor21') + '?', M + 0.2, 3.75, 5.5, 0.8, { size: 14 });
  box(s, M + 6.15, 3.3, 5.95, 1.3, { line: RED, lw: 1.5 });
  T(s, 'What this project asks', M + 6.35, 3.4, 5.5, 0.35, { size: 13, bold: true, color: RED });
  T(s, 'Would the alarm have helped this patient, at a false-alarm burden clinicians accept, and would it still help in the next hospital?', M + 6.35, 3.75, 5.6, 0.8, { size: 14 });
  const rqs = [['RQ1  Predictors', 'Does the whole clinical picture known at that hour (treatments, devices, admission context, history) add signal beyond vital signs and laboratory values?'],
    ['RQ2  Architecture', 'Once causality is enforced, does organ-structured modelling add anything over simpler models?'],
    ['RQ3  Transfer and trust', 'Does positive utility survive in another hospital system, and would healthcare professionals act on the alert?']];
  rqs.forEach((r, i) => { const x = M + i * 4.1; T(s, r[0], x, 4.8, 3.9, 0.35, { size: 15, bold: true, color: RED }); T(s, r[1], x, 5.18, 3.85, 1.2, { size: 13.5 }); });
  refFooter(s);
  s.addNotes('1 min. Read the question slowly. The field asks how high a ranking score can go; we ask whether the alarm would help and whether it travels. Three research questions follow.');

  // ===== 7 HCP IN THE LOOP =====
  s = slide('CONTENT', 'APPROACH', 'Question and approach');
  s.addText('Healthcare professionals in the loop make clinical AI safer and more useful', { placeholder: 'title' });
  const ev = [
    ['Better together', 'AI support improved clinicians\' diagnostic accuracy beyond AI or clinicians alone ' + c('tschandl')],
    ['Engaged clinicians save lives', 'Sepsis alerts confirmed by clinicians within 3 h: 18.7 % lower relative mortality ' + c('adams')],
    ['Trust is built, not assumed', 'Clinicians trust AI through experience, endorsement and systems that respect their judgement ' + c('henrynpj')],
    ['Clinical input at every stage', 'From problem definition to deployment ' + c('wiens') + '; health records encode care decisions ' + c('agniel')],
  ];
  ev.forEach((e, i) => { const x = M + i * 3.07; T(s, e[0], x, 1.6, 2.9, 0.6, { size: 14, bold: true, color: RED, valign: 'bottom' }); T(s, e[1], x, 2.25, 2.9, 0.95, { size: 12.5 }); });
  const exs = [
    [I.pill, 'Example 1: antibiotics', 'Usually: every antibiotic order is an input, so the model predicts sepsis from the treatment that defines it, or antibiotics are dropped entirely.',
      'Here: cefazolin at induction of anaesthesia, stopped within 24 h, with no culture sent, is surgical prophylaxis ' + c('bratzler') + '. Prophylaxis is kept as a predictor by guideline rule; empirical and culture-directed antibiotics are excluded ' + c('evans') + '.'],
    [I.xray, 'Example 2: suspicion proxies', 'Usually: a stress-dose hydrocortisone order or a chest X-ray request is treated as a strong predictor.',
      'Here: these show that the team already suspects sepsis. They are declared as proxies and every result is reported with and without them, separating the patient\'s signal from the team\'s.'],
  ];
  exs.forEach((e, i) => {
    const x = M + i * 6.15, y = 3.3;
    box(s, x, y, 5.95, 3.05, { line: RULE });
    tile(s, e[0], x + 0.2, y + 0.2, 0.55);
    T(s, e[1], x + 0.95, y + 0.2, 4.8, 0.55, { size: 16, bold: true, valign: 'middle' });
    T(s, e[2], x + 0.2, y + 0.9, 5.55, 0.8, { size: 12.5, color: GREY });
    T(s, e[3], x + 0.2, y + 1.7, 5.55, 1.3, { size: 13 });
  });
  refFooter(s);
  s.addNotes('1 min. The evidence first: human and AI together outperform either alone, sepsis alerts save lives when clinicians engage with them, trust has to be built, and health records encode clinical decisions. Then two examples from this project where clinical knowledge decided what the model may and may not see.');

  // ===== 8 DATABASES =====
  s = slide('CONTENT', 'DATA', 'Question and approach');
  s.addText('Three open intensive-care databases, all accessed through PhysioNet', { placeholder: 'title' });
  const dbs = [
    ['MIMIC-IV 3.1', 'Beth Israel Deaconess Medical Center, Boston', 'about 94,000', 'ICU stays', 'Every charted vital sign, laboratory result, medication, procedure, microbiology result and diagnosis, de-identified ' + c('johnson'), 'Development and internal testing'],
    ['eICU-CRD 2.0', '208 US hospitals, 2014 to 2015', '200,859', 'ICU admissions', 'Tele-ICU records from many hospitals with different charting habits; times stored as minutes from ICU admission ' + c('pollard'), 'Second hospital system: the transfer test'],
    ['PhysioNet 2019', 'Challenge data from US hospitals', '40,336', 'patients', '40 hourly variables, prepared by the organisers, with a pre-shifted sepsis label ' + c('reyna'), 'Comparison with published challenge models'],
  ];
  dbs.forEach((d, i) => {
    const x = M + i * 4.1, w = 3.9;
    box(s, x, 1.7, w, 4.15, { line: RULE });
    tile(s, I.db, x + 0.2, 1.88, 0.55);
    T(s, d[0], x + 0.9, 1.88, w - 1.0, 0.55, { size: 18, bold: true, valign: 'middle' });
    T(s, d[1], x + 0.2, 2.55, w - 0.4, 0.55, { size: 12.5, color: GREY });
    T(s, d[2], x + 0.2, 3.05, w - 0.4, 0.6, { size: 30, bold: true, color: RED });
    T(s, d[3], x + 0.2, 3.62, w - 0.4, 0.3, { size: 12.5, color: GREY });
    T(s, d[4], x + 0.2, 4.0, w - 0.4, 1.15, { size: 12.5 });
    T(s, 'Role here: ' + d[5], x + 0.2, 5.2, w - 0.4, 0.6, { size: 12.5, bold: true });
  });
  T(s, 'Access requires credentialing, human-subjects research training and a data use agreement ' + c('goldberger') + '. No patient-level data leave the analysis environment. One sepsis definition is applied to both raw databases with published benchmark code ' + c('yaib', 'ricu') + '.', M, 5.95, CW, 0.55, { size: 12.5 });
  refFooter(s);
  s.addNotes('1 min. Introduce the databases before going deeper. MIMIC-IV is one large Boston teaching hospital; eICU is a network of 208 hospitals with very different charting; PhysioNet 2019 is the prepared challenge set used by most published models. All are open to credentialed researchers, which is what makes this work reproducible.');

  // ===== 9 PIPELINE FIGURE =====
  s = slide('CONTENT', 'APPROACH: MIXED-METHODS DESIGN', 'Question and approach');
  s.addText('The research pipeline, built like the models it trains', { placeholder: 'title' });
  T(s, 'Phase 1  Quantitative', M, 1.6, 4, 0.35, { size: 13, bold: true, color: RED });
  const pipe = [
    ['Raw records', 'MIMIC-IV and eICU', 'two hospital systems make transfer real'],
    ['Harmonise', 'same concept, unit and clock', 'compare like with like'],
    ['One label', 'Sepsis-3 onset hour ' + c('seymour16'), 'results comparable'],
    ['Hourly features', '655, each used only from the hour recorded', 'no information from the future'],
    ['Models', '16 compared on identical hours', 'architecture is a hypothesis'],
    ['Evaluate', 'utility, false alarms per day, transfer, sealed holdout', 'what would help patients'],
  ];
  const bw = 1.82, bg = 0.24;
  pipe.forEach((p, i) => {
    const x = M + i * (bw + bg);
    box(s, x, 2.0, bw, 1.55, { fill: i === 0 ? LIGHT : WHITE, line: INK });
    T(s, p[0], x + 0.1, 2.08, bw - 0.2, 0.4, { size: 14, bold: true, color: RED });
    T(s, p[1], x + 0.1, 2.48, bw - 0.2, 1.05, { size: 12 });
    T(s, 'Why: ' + p[2], x, 3.65, bw, 0.6, { size: 11.5, color: GREY, italic: true });
    if (i < pipe.length - 1) arrow(s, x + bw, 2.78, x + bw + bg, 2.78, INK, 1.5);
  });
  // phase 2 and 3
  const ex = M + 5 * (bw + bg) + bw / 2;
  arrow(s, ex, 4.25, ex, 4.6, RED, 2);
  s.addShape(pres.ShapeType.line, { x: M + 2.0, y: 4.6, w: ex - M - 2.0, h: 0.001, line: { color: RED, width: 2 }, objectName: 'connector' });
  arrow(s, M + 2.0, 4.6, M + 2.0, 4.85, RED, 2);
  box(s, M, 4.85, 5.85, 1.5, { fill: PINK, line: RED });
  T(s, 'Phase 2  Qualitative (in progress)', M + 0.2, 4.93, 5.5, 0.35, { size: 14, bold: true, color: RED });
  T(s, 'Healthcare professionals: would they trust and act on the alert, what explanation do they need, what alarm burden is acceptable ' + c('henrynpj') + '.', M + 0.2, 5.3, 5.5, 1.0, { size: 12.5 });
  arrow(s, M + 5.85, 5.6, M + 6.27, 5.6, RED, 2);
  box(s, M + 6.27, 4.85, CW - 6.27, 1.5, { fill: WHITE, line: RED, lw: 1.5 });
  T(s, 'Phase 3  Future direction: hospital patients', M + 6.47, 4.93, 5.4, 0.35, { size: 14, bold: true, color: RED });
  T(s, 'A silent test on live ICU data (alerts logged, not shown, compared with outcomes), then a clinician-facing pilot ' + c('kwong') + '.', M + 6.47, 5.3, 5.4, 1.0, { size: 12.5 });
  refFooter(s);
  s.addNotes('1 min. Read the figure left to right like a model architecture: raw records, harmonisation, one label, hourly features, models, evaluation. Each box has its reason underneath. The evaluation feeds the qualitative phase with healthcare professionals, which is running now, and the future direction is a silent test on hospital patients.');

  // ===== 10 MODELS =====
  s = slide('CONTENT', 'APPROACH: MODELS', 'Question and approach');
  s.addText('Organ-structured attention is a hypothesis we test, not an assumption', { placeholder: 'title' });
  T(s, 'OSTA: organ-system-aware temporal attention (this project)', M, 1.6, 6.6, 0.35, { size: 14, bold: true, color: RED });
  const og = ['Respiratory', 'Circulation', 'Kidney', 'Liver', 'Clotting', 'Brain', 'Infection, treatment, context'];
  og.forEach((o, i) => {
    const y = 2.05 + i * 0.5;
    box(s, M, y, 2.3, 0.4, { fill: LIGHT, line: LIGHT });
    T(s, o, M + 0.08, y, 2.2, 0.4, { size: 12, valign: 'middle' });
    arrow(s, M + 2.3, y + 0.2, M + 2.6, y + 0.2, INK, 1);
    box(s, M + 2.6, y, 1.35, 0.4, { line: RED });
    T(s, 'attention over time', M + 2.62, y, 1.31, 0.4, { size: 10.5, align: 'center', valign: 'middle', color: RED });
  });
  const my = 2.05 + 3 * 0.5 + 0.2;
  arrow(s, M + 3.95, my, M + 4.25, my, INK, 1.5);
  box(s, M + 4.25, my - 0.8, 1.1, 1.6, { fill: RED, line: RED });
  T(s, 'cross-organ attention', M + 4.28, my - 0.8, 1.04, 1.6, { size: 12, bold: true, color: WHITE, align: 'center', valign: 'middle' });
  arrow(s, M + 5.35, my, M + 5.65, my, INK, 1.5);
  box(s, M + 5.65, my - 0.8, 1.05, 1.6, { fill: INK, line: INK });
  T(s, 'sepsis risk + risk per organ', M + 5.68, my - 0.8, 0.99, 1.6, { size: 12, bold: true, color: WHITE, align: 'center', valign: 'middle' });
  T(s, 'Mirrors how an ICU team reasons: each organ, then how organs affect each other. Built on transformer attention ' + c('vaswani') + '.', M, 5.6, 6.6, 0.75, { size: 12.5, color: GREY });
  const rx = M + 7.2, rw = CW - 7.2;
  T(s, 'Compared on identical hours, rules fixed in advance', rx, 1.6, rw, 0.35, { size: 14, bold: true });
  const arms = [
    ['OSTA without organ grouping', 'the ablation that decides whether organ structure stays'],
    ['CNN-Transformer (earlier work)', 'local patterns over 1 to 12 h, then attention'],
    ['GRU-D, temporal CNN', 'models built for irregular ICU data ' + c('che', 'bai')],
    ['Signatures + boosted trees', 'the PhysioNet 2019 winner\'s method ' + c('morrill')],
    ['Self-supervised pretraining', 'learn from unlabelled stays first ' + c('yeche21')],
    ['Logistic regression, boosted trees', 'simple baselines'],
  ];
  arms.forEach((a, i) => {
    const y = 2.05 + i * 0.66;
    s.addShape(pres.ShapeType.rect, { x: rx, y: y + 0.08, w: 0.14, h: 0.14, fill: { color: RED }, line: { color: RED, width: 0 }, objectName: 'marker' });
    T(s, a[0], rx + 0.3, y, rw - 0.3, 0.3, { size: 13.5, bold: true });
    T(s, a[1], rx + 0.3, y + 0.3, rw - 0.3, 0.33, { size: 12, color: GREY });
  });
  T(s, 'Training loss chosen by clinical utility, against plain and time-smoothed losses ' + c('yeche23') + '.', rx, 6.0, rw, 0.4, { size: 12, color: GREY });
  refFooter(s);
  s.addNotes('1 min. OSTA groups the predictors by organ, reads each organ over time, lets the organs inform each other, and outputs a sepsis risk plus a risk per organ. Because I believe in it, I test it against the same model without the organ grouping, and against the published alternatives including the winner\'s method.');

  // ===== 11 SAME LANGUAGE =====
  pres.addSection({ title: 'Preliminary results' });
  s = slide('CONTENT', 'PRELIMINARY RESULTS', 'Preliminary results'); prelim(s);
  s.addText('Result 1: making two hospital systems speak the same language', { placeholder: 'title' });
  T(s, 'Example: body temperature', M, 1.6, 6, 0.35, { size: 14, bold: true, color: RED });
  box(s, M, 2.0, 3.55, 1.75, { line: RULE });
  rich(s, [['MIMIC-IV ' + c('johnson'), { bold: true, br: true }], ['item 223761: Temperature, Fahrenheit', { size: 12, br: true }], ['item 223762: Temperature, Celsius', { size: 12, br: true }], ['clock: date-shifted date and time', { size: 12, color: GREY }]], M + 0.15, 2.08, 3.3, 1.6, { size: 13.5 });
  box(s, M, 3.95, 3.55, 1.75, { line: RULE });
  rich(s, [['eICU ' + c('pollard'), { bold: true, br: true }], ['vital-sign table: temperature (often empty)', { size: 12, br: true }], ['nurse charting: "Temperature (C)", "(F)"', { size: 12, br: true }], ['clock: minutes from ICU admission', { size: 12, color: GREY }]], M + 0.15, 4.03, 3.3, 1.6, { size: 13.5 });
  arrow(s, M + 3.55, 2.88, M + 4.1, 3.65, RED, 2); arrow(s, M + 3.55, 4.83, M + 4.1, 4.05, RED, 2);
  box(s, M + 4.1, 3.0, 2.25, 1.75, { fill: RED, line: RED });
  rich(s, [['One concept', { bold: true, color: WHITE, br: true }], ['Temperature in °C, hours from ICU admission, usable from the hour it was charted', { size: 12, color: WHITE }]], M + 4.2, 3.08, 2.05, 1.6, { size: 14 });
  T(s, 'Repeated for 76 measurement channels plus drugs, devices, fluids and diagnoses ' + c('thiswork') + '.', M, 5.85, 6.4, 0.5, { size: 12.5, color: GREY });
  s.addChart(pres.ChartType.bar, [
    { name: 'Before harmonisation', labels: ['eICU temp.', 'eICU BP', 'eICU weight', 'eICU GCS', 'MIMIC urine', 'MIMIC GCS'], values: [5, 21, 6, 62, 9, 66] },
    { name: 'After', labels: ['eICU temp.', 'eICU BP', 'eICU weight', 'eICU GCS', 'MIMIC urine', 'MIMIC GCS'], values: [94, 99.5, 96, 83, 44, 78] },
  ], { x: M + 6.65, y: 1.55, w: CW - 6.65, h: 4.8, barDir: 'col', barGrouping: 'clustered', barGapWidthPct: 55, chartColors: [MID, RED],
    showTitle: true, title: 'Patient-hours with a usable value (%)', titleFontSize: 13, titleColor: INK, titleFontFace: '+mn-lt',
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 11, dataLabelColor: INK, dataLabelFontFace: '+mn-lt', dataLabelFormatCode: '0',
    valAxisMinVal: 0, valAxisMaxVal: 110, valAxisMajorUnit: 25, valAxisLabelFontSize: 11, valAxisLabelColor: GREY, valAxisLabelFontFace: '+mn-lt',
    catAxisLabelFontSize: 11, catAxisLabelColor: INK, catAxisLabelFontFace: '+mn-lt', valGridLine: { color: 'E0E0E0', size: 0.5 }, catGridLine: { style: 'none' },
    showLegend: true, legendPos: 'b', legendFontSize: 12, legendColor: INK, legendFontFace: '+mn-lt', objectName: 'coverage chart' });
  refFooter(s);
  s.addNotes('1 min. "Speaking the same language" means that every raw item in both databases is translated to one shared concept, in one unit, on one clock, available from the hour it was recorded. Temperature is the example: MIMIC-IV stores it under two item numbers, one in Fahrenheit and one in Celsius, with real dates; eICU stores it in a vital-sign table that is often empty and in the nurses\' charting table under text labels, with times counted in minutes from ICU admission. Without this, the same patient looks different to the model in each hospital. The chart shows how much usable data that recovered.');

  // ===== 12 LEAKAGE =====
  s = slide('CONTENT', 'PRELIMINARY RESULTS', 'Preliminary results'); prelim(s);
  s.addText('Result 2: removing information from the future is the biggest single correction', { placeholder: 'title' });
  box(s, M, 1.65, 5.7, 4.7, { line: RULE });
  tile(s, I.search, M + 0.2, 1.85, 0.55);
  T(s, 'An audit of our own earlier pipeline found', M + 0.95, 1.85, 4.6, 0.55, { size: 15, bold: true, valign: 'middle' });
  list(s, ['Hours after sepsis onset labelled positive: the model learnt sepsis that had already started.', 'Values used from when they were measured, not when they became available.', 'Treatments that define the label among the inputs.', 'Those models were retired and are not reported.'], M + 0.25, 2.6, 5.2, 2.9, { size: 14 });
  T(s, 'Leakage of this kind is documented across science ' + c('kapoor') + '.', M + 0.25, 5.6, 5.2, 0.6, { size: 13, italic: true, color: GREY });
  T(s, 'Rebuilt causally: OSTA on the PhysioNet 2019 test set, 3-seed ensemble ' + c('reyna', 'thiswork'), M + 5.95, 1.65, CW - 5.95, 0.6, { size: 14, bold: true, color: RED });
  [['0.81', 'patient-level AUROC'], ['0.80', 'hourly AUROC'], ['0.22', 'utility (0.30 at the conformal threshold)']].forEach((k, i) => {
    const x = M + 5.95 + i * 2.08;
    box(s, x, 2.35, 1.95, 1.6, { fill: LIGHT, line: LIGHT });
    T(s, k[0], x + 0.15, 2.45, 1.7, 0.75, { size: 36, bold: true, color: RED });
    T(s, k[1], x + 0.15, 3.2, 1.7, 0.7, { size: 12 });
  });
  list(s, ['Only 1.6 % of hours are positive, so ranking scores look modest even for a useful model.', 'Utility 0.22: the alarms are worth about a fifth of perfect alarms after paying for false alarms.', 'This honest baseline is where every later number starts.'], M + 5.95, 4.2, CW - 5.95, 2.1, { size: 13.5 });
  refFooter(s);
  s.addNotes('1 min. Say "preliminary". We audited our own earlier models, found three kinds of leakage, and retired them. The causal version scores lower, and it is the one we stand behind.');

  // ===== 13 UTILITY =====
  s = slide('CONTENT', 'PRELIMINARY RESULTS', 'Preliminary results'); prelim(s);
  s.addText('Result 3: positive utility on MIMIC-IV, where the challenge winner fell below zero on an unseen hospital', { placeholder: 'title' });
  const labs = ['Winner, new patients, its 2 hospitals', 'Winner, unseen third hospital', 'Our causal OSTA, PhysioNet test', 'Our best model, MIMIC-IV development test'];
  s.addChart(pres.ChartType.bar, [{ name: 'Normalised utility', labels: labs, values: [0.43, -0.12, 0.22, 0.18] }], {
    x: M, y: 1.65, w: 7.4, h: 4.3, barDir: 'bar', barGrouping: 'clustered', barGapWidthPct: 45, chartColors: [MID, MID, RED, RED],
    showTitle: true, title: 'Normalised utility: 1 = perfect, 0 = never alarming, below 0 = worse than silence', titleFontSize: 12, titleColor: INK, titleFontFace: '+mn-lt',
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 12, dataLabelColor: INK, dataLabelFontBold: true, dataLabelFontFace: '+mn-lt', dataLabelFormatCode: '0.00',
    valAxisMinVal: -0.4, valAxisMaxVal: 0.6, valAxisMajorUnit: 0.2, valAxisLabelFontSize: 11, valAxisLabelColor: GREY, valAxisLabelFontFace: '+mn-lt', valAxisLabelFormatCode: '0.0',
    catAxisLabelFontSize: 12, catAxisLabelColor: INK, catAxisLabelFontFace: '+mn-lt', catAxisOrientation: 'maxMin', catAxisLabelPos: 'low', valGridLine: { color: 'E0E0E0', size: 0.5 }, catGridLine: { style: 'none' }, showLegend: false, objectName: 'utility chart' });
  s.addShape(pres.ShapeType.rect, { x: M + 0.3, y: 6.05, w: 0.25, h: 0.2, fill: { color: MID }, line: { color: MID, width: 0 }, objectName: 'legend swatch' });
  T(s, 'Published challenge winner ' + c('reyna', 'morrill'), M + 0.62, 6.0, 3.3, 0.3, { size: 12, valign: 'middle' });
  s.addShape(pres.ShapeType.rect, { x: M + 4.0, y: 6.05, w: 0.25, h: 0.2, fill: { color: RED }, line: { color: RED, width: 0 }, objectName: 'legend swatch' });
  T(s, 'This project, causal evaluation ' + c('thiswork'), M + 4.32, 6.0, 3.1, 0.3, { size: 12, valign: 'middle' });
  const px = M + 7.65, pw = CW - 7.65;
  box(s, px, 1.65, pw, 4.65, { fill: LIGHT, line: LIGHT });
  T(s, 'MIMIC-IV development test split', px + 0.2, 1.75, pw - 0.4, 0.35, { size: 14, bold: true });
  T(s, '1,422 stays, 63,488 hours, 71 sepsis events', px + 0.2, 2.1, pw - 0.4, 0.3, { size: 12, color: GREY });
  [['0.81', 'hourly AUROC, 3 seeds'], ['5 h', 'median warning before onset'], ['1 in 2', 'sepsis events caught at 0.5 false alarms a day'], ['0.08-0.27', '95 % CI of utility 0.18']].forEach((k, i) => {
    const col = i % 2, row = Math.floor(i / 2), x = px + 0.2 + col * (pw - 0.4) / 2, y = 2.55 + row * 1.35;
    T(s, k[0], x, y, (pw - 0.5) / 2, 0.6, { size: k[0].length > 6 ? 22 : 28, bold: true, color: RED });
    T(s, k[1], x, y + 0.6, (pw - 0.6) / 2, 0.6, { size: 12 });
  });
  T(s, 'On 10,000-stay samples all neural models reach AUROC 0.80 to 0.81: the full cohort will separate them. The winner\'s method is being replicated on MIMIC-IV now.', px + 0.2, 5.25, pw - 0.4, 1.0, { size: 12, color: GREY });
  refFooter(s);
  s.addNotes('1 min. Grey is the published winner: 0.43 on new patients from the hospitals it trained on, minus 0.12 on a hospital it had never seen. Red is this project. The point is not that 0.18 is high; it is positive, with its confidence interval above zero, on raw data scored causally. Say the caveats: preliminary, development split, holdout sealed.');

  // ===== 14 CONTRIBUTION + NEXT =====
  pres.addSection({ title: 'Contribution and next steps' });
  s = slide('CONTENT', 'CONTRIBUTION AND NEXT STEPS', 'Contribution and next steps');
  s.addText('An honest, transferable test of sepsis warnings, and the path to hospital patients', { placeholder: 'title' });
  T(s, 'Contribution so far', M, 1.6, 6, 0.35, { size: 15, bold: true, color: RED });
  const con = [
    [I.lock, 'Causal, cross-database pipeline', 'one sepsis definition, two hospital systems, 655 clinically defined predictors ' + c('thiswork')],
    [I.scale, 'Evaluation by clinical utility', 'false alarms per day, warning time, transfer, sealed holdout ' + c('reyna')],
    [I.search, 'Three findings', 'leakage inflates scores; data harmonisation drives transfer; small samples overfit'],
    [I.book, 'Three manuscripts submitted in 2026', 'AMR diagnostics review ' + c('amr') + '; sepsis-onset cohort study ' + c('temporal') + '; thermography meta-analysis ' + c('thermo')],
  ];
  con.forEach((k, i) => {
    const y = 2.05 + i * 0.98;
    tile(s, k[0], M, y + 0.05, 0.5, INK);
    T(s, k[1], M + 0.65, y, 5.4, 0.33, { size: 14, bold: true });
    T(s, k[2], M + 0.65, y + 0.33, 5.6, 0.62, { size: 12.5, color: GREY });
  });
  T(s, 'Next steps', M + 6.55, 1.6, 5, 0.35, { size: 15, bold: true, color: RED });
  const nx = [
    ['Now', 'Complete the qualitative study with healthcare professionals; finish the 16-model comparison'],
    ['Next', 'Full cohort (about 94,000 + 200,000 stays), three seeds, leave-hospital-out testing'],
    ['Then', 'Freeze the protocol; open the sealed holdout once; set the alarm policy with the qualitative findings'],
    ['Future', 'Silent test on hospital patients, then a clinician-facing pilot ' + c('kwong')],
  ];
  nx.forEach((k, i) => {
    const y = 2.05 + i * 0.98;
    box(s, M + 6.55, y + 0.02, 1.05, 0.5, { fill: i === 3 ? RED : INK, line: i === 3 ? RED : INK });
    T(s, k[0], M + 6.55, y + 0.02, 1.05, 0.5, { size: 13, bold: true, color: WHITE, align: 'center', valign: 'middle' });
    T(s, k[1], M + 7.8, y, CW - 7.8, 0.9, { size: 13 });
  });
  T(s, 'Numbers shown today are preliminary development-split results; the full results are in the manuscript in preparation.', M, 6.0, CW, 0.35, { size: 12, italic: true, color: GREY });
  refFooter(s);
  s.addNotes('1 min. Contribution: the pipeline and the evaluation that make results believable, three findings, three submitted papers. Next: finish the qualitative study and the comparison, scale to the full cohort, open the holdout once, then test on hospital patients.');

  // ===== 15 INPUT =====
  pres.addSection({ title: 'Input' });
  s = slide('CLOSING', 'WHERE I WOULD LIKE YOUR INPUT', 'Input');
  s.addText('Where I would like your input', { placeholder: 'title' });
  const qs = [
    [I.scale, 'Which score should choose the model when they disagree?', 'Utility rewards an alarm hours before onset and charges for every false-alarm hour; AUROC rewards ranking ' + c('reyna', 'shah') + '. On our data they already rank models differently. How much sensitivity would you trade to halve false alarms per patient-day?'],
    [I.exchange, 'How should one sepsis label work across two hospital systems?', 'In MIMIC-IV, suspicion of infection needs an antibiotic and a culture; eICU records antibiotics only ' + c('seymour16', 'pollard') + '. Harmonise both to the weaker definition, keep each database\'s best definition, or treat them as two targets?'],
  ];
  qs.forEach((q, i) => {
    const y = 1.75 + i * 2.35;
    box(s, M, y, CW, 2.1, { fill: WHITE, line: WHITE });
    tile(s, q[0], M + 0.25, y + 0.3, 0.7, RED);
    T(s, q[1], M + 1.2, y + 0.25, CW - 1.5, 0.5, { size: 19, bold: true, valign: 'middle' });
    T(s, q[2], M + 1.2, y + 0.8, CW - 1.5, 1.2, { size: 14 });
  });
  refFooter(s, true);
  s.addNotes('1 min. Two questions: which score decides, and how to define sepsis across hospital systems. Then thank the audience and stop.');

  // ===== BACKUPS =====
  pres.addSection({ title: 'Backup' });
  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Glossary of clinical terms', { placeholder: 'title' });
  const gl = [
    ['Sepsis-3', 'Organ dysfunction caused by a dysregulated response to infection; operationalised as suspected infection plus a SOFA rise of 2 or more ' + c('singer')],
    ['SOFA', '0 to 4 points for each of six organ systems ' + c('vincent')],
    ['Suspected infection', 'An antibiotic and a culture within 72 h / 24 h of each other ' + c('seymour16') + '; eICU has antibiotics only'],
    ['Onset and horizon', 'Onset is the first hour both criteria are met; the model asks every hour whether onset falls within the next 6 h'],
    ['qSOFA, NEWS2', 'Bedside screening scores from vital signs and mental state ' + c('seymour16', 'rcp') + '; predictors here, never the label'],
    ['AKI stage', 'Kidney injury stage from creatinine and urine output ' + c('kdigo')],
    ['Utility', 'Challenge score: reward for alarms up to 12 h before onset, cost for false alarms and missed sepsis; 1 perfect, 0 never alarming ' + c('reyna')],
    ['Causal', 'Each value used only from the hour it was recorded, with a measured flag and its age; no hour after onset used'],
  ];
  gl.forEach((g, i) => { const col = i % 2, row = Math.floor(i / 2), x = M + col * 6.15, y = 1.65 + row * 1.15; T(s, g[0], x, y, 1.8, 1.0, { size: 13, bold: true, color: RED }); T(s, g[1], x + 1.85, y, 4.1, 1.05, { size: 12 }); });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('The utility score: what an alarm is worth, hour by hour ' + c('reyna'), { placeholder: 'title' });
  s.addChart(pres.ChartType.line, [
    { name: 'Reward for an alarm (sepsis patient)', labels: ['-14', '-12', '-10', '-8', '-6', '-4', '-2', '0', '+1', '+3'], values: [0, 0, 0.33, 0.67, 1, 0.78, 0.56, 0.33, 0.22, 0] },
    { name: 'Penalty for silence (sepsis patient)', labels: ['-14', '-12', '-10', '-8', '-6', '-4', '-2', '0', '+1', '+3'], values: [0, 0, 0, 0, 0, -0.44, -0.89, -1.33, -1.56, -2] },
  ], { x: M, y: 1.6, w: 7.6, h: 4.7, lineSize: 3, lineDataSymbol: 'none', chartColors: [RED, MID], showTitle: true, title: 'Hours relative to sepsis onset', titleFontSize: 12, titleColor: INK, titleFontFace: '+mn-lt',
    valAxisMinVal: -2, valAxisMaxVal: 1, valAxisMajorUnit: 0.5, valAxisLabelFontSize: 11, valAxisLabelColor: GREY, valAxisLabelFontFace: '+mn-lt', catAxisLabelFontSize: 11, catAxisLabelColor: GREY, catAxisLabelFontFace: '+mn-lt',
    valGridLine: { color: 'E0E0E0', size: 0.5 }, catGridLine: { style: 'none' }, showLegend: true, legendPos: 'b', legendFontSize: 12, legendColor: INK, legendFontFace: '+mn-lt', objectName: 'utility curve' });
  list(s, ['An alarm earns most at 6 h before onset; earlier than 12 h earns nothing.', 'Each false-alarm hour on a patient without sepsis costs 0.05.', 'Silence after onset costs up to 2 points per hour.', 'Normalised: (score - never alarming) / (perfect - never alarming).', 'Official scorer code used unchanged.'], M + 7.9, 1.75, CW - 7.9, 4.5, { size: 13.5 });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Six choices that differ from common practice', { placeholder: 'title' });
  s.addTable([
    [th('Common practice'), th('This project'), th('Why')],
    [td('Challenge-prepared tables ' + c('reyna')), td('Raw MIMIC-IV and eICU', { bold: true }), td('Transfer across hospital systems is tested for real')],
    [td('Each study its own definition ' + c('moor21')), td('One Sepsis-3 definition on both databases ' + c('yaib', 'ricu'), { bold: true }), td('Results comparable')],
    [td('Values carried forward; post-onset hours positive'), td('Each value used from the hour recorded, expires after 24 h; post-onset hours excluded', { bold: true }), td('No information from the future ' + c('kapoor'))],
    [td('40 to 125 variables'), td('655 clinically defined predictors', { bold: true }), td('The whole clinical picture')],
    [td('Antibiotics as predictors'), td('Label-defining antibiotics excluded; prophylaxis kept by rule ' + c('bratzler'), { bold: true }), td('Avoids predicting the label from itself')],
    [td('AUROC on one split'), td('Utility, false alarms per day, warning time, calibration, sealed holdout', { bold: true }), td('What would help patients ' + c('shah'))],
  ], { x: M, y: 1.65, w: CW, colW: [3.4, 5.2, 3.53], border: { type: 'solid', color: RULE, pt: 0.75 }, fontFace: 'Arial', margin: 0.07, objectName: 'choices table' });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('The 655 predictors, each with a measured flag and an age', { placeholder: 'title' });
  const cats = [
    ['Vital signs and monitoring', 'heart rate, cuff and arterial pressures, respiratory rate, oxygen saturation, temperature, end-tidal CO2, CVP, cardiac output, pain and sedation scores'],
    ['Laboratory and blood gas', 'chemistry, full blood count with differential, coagulation, lactate, procalcitonin, troponin, BNP, ferritin, D-dimer, ammonia, urinalysis, blood gases'],
    ['Scores and derived', 'SOFA per organ ' + c('vincent') + ', qSOFA, NEWS2 ' + c('rcp') + ', shock index, P/F and S/F ratios, changes from previous and baseline, 24 h extremes'],
    ['Organ support', 'vasopressor dose (noradrenaline equivalents), ventilation settings, oxygen flow, renal replacement, urine output and AKI stage ' + c('kdigo')],
    ['Fluids, drugs, devices', 'crystalloids, transfusions, nutrition, central and arterial lines, catheters, drains; steroids, immunosuppressants, chemotherapy, sedatives, opioids'],
    ['Context and history', 'admission source, ICU type, hours before ICU, prior admissions, prior positive cultures and antibiotics, 17 comorbidities, imaging orders'],
    ['Prophylactic antibiotics', 'surgical prophylaxis by agent, timing, duration, no culture or escalation ' + c('bratzler') + '; medical prophylaxis by agent and dose'],
    ['Never predictors', 'label-defining antibiotics and cultures; race, ethnicity, insurance (fairness analysis only); anything after the prediction hour'],
  ];
  cats.forEach((k, i) => { const col = i % 2, row = Math.floor(i / 2), x = M + col * 6.15, y = 1.65 + row * 1.2;
    box(s, x, y, 5.95, 1.08, { fill: i === 7 ? PINK : LIGHT, line: i === 7 ? PINK : LIGHT });
    T(s, k[0], x + 0.15, y + 0.06, 5.65, 0.3, { size: 12.5, bold: true, color: RED }); T(s, k[1], x + 0.15, y + 0.38, 5.65, 0.68, { size: 11.5 }); });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Cohorts, splits and the sealed holdout', { placeholder: 'title' });
  s.addTable([
    [th('Database'), th('Candidate stays'), th('Sample so far'), th('After exclusions'), th('Sealed holdout')],
    [td('MIMIC-IV 3.1 ' + c('johnson'), { bold: true }), td('about 94,000'), td('10,000'), td('8,795'), td('20 % of patients, deterministic hash')],
    [td('eICU-CRD 2.0 ' + c('pollard'), { bold: true }), td('200,859'), td('10,000'), td('5,710'), td('20 % of patients, deterministic hash')],
  ], { x: M, y: 1.65, w: CW, colW: [3.0, 2.1, 1.9, 2.0, 3.13], border: { type: 'solid', color: RULE, pt: 0.75 }, fontFace: 'Arial', margin: 0.07, objectName: 'cohort table' });
  list(s, ['Labels: Sepsis-3 via YAIB / ricu ' + c('yaib', 'ricu') + '; onset within the next 6 h; post-onset hours excluded; up to 120 h per stay.', 'The 10,000-stay samples are fixed random draws, identical in every run.', 'The holdout is opened once, after the protocol is frozen; nothing is tuned on it.', 'Unlabelled pretraining corpus: 67,455 MIMIC-IV and 75,000 eICU stays outside the cohort and the holdout.'], M, 3.4, CW, 2.9, { size: 14 });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('On 10,000 stays every model overfits within three epochs', { placeholder: 'title' });
  [['1 to 3', 'epochs to the best validation score, while training loss keeps falling'], ['175', 'septic stays per training split, against 300 to 655 predictors'], ['0.80 to 0.81', 'AUROC of OSTA, CNN-Transformer, output fusion: differences below seed noise (SD 0.012)']].forEach((k, i) => {
    const x = M + i * 4.1; T(s, k[0], x, 1.8, 3.9, 0.8, { size: 36, bold: true, color: RED }); T(s, k[1], x, 2.65, 3.8, 1.1, { size: 14 }); });
  list(s, ['Response: full cohort (about nine times more sepsis cases), self-supervised pretraining on unlabelled stays ' + c('yeche21') + ', loss chosen by utility ' + c('yeche23') + ', three seeds.', 'All figures: ' + 'this work, preliminary ' + c('thiswork') + '.'], M, 4.1, CW, 2.0, { size: 14 });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('RD6 supplement: publications and outputs', { placeholder: 'title' });
  s.addTable([
    [th('Manuscript'), th('Journal'), th('Submitted'), th('Status')],
    [td('Artificial Intelligence in the Diagnosis of Antimicrobial Resistance: Rapid Diagnostics and Imaging Innovations', { bold: true }), td('Int J Antimicrob Agents'), td('9 Oct 2026'), td('Technical check')],
    [td('Temporal Patterns and Predictors of Sepsis Onset in ICU Patients: A Retrospective Cohort Study Using PhysioNet Data', { bold: true }), td('Frontiers in Medicine'), td('23 Sep 2026'), td('Editorial assignment')],
    [td('Diagnostic Applications of Infrared Thermography Across Infectious Diseases: A Systematic Review with a Subgroup Meta-Analysis', { bold: true }), td('JMIR'), td('18 Jul 2026'), td('In review')],
    [td('Early sepsis warning on MIMIC-IV and eICU: causal predictors, utility and transfer', { bold: true }), td('critical care informatics journal'), td('in preparation'), td('full-cohort and holdout results pending')],
  ], { x: M, y: 1.65, w: CW, colW: [6.2, 2.5, 1.5, 1.93], border: { type: 'solid', color: RULE, pt: 0.75 }, fontFace: 'Arial', margin: 0.07, objectName: 'publications table' });
  T(s, 'Earlier CNN-Transformer and OSTA manuscripts were withheld after the leakage audit; both architectures are re-evaluated causally in the current comparison.', M, 5.6, CW, 0.6, { size: 13, color: GREY });

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('RD6 supplement: training and the March 2026 plan', { placeholder: 'title' });
  T(s, 'Training', M, 1.6, 5.8, 0.35, { size: 15, bold: true, color: RED });
  list(s, ['Harvard PPCR: Clinical Trials Design, Implementation and Analysis (completed Feb 2026)', 'Iowa State University: Machine Learning Programme (completed Dec 2025)', 'DataCamp Python Data Science Career Track (in progress)', 'PhysioNet credentialed access: MIMIC-IV 3.1, eICU-CRD 2.0'], M, 2.0, 5.8, 4.0, { size: 13.5 });
  T(s, 'March 2026 plan: what happened', M + 6.3, 1.6, 5.8, 0.35, { size: 15, bold: true, color: RED });
  list(s, ['External validation on MIMIC-IV: became the core programme, extended to eICU.', 'CNN-Transformer and OSTA papers: withheld after the leakage audit.', 'AMR review: revised and submitted to Int J Antimicrob Agents.', 'Clinician study: now the qualitative phase, in progress.', 'Conference presentation: this talk.'], M + 6.3, 2.0, CW - 6.3, 4.0, { size: 13.5 });

  // References (generated last, so every number is final)
  const refs = ORDER.map((k, i) => `[${i + 1}] ${REF[k]}`);
  const half = Math.ceil(refs.length / 2);
  [refs.slice(0, half), refs.slice(half)].forEach((chunk, p) => {
    cur = null;
    const r = pres.addSlide({ masterName: 'BACKUP', sectionTitle: 'Backup' });
    T(r, 'BACKUP', M, 0.26, 8, 0.3, { size: 11, bold: true, color: RED });
    r.addText(`References (${p + 1} of 2)`, { placeholder: 'title' });
    const colN = Math.ceil(chunk.length / 2);
    [chunk.slice(0, colN), chunk.slice(colN)].forEach((col, j) => {
      r.addText(col.map((t, i) => ({ text: t, options: { breakLine: i < col.length - 1, paraSpaceAfter: 4 } })), { x: M + j * 6.15, y: 1.35, w: 5.95, h: 5.6, isTextBox: true, margin: 0, fontSize: 10, color: INK, valign: 'top', objectName: 'reference list' });
    });
  });

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log('written', OUT, 'references:', ORDER.length);
})().catch((e) => { console.error(e); process.exit(1); });
