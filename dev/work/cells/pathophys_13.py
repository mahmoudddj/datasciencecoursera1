# %% MD
## 7. Pathophysiology study (protocol section 10c.1)
Three groups from the stage-1 samples, **training-split and non-cohort patients only**: *incident* (ICU-acquired sepsis, onset at or after the sixth ICU hour), *arrived septic* (sampled stays excluded by YAIB exclusion 7; onset before the sixth hour, features from the unlabelled corpus, onset from the label batches) and *controls* (no onset). Only fresh measurements (age under 1 h) are used for values; measurement frequency is reported separately as the practice signal. Every output is aggregate; counts under 11 are masked.
# %% CODE
# 7a. Groups, onset times and the stay-level manifest
from v10_protocol import partition,protected_group
from v9_train import SequenceStore
PATHO_KEY=signature({'data':DATA_KEY,'ssl':globals().get('SSL_KEY','fixture'),'cohort':globals().get('COHORT_KEY','fixture'),'protocol':'10c-1'})[:16]
PATHO_ROOT=VALIDATION_ROOT/'pathophysiology'/PATHO_KEY;PATHO_ROOT.mkdir(parents=True,exist_ok=True)
SMALL_CELL=11
def _hours(v):
    """Onset as hours from ICU admission whatever the stored type (numeric hours or timedelta)."""
    if pd.api.types.is_timedelta64_dtype(v):return v.dt.total_seconds()/3600.0
    return pd.to_numeric(v,errors='coerce')
def candidate_onsets(ds):
    """Onset for EVERY sampled candidate (before any exclusion) from the label batches; NaN = no sepsis."""
    parts=[]
    if DATA_SOURCE=='clinical':
        for p in sorted((COHORT_ROOT/ds/'batches').rglob('labels.parquet')):
            d=pd.read_parquet(p);col='sep3_alt' if 'sep3_alt' in d else [c for c in d.columns if c!='stay_id'][0]
            parts.append(pd.DataFrame({'stay_id':d.stay_id.astype('int64'),'onset_h':_hours(d[col])}))
    if not parts:   # fixture: the index is the only source
        z=INDEX[INDEX.Dataset.eq(ds)];return pd.DataFrame({'stay_id':z.stay_id.astype('int64'),'onset_h':z.OnsetHour.astype(float)})
    return pd.concat(parts,ignore_index=True).drop_duplicates('stay_id')
GROUPS={}
for ds in DATASETS:
    mf=partition(INDEX,ds,TRAIN_CONFIG);dev=mf[mf.split.isin(['train','observer_fit'])].copy()   # never validation, test or protected
    inc=dev[dev.eligible_positive.eq(1)].copy();inc['group']='incident';inc['onset_h']=inc.OnsetHour.astype(float)
    ctl=dev[dev.OnsetHour.isna()].copy();ctl['group']='control';ctl['onset_h']=np.nan
    on=candidate_onsets(ds);early=on[on.onset_h.notna()&(on.onset_h<6)]
    corp=CORPUS.get(ds)
    if corp is not None and len(corp) and len(early):
        prev=corp[corp.stay_id.astype('int64').isin(set(early.stay_id))].copy()
        prev=prev[~prev.Group_ID.map(protected_group)]   # the corpus already excludes protected patients; keep the guard
        prev=prev.merge(early,on='stay_id',how='left');prev['group']='arrived_septic';prev['Dataset']=ds
    else:prev=pd.DataFrame(columns=list(inc.columns))
    g=pd.concat([inc,prev,ctl],ignore_index=True);g['Dataset']=ds;GROUPS[ds]=g
    cnt=g.groupby('group').size().to_dict()
    print(ds,'| incident',cnt.get('incident',0),'| arrived septic',cnt.get('arrived_septic',0),'| controls',cnt.get('control',0),
          '| candidates with onset before 6 h:',int(len(early)),'| onset range of arrived septic (h): '+(f"{early.onset_h.min():.1f} to {early.onset_h.max():.1f}" if len(early) else 'n/a'))
MANIFEST=pd.concat(GROUPS.values(),ignore_index=True)
MANIFEST[['Dataset','group','file','offset','length','onset_h']].assign(stay=lambda d:range(len(d))).drop(columns=[]).to_parquet(PATHO_ROOT/'manifest_no_ids.parquet',index=False)
# %% CODE
# 7b. Fresh-value trajectories, measurement rates, Cliff's delta with stay-level bootstrap; cross-database rule 10c.1
PHYS=[c for c in ['HR','Temp','Resp','SBP','MAP','DBP','O2Sat','GCS','Lactate','WBC','Bands','Neutrophils','Lymphocytes','Platelets','Creatinine','BUN','Bilirubin_total',
                  'pH','HCO3','BaseExcess','PaO2','PaCO2','FiO2','Glucose','Hgb','Sodium','Potassium','Chloride','AnionGap','CRP','Procalcitonin','INR','PTT','Albumin','UrineOutput'] if c in FEATURES]
SOFA=[c for c in FEATURES if c.startswith('SOFA') and not c.endswith(('_observed','_age'))]
CHANNELS=PHYS+SOFA
BINS=[(-24,-20),(-20,-16),(-16,-12),(-12,-8),(-8,-4),(-4,0),(0,4),(4,8),(8,12),(12,16),(16,20),(20,24)]
ADM_BINS=[(1,4),(5,8),(9,12),(13,16),(17,20),(21,24),(25,30)]
def stay_rows(row):
    """Raw hourly rows of one stay from its shard (values with NaN; ages in hours), relative hours attached."""
    d=pd.read_parquet(row.file).iloc[int(row.offset):int(row.offset+row.length)]
    d=d[['Hour']+[c for c in CHANNELS if c in d]+[c+'_age' for c in PHYS if c+'_age' in d]].copy()
    d['rel_onset']=d.Hour-row.onset_h if pd.notna(row.onset_h) else np.nan
    return d
def fresh_frame(df):
    """Long table: stay, channel, Hour, rel_onset, value (fresh measurements only; SOFA components as carried)."""
    out=[]
    for c in PHYS:
        if c not in df:continue
        fresh=df[c+'_age'].lt(1)&df[c].notna() if c+'_age' in df else df[c].notna()
        out.append(pd.DataFrame({'channel':c,'Hour':df.Hour[fresh],'rel_onset':df.rel_onset[fresh],'value':df[c][fresh]}))
    for c in SOFA:
        if c in df:out.append(pd.DataFrame({'channel':c,'Hour':df.Hour,'rel_onset':df.rel_onset,'value':df[c]}).dropna(subset=['value']))
    return pd.concat(out,ignore_index=True) if out else pd.DataFrame(columns=['channel','Hour','rel_onset','value'])
LONG=[];HOURS=[]
for k,row in MANIFEST.iterrows():
    d=stay_rows(row);f=fresh_frame(d);f['stay']=k;f['group']=row.group;f['Dataset']=row.Dataset;LONG.append(f)
    HOURS.append(pd.DataFrame({'stay':k,'group':row.group,'Dataset':row.Dataset,'Hour':d.Hour,'rel_onset':d.rel_onset}))
LONG=pd.concat(LONG,ignore_index=True);HOURS=pd.concat(HOURS,ignore_index=True)
def binned(x,bins):
    lab=pd.Series(pd.NA,index=x.index,dtype='object')
    for a,b in bins:lab[(x>=a)&(x<b)]=f'{a}..{b}'
    return lab
LONG['bin_onset']=binned(LONG.rel_onset,BINS);LONG['bin_adm']=binned(LONG.Hour,ADM_BINS)
HOURS['bin_onset']=binned(HOURS.rel_onset,BINS);HOURS['bin_adm']=binned(HOURS.Hour,ADM_BINS)
def trajectories(bincol):
    v=LONG.dropna(subset=[bincol]).groupby(['Dataset','group','channel',bincol]).agg(n_stays=('stay','nunique'),n_values=('value','size'),median=('value','median'),q25=('value',lambda s:s.quantile(.25)),q75=('value',lambda s:s.quantile(.75))).reset_index()
    h=HOURS.dropna(subset=[bincol]).groupby(['Dataset','group',bincol]).agg(stay_hours=('Hour','size')).reset_index()
    v=v.merge(h,on=['Dataset','group',bincol],how='left');v['measurements_per_stay_hour']=v.n_values/v.stay_hours
    for c in ['n_stays','n_values']:v[c]=v[c].where(v[c]>=SMALL_CELL,-1)   # -1 = masked (<11)
    return v
TRAJ_ONSET=trajectories('bin_onset');TRAJ_ADM=trajectories('bin_adm')
TRAJ_ONSET.to_csv(PATHO_ROOT/'trajectories_relative_to_onset.csv',index=False);TRAJ_ADM.to_csv(PATHO_ROOT/'trajectories_since_admission.csv',index=False)
# ---- stay-level windows for the five comparisons ----
def stay_window(group,lo,hi,by='rel_onset',stat='median'):
    """Per-stay summary of fresh values inside [lo,hi) hours; stat = median or slope (per hour)."""
    sel=LONG[LONG.group.eq(group)&(LONG[by]>=lo)&(LONG[by]<hi)]
    if stat=='median':return sel.groupby(['Dataset','channel','stay']).value.median().reset_index()
    def slope(g):
        if len(g)<3 or g[by].nunique()<2:return np.nan
        return float(np.polyfit(g[by].to_numpy(float),g.value.to_numpy(float),1)[0])
    return sel.groupby(['Dataset','channel','stay']).apply(slope,include_groups=False).rename('value').reset_index()
def cliffs(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    if len(x)==0 or len(y)==0:return np.nan
    gt=(x[:,None]>y[None,:]).mean();lt=(x[:,None]<y[None,:]).mean();return float(gt-lt)
def compare(name,a,b,n_boot=200,seed=42):
    rng=np.random.default_rng(seed);rows=[]
    for ds in DATASETS:
        for ch in CHANNELS:
            xa=a[(a.Dataset.eq(ds))&(a.channel.eq(ch))].value.dropna().to_numpy();xb=b[(b.Dataset.eq(ds))&(b.channel.eq(ch))].value.dropna().to_numpy()
            if len(xa)<SMALL_CELL or len(xb)<SMALL_CELL:rows.append({'comparison':name,'Dataset':ds,'channel':ch,'n_a':-1 if len(xa)<SMALL_CELL else len(xa),'n_b':-1 if len(xb)<SMALL_CELL else len(xb),'delta':np.nan,'ci_low':np.nan,'ci_high':np.nan});continue
            d=cliffs(xa,xb);bs=[cliffs(rng.choice(xa,len(xa)),rng.choice(xb,len(xb))) for _ in range(n_boot)]
            rows.append({'comparison':name,'Dataset':ds,'channel':ch,'n_a':len(xa),'n_b':len(xb),'delta':d,'ci_low':float(np.quantile(bs,.025)),'ci_high':float(np.quantile(bs,.975)),
                         'median_a':float(np.median(xa)),'median_b':float(np.median(xb))})
    return pd.DataFrame(rows)
COMP=pd.concat([
    compare('1 incident vs control, hours 1-24 since admission',stay_window('incident',1,25,'Hour'),stay_window('control',1,25,'Hour')),
    compare('2 incident 12 h before onset vs control hours 7-30',stay_window('incident',-12,0),stay_window('control',7,31,'Hour')),
    compare('3 arrived septic vs incident, 12 h after onset',stay_window('arrived_septic',0,12),stay_window('incident',0,12)),
    compare('4 arrived septic first 12 h vs incident 12 h before onset',stay_window('arrived_septic',1,13,'Hour'),stay_window('incident',-12,0)),
    compare('5 slope: incident 12 h before onset vs control hours 7-18',stay_window('incident',-12,0,stat='slope'),stay_window('control',7,19,'Hour',stat='slope')),
    compare('5b slope: arrived septic first 12 h vs control hours 7-18',stay_window('arrived_septic',1,13,'Hour',stat='slope'),stay_window('control',7,19,'Hour',stat='slope')),
],ignore_index=True)
def classify(g):
    ok=g.delta.notna()
    if ok.sum()<2:return 'not estimable in both databases'
    s=np.sign(g.delta);m=g.delta.abs()
    if (s.nunique()==1) and (m>=.33).all():return 'strong shared'
    if (s.nunique()==1) and (m>=.147).all():return 'shared'
    if (m>=.147).any():return 'database-specific'
    return 'no signal'
CLASS=COMP.groupby(['comparison','channel']).apply(classify,include_groups=False).rename('cross_database').reset_index()
COMP=COMP.merge(CLASS,on=['comparison','channel'],how='left');COMP.to_csv(PATHO_ROOT/'comparisons_cliffs_delta.csv',index=False)
# measurement-rate (practice) comparison: incident vs control, hours 1-24, per channel, as a ratio per database
rate=TRAJ_ADM[TRAJ_ADM.group.isin(['incident','control','arrived_septic'])].groupby(['Dataset','group','channel']).measurements_per_stay_hour.mean().unstack('group')
rate['incident_over_control']=rate.get('incident')/rate.get('control');rate.reset_index().to_csv(PATHO_ROOT/'measurement_rates.csv',index=False)
shared={c:sorted(CLASS[CLASS.comparison.str.startswith(c)&CLASS.cross_database.isin(['shared','strong shared'])].channel) for c in ['1','2','3','4','5']}
atomic_json(PATHO_ROOT/'shared_physiology.json',{'rule':'same sign and |Cliff delta| >= 0.147 in both databases (strong: >= 0.33)','shared_by_comparison':shared,'channels':CHANNELS})
print('Channels:',len(CHANNELS),'| rows in long table:',len(LONG))
for c in sorted(COMP.comparison.unique()):
    sub=COMP[COMP.comparison.eq(c)];print(f'\n{c}');display(sub.pivot_table(index='channel',columns='Dataset',values='delta').round(2).join(CLASS[CLASS.comparison.eq(c)].set_index('channel').cross_database).sort_values('cross_database'))
print('\nMeasurement rate ratio incident/control (practice signal):');display(rate[['incident_over_control']].unstack('Dataset').round(2))
print('Saved under',PATHO_ROOT)
# %% CODE
# 7c. Figures (small multiples) and the stage-2 predictor-set definitions (protocol 10c.2, items 2a-2c)
import matplotlib.pyplot as plt
KEY=[c for c in ['HR','Temp','Resp','MAP','O2Sat','Lactate','WBC','Platelets','Creatinine','Bilirubin_total','GCS','UrineOutput'] if c in CHANNELS]
def order(b):return int(b.split('..')[0])
fig,axes=plt.subplots(len(KEY),2,figsize=(11,2.1*len(KEY)),squeeze=False)
colors={'incident':'#b3122b','arrived_septic':'#9a5b00','control':'#1f6f3f'};styles={'miiv':'-','eicu':'--'}
for i,ch in enumerate(KEY):
    for j,(T,bincol,xl) in enumerate([(TRAJ_ONSET,'bin_onset','hours relative to onset'),(TRAJ_ADM,'bin_adm','hours since ICU admission')]):
        ax=axes[i,j];t=T[T.channel.eq(ch)]
        for (ds,g),s in t.groupby(['Dataset','group']):
            s=s[s.n_stays.ge(SMALL_CELL)].copy()
            if s.empty:continue
            s['x']=s[bincol].map(order);s=s.sort_values('x');ax.plot(s.x,s['median'],styles.get(ds,'-'),color=colors.get(g,'k'),label=f'{g} ({ds})',lw=1.4)
            ax.fill_between(s.x,s.q25,s.q75,color=colors.get(g,'k'),alpha=.08)
        ax.set_ylabel(ch,fontsize=8);ax.tick_params(labelsize=7)
        if j==0:ax.axvline(0,color='#888',lw=.8)
        if i==len(KEY)-1:ax.set_xlabel(xl,fontsize=8)
axes[0,0].legend(fontsize=6,ncol=2);fig.suptitle('Fresh-value medians (IQR shaded): incident vs arrived septic vs controls; solid MIMIC-IV, dashed eICU',fontsize=9)
fig.tight_layout();fig.savefig(PATHO_ROOT/'trajectories_small_multiples.png',dpi=140);plt.show()
# ---- stage-2 predictor sets by registry class (10c.2 item 2) ----
PHYS_KINDS={'raw measurement','derived criterion/ratio','renal window (availability-aware)'}
base_phys=set(REGISTRY[REGISTRY.kind.isin(PHYS_KINDS)|REGISTRY.kind.str.startswith('handcrafted')].feature)|{'Age','Gender'}
PHYSIOLOGY_ONLY=[f for f in FEATURES if f in base_phys or (f.endswith('_observed') and f[:-9] in base_phys) or (f.endswith('_age') and f[:-4] in base_phys)]
PHYSIOLOGY_NO_MASKS=[f for f in PHYSIOLOGY_ONLY if not f.endswith(('_observed','_age'))]
shared_any=set().union(*[set(v) for v in shared.values()]) if shared else set()
SHARED_PHYSIOLOGY=[f for f in PHYSIOLOGY_ONLY if base_name(f) in shared_any or f in ('Age','Gender')]
atomic_json(PATHO_ROOT/'stage2_predictor_sets.json',{'physiology_only':PHYSIOLOGY_ONLY,'physiology_no_masks':PHYSIOLOGY_NO_MASKS,'shared_physiology':SHARED_PHYSIOLOGY,
    'rule':'10c.2 item 2: classes raw measurement, derived criterion/ratio, renal window, handcrafted physiology, with masks and ages, plus Age and Gender; shared = channels marked shared in any 10c.1 comparison'})
print('Stage-2 predictor sets | full:',len(FEATURES),'| physiology only:',len(PHYSIOLOGY_ONLY),'| without masks/ages:',len(PHYSIOLOGY_NO_MASKS),'| shared physiology:',len(SHARED_PHYSIOLOGY))
print('Written:',PATHO_ROOT/'stage2_predictor_sets.json')
