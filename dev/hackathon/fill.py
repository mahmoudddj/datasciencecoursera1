"""Fill the MEDATHON template with the SIREN hackathon deck (students' idea slides; no development results)."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
import sys

SRC, OUT = sys.argv[1], sys.argv[2]
p = Presentation(SRC)
S = list(p.slides)
WHITE = RGBColor(0xFF, 0xFF, 0xFF); CYAN = RGBColor(0x00, 0xE4, 0xFF); INK = RGBColor(0x27, 0x37, 0x4D)
MUTED = RGBColor(0xC9, 0xD6, 0xDF); PANEL = RGBColor(0x12, 0x3A, 0x45); PANEL2 = RGBColor(0x0E, 0x2B, 0x33)
FONT = 'Tahoma'

def find(slide, needle):
    for sh in slide.shapes:
        if sh.has_text_frame and needle in sh.text_frame.text:
            return sh
    raise KeyError(needle)

def set_text(shape, lines, size=None, color=None, bold=None, align=None):
    """Replace all text keeping the first run's formatting; lines = list of str or (str, dict)."""
    tf = shape.text_frame
    first = tf.paragraphs[0]
    proto_r = first.runs[0]._r if first.runs else None
    proto_p = first._p
    # remove all paragraphs
    for para in list(tf.paragraphs):
        para._p.getparent().remove(para._p)
    for ln in lines:
        text, opt = (ln, {}) if isinstance(ln, str) else ln
        para = tf.add_paragraph()
        if align or opt.get('align'):
            para.alignment = opt.get('align', align)
        r = para.add_run(); r.text = text
        f = r.font; f.name = FONT
        sz = opt.get('size', size)
        if sz: f.size = Pt(sz)
        col = opt.get('color', color)
        if col is not None: f.color.rgb = col
        b = opt.get('bold', bold)
        if b is not None: f.bold = b
        if opt.get('space_after') is not None: para.space_after = Pt(opt['space_after'])
    return tf

def tb(slide, x, y, w, h, lines, size=14, color=WHITE, bold=None, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, name='text'):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    box.name = name
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.08); tf.margin_top = tf.margin_bottom = Inches(0.04)
    tf.vertical_anchor = anchor
    first = True
    for ln in lines:
        text, opt = (ln, {}) if isinstance(ln, str) else ln
        para = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        para.alignment = opt.get('align', align)
        r = para.add_run(); r.text = text
        f = r.font; f.name = FONT; f.size = Pt(opt.get('size', size)); f.color.rgb = opt.get('color', color)
        b = opt.get('bold', bold)
        if b is not None: f.bold = b
        if opt.get('space_after') is not None: para.space_after = Pt(opt['space_after'])
        if opt.get('space_before') is not None: para.space_before = Pt(opt['space_before'])
    return box

def card(slide, x, y, w, h, fill=PANEL, line=None, name='card', radius=True):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.name = name
    if radius: shp.adjustments[0] = 0.06
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None: shp.line.fill.background()
    else: shp.line.color.rgb = line; shp.line.width = Pt(1)
    shp.shadow.inherit = False
    shp.text_frame.text = ''
    return shp

def arrow(slide, x, y, w, h, name='arrow'):
    a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    a.name = name; a.fill.solid(); a.fill.fore_color.rgb = CYAN; a.line.fill.background(); a.shadow.inherit = False
    return a

def title_only(slide, text, y=1.75):
    """Big slide title for the free-layout duplicates (same position on each)."""
    return tb(slide, 1.33, y, 14, 1.0, [text], size=40, color=WHITE, bold=True, name='title')

# ---------------------------------------------------------------- 1 title
s = S[0]
set_text(find(s, 'Project title'), ['SIREN'], size=60, bold=True, color=WHITE)
sub = find(s, 'NAME OF TEAM')
set_text(sub, [('Sepsis Infection Risk Early Notification', {'size': 24, 'color': CYAN, 'bold': True}),
               ('[TEAM NAME]', {'size': 20, 'color': WHITE}),
               ('Track: Healthcare Digital Transformation', {'size': 18, 'color': MUTED})])
sub.top = Inches(5.55); sub.height = Inches(2.0); sub.width = Inches(9)

# ---------------------------------------------------------------- 2 team members
s = S[1]
members = [('[Student name]', 'Clinical lead  ·  Year [x] medical student'),
           ('[Student name]', 'Data and prototype lead  ·  Year [x] medical student'),
           ('[Student name]', 'Design and user research lead  ·  Year [x] medical student')]
for i, (nm, role) in enumerate(members):
    x = 4.59 + i * 3.725
    tb(s, x + 0.1, 4.55, 3.05, 1.15, [nm], size=20, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f'member name {i+1}')
    tb(s, x + 0.1, 5.85, 3.05, 1.6, [role], size=13, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f'member role {i+1}')
tb(s, 1.33, 8.2, 14, 0.9, ['Mentored by a clinical pharmacist and PhD researcher in AI for sepsis (advisory role only; the idea, prototype and presentation are the team\'s own).'], size=14, color=MUTED, name='mentor note')

# ---------------------------------------------------------------- 3 problem statement
s = S[2]
set_text(find(s, 'Teams must clearly define'), [
    'Sepsis is the body\'s life-threatening response to infection. It kills about 11 million people a year worldwide and is involved in one in every two to three hospital deaths. Every hour of delay in treatment raises the odds of death by about 4 %.',
], size=20, color=WHITE)
body = find(s, 'Sepsis is the body')
body.top = Inches(5.2); body.height = Inches(1.9); body.width = Inches(13.0)
# stat tiles under the text
stats = [('11 M', 'deaths a year worldwide (Rudd, Lancet 2020)'),
         ('1 in 2–3', 'hospital deaths involve sepsis (Liu, JAMA 2014)'),
         ('+4 % / h', 'odds of death per hour of treatment delay (Seymour, NEJM 2017)'),
         ('40 %', 'ICU mortality among septic patients in one Saudi hospital (Buraidah, 2012)')]
for i, (n, lab) in enumerate(stats):
    x = 1.73 + i * 3.35
    card(s, x, 7.35, 3.1, 2.0, fill=PANEL, name=f'stat card {i+1}')
    tb(s, x, 7.4, 3.1, 0.9, [n], size=30, color=CYAN, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f'stat {i+1}')
    tb(s, x + 0.1, 8.25, 2.9, 1.05, [lab], size=11.5, color=WHITE, align=PP_ALIGN.CENTER, name=f'stat label {i+1}')
tb(s, 1.73, 9.5, 12.5, 0.5, ['Stakeholders: ICU and ward patients, nurses, physicians, hospital quality teams, the Ministry of Health. The problem is not detection in theory; it is detection early enough, in every hospital, without drowning clinicians in alarms.'], size=12, color=MUTED, name='stakeholders')

# ---------------------------------------------------------------- 4 why existing alerts fail (dup of free slide)
s = S[3]
ph = find(s, 'This slide can be used'); ph._element.getparent().remove(ph._element)
title_only(s, 'Why today\'s sepsis alerts fail')
fails = [
    ('Missed cases, constant alarms', 'The most widely deployed hospital sepsis model missed 67 % of sepsis cases and alerted on 18 % of all admitted patients.', 'Wong et al., JAMA Intern Med 2021'),
    ('Models that do not travel', 'The winning model of the PhysioNet 2019 challenge scored 0.43 on its own hospitals and −0.12, worse than silence, on a hospital it had never seen.', 'Reyna et al., Crit Care Med 2020'),
    ('Tested on themselves', '81 % of published clinical AI models were never tested on data from another hospital; most of the rest lost performance when they were.', 'Yu et al., Radiol Artif Intell 2022'),
]
for i, (h, body_t, src) in enumerate(fails):
    x = 1.33 + i * 5.85
    card(s, x, 3.1, 5.45, 4.0, fill=PANEL, name=f'fail card {i+1}')
    tb(s, x + 0.2, 3.25, 5.05, 0.7, [h], size=20, color=CYAN, bold=True, name=f'fail head {i+1}')
    tb(s, x + 0.2, 4.0, 5.05, 2.3, [body_t], size=15, color=WHITE, name=f'fail body {i+1}')
    tb(s, x + 0.2, 6.45, 5.05, 0.5, [src], size=11, color=MUTED, name=f'fail src {i+1}')
tb(s, 1.33, 7.5, 17.3, 0.6, ['Three root causes we read in the literature'], size=18, color=WHITE, bold=True, name='root causes head')
roots = ['Every hospital stores the same vital sign under a different name, unit and clock, so a model trained in one hospital reads nonsense in the next.',
         'Models are often trained with information from after the moment of prediction (a test ordered because the doctor already suspected sepsis), so they look brilliant on paper and fail at the bedside.',
         'They are judged by a statistic (AUROC) that counts neither the patients missed nor the alarms clinicians have to answer.']
for i, r in enumerate(roots):
    x = 1.33 + i * 5.85
    tb(s, x, 8.15, 5.45, 1.6, [(f'{i+1}.  ', {'color': CYAN, 'bold': True, 'size': 14}), ], size=14, color=WHITE, name=f'root num {i+1}')
    tb(s, x + 0.45, 8.15, 5.0, 1.6, [r], size=13, color=WHITE, name=f'root {i+1}')

# ---------------------------------------------------------------- 5 innovation overview
s = S[4]
set_text(find(s, 'Teams introduce'), [
    'SIREN is an early sepsis warning for the whole hospital that speaks every ward\'s data language, uses only what the clinician could have known at that hour, and is judged by patients helped and alarms raised, not by a statistic.'
], size=19, color=WHITE)
b = find(s, 'SIREN is an early'); b.top = Inches(5.15); b.height = Inches(1.7); b.width = Inches(15.0); b.left = Inches(1.73)
pillars = [('One language', 'Every vital sign, lab and drug is translated to one name, one unit and one clock before any model sees it.'),
           ('Only the past', 'Each value is used from the hour it became available. No information from the future, ever.'),
           ('Judged by utility', 'A score that pays for every hour of early warning and charges for every false alarm and every missed patient.'),
           ('Clinician in the loop', 'Clinicians set the alarm budget and get a reason per organ, so the alert is one they will act on.')]
for i, (h, t) in enumerate(pillars):
    x = 1.73 + i * 4.0
    card(s, x, 7.1, 3.75, 2.75, fill=PANEL, name=f'pillar {i+1}')
    tb(s, x + 0.15, 7.2, 3.45, 0.6, [h], size=17, color=CYAN, bold=True, name=f'pillar head {i+1}')
    tb(s, x + 0.15, 7.8, 3.45, 2.0, [t], size=13, color=WHITE, name=f'pillar body {i+1}')
tb(s, 1.73, 10.0, 15, 0.5, ['What is different: existing alerts are one model, one hospital, one statistic. SIREN is a method that any hospital can plug its own records into and get a warning it can trust and tune.'], size=12.5, color=MUTED, name='difference')

# ---------------------------------------------------------------- 6 how it works (dup)
s = S[5]
ph = find(s, 'This slide can be used'); ph._element.getparent().remove(ph._element)
title_only(s, 'How SIREN works')
steps = [('Hospital records', 'vital signs, labs, drugs, nursing charts, as they are stored'),
         ('One language', 'same name, unit and clock in every ward and hospital'),
         ('One definition', 'Sepsis-3: suspected infection plus new organ dysfunction, applied identically'),
         ('Hour by hour', 'at every hour the model sees only what was known by then'),
         ('Risk + reason', 'risk of sepsis in the next 6 hours, and which organ is driving it'),
         ('Alarm policy', 'the ward\'s alarm budget decides when a rising risk becomes a bell')]
n = len(steps); w = 2.55; gap = 0.42; x0 = 1.33
for i, (h, t) in enumerate(steps):
    x = x0 + i * (w + gap)
    card(s, x, 3.3, w, 3.6, fill=PANEL if i != 4 else PANEL2, line=CYAN if i == 4 else None, name=f'step {i+1}')
    tb(s, x + 0.1, 3.4, w - 0.2, 0.5, [str(i + 1)], size=22, color=CYAN, bold=True, name=f'step num {i+1}')
    tb(s, x + 0.1, 3.95, w - 0.2, 0.75, [h], size=17, color=WHITE, bold=True, name=f'step head {i+1}')
    tb(s, x + 0.1, 4.7, w - 0.2, 2.1, [t], size=12.5, color=MUTED, name=f'step body {i+1}')
    if i < n - 1:
        arrow(s, x + w + 0.06, 4.85, 0.3, 0.35, name=f'arrow {i+1}')
tb(s, 1.33, 7.4, 17.3, 0.55, ['What the clinician sees'], size=18, color=WHITE, bold=True, name='sees head')
sees = [('A risk trajectory', 'the patient\'s six-hour sepsis risk over the stay, not a single number'),
        ('An organ panel', 'kidneys, lungs, circulation, liver, clotting, brain: which one is moving'),
        ('An alarm that respects a budget', 'two hours of rising risk, no repeat for six hours, only when something new was charted')]
for i, (h, t) in enumerate(sees):
    x = 1.33 + i * 5.85
    tb(s, x, 8.05, 5.45, 1.8, [(h, {'bold': True, 'color': CYAN, 'size': 15}), (t, {'size': 13, 'color': WHITE})], name=f'sees {i+1}')

# ---------------------------------------------------------------- 7 prototype, feasibility, risks (dup)
s = S[6]
ph = find(s, 'This slide can be used'); ph._element.getparent().remove(ph._element)
title_only(s, 'Prototype plan, feasibility and risks')
card(s, 1.33, 3.1, 8.6, 6.7, fill=PANEL, name='prototype card')
tb(s, 1.55, 3.2, 8.2, 0.6, ['What we build in the two-week sprint'], size=19, color=CYAN, bold=True, name='proto head')
proto = [('Data', 'The open PhysioNet 2019 Sepsis Challenge set: 40,336 ICU patients from two US hospitals, hourly vitals and labs, free for research. No patient data of our own is needed.'),
         ('Model', 'A simple hour-by-hour model (logistic regression or gradient-boosted trees) in Google Colab, trained with the strict rule that each hour sees only earlier hours.'),
         ('Score', 'The challenge\'s published utility score: reward for warnings up to 12 h early, a cost for each false alarm, a penalty for each missed patient.'),
         ('Screen', 'A Figma dashboard: risk trajectory, organ panel, alarm-budget slider. Tested with five clinicians using Google Forms feedback.')]
for i, (h, t) in enumerate(proto):
    y = 3.9 + i * 1.42
    tb(s, 1.55, y, 1.5, 1.3, [h], size=14, color=CYAN, bold=True, name=f'proto label {i+1}')
    tb(s, 3.0, y, 6.75, 1.3, [t], size=12.5, color=WHITE, name=f'proto text {i+1}')
card(s, 10.4, 3.1, 8.25, 6.7, fill=PANEL2, name='risk card')
tb(s, 10.6, 3.2, 7.9, 0.6, ['Risks we already know about'], size=19, color=CYAN, bold=True, name='risk head')
risks = [('Alert fatigue', 'a budget of false alarms per patient-day, set with clinicians, is part of the design'),
         ('Information from the future', 'every input is time-stamped by when it became available; we test the model with that rule enforced'),
         ('Does not transfer', 'the challenge set has two hospitals; we train on one and test on the other before we claim anything'),
         ('Privacy and regulation', 'open de-identified data only; a deployed version would be software as a medical device under SFDA rules'),
         ('Clinician trust', 'a reason per organ and a tunable budget, tested with clinicians before any pilot')]
for i, (h, t) in enumerate(risks):
    y = 3.9 + i * 1.14
    tb(s, 10.6, y, 2.6, 1.1, [h], size=13.5, color=CYAN, bold=True, name=f'risk label {i+1}')
    tb(s, 13.1, y, 5.4, 1.1, [t], size=12, color=WHITE, name=f'risk text {i+1}')

# ---------------------------------------------------------------- 8 sustainability
s = S[7]
set_text(find(s, 'Teams describe'), [
    'SIREN keeps working because it is built as a method the hospital owns, not a black box it rents.'
], size=22, color=WHITE)
b = find(s, 'SIREN keeps working'); b.top = Inches(5.2); b.height = Inches(1.0); b.width = Inches(15.0); b.left = Inches(1.73)
sus = [('Lives in the hospital system', 'Runs on the electronic record the hospital already has, through standard interfaces (HL7 FHIR). No new devices, no new data entry.'),
       ('Learns the local language once', 'The translation of each hospital\'s records is built once with its own informatics team and then reused for every future model and audit.'),
       ('Watched after launch', 'Alarm rate, missed cases and clinician response are monitored every month; the model is retrained when they drift, which is also how the quality team reports it.'),
       ('Funded by what it saves', 'Earlier antibiotics shorten ICU stays. Hospital quality budgets and national digital-health programmes already fund early-warning tools.')]
for i, (h, t) in enumerate(sus):
    col, row = i % 2, i // 2
    x = 1.73 + col * 8.2; y = 6.4 + row * 1.72
    card(s, x, y, 7.9, 1.58, fill=PANEL, name=f'sus card {i+1}')
    tb(s, x + 0.15, y + 0.08, 7.6, 0.5, [h], size=16, color=CYAN, bold=True, name=f'sus head {i+1}')
    tb(s, x + 0.15, y + 0.58, 7.6, 1.05, [t], size=12.5, color=WHITE, name=f'sus body {i+1}')

# ---------------------------------------------------------------- 9 business model canvas (fill the template blocks)
s = S[8]
OFF = (2218281, 2641840); EXT = (14651227, 6259035); CHOFF = (544100, 1917130); CHEXT = (20295800, 12645964)
sx = EXT[0] / CHEXT[0]; sy = EXT[1] / CHEXT[1]
def M(cx, cy, cw, ch):  # child inches -> slide inches
    X = (OFF[0] + (cx * 914400 - CHOFF[0]) * sx) / 914400
    Y = (OFF[1] + (cy * 914400 - CHOFF[1]) * sy) / 914400
    return X, Y, cw * sx, ch * sy
blocks = {
    'Key Partners': ((0.62, 3.12, 4.25, 8.30), ['Hospital informatics and quality teams', 'ICU and emergency clinicians', 'Ministry of Health digital-health programme', 'University research groups', 'Open ICU databases (PhysioNet)']),
    'Key Activities': ((5.10, 3.12, 4.25, 3.71), ['Translate each hospital\'s records to one language', 'Train and audit the hourly model', 'Co-design the alarm policy with clinicians']),
    'Key Resources': ((5.10, 7.72, 4.25, 3.71), ['Open ICU data for development', 'Hospital EHR access via FHIR', 'Clinical advisors; cloud compute']),
    'Value Proposition': ((9.57, 3.12, 4.25, 8.30), ['A sepsis warning hours earlier that works in this hospital, not only the one it was built in', 'Fewer false alarms through a clinician-set budget', 'A reason per organ, so the alert is actionable', 'Transparent, auditable, hospital-owned']),
    'Customer Relationships': ((14.04, 3.12, 4.25, 3.71), ['Co-design with ICU teams', 'Monthly performance reports to the quality committee', 'Clinician feedback loop in the dashboard']),
    'Channels': ((14.04, 7.72, 4.25, 3.71), ['Inside the hospital EHR and nursing dashboards', 'Pilot through a university hospital', 'Ministry of Health innovation programmes']),
    'Customer Segments': ((18.52, 3.12, 4.25, 8.30), ['Public and private hospitals with ICUs', 'Hospital quality and patient-safety departments', 'Regional health clusters', 'Later: wards and emergency departments']),
    'Cost Structure': ((0.62, 12.32, 10.96, 3.61), ['Data translation per hospital (one-off)  ·  cloud compute and monitoring  ·  clinical and regulatory review  ·  team salaries']),
    'Revenue Streams': ((11.81, 12.32, 10.97, 3.61), ['Annual licence per hospital  ·  implementation service per site  ·  research and innovation grants during development  ·  savings from shorter ICU stays fund adoption']),
}
for name, (geom, items) in blocks.items():
    X, Y, W, H = M(*geom)
    size = 11 if H > 2.5 else 10.5
    lines = [(('•  ' + it) if len(items) > 1 else it, {'size': size, 'space_after': 3}) for it in items]
    tb(s, X + 0.08, Y + 0.18, W - 0.16, H - 0.25, lines, size=size, color=WHITE, name=f'canvas {name}')

# ---------------------------------------------------------------- 10 roadmap (dup)
s = S[9]
ph = find(s, 'This slide can be used'); ph._element.getparent().remove(ph._element)
title_only(s, 'Development vision and next steps')
phases = [('Now · Sprint', 'Oct 26 to Nov 10', ['Prototype on open PhysioNet data in Colab', 'Figma dashboard', 'Feedback from five clinicians']),
          ('Finals · Nov 27–28', 'first test', ['Train on hospital A, test on hospital B of the open set', 'Report utility, false alarms per day, warning time', 'Show the dashboard live']),
          ('Phase 2 · 6 months', 'one hospital, silent', ['Translate one Saudi hospital\'s records with its informatics team', 'Run silently: alerts logged, not shown', 'Compare with what happened']),
          ('Phase 3 · 12 months', 'clinician pilot', ['Alarm budget set with the ICU team', 'Pilot on one unit with before-and-after measures', 'SFDA pathway and ethics approval']),
          ('Phase 4 · beyond', 'scale', ['Second hospital with a different record system', 'Wards and emergency department', 'Regional cluster licence'])]
w = 3.3; gap = 0.2; x0 = 1.33
for i, (h, sub, items) in enumerate(phases):
    x = x0 + i * (w + gap)
    card(s, x, 3.2, w, 5.9, fill=PANEL if i > 0 else PANEL2, line=CYAN if i == 0 else None, name=f'phase {i+1}')
    tb(s, x + 0.12, 3.3, w - 0.24, 0.6, [h], size=16, color=CYAN, bold=True, name=f'phase head {i+1}')
    tb(s, x + 0.12, 3.85, w - 0.24, 0.45, [sub], size=12, color=MUTED, name=f'phase sub {i+1}')
    tb(s, x + 0.12, 4.4, w - 0.24, 4.6, [('•  ' + it, {'space_after': 6}) for it in items], size=12.5, color=WHITE, name=f'phase items {i+1}')
tb(s, 1.33, 9.35, 17.3, 0.6, ['Success at each phase is defined before the phase starts: a utility score above zero on the unseen hospital, a false-alarm rate inside the budget the clinicians set, and a warning that arrives before the first antibiotic order.'], size=12.5, color=MUTED, name='success')

# ---------------------------------------------------------------- 11 references (original free slide)
s = S[10]
ph = find(s, 'This slide can be used')
set_text(ph, ['References'], size=36, bold=True)
ph.top = Inches(1.75); ph.left = Inches(1.33); ph.width = Inches(10); ph.height = Inches(0.9)
refs = ['Rudd KE, et al. Global, regional, and national sepsis incidence and mortality, 1990–2017. Lancet. 2020;395:200–211.',
        'Liu V, et al. Hospital deaths in patients with sepsis from 2 independent cohorts. JAMA. 2014;312:90–92.',
        'Seymour CW, et al. Time to treatment and mortality during mandated emergency care for sepsis. N Engl J Med. 2017;376:2235–2244.',
        'Singer M, et al. The Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3). JAMA. 2016;315:801–810.',
        'Wong A, et al. External validation of a widely implemented proprietary sepsis prediction model in hospitalized patients. JAMA Intern Med. 2021;181:1065–1070.',
        'Reyna MA, et al. Early prediction of sepsis from clinical data: the PhysioNet/Computing in Cardiology Challenge 2019. Crit Care Med. 2020;48:210–217.',
        'Yu AC, Mohajer B, Eng J. External validation of deep learning algorithms for radiologic diagnosis: a systematic review. Radiol Artif Intell. 2022;4:e210064.',
        'Kapoor S, Narayanan A. Leakage and the reproducibility crisis in machine-learning-based science. Patterns. 2023;4:100804.',
        'Alamri A, et al. Sepsis in Buraidah Central Hospital, Qassim, Kingdom of Saudi Arabia. Int J Health Sci (Qassim). 2015;9:393–400 (single centre, 2012).',
        'PhysioNet 2019 Challenge data: physionet.org/content/challenge-2019 (open access).']
tb(s, 1.33, 2.9, 17.3, 7.0, [(f'{i+1}.  {r}', {'space_after': 5}) for i, r in enumerate(refs)], size=13, color=WHITE, name='references')

# ---------------------------------------------------------------- 12 thank you
s = S[11]
set_text(find(s, 'Thank you'), [('Thank you', {'size': 88, 'bold': True, 'color': WHITE})])
t = find(s, 'Thank you'); t.width = Inches(9); t.left = Inches(5.5); t.top = Inches(4.0); t.height = Inches(1.8)
tb(s, 5.5, 6.1, 9, 1.4, ['SIREN  ·  Sepsis Infection Risk Early Notification', '[Team name]  ·  [contact email]'], size=18, color=CYAN, name='closing contact')

for sl in S:
    for sh in sl.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip() == 'MEDATHON':
            sh.left = Inches(16.4); sh.width = Inches(2.8)
p.save(OUT)
print('saved', OUT)
