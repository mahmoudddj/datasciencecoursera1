"""Shared experiment contract; no outcome-dependent allocation to protected groups."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

VERSION='sepsis-evaluation-10.1'
def protected_group(group):
    return int(hashlib.sha256(('sepsis-final-v1|'+str(group)).encode()).hexdigest()[:8],16)%5==0

def config(mode='smoke',max_hours=120):
    if mode not in ['smoke','full']:raise ValueError(mode)
    smoke=mode=='smoke'
    return dict(mode=mode,split_seed=42,max_hours=max_hours,horizon=6,batch=8,
      learning_rate=3e-4,dropout=.1,patience=5,small_model=smoke,
      epochs=2 if smoke else 30,observer_epochs=2 if smoke else 10,observer_hidden=32,
      seeds=[42] if smoke else [42,7,123],
      arms=['osta','observer_features','output_fusion','gated_attention','ungated_attention','cnn','logistic','boosted_tree'],
      false_alarm_budget=.5,alarm_cooldown=6,
      stress_conditions=['missing_all','stale_6h'] if smoke else ['missing_all','missing_half','incorrect','conflicting','stale_6h','delayed_2h'],
      bootstrap=5 if smoke else 200,tabular_max_bytes=2*1024**3,
      tree_iterations=10 if smoke else 200,release_final=False,
      protocol=VERSION)

def resolve_onsets(folder,summary):
    """Read cached unwindowed ricu events. No blind first_positive+6 reconstruction.
    YAIB sep3_alt is an event series; its nonmissing rows have onset in `time`.
    v9 already saves these events in every labels batch, so no R reimport is needed.
    """
    from v9_data import hour_values
    paths=sorted(Path(folder).glob('batches/*/*/labels.parquet'))
    if not paths:raise FileNotFoundError('Unwindowed labels.parquet absent. Restore original batch folders or rerun label extraction; shifted labels cannot identify clipped onset safely.')
    events=[];known=set()
    for p in paths:
        ids=p.parent/'ids.json';done=p.parent/'labels_complete.json'
        if not ids.is_file() or not done.is_file():continue
        known.update(json.loads(ids.read_text()))
        z=pd.read_parquet(p)
        if not {'stay_id','time','sep3_alt'}<=set(z):raise ValueError('Unexpected pinned ricu event schema: '+str(p))
        z=z[z.sep3_alt.notna()].copy();z['OnsetHour']=hour_values(z.time)
        events.append(z[['stay_id','OnsetHour']])
    if not set(summary.stay_id)<=known:raise ValueError('Label prepass does not cover cohort stay IDs')
    ev=pd.concat(events,ignore_index=True).drop_duplicates() if events else pd.DataFrame(columns=['stay_id','OnsetHour'])
    ev=ev.groupby('stay_id',as_index=False).OnsetHour.min()
    z=summary.merge(ev,on='stay_id',how='left',validate='one_to_one')
    z['OnsetSource']='cached_unwindowed_sep3_alt'
    z['WindowReconstructionDifference']=z.first_positive+6-z.OnsetHour
    if (z.first_positive.notna()&z.OnsetHour.isna()).any():raise ValueError('Windowed positive has no operational onset event')
    z['Outcome']=z.OnsetHour.notna().astype(int)
    z[['stay_id','first_hour','first_positive','OnsetHour','WindowReconstructionDifference','OnsetSource']].to_parquet(Path(folder)/'v10_onset_audit.parquet',index=False)
    return z

def partition(index,target,cfg):
    from sklearn.model_selection import train_test_split
    reserve=index.Group_ID.map(protected_group)
    if cfg['mode']=='smoke' and cfg.get('release_final'):raise ValueError('Smoke cannot release final holdouts')
    final=cfg.get('release_final',False)
    if final:
        dev=index[index.Dataset.ne(target)&~reserve].copy()
        test=index[index.Dataset.eq(target)&reserve].copy()
        label='protected_cross_database_test_prior_exposure_must_be_declared'
    else:
        # Only development-designated patients of ONE database. The other source
        # is not used as an external test during notebook implementation.
        dev=index[index.Dataset.eq(target)&~reserve].copy();test=None
        label='internal_development_smoke' if cfg['mode']=='smoke' else 'internal_development'
    groups=dev.groupby('Group_ID').eligible_positive.max()
    if groups.nunique()!=2 or groups.value_counts().min()<12:
        raise ValueError(f'{target}: need >=12 positive and negative development patient groups. Increase the capped smoke candidate count after inspecting attrition; no automatic retries.')
    def split(ids,frac):return train_test_split(ids,test_size=frac,random_state=cfg['split_seed'],stratify=groups.loc[ids])
    if test is None:
        ids,ti=split(groups.index.to_numpy(),.2);test=dev[dev.Group_ID.isin(ti)].copy();dev=dev[dev.Group_ID.isin(ids)].copy()
    else:ids=groups.index.to_numpy()
    main,hold=split(ids,.4);observer,vc=split(hold,.5);val,calib=split(vc,.5)
    role={g:s for s,a in [('train',main),('observer_fit',observer),('val',val),('calib',calib)] for g in a}
    dev['split']=dev.Group_ID.map(role);test['split']='test'
    m=pd.concat([dev,test],ignore_index=True);m['evaluation_scope']=label
    if m.groupby('Group_ID').split.nunique().max()!=1:raise AssertionError('Patient leakage')
    for sp,g in m.groupby('split'):
        if g.eligible_positive.nunique()!=2:raise ValueError(f'{target}/{sp}: both classes required; enlarge smoke sample')
    if not final and m.Group_ID.map(protected_group).any():raise AssertionError('Protected patient exposed')
    return m
