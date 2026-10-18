"""Corrected supplied architectures and matched frozen-observer integration arms."""
import math
import torch
from torch import nn
import torch.nn.functional as F
import v9_osta_base as original_osta
import v9_cnn_base as original_cnn

ORGAN_FEATURES={
 'respiratory':['O2Sat','Resp','FiO2','PaO2','PaCO2','pH','MetHb','SaO2','EtCO2','Intubated','IntubatedHours'],
 'cardiovascular':['HR','MAP','SBP','DBP','Lactate','ShockIndex','TroponinT','TroponinI','CK','CKMB','VasopressorRecorded','InotropeRecorded'],
 'hepatic':['Bilirubin_total','Bilirubin_direct','AST','ALT','Alkalinephos','Albumin'],
 'hematologic':['Platelets','INR','PTT','Fibrinogen','Hgb','Hct','MCH','MCHC','MCV'],
 'renal':['Creatinine','BUN','UrineOutput','UrineOutput_6h','UrineOutput_24h','UrineCoverage_6h','UrineCoverage_24h','Urine_mlkg_h_6h','Oliguria6h',
          'UrineCoverageFraction_6h','Urine_HoursSinceLast'],
 'inflammatory':['Temp','WBC','CRP','Bands','Neutrophils','Lymphocytes','SIRS_Count','SIRS_ObservedComponents','SIRS_Temp','SIRS_HR','SIRS_Resp','SIRS_WBC'],
 'neurologic':['GCS','GCS_Below15'],
 'metabolic':['BaseExcess','HCO3','Glucose','Sodium','Potassium','Chloride','Calcium','CalciumIonized','Magnesium','Phosphate'],
 'demographic':['Age','Gender','Weight','PostoperativeAdmission'],
 # Chronic background (documented from its own time); a separate group for interpretability.
 'comorbidity':['Comorbidity_chronic_heart_failure','Comorbidity_chronic_liver_disease_cirrhosis','Comorbidity_diabetes',
   'Comorbidity_metastatic_carcinoma','Comorbidity_hematological_malignancy','Comorbidity_immunocompromised',
   'Comorbidity_chronic_organ_insufficiency']}
# v10.4 additions.
for g,fs in {'inflammatory':['Procalcitonin','Ferritin'],'hematologic':['DDimer','RDW'],'hepatic':['Lipase'],
             'metabolic':['LDH','AnionGap'],'cardiovascular':['BNP','NTproBNP','CVP','FluidIn_6h','FluidIn_24h','Transfusion_24h'],
             'respiratory':['PEEP','PF_Ratio','SF_Ratio']}.items():ORGAN_FEATURES[g]+=fs
ORGAN_FEATURES['admission']=['HospitalHoursBeforeICU','AdmitSource_ED','AdmitSource_OR','AdmitSource_Ward','AdmitSource_OtherHospital',
  'ICUType_Medical','ICUType_Surgical','ICUType_Cardiac','ICUType_Neuro','AdmitDx_Infection','AdmitDx_Operative']
_dev=['Device_'+k for k in ['CentralLine','ArterialLine','DialysisCatheter','UrinaryCatheter','Drain']]
ORGAN_FEATURES['infection_risk']=_dev+[d+'_Hours' for d in _dev]
ORGAN_FEATURES['treatment']=['Med_'+k+'_24h' for k in ['Immunosuppressant','Chemotherapy','Corticosteroid','Hydrocortisone',
  'BetaBlocker','Antipyretic','Sedative','Opioid','Diuretic']]+['Imaging_24h']
# v10.5 additions.
for g,fs in {'respiratory':['O2_HighFlow','O2_NIV','O2Flow','TidalVolume','MinuteVentilation','PeakPressure','PlateauPressure','SupplementalO2','Procedure_Bronchoscopy_24h'],
             'neurologic':['RASS','Delirium'],'cardiovascular':['Rhythm_AF','NetBalance_24h','VasopressorDose_NEeq'],
             'demographic':['Height','BMI'],'inflammatory':['UrineWBC','Monocytes','Eosinophils','ESR','NLR'],'hepatic':['Ammonia','Amylase'],
             'renal':['AKI_Stage','Procedure_RRT_24h'],'admission':['ICULOS','PriorAdmissions_1y','DaysSinceLastDischarge','PriorICUStays_SameAdmission',
             'AdmitFrom_NursingFacility','PriorPositiveCulture_1y'],'infection_risk':['StoolRecords_24h','Nutrition_TPN_24h','Nutrition_Enteral_24h'],
             'treatment':['Med_PPI_24h','Med_Insulin_24h','Med_Anticoagulant_24h','LabResults_24h']}.items():ORGAN_FEATURES[g]+=fs
for g,fs in {'hematologic':['RBC'],'inflammatory':['Basophils'],'cardiovascular':['CapRefill_Abnormal','Skin_Abnormal'],'admission':['PriorAntibiotics_90d']}.items():ORGAN_FEATURES[g]+=fs
for g,fs in {'neurologic':['PainScore'],'cardiovascular':['PAmean','CardiacOutput','ScvO2'],'inflammatory':['UrineNitrite','UrineLeukEsterase'],
             'infection_risk':['DrainOutput_24h'],'comorbidity':['Comorbidity_'+k for k in ['chronic_pulmonary_disease','chronic_kidney_disease',
             'dementia','alcohol_use_disorder','malnutrition','obesity','prior_sepsis','stroke_hemiplegia','pressure_ulcer','solid_tumor']]}.items():ORGAN_FEATURES[g]+=fs
_base={f:g for g,fs in ORGAN_FEATURES.items() for f in fs}
for _l in ['Lactate','Creatinine','Platelets','WBC','Bilirubin_total','BUN','CRP','Procalcitonin','pH','HCO3','Hgb','Albumin']:
    for _s in ['_DeltaPrev','_DeltaBaseline']:ORGAN_FEATURES[_base[_l]].append(_l+_s)
LOOKUP={f:g for g,fs in ORGAN_FEATURES.items() for f in fs}
from v10_features import GROUPS
LOOKUP.update(GROUPS)
EVIDENCE={
 'respiratory':['O2Sat','Resp','FiO2','PaO2','PaCO2','pH'],
 'cardiovascular':['HR','MAP','SBP','DBP','Lactate','VasopressorRecorded','InotropeRecorded'],
 'hepatic':['Bilirubin_total','Bilirubin_direct','AST','ALT'],
 'hematologic':['Platelets','INR','PTT','Hgb'],
 'renal':['Creatinine','BUN','UrineOutput','UrineOutput_6h'],
 'inflammatory':['Temp','WBC','CRP','Bands'],
 'neurologic':['GCS']}

def base_name(name):
    for suffix in ['_observed','_age']:
        if name.endswith(suffix):return name[:-len(suffix)]
    return name

def organ_mapping(names):
    mapping={};indices={}
    for i,f in enumerate(names):
        group='observer_evidence' if f.startswith('Observer_') else LOOKUP.get(base_name(f))
        if group is None:raise ValueError('Unmapped canonical feature: '+f)
        mapping[f]=group;indices.setdefault(group,[]).append(i)
    return mapping,indices

original_osta.build_feature_to_organ_mapping=organ_mapping

class ChannelLayerNorm(nn.Module):
    """Normalize channels independently at each time, never across future timesteps."""
    def __init__(self,channels):super().__init__();self.norm=nn.LayerNorm(channels)
    def forward(self,x):return self.norm(x.transpose(1,2)).transpose(1,2)

def replace_sequence_batchnorm(module):
    for name,child in list(module.named_children()):
        if isinstance(child,nn.BatchNorm1d):setattr(module,name,ChannelLayerNorm(child.num_features))
        else:replace_sequence_batchnorm(child)

class ObserverBank(nn.Module):
    """Narrow feature-group MLP observers; trained on an independent development subset.
    Outputs are sepsis-risk summaries, not externally certified organ experts.
    """
    def __init__(self,features,hidden=32):
        super().__init__();self.features=features;mapping,_=organ_mapping(features)
        self.names=[g for g in EVIDENCE if any(f in features for f in EVIDENCE[g])]
        self.indices={g:[i for i,f in enumerate(features) if mapping[f]==g] for g in self.names}
        self.mask_indices={g:[features.index(f+'_observed') for f in EVIDENCE[g] if f+'_observed' in features] for g in self.names}
        self.networks=nn.ModuleDict({g:nn.Sequential(nn.Linear(len(self.indices[g]),hidden),nn.GELU(),nn.Linear(hidden,1)) for g in self.names})

    def forward(self,x):
        logits=[];active=[];coverage=[]
        for g in self.names:
            observed=x[:,:,self.mask_indices[g]]>.5
            a=observed.any(-1).float();c=observed.float().mean(-1)
            z=self.networks[g](x[:,:,self.indices[g]]).squeeze(-1).clamp(-10,10)
            logits.append(z*a);active.append(a);coverage.append(c)
        return {'logit':torch.stack(logits,-1),'active':torch.stack(active,-1),'coverage':torch.stack(coverage,-1)}

def perturb_guidance(z,condition):
    z={k:v.clone() for k,v in z.items()}
    if condition=='normal':return z
    if condition=='missing_all':
        return {k:torch.zeros_like(v) for k,v in z.items()}
    if condition=='missing_half':
        for k in z:z[k][:,:,::2]=0
    elif condition=='incorrect':z['logit']=-z['logit']
    elif condition=='conflicting':z['logit'][:,:,::2]*=-1
    elif condition in ['stale_6h','delayed_2h']:
        delay=6 if condition=='stale_6h' else 2
        for k,v in z.items():
            z[k]=torch.zeros_like(v)
            if v.size(1)>delay:z[k][:,delay:]=v[:,:-delay]
    else:raise ValueError(condition)
    return z

class GuidedInterOrgan(original_osta.InterOrganAttention):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.bias=None
    def forward(self,x):
        norm=self.norm1(x);bias=None if self.bias is None else self.bias.repeat_interleave(self.cross_attention.num_heads,dim=0)
        a,w=self.cross_attention(norm,norm,norm,attn_mask=bias,need_weights=True)
        x=x+a;x=x+self.ffn(self.norm2(x));return x,w

class ExperimentModel(nn.Module):
    def __init__(self,features,arm,observer_names=(),small=False,dropout=.1):
        super().__init__();self.arm=arm;self.features=features;self.observer_names=list(observer_names)
        self.last_gates=None;self.last_bias=None;self.last_core_output=None
        if arm=='cnn':
            self.core=original_cnn.EnhancedSepsisTransformer(len(features),d_model=32 if small else 128,n_heads=4,num_layers=1 if small else 2,dim_feedforward=64 if small else 256,dropout=dropout,use_cnn=True,use_continuous_time=True)
            replace_sequence_batchnorm(self.core);return
        model_features=features.copy()
        if arm=='observer_features':
            model_features += [f'Observer_{g}_{part}' for part in ['logit','active','coverage'] for g in self.observer_names]
        self.core=original_osta.OSTATransformer(model_features,d_organ=16 if small else 32,d_global=32 if small else 128,n_heads_organ=4,n_heads_inter=4,n_layers_organ=1 if small else 2,n_layers_global=1 if small else 2,dropout=dropout,mc_samples=1)
        if arm=='output_fusion':self.fusion=nn.Linear(len(self.observer_names)*3,1,bias=False)
        if arm in ['gated_attention','ungated_attention']:
            layers=[]
            for old in self.core.inter_organ_layers:
                layer=GuidedInterOrgan(16 if small else 32,4,dropout);layer.load_state_dict(old.state_dict());layers.append(layer)
            self.core.inter_organ_layers=nn.ModuleList(layers)
            self.gates=nn.ModuleDict({g:nn.Sequential(nn.Linear(3,8),nn.GELU(),nn.Linear(8,1)) for g in self.observer_names})
            self.scale=nn.Parameter(torch.tensor(.1))

    def _core(self,*args):
        # The original OSTA loss needs organ_risks and organ_risk_weights; keep the full dict.
        out=self.core(*args);self.last_core_output=out;return out
    def forward(self,x,mask,hours,guidance=None):
        self.last_gates=None;self.last_bias=None;self.last_core_output=None
        if self.arm=='cnn':return self.core(x,mask,hours)
        if self.arm=='osta':return self._core(x,mask,hours)['logits']
        if guidance is None:raise ValueError('Observer integration requires an explicit evidence package.')
        z=guidance;summary=torch.cat([z['logit']*z['active'],z['active'],z['coverage']*z['active']],dim=-1)
        if self.arm=='observer_features':return self._core(torch.cat([x,summary],dim=-1),mask,hours)['logits']
        if self.arm=='output_fusion':return self._core(x,mask,hours)['logits']+self.fusion(summary).squeeze(-1)
        B,T,_=x.shape;K=self.core.n_organs
        priority=torch.zeros((B,T,K),device=x.device,dtype=x.dtype);gates=[]
        for j,g in enumerate(self.observer_names):
            active=z['active'][:,:,j]*mask
            inputs=torch.stack([z['logit'][:,:,j]/10,z['coverage'][:,:,j],active],dim=-1)
            gate=torch.sigmoid(self.gates[g](inputs).squeeze(-1))*active
            if self.arm=='ungated_attention':gate=active
            gates.append(gate)
            if g in self.core.organ_names:
                priority[:,:,self.core.organ_names.index(g)]+=gate*torch.tanh(z['logit'][:,:,j]/3)
        bias=torch.tanh(self.scale)*priority.unsqueeze(-2).expand(B,T,K,K)
        self.last_gates=torch.stack(gates,-1);self.last_bias=bias
        for layer in self.core.inter_organ_layers:layer.bias=bias.reshape(B*T,K,K)
        return self._core(x,mask,hours)['logits']
