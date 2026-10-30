"""Stage-2 models (protocol 10c.2 item 14): column-subset flat OSTA and the two-channel model.

SubsetFlatOSTA : the flat OSTA backbone over a subset of the predictor columns (physiology path only, practice path only,
                 physiology without the host block), used for the single-path probes.
TwoChannelOSTA : two flat OSTA cores, one over the physiology columns and one over the practice columns, each read at the
                 input of its own prediction head (the stay representation); the two representations are concatenated and
                 a linear head gives the sepsis logit. The cores' own logits are unused. `practice_zero=True` at inference
                 zeroes the practice input (the training mean in normalised space): the "practice path zeroed" row.
The input split comes from v12_manifest; re-standardisation and concept grouping of the practice path are data
transforms applied to the store (v12_train), not model changes.
"""
import torch
from torch import nn
from v11_models import osta_core
from v12_manifest import manifest,path_indices

class _Core(nn.Module):
    """A flat OSTA core over selected columns that exposes its stay representation."""
    def __init__(self,features,indices,small,dropout):
        super().__init__();self.indices=list(indices);self.core=osta_core([features[i] for i in self.indices],small,dropout,flat=True);self._global=None
        self.core.prediction_head[0].register_forward_hook(lambda m,i,o:setattr(self,'_global',i[0]))
        self.width=32 if small else 128
    def forward(self,x,mask,hours):
        out=self.core(x[:,:,self.indices],mask,hours);return out['logits'],self._global

class SubsetFlatOSTA(nn.Module):
    def __init__(self,features,indices,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None;self.sub=_Core(features,indices,small,dropout)
    def forward(self,x,mask,hours,guidance=None):
        logits,_=self.sub(x,mask,hours);return logits

class TwoChannelOSTA(nn.Module):
    def __init__(self,features,small=False,dropout=.1,host=True,manifest_df=None):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        m=manifest(features) if manifest_df is None else manifest_df
        self.phys_idx=path_indices(features,'physiology',m,exclude_blocks=() if host else ('host',));self.prac_idx=path_indices(features,'practice',m)
        if not self.phys_idx or not self.prac_idx:raise ValueError('Two-channel model needs both paths non-empty')
        self.physiology=_Core(features,self.phys_idx,small,dropout);self.practice=_Core(features,self.prac_idx,small,dropout)
        self.head=nn.Sequential(nn.LayerNorm(self.physiology.width+self.practice.width),nn.Dropout(dropout),nn.Linear(self.physiology.width+self.practice.width,1))
        self.practice_zero=False
    def forward(self,x,mask,hours,guidance=None):
        xp=x
        if self.practice_zero:
            xp=x.clone();xp[:,:,self.prac_idx]=0.
        _,g1=self.physiology(x,mask,hours);_,g2=self.practice(xp,mask,hours)
        return self.head(torch.cat((g1,g2),dim=-1)).squeeze(-1)

def make_stage2_model(arm,features,cfg,manifest_df=None):
    small=cfg['small_model'];dropout=cfg['dropout'];m=manifest(features) if manifest_df is None else manifest_df
    if arm=='two_channel':return TwoChannelOSTA(features,small,dropout,host=True,manifest_df=m)
    if arm=='two_channel_nohost':return TwoChannelOSTA(features,small,dropout,host=False,manifest_df=m)
    if arm=='physiology_path':return SubsetFlatOSTA(features,path_indices(features,'physiology',m),small,dropout)
    if arm=='physiology_path_nohost':return SubsetFlatOSTA(features,path_indices(features,'physiology',m,exclude_blocks=('host',)),small,dropout)
    if arm=='practice_path':return SubsetFlatOSTA(features,path_indices(features,'practice',m),small,dropout)
    raise ValueError('Unknown stage-2 arm: '+arm)

STAGE2_ARMS=['two_channel','two_channel_nohost','physiology_path','physiology_path_nohost','practice_path']
