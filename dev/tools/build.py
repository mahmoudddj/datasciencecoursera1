import json,gzip,base64,hashlib,io,sys,ast
from pathlib import Path
S=Path(sys.argv[1]);W=S/'work';C=W/'cells';OUT=Path(sys.argv[2]);OUT.mkdir(parents=True,exist_ok=True)
mods=sorted(p for p in (W/'mods').iterdir() if p.is_file() and not p.name.endswith('.pyc'))
emb={}
for p in mods:
    raw=p.read_bytes();buf=io.BytesIO()
    with gzip.GzipFile(fileobj=buf,mode='wb',mtime=0,filename='') as g:g.write(raw)
    emb[p.name]={'sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(buf.getvalue()).decode()}
orig_main=json.load(open(S/'in/1bc985bc-Sepsis_V10_Improved_MIMIC_eICU_1.ipynb'))
orig_leg=json.load(open(S/'in/8c470c15-PhysioNet_Models_External_Validation_MIMIC_eICU_1.ipynb'))
def src(nb,i):return ''.join(nb['cells'][i]['source'])
rest=[l for l in src(orig_main,3).splitlines() if not l.startswith('EMBEDDED_MODULES = ')]
rest='\n'.join(rest)
rest=rest.replace("from v9_data import fingerprint,signature,cohort_index,RawExtractor,build_shards,PRIMARY,SPEC,BASE,SUPPORT,RENAL,DERIVED,PHENO,MED_CONTEXT",
                  "from v9_data import fingerprint,signature,cohort_index,RawExtractor,build_shards,raw_stage_key,PRIMARY,SPEC,BASE,SUPPORT,RENAL,DERIVED,PHENO,MED_CONTEXT")
rest=rest.replace("from v10_features import ENGINEERED,GROUPS","from v10_features import ENGINEERED,GROUPS,VERSION as FEATURE_VERSION")
assert 'raw_stage_key' in rest and 'FEATURE_VERSION' in rest
lines=rest.splitlines();embedded='\n'.join([lines[0],'EMBEDDED_MODULES = '+repr(emb)]+lines[1:])
_n=[0]
def _id():_n[0]+=1;return 'c%03d'%_n[0]
def code(s):return {'cell_type':'code','execution_count':None,'id':_id(),'metadata':{},'outputs':[],'source':s.rstrip(chr(10))}
def md(s):return {'cell_type':'markdown','id':_id(),'metadata':{},'source':s.rstrip('\n')}
def f(n):return (C/n).read_text()
ver=W/'verification_main.md';verl=W/'verification_legacy.md'
vmain=ver.read_text() if ver.exists() else '## Verification record\n(pending)'
vleg=verl.read_text() if verl.exists() else '## Verification record\n(pending)'
main=[md(f('main_md0.md')),md(f('main_md1.md')),code(f('main_2.py')),code(embedded),code(src(orig_main,4)),md(f('main_md5.md'))]+\
     [code(src(orig_main,6)),code(f('repair.py')),code(f('main_7.py'))]+[code(src(orig_main,i)) for i in range(8,11)]+[md(f('main_md11.md')),code(f('main_12.py')),code(f('main_13.py')),code(f('main_14.py')),
     code(f('main_15.py')),md(f('main_md16.md')),code(f('main_17.py')),md(f('main_md18.md')),md(vmain)]
leg=[md(f('leg_md0.md')),code(f('leg_1.py')),code(embedded),code(src(orig_leg,3)),md(f('leg_md4.md')),code(f('leg_5.py')),md(f('leg_md6.md'))]+\
    [code(src(orig_leg,7)),code(f('repair.py')),code(f('main_7.py'))]+[code(src(orig_leg,i)) for i in range(9,12)]+[md(f('leg_md12.md')),code(f('leg_13.py')),md(f('leg_md14.md')),code(f('leg_15.py')),md(f('leg_md16.md')),md(vleg)]
meta_extra={}
mj=W/'validation_metadata.json'
if mj.exists():meta_extra=json.loads(mj.read_text())
for name,cells,key in [('Sepsis_V10_Improved_MIMIC_eICU.ipynb',main,'main'),('PhysioNet_Models_External_Validation_MIMIC_eICU.ipynb',leg,'legacy')]:
    for c in cells:
        if c['cell_type']=='code':ast.parse(c['source'])
    nb={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python','version':'3.12'},'sepsis_validation':meta_extra.get(key,{'status':'pending'})},'nbformat':4,'nbformat_minor':5}
    (OUT/name).write_text(json.dumps(nb,indent=1,ensure_ascii=False))
    print(name,len(cells),'cells',(OUT/name).stat().st_size//1024,'KB')
print('modules',len(emb))
