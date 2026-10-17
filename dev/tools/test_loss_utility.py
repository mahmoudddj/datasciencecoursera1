import sys,ast,os,types;sys.path.insert(0,'/home/user/datasciencecoursera1/dev/work/mods')
import torch,torch.nn.functional as F,numpy as np,pandas as pd
# (a) loss: extract the ORIGINAL osta_loss source without importing the training script
src=open('/home/user/datasciencecoursera1/dev/work/mods/legacy_osta_original.py').read()
tree=ast.parse(src);fn=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='osta_loss'][0]
ns={'torch':torch,'F':F,'os':os};exec(compile(ast.Module([fn],[]),'osta_loss','exec'),ns);orig=ns['osta_loss']
from v9_train import osta_original_loss
g=torch.Generator().manual_seed(0);worst=0.
for trial in range(20):
    B,T,K=5,30,7
    logits=torch.randn(B,T,generator=g)*2;targets=torch.zeros(B,T)
    for b in range(B):
        if b%2==0:
            s=int(torch.randint(5,25,(1,),generator=g));targets[b,s:]=1   # step label like PhysioNet / our 6-h window + post
    masks=(torch.rand(B,T,generator=g)>.2).float();masks[:,:3]=1
    organ={f'o{k}':torch.randn(B,T,generator=g) for k in range(K)};w=torch.softmax(torch.randn(K,generator=g),0)
    out={'logits':logits,'organ_risks':organ,'organ_risk_weights':w}
    a=orig(out,targets,masks).item();b_=osta_original_loss(out,targets,masks).item();worst=max(worst,abs(a-b_))
print('loss: max |original - ported| over 20 random batches =',worst);assert worst<1e-5
# gradient flows through organ weights and logits
logits.requires_grad_(True);w2=torch.softmax(torch.randn(K,generator=g),0).requires_grad_(True)
l=osta_original_loss({'logits':logits,'organ_risks':organ,'organ_risk_weights':w2},targets,masks);l.backward()
assert logits.grad is not None and w2.grad is not None;print('loss: gradients ok')
# (b) utility: per-stay helper == existing normalized_utility (hourly rule, persistence 1)
from v10_evaluation import patient_utilities,normalized_from,normalized_utility,step_labels,utility_threshold_sweep,utility_ci
rng=np.random.default_rng(1);frames=[];rows=[]
for i in range(60):
    n=int(rng.integers(8,40));h=np.arange(1,n+1,dtype=float);onset=float(rng.integers(7,n+8)) if i%3 else np.nan
    risk=rng.random(n);pid=f'p{i}'
    frames.append(pd.DataFrame({'Hour':h,'StepLabel':step_labels(h,onset),'risk':risk}))
    rows.append(pd.DataFrame({'Patient_ID':pid,'Group_ID':pid,'Hour':h,'OnsetHour':onset,'risk':risk}))
full=pd.concat(rows,ignore_index=True)
for thr in [.2,.5,.8]:
    a=normalized_utility(frames,thr,{'persistence':1,'min_rise':-1e9})['normalized_utility'];b_=normalized_from(patient_utilities(full,thr))
    print(f'utility thr={thr}: existing={a:.6f} new={b_:.6f}');assert abs(a-b_)<1e-9
thr,sweep=utility_threshold_sweep(full,np.linspace(.05,.95,19));print('sweep chosen',thr,'| rows',len(sweep));ci=utility_ci(patient_utilities(full,thr),50);print('ci',ci)
print('ALL LOSS/UTILITY TESTS PASS')
