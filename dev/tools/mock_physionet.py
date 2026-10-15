import sys,os,threading,hashlib,base64,tempfile,http.server,functools
from pathlib import Path
sys.path.insert(0,sys.argv[1]+'/work/mods')
from v10_preflight import repair_from_physionet,FULL_MIN_BYTES,table_sizes
srv=Path(tempfile.mkdtemp());files={}
for stem,mn in FULL_MIN_BYTES['miiv'].items():
    data=os.urandom(1000)*((mn//1000)+2) if stem in ('icu/icustays','hosp/patients') else b'x'
    p=srv/(stem+'.csv.gz');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);files[stem]=hashlib.sha256(data).hexdigest()
(srv/'SHA256SUMS.txt').write_text(''.join(f'{h}  {s}.csv.gz\n' for s,h in files.items()))
state={'cut':True}
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.headers.get('Authorization')!='Basic '+base64.b64encode(b'dr:pw').decode():self.send_response(401);self.end_headers();return
        p=srv/self.path.split('/files/x/')[-1];data=p.read_bytes();start=0
        rng=self.headers.get('Range')
        if rng:start=int(rng.split('=')[1].rstrip('-'))
        body=data[start:]
        if state['cut'] and p.name=='icustays.csv.gz' and not rng:body=body[:len(body)//3];state['cut']=False   # simulated dropped connection
        full=len(data)-start
        self.send_response(206 if rng else 200);self.send_header('Content-Length',str(full));self.end_headers();self.wfile.write(body);self.close_connection=True
s=http.server.ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=s.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{s.server_port}/files/x/'
root=Path(tempfile.mkdtemp())/'mimic-iv-3.1'
for stem,mn in FULL_MIN_BYTES['miiv'].items():
    f=root/(stem+'.csv.gz');f.parent.mkdir(parents=True,exist_ok=True)
    with open(f,'wb') as h:h.truncate(5000 if stem in ('icu/icustays','hosp/patients') else mn+1)
print('before:',[(r['table'],r['status']) for r in table_sizes('miiv',root) if r['status']!='ok'])
try:repair_from_physionet('miiv',root,'dr','pw',base=base)
except (ValueError,OSError) as e:print('1st attempt (connection dropped):',str(e)[:110])
a=repair_from_physionet('miiv',root,'dr','pw',base=base)
print('2nd attempt actions:',[(x['table'],x['bytes']) for x in a])
print('after:',[(r['table'],r['status']) for r in table_sizes('miiv',root) if r['status']!='ok'] or 'all ok')
print('quarantined:',sorted(str(p.relative_to(root)) for p in (root/'_quarantined_demo_files').rglob('*.gz')))
print('sha verified:',hashlib.sha256((root/'icu/icustays.csv.gz').read_bytes()).hexdigest()==files['icu/icustays'])
try:repair_from_physionet('miiv',root,'dr','WRONG',stems=['icu/icustays'],base=base)
except Exception as e:print('wrong password ->',type(e).__name__,str(e)[:40])
(srv/'icu/icustays.csv.gz').write_bytes(b'corrupt'*400000)
try:repair_from_physionet('miiv',root,'dr','pw',stems=['icu/icustays'],base=base)
except ValueError as e:print('corrupted download ->',str(e)[:80])
