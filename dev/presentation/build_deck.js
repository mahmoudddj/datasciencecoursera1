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
const SECOND_SUPERVISOR = process.env.SECOND_SUPERVISOR || 'Dr Kia Dashtipour';

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
  friedman: 'Friedman JH. Greedy function approximation: a gradient boosting machine. Ann Stat. 2001;29:1189-1232.',
  horn: 'Horn M, Moor M, Bock C, Rieck B, Borgwardt K. Set functions for time series. International Conference on Machine Learning (ICML). 2020.',
  gensheimer: 'Gensheimer MF, Narasimhan B. A scalable discrete-time survival model for neural networks. PeerJ. 2019;7:e6257.',
  gbd33: 'GBD 2019 Antimicrobial Resistance Collaborators. Global mortality associated with 33 bacterial pathogens in 2019: a systematic analysis for the Global Burden of Disease Study 2019. Lancet. 2022;400:2221-2248.',
  whotb: 'World Health Organization. WHO consolidated guidelines on tuberculosis. Module 2: screening. Systematic screening for tuberculosis disease. Geneva: WHO; 2021.',
  qin: 'Qin ZZ, Ahmed S, Sarker MS, et al. Tuberculosis detection from chest x-rays for triaging in a high tuberculosis-burden setting: a prospective study of CAD products. Lancet Digit Health. 2021;3:e543-e554.',
  hassan21: 'Hassan C, Spadaccini M, Iannone A, et al. Performance of artificial intelligence in colonoscopy for adenoma and polyp detection: a systematic review and meta-analysis. Gastrointest Endosc. 2021;93:77-85.',
  bone: 'Bone RC, Balk RA, Cerra FB, et al. Definitions for sepsis and organ failure and guidelines for the use of innovative therapies in sepsis. Chest. 1992;101:1644-1655.',
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
SHORT.yaib = 'van de Water et al., ICLR 2024'; SHORT.gbd33 = 'GBD 2019 AMR Collaborators, Lancet 2022'; SHORT.whotb = 'WHO 2021'; SHORT.qin = 'Qin et al., Lancet Digit Health 2021'; SHORT.hassan21 = 'Hassan et al., Gastrointest Endosc 2021'; SHORT.bone = 'Bone et al., Chest 1992'; SHORT.horn = 'Horn et al., ICML 2020'; SHORT.friedman = 'Friedman, Ann Stat 2001'; SHORT.gensheimer = 'Gensheimer and Narasimhan, PeerJ 2019'; SHORT.vaswani = 'Vaswani et al., NeurIPS 2017'; SHORT.bai = 'Bai et al., arXiv 2018'; SHORT.yeche23 = 'Yeche et al., ICML 2023'; SHORT.yeche21 = 'Yeche et al., ICML 2021';
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
  T(s, 'Using AI for Sepsis Prediction: A Data-Driven, Mixed-Method Approach', M, 1.0, W - 3.6 - M - 0.5, 2.3, { size: 32, bold: true, color: INK, valign: 'bottom', name: 'main title' });
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
  s = slide('CONTENT', 'INFECTIOUS DISEASE', 'Context');
  s.addText('Early detection of infection: lives and antibiotics saved', { placeholder: 'title' });
  const ids = [
    [I.globe, '13.7 M', 'infection-related deaths in 2019, 7.7 M of them linked to 33 common bacteria: 13.6 % of all deaths worldwide ' + c('gbd33')],
    [I.pill, '1.27 M', 'deaths in 2019 caused directly by antibiotic-resistant bacteria; 4.95 M associated ' + c('murray')],
    [I.micro, 'OR 0.66', 'odds of death with rapid diagnosis of bloodstream infection; effective therapy about 5 h sooner ' + c('timbrook')],
    [I.bell, 'WHO 2021', 'recommended AI reading of chest X-rays for tuberculosis screening, after independent testing matched expert readers ' + c('whotb', 'qin')],
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
  s.addNotes('1 min. No sepsis yet. Four numbers: the burden of infection, the burden of resistance, and two pieces of evidence that earlier detection helps: rapid diagnostics with stewardship, and AI reading of chest X-rays for TB, now WHO-recommended. The pathway shows where AI helps: earlier recognition (my project) and faster diagnosis (my review).');

  // ===== 3 SEPSIS =====
  s = slide('CONTENT', 'SEPSIS', 'Context');
  s.addText('Sepsis: infection with organ failure', { placeholder: 'title' });
  T(s, 'Sepsis-3: life-threatening organ dysfunction caused by a dysregulated host response to infection ' + c('singer'), M, 1.6, 6.3, 0.75, { size: 15, bold: true });
  T(s, 'Organ failure is measured by the SOFA score: 0 to 4 points for each organ system ' + c('vincent'), M, 2.4, 6.3, 0.5, { size: 13, color: GREY });
  const organs = [[I.lungs, 'Lungs', 'oxygen ratio PaO2/FiO2'], [I.heart, 'Circulation', 'blood pressure, vasopressors'], [I.kidney, 'Kidneys', 'creatinine, urine output'],
    [I.liver, 'Liver', 'bilirubin'], [I.drop, 'Clotting', 'platelets'], [I.brain, 'Brain', 'Glasgow Coma Scale']];
  organs.forEach((o, i) => {
    const col = i % 3, row = Math.floor(i / 3), x = M + col * 2.12, y = 2.95 + row * 1.5;
    tile(s, o[0], x, y, 0.7);
    T(s, o[1], x + 0.8, y, 1.25, 0.35, { size: 14, bold: true });
    T(s, o[2], x + 0.8, y + 0.35, 1.25, 0.9, { size: 12, color: GREY });
  });
  box(s, 7.3, 1.6, W - M - 7.3, 4.75, { fill: LIGHT, line: LIGHT });
  T(s, 'Why it is hard', 7.5, 1.72, 5, 0.35, { size: 15, bold: true, color: RED });
  s.addText([
    { text: 'Sepsis contributes to between one in two and one in three hospital deaths ' + c('liu') + '.', options: { bullet: { indent: 16 }, breakLine: true, paraSpaceAfter: 10, bold: true, color: RED } },
    { text: 'Each hour of delay to antibiotics raises the odds of death by about 4 % ' + c('seymour17') + '; in septic shock survival falls by 7.6 % per hour ' + c('kumar') + '.', options: { bullet: { indent: 16 }, breakLine: true, paraSpaceAfter: 10, bold: true, color: RED } },
    { text: 'Early signs are non-specific: fever, a fast heart rate and fast breathing are common in many ICU patients.', options: { bullet: { indent: 16 }, breakLine: true, paraSpaceAfter: 10 } },
    { text: 'Bedside screening scores such as qSOFA and SIRS detect deterioration less accurately than early-warning scores ' + c('churpek') + '.', options: { bullet: { indent: 16 }, paraSpaceAfter: 10 } },
  ], { x: 7.5, y: 2.15, w: W - M - 7.7, h: 4.1, isTextBox: true, margin: 0, fontSize: 14, color: INK, valign: 'top', objectName: 'why it is hard' });
  T(s, 'Sepsis-3: the Third International Consensus Definition (2016) ' + c('singer') + '.  SOFA: Sequential (Sepsis-related) Organ Failure Assessment ' + c('vincent') + '.  SIRS: Systemic Inflammatory Response Syndrome, the 1992 criteria (temperature, heart rate, respiratory rate, white cells) ' + c('bone') + '.  qSOFA: quick SOFA ' + c('seymour16') + '.', M, 6.0, 6.6, 0.5, { size: 9.5, color: GREY });
  refFooter(s);
  s.addNotes('1 min. Define sepsis as infection plus organ failure, and SOFA as the organ scoring system, pointing at the six organs. Then: it is common, time-critical, and hard to recognise early, which is why prediction matters.');

  // ===== 4 CLINICAL AI LITERATURE =====
  s = slide('CONTENT', 'CLINICAL AI', 'Context');
  s.addText('Clinical AI: strong in development, weak on external validation', { placeholder: 'title' });
  const probs = [
    [I.hospital, 'It fails on new data', '81 % of 86 deep-learning algorithms for medical imaging performed worse on external data ' + c('yu') + '. A model fell from AUC 0.90 to 0.50 when run silently on new patients ' + c('kwong') + '. Of 81 deep-learning studies, 9 were prospective and 6 tested in real clinical settings ' + c('nagendran') + '.'],
    [I.search, 'It sees a narrow picture', 'The most used sepsis benchmark gives models 40 hourly variables ' + c('reyna') + '; treatments, devices and history are usually left out.'],
    [I.users, 'It learns the care process, not the patient', 'Across 272 common laboratory tests, the fact that a test was ordered predicted survival in 86 % of them; for 68 %, the time of day it was ordered predicted survival better than the result ' + c('agniel') + '. The record carries the clinicians\' decisions, and a model learns them. A pneumonia model learned which hospital took the X-ray ' + c('zech') + '.'],
    [I.chart, 'It is judged by numbers, not clinical meaning', 'Data leakage: the model is given information from after the prediction time, or from the answer itself; it inflated results in at least 17 fields of science ' + c('kapoor') + '. Usefulness depends on the action a prediction triggers, not on AUROC alone ' + c('shah', 'kelly') + '.'],
  ];
  probs.forEach((p, i) => {
    const col = i % 2, row = Math.floor(i / 2), x = M + col * 6.15, y = 1.7 + row * 2.4;
    box(s, x, y, 5.95, 2.2, { line: RULE });
    tile(s, p[0], x + 0.2, y + 0.2, 0.55);
    T(s, p[1], x + 0.95, y + 0.2, 4.85, 0.55, { size: 16, bold: true, valign: 'middle' });
    T(s, p[2], x + 0.2, y + 0.85, 5.55, 1.3, { size: 12.5 });
  });
  refFooter(s);
  s.addNotes('1 min. The general lesson from medical AI, before sepsis: models fail on new data, see only part of the patient, learn how care is delivered rather than the disease, and are judged by numbers rather than by what a clinician would do with them.');

  // ===== 5 SEPSIS AI =====
  s = slide('CONTENT', 'SEPSIS AI', 'Context');
  s.addText('Sepsis AI: the same gap, and what AUROC hides', { placeholder: 'title' });
  box(s, M, 1.7, 5.95, 2.65, { line: RULE });
  T(s, 'PhysioNet 2019 Challenge: 104 teams ' + c('reyna'), M + 0.2, 1.82, 5.6, 0.4, { size: 15, bold: true });
  T(s, '0.43', M + 0.2, 2.3, 2.2, 0.8, { size: 44, bold: true, color: INK });
  T(s, 'winner\'s utility on new patients from its two training hospitals (official overall score 0.36)', M + 0.2, 3.1, 2.5, 0.9, { size: 12.5, color: GREY });
  arrow(s, M + 2.55, 2.7, M + 3.15, 2.7, RED, 2.5);
  T(s, '-0.12', M + 3.3, 2.3, 2.4, 0.8, { size: 44, bold: true, color: RED });
  T(s, 'on a third hospital it had never seen: worse than no alarm ' + c('morrill'), M + 3.3, 3.1, 2.5, 0.9, { size: 12.5, color: GREY });
  box(s, M + 6.15, 1.7, 5.95, 2.65, { line: RULE });
  T(s, 'Epic Sepsis Model, widely deployed ' + c('wong'), M + 6.35, 1.82, 5.6, 0.4, { size: 15, bold: true });
  T(s, '0.63', M + 6.35, 2.3, 2.3, 0.8, { size: 44, bold: true, color: RED });
  T(s, 'AUROC in independent validation (vendor: 0.76 to 0.83)', M + 6.35, 3.1, 2.5, 0.9, { size: 12.5, color: GREY });
  T(s, '67 %', M + 9.2, 2.3, 2.6, 0.8, { size: 44, bold: true, color: RED });
  T(s, 'of sepsis cases missed while alerting on 18 % of all admissions', M + 9.2, 3.1, 2.7, 0.7, { size: 12.5, color: GREY });
  T(s, 'An AUROC cannot show this. A utility score counts every missed patient, every false alarm and the hours gained.', M + 6.35, 3.78, 5.55, 0.52, { size: 12, bold: true, color: RED });
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
  s.addText('The research question', { placeholder: 'title' });
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
  s.addText('Healthcare professionals in the loop', { placeholder: 'title' });
  const ev = [
    ['Better together', 'AI support improved clinicians\' diagnostic accuracy beyond AI or clinicians alone ' + c('tschandl')],
    ['Clinician plus AI finds more disease', 'In randomised trials, endoscopists working with an AI detector found more pre-cancerous polyps: 37 % against 25 % ' + c('hassan21')],
    ['Trust is built, not assumed', 'Clinicians trust AI through experience, endorsement and systems that respect their judgement ' + c('henrynpj')],
    ['Clinical input at every stage', 'From problem definition to deployment ' + c('wiens') + '; health records encode care decisions ' + c('agniel')],
  ];
  ev.forEach((e, i) => { const x = M + i * 3.07; T(s, e[0], x, 1.6, 2.9, 0.6, { size: 14, bold: true, color: RED, valign: 'bottom' }); T(s, e[1], x, 2.25, 2.9, 0.95, { size: 12.5 }); });
  const exs = [
    [I.pill, 'Example 1: antibiotics', 'Usually: antibiotics are either fed to the model, which then "predicts" sepsis from the treatment given for sepsis, or thrown out altogether.',
      'Here: a clinician can tell two kinds apart. One dose as the anaesthetic starts, stopped within a day, no culture sent: routine surgical prevention ' + c('bratzler') + ', which tells the model the patient has just had an operation. Antibiotics started because infection is suspected are part of the sepsis definition ' + c('evans') + ', so they are never an input.'],
    [I.xray, 'Example 2: suspicion proxies', 'Usually: a chest X-ray request or a stress-dose steroid order looks like a strong predictor.',
      'Here: they mostly mean the team already suspects sepsis. Every result is reported with and without them, so we can tell how much of the signal comes from the patient and how much from the team.'],
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
  s.addNotes('1 min. The evidence first: human and AI together outperform either alone, clinicians acting on an AI detector find more disease, trust has to be built, and health records encode clinical decisions. Then two examples from this project where clinical knowledge decided what the model may and may not see.');

  // ===== 8 DATABASES =====
  s = slide('CONTENT', 'DATA', 'Question and approach');
  s.addText('Chosen databases', { placeholder: 'title' });
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
  s.addText('The research pipeline', { placeholder: 'title' });
  T(s, 'Phase 1  Quantitative', M, 1.6, 4, 0.35, { size: 13, bold: true, color: RED });
  const pipe = [
    ['Raw records', 'MIMIC-IV and eICU', 'two hospital systems make transfer real'],
    ['Harmonise', 'same concept, unit and clock', 'compare like with like'],
    ['One label', 'Sepsis-3 onset hour ' + c('seymour16'), 'results comparable'],
    ['Hourly features', '659, each used only from the hour it became available', 'no information from the future'],
    ['Models', '21 compared on identical hours', 'architecture is a hypothesis'],
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
  T(s, 'Online interviews and round-table discussions with 20 infectious disease and critical care consultants from different hospitals: would they trust and act on the alert, what explanation do they need, what alarm burden is acceptable ' + c('henrynpj') + '.', M + 0.2, 5.3, 5.5, 1.0, { size: 12 });
  arrow(s, M + 5.85, 5.6, M + 6.27, 5.6, RED, 2);
  box(s, M + 6.27, 4.85, CW - 6.27, 1.5, { fill: WHITE, line: RED, lw: 1.5 });
  T(s, 'Phase 3  Future direction: hospital patients', M + 6.47, 4.93, 5.4, 0.35, { size: 14, bold: true, color: RED });
  T(s, 'A silent test on live ICU data (alerts logged, not shown, compared with outcomes), then a clinician-facing pilot ' + c('kwong') + '.', M + 6.47, 5.3, 5.4, 1.0, { size: 12.5 });
  refFooter(s);
  s.addNotes('1 min. Read the figure left to right like a model architecture: raw records, harmonisation, one label, hourly features, models, evaluation. Each box has its reason underneath. The evaluation feeds the qualitative phase with healthcare professionals, which is running now, and the future direction is a silent test on hospital patients.');

  // ===== 10 MODELS =====
  s = slide('CONTENT', 'APPROACH: MODELS', 'Question and approach');
  s.addText('Models compared', { placeholder: 'title' });
  T(s, 'OSTA: organ-system-aware temporal attention, as built ' + c('vaswani', 'vincent'), M, 1.55, 7.0, 0.3, { size: 13, bold: true, color: RED });
  const st = [
    ['1  Input, hour by hour', '659 predictors, each as value, measured? and age; grouped by organ system: the 6 SOFA organs and 8 other groups'],
    ['2  Attention over time', 'one small transformer per group reads that organ\'s past hours and weights them; causal: no future hour is visible'],
    ['3  Cross-organ attention', 'at each hour the organ summaries exchange information: the kidney picture adjusts the reading of circulation'],
    ['4  Global integration', 'a second transformer reads the whole stay (width 128, 4 heads)'],
    ['5  Outputs', 'sepsis risk in the next 6 h, plus a risk per organ: which organ is driving it'],
  ];
  const sbw = 1.3, sbg = 0.125;
  st.forEach((k, i) => {
    const x = M + i * (sbw + sbg);
    box(s, x, 1.9, sbw, 1.75, { fill: i === 1 ? RED : LIGHT, line: i === 1 ? RED : LIGHT });
    T(s, k[0], x + 0.08, 1.95, sbw - 0.16, 0.45, { size: 10.5, bold: true, color: i === 1 ? WHITE : RED });
    T(s, k[1], x + 0.08, 2.42, sbw - 0.16, 1.2, { size: 9, color: i === 1 ? WHITE : INK });
    if (i < 4) arrow(s, x + sbw, 2.77, x + sbw + sbg, 2.77, INK, 1);
  });
  T(s, 'Attention over time, one organ (kidneys): which past hours count for the current hour; illustrative weights', M, 3.75, 7.0, 0.28, { size: 10.5, bold: true });
  const hrs = 12, hw = 0.4, hx0 = M + 0.95, hy = 4.95;
  const wts = [0.02, 0.04, 0.35, 0.12, 0.04, 0.03, 0.08, 0.25, 0.45, 0.6, 0.35, 1.0];
  for (let i = 0; i < hrs; i++) {
    const x = hx0 + i * hw, bh = 0.65 * wts[i];
    s.addShape(pres.ShapeType.rect, { x: x + 0.04, y: hy - bh, w: hw - 0.08, h: bh, fill: { color: i === hrs - 1 ? INK : RED }, line: { color: WHITE, width: 0 }, objectName: 'weight bar' });
    box(s, x + 0.02, hy + 0.02, hw - 0.04, 0.28, { fill: i === hrs - 1 ? INK : LIGHT, line: i === hrs - 1 ? INK : RULE, lw: 0.5 });
    T(s, i === hrs - 1 ? 'now' : String(i - hrs + 1) + ' h', x + 0.02, hy + 0.02, hw - 0.04, 0.28, { size: 7.5, color: i === hrs - 1 ? WHITE : GREY, align: 'center', valign: 'middle' });
  }
  T(s, 'hours', M, hy + 0.02, 0.9, 0.28, { size: 9.5, color: GREY, valign: 'middle' });
  T(s, 'weight', M, hy - 0.55, 0.9, 0.28, { size: 9.5, color: GREY });
  T(s, 'creatinine rose', hx0 + 1.3 * hw, 4.08, 1.5, 0.22, { size: 8.5, color: RED, align: 'center' });
  T(s, 'urine output falling', hx0 + 7.6 * hw, 4.08, 1.9, 0.22, { size: 8.5, color: RED, align: 'center' });
  s.addShape(pres.ShapeType.rect, { x: hx0 + hrs * hw + 0.1, y: hy - 0.6, w: 1.05, h: 0.9, fill: { color: WHITE }, line: { color: RULE, width: 0.75, dashType: 'dash' }, objectName: 'future mask' });
  T(s, 'future hours: masked', hx0 + hrs * hw + 0.12, hy - 0.6, 1.0, 0.9, { size: 8.5, color: GREY, align: 'center', valign: 'middle' });
  T(s, 'Why different: a flat model sees 659 numbers with no time; a recurrent model keeps one running summary; OSTA reads each organ\'s history, lets organs inform each other, and says which organ drives the risk.', M, 5.35, 7.0, 0.5, { size: 10 });
  T(s, 'How built: per-organ encoders of width 32, global width 128, 4 heads, 2 + 2 layers, causal masks throughout, time as hours since ICU admission; every output passes a future-perturbation test ' + c('thiswork') + '.', M, 5.85, 7.0, 0.5, { size: 10, color: GREY });
  const rx = M + 7.3, rw = CW - 7.3;
  T(s, 'Compared on identical hours, rules fixed in advance', rx, 1.55, rw, 0.3, { size: 12.5, bold: true });
  const arms = [
    ['OSTA without organ grouping', 'the ablation that decides whether organ structure stays'],
    ['CNN-Transformer (earlier work)', 'local patterns over 1 to 12 h, then attention'],
    ['GRU-D, temporal CNN', 'models built for irregular ICU data ' + c('che', 'bai')],
    ['Signatures + boosted trees', 'the PhysioNet 2019 winner\'s approach ' + c('morrill')],
    ['Self-supervised pretraining', 'learn from unlabelled stays first ' + c('yeche21')],
    ['Logistic regression, boosted trees', 'simple baselines'],
  ];
  arms.forEach((a, i) => {
    const y = 1.95 + i * 0.62;
    s.addShape(pres.ShapeType.rect, { x: rx, y: y + 0.07, w: 0.12, h: 0.12, fill: { color: RED }, line: { color: RED, width: 0 }, objectName: 'marker' });
    T(s, a[0], rx + 0.25, y, rw - 0.25, 0.27, { size: 12, bold: true });
    T(s, a[1], rx + 0.25, y + 0.27, rw - 0.25, 0.33, { size: 10.5, color: GREY });
  });
  T(s, 'Training loss chosen by clinical utility, against plain and time-smoothed losses ' + c('yeche23') + '. Organ structure stays only if OSTA beats the flat model on validation.', rx, 5.7, rw, 0.6, { size: 10.5, color: GREY });
  refFooter(s);
  s.addNotes('1 min. Walk the five stages left to right, then the inset: for the current hour the kidney encoder weights the past hours, high where creatinine rose and urine output fell, zero for the future. Then cross-organ attention and the per-organ risk. Why different in one breath. Then the right column: OSTA is a hypothesis tested against the same model without organ grouping and against the published alternatives, with the rules fixed in advance.');

  // ===== 11 COHORT STUDY =====
  pres.addSection({ title: 'Results' });
  s = slide('CONTENT', 'RESULTS: COHORT STUDY', 'Results');
  s.addShape(pres.ShapeType.rect, { x: W - M - 4.6, y: 0.24, w: 4.6, h: 0.32, fill: { color: PINK }, line: { color: PINK, width: 0 }, objectName: 'status tag' });
  T(s, 'SUBMITTED  |  Frontiers in Medicine, under review', W - M - 4.55, 0.24, 4.5, 0.32, { size: 10, bold: true, color: RED, align: 'center', valign: 'middle' });
  s.addText('Sepsis onset in the ICU: the cohort study', { placeholder: 'title' });
  T(s, 'PhysioNet 2019 ICU patients: descriptive analysis and Cox regression ' + c('temporal', 'reyna'), M, 1.55, CW, 0.3, { size: 13, bold: true, color: RED });
  [['27,101', 'ICU patients'], ['8 %', 'developed sepsis (2,181 patients)'], ['100 h', 'median time to onset (Kaplan-Meier)'], ['81 h vs 48 h', 'hospital-to-ICU time, sepsis vs no sepsis']].forEach((k, i) => {
    const x = M + i * 3.07;
    box(s, x, 1.95, 2.9, 1.25, { fill: LIGHT, line: LIGHT });
    T(s, k[0], x + 0.15, 2.02, 2.6, 0.6, { size: 28, bold: true, color: RED });
    T(s, k[1], x + 0.15, 2.65, 2.6, 0.5, { size: 12 });
  });
  T(s, 'Descriptive: who develops sepsis', M, 3.4, 5.6, 0.3, { size: 13, bold: true });
  list(s, ['Sepsis patients reached the ICU later and stayed longer (27 h vs 20 h).', 'APACHE II, SOFA, NEWS and SIRS all higher in the sepsis group, and rising over the stay.', 'Heart rate and respiratory rate higher; creatinine, urea and glucose higher; haemoglobin lower.'], M, 3.75, 5.6, 1.8, { size: 12, psa: 6 });
  T(s, 'Early predictors, label moved 6 h earlier: Cox hazard ratios', M + 6.0, 3.4, 6.1, 0.3, { size: 13, bold: true });
  s.addTable([
    [th('Predictor'), th('HR'), th('95 % CI'), th('Predictor'), th('HR'), th('95 % CI')],
    [td('SIRS criteria, per point'), td('1.20'), td('1.05 to 1.36'), td('Heart rate, per beat/min'), td('1.02'), td('1.01 to 1.02')],
    [td('APACHE II, per point'), td('1.04'), td('1.02 to 1.07'), td('Respiratory rate, per breath/min'), td('1.01'), td('1.00 to 1.02')],
    [td('Male sex'), td('1.16'), td('1.04 to 1.28'), td('Potassium, per mmol/L'), td('0.89'), td('0.80 to 0.98')],
  ], { x: M + 6.0, y: 3.75, w: 6.1, colW: [1.55, 0.5, 1.0, 1.55, 0.5, 1.0], border: { type: 'solid', color: RULE, pt: 0.75 }, fontFace: 'Arial', margin: 0.04, objectName: 'cox table' });
  box(s, M, 5.6, CW, 0.7, { fill: PINK, line: PINK });
  T(s, 'The signal is present in routine measurements hours before onset, but spread across many weak predictors, each with a hazard ratio close to 1. That is the case for models that read the whole picture, hour by hour.', M + 0.2, 5.6, CW - 0.4, 0.7, { size: 12.5, bold: true, valign: 'middle' });
  refFooter(s);
  s.addNotes('1 min. This is the submitted cohort paper, on the PhysioNet 2019 patients. Descriptive first: 27,101 patients, 8 per cent septic, median onset at 100 hours, later ICU arrival and longer stays; the standard scores higher and rising. Then the Cox model with the label moved six hours earlier: SIRS, APACHE II, male sex, heart rate, respiratory rate and potassium are independent early predictors, each weak on its own. That is the argument for hourly models that read everything.');

  // ===== 12 SAME LANGUAGE =====
  pres.addSection({ title: 'Preliminary results' });
  s = slide('CONTENT', 'PRELIMINARY RESULTS', 'Preliminary results'); prelim(s);
  s.addText('Two hospital systems, one language', { placeholder: 'title' });
  T(s, 'Four things differ between the databases for every measurement', M, 1.55, 6.45, 0.3, { size: 13, bold: true, color: RED });
  const h4 = (t) => ({ text: t, options: { bold: true, color: WHITE, fill: { color: INK }, fontSize: 10.5, valign: 'middle' } });
  const c4 = (t, o = {}) => ({ text: t, options: { fontSize: 10, color: INK, valign: 'middle', ...o } });
  s.addTable([
    [h4('Difference'), h4('MIMIC-IV ' + c('johnson')), h4('eICU ' + c('pollard')), h4('Harmonised')],
    [c4('Where it is stored', { bold: true }), c4('one charting table for all vital signs; a laboratory table'), c4('periodic monitor table; aperiodic table for cuff pressures; nurse-charting table for temperature, GCS and many vital signs'), c4('every table where a value lives is read', { bold: true, color: RED })],
    [c4('What it is called', { bold: true }), c4('item numbers: 223761 (°F), 223762 (°C)'), c4('text labels: "Temperature (C)", "Temperature (F)", "Glasgow coma score"'), c4('one concept per channel: 83 channels, plus derived values', { bold: true, color: RED })],
    [c4('Unit', { bold: true }), c4('°F and °C both charted; ionised calcium in mmol/L'), c4('°C or °F by label; ionised calcium in mg/dL'), c4('one unit per concept, converted and range-checked', { bold: true, color: RED })],
    [c4('Clock', { bold: true }), c4('date-shifted timestamps; a chart time and a store time'), c4('minutes from ICU admission'), c4('hours from ICU admission; each value usable only from the hour it became available', { bold: true, color: RED })],
  ], { x: M, y: 1.9, w: 6.45, colW: [1.15, 1.65, 1.95, 1.7], border: { type: 'solid', color: RULE, pt: 0.75 }, fontFace: 'Arial', margin: 0.05, objectName: 'harmonisation table' });
  T(s, 'Published pipelines read the periodic monitor tables; we read where the values actually are and put 659 predictors on one concept, one unit and one clock in both databases. Our own earlier pipeline failed the clock test, information from the future, and was rebuilt (backup).', M, 5.15, 6.45, 0.8, { size: 10.5, color: GREY });
  T(s, 'Before: eICU temperature in 5 % of patient-hours. After: 94 % ' + c('thiswork') + '.', M, 5.95, 6.45, 0.3, { size: 11.5, bold: true, color: RED });
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

  // ===== 13 UTILITY =====
  s = slide('CONTENT', 'PRELIMINARY RESULTS', 'Preliminary results'); prelim(s);
  s.addText('Utility on own and unseen hospital systems: 21 models on identical hours', { placeholder: 'title' });
  box(s, M, 1.55, 7.3, 4.9, { line: RULE });
  T(s, 'Own hospital system', M + 0.15, 1.62, 4, 0.3, { size: 13, bold: true, color: RED });
  T(s, 'the winner on its training hospitals; this project on the MIMIC-IV test split (1,422 stays, 71 events), 8 of 21 models shown', M + 0.15, 1.9, 7.0, 0.3, { size: 10, color: GREY });
  const labsL = ['Winner, published (official 0.36; 0.43 own hospitals)', 'Logistic regression', 'Boosted trees', 'Winner\'s approach, rebuilt here', 'Temporal CNN', 'GRU-D (chosen on validation)', 'Flat OSTA (no organ grouping)', 'OSTA', 'Self-supervised CNN to OSTA'];
  s.addChart(pres.ChartType.bar, [{ name: 'Normalised utility', labels: labsL, values: [0.36, 0.08, 0.10, 0.15, 0.17, 0.19, 0.23, 0.23, 0.29] }], {
    x: M + 0.1, y: 2.2, w: 7.1, h: 3.55, barDir: 'bar', barGrouping: 'clustered', barGapWidthPct: 35, chartColors: ['D0D0D0', MID, MID, '3A3A3A', RED, RED, RED, RED, RED],
    showTitle: false, showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 10.5, dataLabelColor: INK, dataLabelFontBold: true, dataLabelFontFace: '+mn-lt', dataLabelFormatCode: '0.00',
    valAxisMinVal: 0, valAxisMaxVal: 0.5, valAxisMajorUnit: 0.1, valAxisLabelFontSize: 10, valAxisLabelColor: GREY, valAxisLabelFontFace: '+mn-lt', valAxisLabelFormatCode: '0.0',
    catAxisLabelFontSize: 10, catAxisLabelColor: INK, catAxisLabelFontFace: '+mn-lt', catAxisOrientation: 'maxMin', catAxisLabelPos: 'low', valGridLine: { color: 'E0E0E0', size: 0.5 }, catGridLine: { style: 'none' }, showLegend: false, objectName: 'own-system chart' });
  [['D0D0D0', 'Published ' + c('reyna', 'morrill')], [MID, 'Baselines'], ['3A3A3A', 'Winner\'s approach'], [RED, 'This project ' + c('thiswork')]].forEach((l, i) => {
    const x = M + 0.2 + i * 1.75;
    s.addShape(pres.ShapeType.rect, { x, y: 5.85, w: 0.22, h: 0.18, fill: { color: l[0] }, line: { color: l[0], width: 0 }, objectName: 'legend swatch' });
    T(s, l[1], x + 0.28, 5.8, 1.5, 0.28, { size: 10.5, valign: 'middle' });
  });
  T(s, '21 of 21 models above zero, every 95 % CI above zero (range 0.08 to 0.29). No model is shown to be better than another.', M + 0.15, 6.1, 7.0, 0.3, { size: 10, color: GREY });
  const ux = M + 7.5, uw = CW - 7.5;
  box(s, ux, 1.55, uw, 4.9, { line: RULE });
  T(s, 'Unseen hospital system', ux + 0.15, 1.62, uw - 0.3, 0.3, { size: 13, bold: true, color: RED });
  T(s, 'the winner on a hidden third hospital; this project: MIMIC-IV models scored on eICU patients (888 stays, 45 events), development level', ux + 0.15, 1.9, uw - 0.3, 0.45, { size: 10, color: GREY });
  const ax0 = ux + 1.85, aw = uw - 2.1, umin = -0.2, umax = 0.12, X = (u) => ax0 + (u - umin) / (umax - umin) * aw, ay = 5.5;
  s.addShape(pres.ShapeType.line, { x: ax0, y: ay, w: aw, h: 0.001, line: { color: GREY, width: 0.75 }, objectName: 'axis' });
  [-0.2, -0.1, 0, 0.1].forEach((u) => { s.addShape(pres.ShapeType.line, { x: X(u), y: ay, w: 0.001, h: 0.08, line: { color: GREY, width: 0.75 }, objectName: 'tick' }); T(s, u.toFixed(1), X(u) - 0.3, ay + 0.06, 0.6, 0.22, { size: 9, color: GREY, align: 'center' }); });
  s.addShape(pres.ShapeType.line, { x: X(0), y: 2.38, w: 0.001, h: ay - 2.38, line: { color: RULE, width: 0.75, dashType: 'dash' }, objectName: 'zero line' });
  const rowsU = [
    ['Winner, published', -0.12, null, null, 'D0D0D0', '-0.12'],
    ['Logistic regression', -0.15, null, null, MID, '-0.15'],
    ['Boosted trees', 0.01, 0.00, 0.03, MID, '0.01'],
    ['Winner\'s approach', 0.02, null, null, '3A3A3A', '0.02'],
    ['Temporal CNN', 0.01, null, null, RED, '0.01'],
    ['GRU-D', 0.01, -0.04, 0.06, RED, '0.01'],
    ['Flat OSTA', 0.03, null, null, RED, '0.03'],
    ['OSTA', 0.04, null, null, RED, '0.04'],
    ['SSL CNN to OSTA', 0.04, null, null, RED, '0.04'],
    ['eICU models at home (21)', null, 0.00, 0.08, 'F0A8A8', '0.00 to 0.08'],
  ];
  rowsU.forEach((r, i) => {
    const y = 2.42 + i * 0.3;
    T(s, r[0], ux + 0.12, y, 1.7, 0.26, { size: 9.5, bold: i === 0 || i === 9, valign: 'middle' });
    if (r[1] !== null && r[2] === null) {
      s.addShape(pres.ShapeType.rect, { x: Math.min(X(0), X(r[1])), y: y + 0.04, w: Math.abs(X(r[1]) - X(0)), h: 0.18, fill: { color: r[4] }, line: { color: r[4], width: 0 }, objectName: 'bar' });
    } else if (r[1] === null) {
      s.addShape(pres.ShapeType.rect, { x: X(r[2]), y: y + 0.04, w: X(r[3]) - X(r[2]), h: 0.18, fill: { color: r[4] }, line: { color: r[4], width: 0 }, objectName: 'range band' });
    } else {
      s.addShape(pres.ShapeType.line, { x: X(r[2]), y: y + 0.13, w: X(r[3]) - X(r[2]), h: 0.001, line: { color: r[4], width: 1.5 }, objectName: 'ci' });
      s.addShape(pres.ShapeType.rect, { x: X(r[1]) - 0.05, y: y + 0.08, w: 0.1, h: 0.1, fill: { color: r[4] }, line: { color: r[4], width: 0 }, objectName: 'point' });
    }
    T(s, r[5], X(umax) + 0.02, y, 0.8, 0.26, { size: 9, bold: true, color: i === 0 ? INK : RED, valign: 'middle' });
  });
  T(s, 'MIMIC-IV models on eICU: -0.03 to +0.04 across 20 models, CIs include zero where computed. eICU\'s own models score 0.00 to 0.08 on the same 45 events: away and at home coincide there. The sealed holdout is the real test.', ux + 0.15, 5.82, uw - 0.3, 0.62, { size: 9.5, color: GREY });
  refFooter(s);
  s.addNotes('1 min. Left, own hospital system: the winner at 0.36 official (0.43 on its own hospitals) and this project on MIMIC-IV, 0.08 to 0.29, all above zero, none shown best. Right, unseen hospital system: the winner at minus 0.12; this project, the same eight models trained on MIMIC-IV and scored on eICU patients, minus 0.15 (logistic) to plus 0.04, about zero. The pink band is eICU\'s own models trained on eICU itself: 0.00 to 0.08 on the same 45 events. Say it plainly: at home on MIMIC-IV every model keeps a positive utility; on eICU, away and at home coincide near zero, so the problem there is the sample and the label as much as transfer, and the full cohort and the sealed holdout decide. Organ grouping not supported on either database; shortlists GRU-D, TCN, flat OSTA (MIMIC-IV) and GRU-D, flat OSTA, pooled self-supervised flat CNN (eICU).');

  // ===== 14 CONTRIBUTION + NEXT =====
  pres.addSection({ title: 'Contribution and next steps' });
  s = slide('CONTENT', 'CONTRIBUTION AND NEXT STEPS', 'Contribution and next steps');
  s.addText('Contribution and next steps', { placeholder: 'title' });
  T(s, 'Contribution so far', M, 1.6, 6, 0.35, { size: 15, bold: true, color: RED });
  const con = [
    [I.lock, 'Causal, cross-database pipeline', 'one sepsis definition, two hospital systems, 659 clinically defined predictors ' + c('thiswork')],
    [I.scale, 'Evaluation by clinical utility', 'false alarms per day, warning time, transfer, sealed holdout ' + c('reyna')],
    [I.search, 'Three findings so far', 'harmonisation recovers the data; all 21 above zero on MIMIC-IV, near zero on eICU at home or transferred; small samples overfit, none shown best'],
    [I.book, 'Three manuscripts submitted in 2026', 'AMR diagnostics review ' + c('amr') + '; sepsis-onset cohort study ' + c('temporal') + '; thermography meta-analysis ' + c('thermo')],
  ];
  con.forEach((k, i) => {
    const y = 2.05 + i * 0.98;
    tile(s, k[0], M, y + 0.05, 0.5, INK);
    T(s, k[1], M + 0.65, y, 5.4, 0.33, { size: 14, bold: true });
    T(s, k[2], M + 0.65, y + 0.33, 5.75, 0.62, { size: i === 2 ? 11.5 : 12.5, color: GREY });
  });
  T(s, 'Next steps', M + 6.55, 1.6, 5, 0.35, { size: 15, bold: true, color: RED });
  const nx = [
    ['Now', 'Complete the qualitative study (20 infectious disease and critical care consultants); fix the full-cohort arms from the MIMIC-IV and eICU shortlists'],
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

  // ===== 15 TAKE-HOME =====
  pres.addSection({ title: 'Take-home' });
  s = slide('CLOSING', 'TAKE-HOME MESSAGE', 'Take-home');
  s.addText('What this work adds', { placeholder: 'title' });
  box(s, M, 1.6, CW, 0.75, { fill: WHITE, line: WHITE });
  T(s, 'An early sepsis warning built on raw hospital data, scored only on what a clinician could have known, and judged by what an alarm costs and gains rather than by AUROC.', M + 0.2, 1.6, CW - 0.4, 0.75, { size: 14, bold: true, color: RED, valign: 'middle' });
  T(s, 'Done differently', M, 2.5, 6, 0.3, { size: 12.5, bold: true, color: WHITE });
  [['Challenge-prepared tables', 'Raw MIMIC-IV and eICU: two hospital systems'], ['Each study its own sepsis definition', 'One Sepsis-3 definition on both'], ['Values carried forward; information from the future', 'Every value only from the hour it was available'],
   ['40 to 125 variables', '659 clinically defined predictors, text entries included'], ['Antibiotics as inputs', 'Label-defining antibiotics excluded; prophylaxis kept by rule'], ['AUROC on one split', 'Utility, false alarms per day, warning time, a sealed holdout']].forEach((r, i) => {
    const y = 2.85 + i * 0.38;
    T(s, r[0], M, y, 5.0, 0.34, { size: 11.5, color: 'F3C6CC', valign: 'middle' });
    T(s, '→', M + 5.05, y, 0.4, 0.34, { size: 13, bold: true, color: WHITE, align: 'center', valign: 'middle' });
    T(s, r[1], M + 5.5, y, CW - 5.5, 0.34, { size: 11.5, bold: true, color: WHITE, valign: 'middle' });
  });
  T(s, 'Known so far', M, 5.25, 6, 0.3, { size: 12.5, bold: true, color: WHITE });
  list(s, ['On honest, harmonised data, all 21 models keep a positive utility on MIMIC-IV; on eICU, with 45 events, models trained there and models transferred sit near zero alike ' + c('thiswork') + '.', 'The project\'s own organ-grouping idea is not supported on either database, and is reported as found.', 'Whether a warning travels to an unseen hospital system is the open question: the full cohort, the consultants\' study and the sealed holdout answer next.'], M, 5.58, CW - 3.2, 0.95, { size: 11.5, color: WHITE, psa: 3 });
  T(s, 'Thank you', W - M - 3.0, 5.6, 3.0, 0.6, { size: 24, bold: true, color: WHITE, align: 'right' });
  refFooter(s, true);
  s.addNotes('1 min. One sentence of take-home, then the six things done differently, read as pairs, then what is known so far in three honest lines. Thank the audience and stop; the chair opens questions.');

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
    ['Causal', 'Each value used only from the hour it became available, with a measured flag and its age; hours after onset are never scored as warnings'],
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
    [td('Values carried forward; post-onset hours positive'), td('Each value used from the hour available, most expire after 24 h; hours after onset never scored as warnings', { bold: true }), td('No information from the future ' + c('kapoor'))],
    [td('40 to 125 variables'), td('659 clinically defined predictors', { bold: true }), td('The whole clinical picture')],
    [td('Antibiotics as predictors'), td('Label-defining antibiotics excluded; prophylaxis kept by rule ' + c('bratzler'), { bold: true }), td('Avoids predicting the label from itself')],
    [td('AUROC on one split'), td('Utility, false alarms per day, warning time, calibration, sealed holdout', { bold: true }), td('What would help patients ' + c('shah'))],
  ], { x: M, y: 1.65, w: CW, colW: [3.4, 5.2, 3.53], border: { type: 'solid', color: RULE, pt: 0.75 }, fontFace: 'Arial', margin: 0.07, objectName: 'choices table' });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('The 659 predictors, each with a measured flag and an age', { placeholder: 'title' });
  const cats = [
    ['Vital signs and monitoring', 'heart rate, cuff and arterial pressures, respiratory rate, oxygen saturation, temperature, end-tidal CO2, CVP, cardiac output, pain and sedation scores'],
    ['Laboratory and blood gas', 'chemistry, full blood count with differential, coagulation, lactate, procalcitonin, troponin, BNP, ferritin, D-dimer, ammonia, urinalysis, blood gases'],
    ['Scores and derived', 'SOFA per organ ' + c('vincent') + ', qSOFA, NEWS2 ' + c('rcp') + ', shock index, P/F and S/F ratios, changes from previous and baseline, 24 h extremes'],
    ['Organ support', 'vasopressor dose (noradrenaline equivalents), ventilation settings, oxygen flow, renal replacement, urine output and AKI stage ' + c('kdigo')],
    ['Fluids, drugs, devices', 'crystalloids, transfusions, nutrition, central and arterial lines, catheters, drains; steroids, immunosuppressants, chemotherapy, sedatives, opioids'],
    ['Context and history', 'admission source, ICU type, hours before ICU, prior admissions, prior positive cultures and antibiotics (MIMIC-IV only), 17 comorbidities, imaging orders'],
    ['Prophylactic antibiotics', 'surgical prophylaxis by agent, timing, duration, no culture or escalation ' + c('bratzler') + '; medical prophylaxis by agent and dose'],
    ['Never predictors', 'label-defining antibiotics and cultures; race, ethnicity, insurance (reserved for a planned fairness analysis); anything after the prediction hour'],
  ];
  cats.forEach((k, i) => { const col = i % 2, row = Math.floor(i / 2), x = M + col * 6.15, y = 1.65 + row * 1.2;
    box(s, x, y, 5.95, 1.08, { fill: i === 7 ? PINK : LIGHT, line: i === 7 ? PINK : LIGHT });
    T(s, k[0], x + 0.15, y + 0.06, 5.65, 0.3, { size: 12.5, bold: true, color: RED }); T(s, k[1], x + 0.15, y + 0.38, 5.65, 0.68, { size: 11.5 }); });
  refFooter(s);

  // ===== BACKUP: HOW THE MODELS EVOLVED =====
  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('How the models evolved', { placeholder: 'title' });
  const stages = [
    ['Earlier work: PhysioNet 2019', [
      ['CNN-Transformer', 'Convolution for local patterns, then attention; no clinical structure ' + c('vaswani')],
      ['OSTA', 'Predictors grouped by organ, as SOFA does, with a risk per organ ' + c('vincent')],
      ['Leakage audit', 'Future information found; both retired, OSTA rebuilt causally ' + c('kapoor')],
    ], 'Found: the honest baseline is modest (utility 0.22) ' + c('thiswork')],
    ['V10: MIMIC-IV and eICU', [
      ['OSTA + per-organ observers', 'Small organ models trained on separate patients, like specialty consults'],
      ['Four ways to use them', 'As inputs; added at the output (fusion); steering cross-organ attention, gated or ungated'],
      ['Controls', 'Raw values only; extra labelled patients; the original OSTA loss restored'],
    ], 'Found: no variant beat OSTA; models peaked within 1 to 3 epochs ' + c('thiswork')],
    ['V11: prespecified comparison', [
      ['Test the organ idea', 'Flat OSTA: the same model without organ grouping'],
      ['Learn from the literature', 'GRU-D, temporal CNN, the winner\'s approach ' + c('che', 'bai', 'morrill')],
      ['Use scarce labels better', 'Self-supervised pretraining, per-channel encoders, hazard head, utility-weighted loss ' + c('yeche21')],
    ], 'Found: all 21 models above zero; organ grouping not supported; scale decides ' + c('thiswork')],
  ];
  const evW = 3.75, evG = (CW - 3 * evW) / 2;
  stages.forEach((st, i) => {
    const x = M + i * (evW + evG);
    box(s, x, 1.6, evW, 0.5, { fill: INK, line: INK });
    T(s, st[0], x + 0.12, 1.6, evW - 0.24, 0.5, { size: 13.5, bold: true, color: WHITE, valign: 'middle' });
    st[1].forEach((it, j) => {
      const y = 2.22 + j * 1.07;
      box(s, x, y, evW, 0.97, { fill: LIGHT, line: LIGHT });
      T(s, it[0], x + 0.12, y + 0.04, evW - 0.24, 0.3, { size: 13, bold: true, color: RED });
      T(s, it[1], x + 0.12, y + 0.34, evW - 0.24, 0.6, { size: 11.5 });
    });
    box(s, x, 5.5, evW, 0.8, { fill: PINK, line: PINK });
    T(s, st[2], x + 0.12, 5.5, evW - 0.24, 0.8, { size: 12, bold: true, valign: 'middle' });
    if (i < 2) arrow(s, x + evW + 0.04, 5.9, x + evW + evG - 0.04, 5.9, RED, 2);
  });
  refFooter(s);

  // ===== BACKUP: ALL MODELS (two slides) =====
  const modelTable = (rows) => s.addTable([
    [th('Model'), th('Core idea'), th('How it differs'), th('Utility')],
    ...rows.map((r) => [td(r[0], { bold: true, fontSize: 12.5 }), td(r[1], { fontSize: 12.5 }), td(r[2], { fontSize: 12.5 }), td(r[3], { align: 'center', bold: true, color: RED, fontSize: 12.5 })]),
  ], { x: M, y: 1.55, w: CW, colW: [2.55, 4.45, 4.13, 1.0], border: { type: 'solid', color: RULE, pt: 0.75 }, fontFace: 'Arial', margin: 0.05, objectName: 'models table' });
  const modelNote = 'Utility: normalised utility on the MIMIC-IV development test split, one seed, preliminary ' + c('thiswork') + '. Every 95 % CI is above zero and the intervals overlap, so the order is not a ranking.';
  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Every model compared (1 of 2): baselines, the winner\'s approach and sequence models', { placeholder: 'title' });
  modelTable([
    ['Logistic regression', 'One weighted sum of the current hour\'s predictors', 'No time modelling: the floor every model must beat', '0.08'],
    ['Boosted trees ' + c('friedman'), 'Many small decision trees, each correcting the last', 'Non-linear thresholds, but sees one hour at a time', '0.10'],
    ['Signatures + boosted trees ' + c('morrill'), 'Recent trajectories summarised as path signatures, then boosted trees', 'The PhysioNet 2019 winner\'s approach, not its full pipeline; time enters through fixed summaries', '0.15'],
    ['OSTA (earlier work)', 'Predictors grouped by organ, attention over time per organ, then across organs', 'The reference model; risk per organ', '0.23'],
    ['Output fusion (earlier work)', 'OSTA plus small per-organ models trained on separate patients, added at the output', 'Independent per-organ second opinions fused at the end', '0.25'],
    ['CNN-Transformer (earlier work) ' + c('vaswani'), 'Convolution finds 1 to 12 h patterns, then attention', 'No organ grouping', '0.24'],
    ['Flat OSTA', 'OSTA with every predictor in one group', 'Removes only the organ grouping: the decisive test', '0.23'],
    ['GRU-D ' + c('che'), 'Recurrent memory; values fade towards normal as they age', 'Models missing and stale data explicitly', '0.19'],
    ['TCN ' + c('bai'), 'Stacked causal convolutions with a widening reach', 'No attention; fixed look-back', '0.17'],
  ]);
  T(s, modelNote, M, 6.3, CW, 0.4, { size: 11, color: GREY });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Every model compared (2 of 2): channel encoders, self-supervised pretraining, ensemble', { placeholder: 'title' });
  modelTable([
    ['CNN to OSTA', 'A small convolution per channel over value, measured flag and age, then OSTA', 'Learns each signal\'s own pattern before organ grouping', '0.28'],
    ['Event OSTA ' + c('horn'), 'Each hour attends to fresh vital-sign measurements of the last 24 h', 'Uses new measurements only, not carried-forward values', '0.21'],
    ['Self-supervised CNN to OSTA ' + c('yeche21'), 'The same encoder first trained on unlabelled stays to forecast values and organ scores', 'Learns physiology before it sees a sepsis label', '0.29'],
    ['Self-supervised CNN, flat head', 'The same pretrained encoder with one group', 'Its organ ablation; added as a declared exploratory pair', '0.21'],
    ['Pooled encoder twins', 'Encoder pretrained on both databases', 'Adaptation across hospital systems', '0.23 / 0.20'],
    ['Hazard head ' + c('gensheimer'), 'Risk at 1, 3, 6, 12 and 24 h as a survival curve', 'Uses when onset happens, not only whether', '0.18'],
    ['Mean ensemble', 'Average of OSTA, CNN-Transformer and self-supervised CNN to OSTA', 'No learned weights', '0.28'],
  ]);
  T(s, 'Retired in earlier versions: gated and ungated attention and observer features, which did not differ from OSTA. ' + modelNote, M, 5.75, CW, 0.7, { size: 11, color: GREY });
  refFooter(s);
  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Cohorts, splits and the sealed holdout', { placeholder: 'title' });
  s.addTable([
    [th('Database'), th('Candidate stays'), th('Sample so far'), th('After exclusions'), th('Sealed holdout')],
    [td('MIMIC-IV 3.1 ' + c('johnson'), { bold: true }), td('about 94,000'), td('10,000'), td('8,758'), td('20 % of patients, deterministic hash')],
    [td('eICU-CRD 2.0 ' + c('pollard'), { bold: true }), td('200,859'), td('10,000'), td('5,623'), td('20 % of patients, deterministic hash')],
  ], { x: M, y: 1.65, w: CW, colW: [3.0, 2.1, 1.9, 2.0, 3.13], border: { type: 'solid', color: RULE, pt: 0.75 }, fontFace: 'Arial', margin: 0.07, objectName: 'cohort table' });
  list(s, ['Labels: Sepsis-3 via YAIB / ricu ' + c('yaib', 'ricu') + '; onset within the next 6 h; hours after onset never scored as warnings; up to 120 h per stay.', 'The 10,000-stay samples are fixed random draws, identical in every run.', 'The holdout is opened once, after the protocol is frozen; nothing is tuned on it.', 'Unlabelled pretraining corpus: 67,193 MIMIC-IV and 74,139 eICU stays outside the cohort and the holdout.'], M, 3.4, CW, 2.9, { size: 14 });
  refFooter(s);

  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Overfitting and validation on 10,000 stays', { placeholder: 'title' });
  [['1 to 3', 'epochs to the best validation score, while training loss keeps falling'], ['175', 'septic stays per training split, against 300 to 659 predictors'], ['0.12 vs 0.28', 'validation utility of OSTA and flat OSTA, which tie on test (0.23): validation and test rankings disagree']].forEach((k, i) => {
    const x = M + i * 4.1; T(s, k[0], x, 1.8, 3.9, 0.8, { size: 36, bold: true, color: RED }); T(s, k[1], x, 2.65, 3.8, 1.1, { size: 14 }); });
  list(s, ['Response: full cohort (about nine times more sepsis cases), self-supervised pretraining on unlabelled stays ' + c('yeche21') + ', loss chosen by utility ' + c('yeche23') + ', three seeds.', 'All figures: ' + 'this work, preliminary ' + c('thiswork') + '.'], M, 4.1, CW, 2.0, { size: 14 });
  refFooter(s);

  // ===== BACKUP: LEAKAGE AUDIT =====
  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Leakage audit and the causal baseline', { placeholder: 'title' });
  box(s, M, 1.65, 5.7, 4.7, { line: RULE });
  tile(s, I.search, M + 0.2, 1.85, 0.55);
  T(s, 'An audit of our own earlier pipeline found', M + 0.95, 1.85, 4.6, 0.55, { size: 15, bold: true, valign: 'middle' });
  list(s, ['Hours after onset scored as correct early warnings: recognising sepsis already present counted as predicting it.', 'Values used from when they were measured, not when they became available.', 'Treatments that define the label among the inputs.', 'Those models were retired and are not reported.'], M + 0.25, 2.6, 5.2, 2.9, { size: 14 });
  T(s, 'Leakage of this kind is documented across science ' + c('kapoor') + '.', M + 0.25, 5.6, 5.2, 0.6, { size: 13, italic: true, color: GREY });
  T(s, 'Rebuilt causally: OSTA on the PhysioNet 2019 test set, 3-seed ensemble ' + c('reyna', 'thiswork'), M + 5.95, 1.65, CW - 5.95, 0.6, { size: 14, bold: true, color: RED });
  [['0.81', 'patient-level AUROC'], ['0.80', 'hourly AUROC'], ['0.22', 'utility (0.30 at the conformal threshold)']].forEach((k, i) => {
    const x = M + 5.95 + i * 2.08;
    box(s, x, 2.35, 1.95, 1.6, { fill: LIGHT, line: LIGHT });
    T(s, k[0], x + 0.15, 2.45, 1.7, 0.75, { size: 36, bold: true, color: RED });
    T(s, k[1], x + 0.15, 3.2, 1.7, 0.7, { size: 12 });
  });
  list(s, ['Only 1.6 % of hours are positive, so ranking scores look modest even for a useful model.', 'Utility 0.22: about a fifth of the way from never alarming to perfect alarms, under the challenge\'s scoring rules; a score, not a measured clinical benefit.', 'This honest baseline is where every later number starts.'], M + 5.95, 4.2, CW - 5.95, 2.1, { size: 13.5 });
  refFooter(s);
  s.addNotes('1 min. Say "preliminary". We audited our own earlier models, found three kinds of leakage, and retired them. The causal version scores lower, and it is the one we stand behind.');

  // ===== BACKUP: QUESTIONS FOR DISCUSSION =====
  s = slide('BACKUP', 'BACKUP', 'Backup');
  s.addText('Questions for discussion', { placeholder: 'title' });
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
  refFooter(s);
  s.addNotes('Backup: the two open questions, for the chair or the RD6 panel.');

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
  list(s, ['External validation on MIMIC-IV: became the core programme, extended to eICU.', 'CNN-Transformer and OSTA papers: withheld after the leakage audit.', 'AMR review: revised and submitted to Int J Antimicrob Agents.', 'Clinician study: now the qualitative phase (20 consultants), nearly complete.', 'Conference presentation: this talk.'], M + 6.3, 2.0, CW - 6.3, 4.0, { size: 13.5 });

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
