"""V11 architectures. Every model is causal by construction (past-hour outputs cannot change when
only future inputs change; verified by v11_tests) and exposes the same interface as v9_models:
forward(x, mask, hours, guidance=None) -> hourly logits; attributes arm, last_core_output, last_gates.

Arms
- flat_osta         OSTA transformer with ALL features in one group: the organ-structure ablation.
- grud              GRU with learned input/hidden decay from the age channels (Che et al. 2018 style).
- tcn               causal dilated temporal convolution network (Moor et al. style).
- cnn_osta          per-channel causal CNN encoder over [value, observed, age] -> OSTA (supervised).
- ssl_cnn_osta      the same encoder pretrained without labels (v11_train.pretrain) -> OSTA.
- ssl_cnn_flat      the pretrained encoder -> flat (single-group) head: the decisive SSL comparison.
- event_osta        attention over fresh observations of the fast channels (hourly proxy) -> OSTA.
- hazard_ssl_cnn_osta  pretrained encoder -> OSTA -> discrete-time hazard head (1/3/6/12/24 h);
                       the reported 6 h logit is logit(1 - S(6 h)).
"""
import math
import contextlib
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
import v9_osta_base as original_osta
from v9_models import LOOKUP,organ_mapping,base_name,ExperimentModel
from v9_train import AGE_SCALE

FAST=['HR','MAP','SBP','DBP','Resp','O2Sat','Temp']
HAZARD_EDGES=[0.,1.,3.,6.,12.,24.]   # hours; bins (0,1],(1,3],(3,6],(6,12],(12,24]

def measured_channels(features):
    """Features that carry both an observed mask and an age channel (the measured channels)."""
    s=set(features)
    return [f for f in features if f+'_observed' in s and f+'_age' in s]

@contextlib.contextmanager
def flat_mapping():
    """Temporarily make every feature belong to one group so OSTA builds a single organ encoder."""
    old=original_osta.build_feature_to_organ_mapping
    def one(names):
        return {f:'all' for f in names},{'all':list(range(len(names)))}
    original_osta.build_feature_to_organ_mapping=one
    try:yield
    finally:original_osta.build_feature_to_organ_mapping=old

def osta_core(features,small,dropout,flat=False):
    kw=dict(d_organ=16 if small else 32,d_global=32 if small else 128,n_heads_organ=4,n_heads_inter=4,
            n_layers_organ=1 if small else 2,n_layers_global=1 if small else 2,dropout=dropout,mc_samples=1)
    if flat:
        with flat_mapping():return original_osta.OSTATransformer(list(features),**kw)
    return original_osta.OSTATransformer(list(features),**kw)

class CausalConv(nn.Module):
    """Left-padded 1D convolution: output at t depends on inputs <= t only."""
    def __init__(self,cin,cout,kernel,groups=1,dilation=1):
        super().__init__();self.pad=(kernel-1)*dilation;self.conv=nn.Conv1d(cin,cout,kernel,groups=groups,dilation=dilation)
    def forward(self,z):return self.conv(F.pad(z,(self.pad,0)))

class MultiChannelCausalEncoder(nn.Module):
    """Per-channel depthwise causal CNN over [value, observed, age] for every measured channel.
    Channels never mix (groups=K), so each latent stays attributable to its source channel and can be
    mapped to that channel's organ group. Dilations 1,2,4 give a receptive field of 15 h with kernel 3.
    Output: (B,T,K*depth) latents, tanh-bounded and gated (gate starts at 0.5)."""
    def __init__(self,features,channels,depth=2,hidden=8,kernel=3,dilations=(1,2,4),dropout=.1):
        super().__init__()
        self.channels=list(channels);self.depth=depth;k=len(self.channels)
        self.values=[features.index(f) for f in self.channels]
        self.observed=[features.index(f+'_observed') for f in self.channels]
        self.ages=[features.index(f+'_age') for f in self.channels]
        self.inp=CausalConv(k*3,k*hidden,kernel,groups=k)
        self.blocks=nn.ModuleList([CausalConv(k*hidden,k*hidden,kernel,groups=k,dilation=d) for d in dilations])
        self.out=CausalConv(k*hidden,k*depth,1,groups=k)
        self.dropout=nn.Dropout(dropout);self.gate=nn.Parameter(torch.zeros(k*depth))
        self.latent_names=[f'V11_CNN_{f}_{j}' for f in self.channels for j in range(depth)]
        for f in self.channels:
            for j in range(depth):LOOKUP[f'V11_CNN_{f}_{j}']=LOOKUP[base_name(f)]
    def forward(self,x):
        b,t,_=x.shape
        v=torch.stack((x[:,:,self.values],x[:,:,self.observed],x[:,:,self.ages]),dim=-1).reshape(b,t,-1).transpose(1,2)
        h=F.gelu(self.inp(v))
        for blk in self.blocks:h=h+F.gelu(blk(h))
        z=self.out(h).transpose(1,2)
        return self.dropout(torch.tanh(z)*torch.sigmoid(self.gate).view(1,1,-1))

class EncoderOSTA(nn.Module):
    """[features, encoder latents] -> OSTA (organ-grouped) or flat head."""
    def __init__(self,features,small=False,dropout=.1,depth=2,flat=False,hazard=False):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None;self.last_hazards=None
        self.encoder=MultiChannelCausalEncoder(features,measured_channels(features),depth=depth,dropout=dropout)
        self.core=osta_core(list(features)+self.encoder.latent_names,small,dropout,flat=flat)
        self.hazard=nn.Linear(32 if small else 128,len(HAZARD_EDGES)-1) if hazard else None
        self._global=None
        if hazard:
            self.core.prediction_head[0].register_forward_hook(lambda m,i,o:setattr(self,'_global',i[0]))
    def forward(self,x,mask,hours,guidance=None):
        out=self.core(torch.cat((x,self.encoder(x)),dim=-1),mask,hours);self.last_core_output=out
        if self.hazard is None:return out['logits']
        # Discrete-time hazards per bin; P(onset <= 6 h) = 1 - prod_{bins within 6 h}(1 - h_k).
        hz=torch.sigmoid(self.hazard(self._global)).clamp(1e-6,1-1e-6);self.last_hazards=hz
        within=[i for i,e in enumerate(HAZARD_EDGES[1:]) if e<=6.]
        p=1-torch.prod(1-hz[:,:,within],dim=-1)
        return torch.log(p)-torch.log1p(-p)

class FlatOSTA(nn.Module):
    def __init__(self,features,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        self.core=osta_core(features,small,dropout,flat=True)
    def forward(self,x,mask,hours,guidance=None):
        out=self.core(x,mask,hours);self.last_core_output=out;return out['logits']

HEAD_SOFA=['SOFA_Resp','SOFAproxy_Coag','SOFAproxy_Liver','SOFA_CV','SOFAproxy_CNS','SOFA_Renal']   # the six SOFA organs, in SOFA order
HEAD_NAMES=['respiration','coagulation','liver','cardiovascular','cns','renal','any_organ']
HEAD_HORIZONS=(6,12,24)

class FlatOSTAHeads(nn.Module):
    """Stage 1b (protocol 10b): the flat backbone (one group, unrestricted attention over all predictors)
    with seven organ heads at the OUTPUT. Each head is a linear readout on the shared stay representation
    (the input of the prediction head) and predicts whether that organ's SOFA component rises within 6, 12
    and 24 h (the any_organ head: any component). The heads never feed back into the sepsis logits. The
    head losses and the sepsis loss are combined by learned uncertainty weighting (Kendall et al. 2018):
    one log-variance per task, so no auxiliary weight is chosen by hand."""
    def __init__(self,features,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None;self.last_head_logits=None;self._global=None
        self.core=osta_core(features,small,dropout,flat=True)
        self.sofa=[features.index(f) for f in HEAD_SOFA if f in features];self.sofa_obs=[features.index(f+'_observed') for f in HEAD_SOFA if f in features]
        self.sofa_names=[n for f,n in zip(HEAD_SOFA,HEAD_NAMES[:6]) if f in features]
        self.n_heads=len(self.sofa)+1;d=32 if small else 128
        self.heads=nn.Linear(d,self.n_heads*len(HEAD_HORIZONS))
        self.log_var=nn.Parameter(torch.zeros(1+self.n_heads))   # task 0 = sepsis, then one per head
        self.core.prediction_head[0].register_forward_hook(lambda m,i,o:setattr(self,'_global',i[0]))
    @property
    def head_names(self):return self.sofa_names+['any_organ']
    def task_weights(self):
        """exp(-log_var) per task: the learned relative weight of each loss (reported, never set by hand)."""
        return torch.exp(-self.log_var).detach().cpu().numpy().tolist()
    def forward(self,x,mask,hours,guidance=None):
        out=self.core(x,mask,hours);self.last_core_output=out
        b,t,_=x.shape
        self.last_head_logits=self.heads(self._global).reshape(b,t,self.n_heads,len(HEAD_HORIZONS))
        return out['logits']

class GRUD(nn.Module):
    """GRU with learned decays. Input decay: each measured channel's carried value is pulled toward
    0 (the training mean after z-scoring) by exp(-relu(w)*age) when not freshly observed. Hidden
    decay: the state is damped by exp(-relu(v)*mean age) before each step. Strictly causal."""
    def __init__(self,features,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        ch=measured_channels(features);self.values=[features.index(f) for f in ch]
        self.observed=[features.index(f+'_observed') for f in ch];self.ages=[features.index(f+'_age') for f in ch]
        self.w=nn.Parameter(torch.zeros(len(ch)));self.v=nn.Parameter(torch.zeros(1))
        hidden=32 if small else 128
        self.proj=nn.Linear(len(features),hidden);self.gru=nn.GRU(hidden,hidden,batch_first=True)
        self.head=nn.Sequential(nn.LayerNorm(hidden),nn.Dropout(dropout),nn.Linear(hidden,hidden//2),nn.GELU(),nn.Linear(hidden//2,1))
    def forward(self,x,mask,hours,guidance=None):
        age=x[:,:,self.ages].clamp_min(0);fresh=(x[:,:,self.observed]>.5)&(age*AGE_SCALE<1)
        decay=torch.exp(-F.relu(self.w)*age);vals=x[:,:,self.values]
        x=x.clone();x[:,:,self.values]=torch.where(fresh,vals,vals*decay)
        z=F.gelu(self.proj(x));b,t,_=z.shape
        h=torch.zeros(b,z.size(-1),device=x.device);outs=[]
        mean_age=age.mean(-1,keepdim=True)
        for i in range(t):
            h=h*torch.exp(-F.relu(self.v)*mean_age[:,i]).expand_as(h)
            h=self.gru(z[:,i:i+1],h.unsqueeze(0))[1][0];outs.append(h)
        return self.head(torch.stack(outs,1)).squeeze(-1)

class TCNBlock(nn.Module):
    def __init__(self,c,dilation,dropout):
        super().__init__();self.conv=CausalConv(c,c,3,dilation=dilation);self.norm=nn.LayerNorm(c);self.dropout=nn.Dropout(dropout)
    def forward(self,z):
        h=self.conv(z).transpose(1,2);h=self.dropout(F.gelu(self.norm(h))).transpose(1,2);return z+h

class CausalTCN(nn.Module):
    def __init__(self,features,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        width=32 if small else 96
        self.project=nn.Conv1d(len(features),width,1)
        self.blocks=nn.Sequential(*(TCNBlock(width,d,dropout) for d in (1,2,4,8,16)))
        self.head=nn.Sequential(nn.LayerNorm(width),nn.Linear(width,width//2),nn.GELU(),nn.Linear(width//2,1))
    def forward(self,x,mask,hours,guidance=None):
        h=self.blocks(self.project(x.transpose(1,2))).transpose(1,2);return self.head(h).squeeze(-1)

class HourlyEventOSTA(nn.Module):
    """Attention from each hour to the FRESH observations of the fast channels within a causal lookback
    (hourly proxy of an observation-event model; keys exist only where a channel was measured)."""
    def __init__(self,features,small=False,dropout=.1,lookback=24):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        self.fast=[f for f in FAST if f in features and f+'_observed' in features and f+'_age' in features]
        self.value=[features.index(f) for f in self.fast];self.observed=[features.index(f+'_observed') for f in self.fast]
        self.age=[features.index(f+'_age') for f in self.fast];self.lookback=lookback
        self.dim=8 if small else 16;self.heads=2 if small else 4
        self.variable=nn.Embedding(len(self.fast),self.dim);self.event=nn.Linear(2,self.dim)
        self.query=nn.Sequential(nn.Linear(2,self.dim),nn.LayerNorm(self.dim))
        self.attn=nn.MultiheadAttention(self.dim,self.heads,batch_first=True,dropout=dropout)
        self.sentinel=nn.Parameter(torch.zeros(1,1,self.dim))
        self.latents=[f'V11_EVENT_{j}' for j in range(self.dim)]
        for c in self.latents:LOOKUP[c]='temporal_events'
        self.core=osta_core(list(features)+self.latents,small,dropout)
    def forward(self,x,mask,hours,guidance=None):
        b,t,_=x.shape;k=len(self.fast)
        fresh=(x[:,:,self.observed]>.5)&(x[:,:,self.age]*AGE_SCALE<1)&(mask.unsqueeze(-1)>.5)
        vals=x[:,:,self.value]
        etime=hours.unsqueeze(-1).expand(-1,-1,k).reshape(b,t*k);value=vals.reshape(b,t*k)
        var=torch.arange(k,device=x.device).view(1,1,k).expand(b,t,k).reshape(b,t*k)
        emb=self.event(torch.stack([value,etime/120.],-1))+self.variable(var)
        emb=torch.cat([self.sentinel.expand(b,-1,-1),emb],1)
        queries=self.query(torch.stack([hours/120.,(hours/120.)**2],-1))
        lag=hours.unsqueeze(-1)-etime.unsqueeze(1)
        allow=(lag>=0)&(lag<self.lookback)&fresh.reshape(b,t*k)[:,None,:]
        allowed=torch.cat([torch.ones((b,t,1),device=x.device,dtype=torch.bool),allow],-1)
        disallow=(~allowed).repeat_interleave(self.heads,dim=0)
        ctx,_=self.attn(queries,emb,emb,attn_mask=disallow,need_weights=False)
        out=self.core(torch.cat([x,ctx*mask.unsqueeze(-1)],-1),mask,hours);self.last_core_output=out
        return out['logits']

class Pretrainer(nn.Module):
    """Self-supervised heads on the encoder latents (no sepsis labels anywhere):
    forecast: next fresh value of each measured channel;   measured: channel measured within 6 h;
    organ: the 6 SOFA components at +6/+12/+24 h;          worsening: any SOFA component rises within 6/12/24 h."""
    SOFA=['SOFA_Resp','SOFA_CV','SOFA_Renal','SOFAproxy_Coag','SOFAproxy_Liver','SOFAproxy_CNS']
    def __init__(self,features,depth=2,dropout=.1):
        super().__init__()
        self.encoder=MultiChannelCausalEncoder(features,measured_channels(features),depth=depth,dropout=dropout)
        k=len(self.encoder.channels);self.k=k;d=k*depth
        self.forecast=nn.Linear(depth,1);self.measured=nn.Linear(depth,1)
        self.sofa=[features.index(f) for f in self.SOFA if f in features];self.sofa_obs=[features.index(f+'_observed') for f in self.SOFA if f in features]
        self.organ=nn.Sequential(nn.Linear(d,64),nn.GELU(),nn.Linear(64,len(self.sofa)*3))
        self.worsen=nn.Sequential(nn.Linear(d,32),nn.GELU(),nn.Linear(32,3))
    def forward(self,x):
        z=self.encoder(x);b,t,_=z.shape
        per=z.reshape(b,t,self.k,self.encoder.depth)
        return {'latent':z,'forecast':self.forecast(per).squeeze(-1),'measured':self.measured(per).squeeze(-1),
                'organ':self.organ(z).reshape(b,t,len(self.sofa),3),'worsen':self.worsen(z)}

def make_model(arm,features,cfg):
    small=cfg['small_model'];dropout=cfg['dropout']
    if arm in ['osta','output_fusion','cnn']:raise ValueError('v9 arms are built by v9_models.ExperimentModel')
    if arm=='flat_osta':return FlatOSTA(features,small,dropout)
    if arm=='flat_osta_heads':return FlatOSTAHeads(features,small,dropout)
    if arm=='grud':return GRUD(features,small,dropout)
    if arm=='tcn':return CausalTCN(features,small,dropout)
    if arm=='event_osta':return HourlyEventOSTA(features,small,dropout,cfg.get('event_lookback',24))
    if arm in ['cnn_osta','ssl_cnn_osta','ssl_cnn_osta_pooled']:return EncoderOSTA(features,small,dropout,cfg.get('cnn_depth',2))
    if arm in ['ssl_cnn_flat','ssl_cnn_flat_pooled']:return EncoderOSTA(features,small,dropout,cfg.get('cnn_depth',2),flat=True)
    if arm in ['hazard_ssl_cnn_osta']:return EncoderOSTA(features,small,dropout,cfg.get('cnn_depth',2),hazard=True)
    raise ValueError('Unknown v11 arm: '+arm)

SSL_ARMS={'ssl_cnn_osta':'site','ssl_cnn_flat':'site','hazard_ssl_cnn_osta':'site','ssl_cnn_osta_pooled':'pooled','ssl_cnn_flat_pooled':'pooled'}
