"""Two-channel feature manifest (protocol 10c.2 item 14): every predictor column is assigned to exactly ONE path.

physiology : raw measurements, derived criteria and ratios, renal windows, handcrafted physiology, and the host block
             (age, sex, weight, height, body-mass index, chronic comorbidity flags; candidate's decision of 31 Oct 2026).
practice   : observed-value masks, measurement ages, documented exposures (devices, medications, imaging, fluids, procedures,
             nutrition, lab-result counts), charted clinical states, invasive-airway state, admission context, prophylaxis,
             and the handcrafted features that count or time MEASUREMENTS rather than describe the body
             (availability counts, measurement counts, coverage, hours since a measurement or an event, time since admission).
Derived Sepsis-3 criteria that depend on which components were measured ('MetAmongMeasured', 'SIRS_Count') stay in the
physiology path and are flagged availability_dependent=True for the audit (protocol: the leak point between the paths).
"""
import re
import pandas as pd
from v9_data import BASE,SUPPORT,AIRWAY,RENAL,DERIVED,STATES,ADMISSION,PROPHYLAXIS,EXPOSURES,COMORBID
from v10_features import ENGINEERED

HOST=['Age','Gender','Weight','Height','BMI']+list(COMORBID)
PRACTICE_RENAL={'UrineCoverage_6h','UrineCoverage_24h','UrineCoverageFraction_6h','Urine_HoursSinceLast'}
PRACTICE_DERIVED={'ICULOS','SIRS_ObservedComponents'}
_PRACTICE_ENGINEERED_RE=re.compile(r'(_Count\d+h$)|(_Available$)|(_HoursSince(First|Last)$)|(^ICULOS$)')
AVAILABILITY_DEPENDENT_RE=re.compile(r'(MetAmongMeasured$)|(^SIRS_Count$)|(^SOFA_Delta2?$)|(^qSOFA_Total$)|(^SOFA_Total$)|(^SOFAproxy_Total$)|(^SOFAproxy_MaxSoFar$)')

def base_name(feature):
    for suf in ('_observed','_age'):
        if feature.endswith(suf):return feature[:-len(suf)]
    return feature

def path_of(feature):
    """Return (path, block) for one predictor column."""
    if feature.endswith('_observed'):return 'practice','mask'
    if feature.endswith('_age'):return 'practice','measurement_age'
    f=feature
    if f in HOST:return 'physiology','host'
    if f in EXPOSURES:return 'practice','exposure'
    if f in ADMISSION:return 'practice','admission_context'
    if f in PROPHYLAXIS:return 'practice','prophylaxis'
    if f in STATES:return 'practice','charted_state'
    if f in AIRWAY:return 'practice','airway_state'
    if f in PRACTICE_RENAL:return 'practice','measurement_coverage'
    if f in PRACTICE_DERIVED or _PRACTICE_ENGINEERED_RE.search(f):return 'practice','measurement_process'
    if f in ENGINEERED:return 'physiology','handcrafted'
    if f in RENAL:return 'physiology','renal_window'
    if f in DERIVED:return 'physiology','derived_criterion'
    if f in SUPPORT:return 'physiology','support_state'   # vasopressor/inotrope recorded: part of the cardiovascular SOFA criterion
    if f in BASE:return 'physiology','raw_measurement'
    return 'physiology','other_physiology'

def manifest(features):
    rows=[]
    for f in features:
        path,block=path_of(f)
        rows.append({'feature':f,'path':path,'block':block,'availability_dependent':bool(AVAILABILITY_DEPENDENT_RE.search(base_name(f))) and path=='physiology'})
    return pd.DataFrame(rows)

def audit(m,features):
    """Every feature exactly once; both paths non-empty; summary counts. Raises on any violation."""
    if list(m.feature)!=list(features):raise AssertionError('Manifest order differs from the feature list')
    if m.feature.duplicated().any():raise AssertionError('Duplicate feature in manifest')
    if not set(m.path)<={'physiology','practice'}:raise AssertionError('Unknown path')
    if (m.path.eq('physiology').sum()==0) or (m.path.eq('practice').sum()==0):raise AssertionError('A path is empty')
    if not m.loc[m.feature.str.endswith(('_observed','_age')),'path'].eq('practice').all():raise AssertionError('A mask or age column is not in the practice path')
    host=m[m.block.eq('host')]
    if not set(host.feature)<=set(HOST):raise AssertionError('Host block contains a non-host column')
    return m.groupby(['path','block']).size().rename('columns').reset_index()

def path_indices(features,path,manifest_df=None,exclude_blocks=()):
    m=manifest(features) if manifest_df is None else manifest_df
    keep=m.path.eq(path)&~m.block.isin(list(exclude_blocks))
    return [i for i,k in enumerate(keep) if k]

def concept_grouped_practice(features,mapping):
    """Concept-grouped practice path (protocol item 14 comparator): the mask and age columns of each organ group are
    summarised as one measurement-intensity column per group (mean of masks) and one freshest-age column per group.
    `mapping` is the organ_mapping(features) dict. Returns a list of (new_column, [source columns], 'mean'|'min')."""
    groups={}
    for f in features:
        if f.endswith('_observed'):groups.setdefault(('intensity',mapping.get(f,mapping.get(base_name(f),'other'))),[]).append(f)
        elif f.endswith('_age'):groups.setdefault(('freshest_age',mapping.get(f,mapping.get(base_name(f),'other'))),[]).append(f)
    return [(f'PracticeGroup_{kind}_{g}',cols,'mean' if kind=='intensity' else 'min') for (kind,g),cols in sorted(groups.items())]
