import json,sys
nb=json.load(open(sys.argv[1]))
for i,c in enumerate(nb['cells']):
    if c['cell_type']!='code':continue
    for o in c.get('outputs',[]):
        t=o.get('text') or o.get('data',{}).get('text/plain') or (o.get('ename','')+': '+o.get('evalue',''))
        if t:print(f'[{i}]',''.join(t)[:1500])
