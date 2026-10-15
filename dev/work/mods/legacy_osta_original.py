# Cell 0: Imports
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, precision_score, recall_score, fbeta_score, classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight

# ======================================================================

# Cell 1: Load data
import os
csv_path = os.getenv(
    'SEPSIS_DATA_PATH',
    'Dataset_ previous values_gpbyID+NoShift+F.Engv3.0.csv',
)



# ======================================================================

# Cell 2: OSTA-Transformer v5 — v2 architecture preserved exactly
# ============================================================================
# DESIGN PHILOSOPHY:
#   v2 is the best-performing version to date. v3 introduced architectural
#   changes that hurt performance. v4 added a weighted random sampler and LR
#   warmup that hurt performance further (sampler stacked on top of focal
#   loss + α=0.75 + time-weighting caused over-prediction; threshold collapsed
#   to 0.05 floor and one organ absorbed 99% of the weight).
#
#   v5 is v2 verbatim, with TWO zero-impact changes only:
#
#   [LABEL]  Renamed 'neurological' → 'systemic_inflammatory'.
#            Temp/WBC/HCO3 are SIRS criteria, not GCS (which is absent from
#            PhysioNet 2019). Pure relabel — zero performance impact, fixes
#            the clinical narrative for the paper.
#
#   [SAFETY] MC Dropout inference now sets ONLY Dropout layers to train mode
#            instead of self.train(). Functionally identical today (no
#            BatchNorm in the model), but BN-future-proof.
#
#   Everything else — architecture, loss, optimiser, scheduler, sampler,
#   thresholds, hyperparameters — is bit-for-bit identical to v2.
# ============================================================================
# Cell 2: OSTA-Transformer — Complete Standalone Implementation

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
import math
import time
import warnings
import os
import contextlib
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.linear_model import LogisticRegression
from typing import Dict, List, Tuple, Optional

# Alarm post-processing controls (false-positive mitigation)
ALARM_MIN_CONSECUTIVE = int(os.getenv('ALARM_MIN_CONSECUTIVE', '1'))
ALARM_MIN_RISE = float(os.getenv('ALARM_MIN_RISE', '0.0'))


# ============================================================================
# GPU SETUP
# ============================================================================

def setup_colab_environment():
    if torch.cuda.is_available():
        device = torch.device('cuda')
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"GPU: {gpu_name} ({gpu_memory:.1f} GB)")
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.backends.cuda.matmul.allow_tf32 = True
    else:
        device = torch.device('cpu')
        print("No GPU — training will be slow.")
    return device


def clear_gpu_memory():
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def build_loader_kwargs(batch_size, shuffle):
    kwargs = {'batch_size': batch_size, 'shuffle': shuffle}
    if torch.cuda.is_available():
        kwargs.update({
            'num_workers': min(8, os.cpu_count() or 4),
            'pin_memory': True,
            'persistent_workers': True,
            'prefetch_factor': 4,
        })
    return kwargs


# ============================================================================
# ORGAN SYSTEM DEFINITIONS (aligned with SOFA score)
# ============================================================================

ORGAN_SYSTEM_FEATURES = {
    'respiratory': {
        'features': ['O2Sat', 'Resp', 'FiO2', 'PaCO2', 'SaO2', 'EtCO2', 'pH'],
        'sofa_component': 'PaO2/FiO2 ratio',
    },
    'cardiovascular': {
        'features': ['HR', 'MAP', 'SBP', 'DBP', 'Lactate'],
        'sofa_component': 'MAP and vasopressor requirement',
    },
    'hepatic': {
        'features': ['Bilirubin_total', 'Bilirubin_direct', 'AST', 'Alkalinephos', 'BaseExcess'],
        'sofa_component': 'Bilirubin level',
    },
    'coagulation': {
        'features': ['Platelets', 'PTT', 'Fibrinogen'],
        'sofa_component': 'Platelet count',
    },
    'renal': {
        'features': ['Creatinine', 'BUN', 'Calcium', 'Chloride', 'Glucose',
                     'Magnesium', 'Phosphate', 'Potassium'],
        'sofa_component': 'Creatinine / urine output',
    },
    'systemic_inflammatory': {
        'features': ['Temp', 'WBC', 'HCO3'],
        'sofa_component': 'SIRS criteria: fever/hypothermia, leukocytosis, metabolic acidosis',
    },
    'demographic': {
        'features': ['Age', 'Gender', 'HospAdmTime'],
        'sofa_component': None,
    }
}


def build_feature_to_organ_mapping(feature_cols):
    """Map each feature to its organ system. Unmatched features go to 'other'."""
    organ_lookup = {}
    for organ, info in ORGAN_SYSTEM_FEATURES.items():
        for feat in info['features']:
            organ_lookup[feat.lower()] = organ

    feature_to_organ = {}
    organ_to_indices = {organ: [] for organ in ORGAN_SYSTEM_FEATURES}
    organ_to_indices['other'] = []

    for idx, col in enumerate(feature_cols):
        col_lower = col.lower().replace('_', '').replace(' ', '')
        matched = False
        for feat_name, organ in organ_lookup.items():
            feat_lower = feat_name.lower().replace('_', '').replace(' ', '')
            if col_lower == feat_lower or col_lower.startswith(feat_lower):
                feature_to_organ[col] = organ
                organ_to_indices[organ].append(idx)
                matched = True
                break
        if not matched:
            # Check if it's a temporal derivative or rolling stat of a known feature
            base_matched = False
            for feat_name, organ in organ_lookup.items():
                feat_lower = feat_name.lower().replace('_', '')
                if col_lower.startswith(feat_lower):
                    feature_to_organ[col] = organ
                    organ_to_indices[organ].append(idx)
                    base_matched = True
                    break
            if not base_matched:
                # Check for missingness indicators
                if col.endswith('_missing'):
                    base_feat = col.replace('_missing', '').lower().replace('_', '')
                    for feat_name, organ in organ_lookup.items():
                        if base_feat == feat_name.lower().replace('_', ''):
                            feature_to_organ[col] = organ
                            organ_to_indices[organ].append(idx)
                            base_matched = True
                            break
                if not base_matched:
                    feature_to_organ[col] = 'other'
                    organ_to_indices['other'].append(idx)

    organ_to_indices = {k: v for k, v in organ_to_indices.items() if len(v) > 0}
    return feature_to_organ, organ_to_indices


# ============================================================================
# TEMPORAL FEATURE ENGINEERING (from Paper 1)
# ============================================================================

def engineer_temporal_features(df, base_feature_cols):
    print("  Engineering temporal features...")
    df = df.sort_values(['Patient_ID', 'Hour']).copy()
    raw_clinical_vars = [
        'HR', 'O2Sat', 'Temp', 'SBP', 'MAP', 'DBP', 'Resp', 'EtCO2',
        'BaseExcess', 'HCO3', 'FiO2', 'pH', 'PaCO2', 'SaO2', 'AST', 'BUN',
        'Alkalinephos', 'Calcium', 'Chloride', 'Creatinine',
        'Bilirubin_direct', 'Glucose', 'Lactate', 'Magnesium', 'Phosphate',
        'Potassium', 'Bilirubin_total', 'TroponinI', 'Hct', 'Hgb', 'PTT',
        'WBC', 'Fibrinogen', 'Platelets'
    ]
    raw_clinical_vars = [c for c in raw_clinical_vars if c in df.columns]
    vital_signs = [v for v in ['HR', 'SBP', 'DBP', 'MAP', 'Resp', 'O2Sat', 'Temp'] if v in base_feature_cols]
    key_labs = [l for l in ['Lactate', 'WBC', 'Creatinine', 'BUN', 'Platelets', 'Bilirubin_total'] if l in base_feature_cols]
    rolling_vars = vital_signs + key_labs
    new_cols = []
    pid_group = df.groupby('Patient_ID', sort=False)

    for var in rolling_vars:
        if var not in df.columns:
            continue
        col_name = f'{var}_delta'
        df[col_name] = pid_group[var].diff().fillna(0)
        new_cols.append(col_name)

        col_mean = f'{var}_roll6_mean'
        col_std = f'{var}_roll6_std'
        grouped = pid_group[var]
        df[col_mean] = grouped.transform(lambda x: x.rolling(6, min_periods=1).mean())
        df[col_std] = grouped.transform(lambda x: x.rolling(6, min_periods=1).std().fillna(0))
        new_cols.extend([col_mean, col_std])

        if var in vital_signs:
            col_mean12 = f'{var}_roll12_mean'
            df[col_mean12] = grouped.transform(lambda x: x.rolling(12, min_periods=1).mean())
            new_cols.append(col_mean12)

    for var in raw_clinical_vars:
        miss = df[var].isna()
        streak = miss.groupby(df['Patient_ID']).cumsum()
        measured_streak = (~miss).groupby(df['Patient_ID']).cumsum()
        dt_raw = streak - measured_streak.where(miss, 0)
        dt_col = f'{var}_tslm'
        df[dt_col] = np.log1p(np.maximum(dt_raw.values, 0))
        new_cols.append(dt_col)

    for var in ['HR', 'SBP', 'MAP', 'Resp', 'O2Sat', 'Temp']:
        if var not in df.columns:
            continue
        filled = pid_group[var].transform(lambda x: x.ffill().fillna(0))
        for w in [2, 6, 12]:
            alpha = 2.0 / (w + 1.0)
            col = f'{var}_ema{w}'
            df[col] = (
                filled.groupby(df['Patient_ID'])
                .transform(lambda x, a=alpha: x.ewm(alpha=a, adjust=False).mean())
            )
            new_cols.append(col)

    if 'HR' in df.columns and 'SBP' in df.columns:
        df['shock_index'] = df['HR'] / (df['SBP'] + 1e-8)
        new_cols.append('shock_index')
    if 'BUN' in df.columns and 'Creatinine' in df.columns:
        df['BUN_Creatinine_ratio'] = df['BUN'] / (df['Creatinine'] + 1e-8)
        new_cols.append('BUN_Creatinine_ratio')
    if 'SBP' in df.columns and 'DBP' in df.columns:
        df['pulse_pressure'] = df['SBP'] - df['DBP']
        new_cols.append('pulse_pressure')

    for col in new_cols:
        df[col] = df[col].replace([np.inf, -np.inf], 0).fillna(0)

    print(f"  Added {len(new_cols)} temporal features")
    return df, new_cols


def patient_outcomes_within_horizon(df, max_hours=120):
    """Patient-level sepsis outcome using only the first max_hours rows per patient."""
    ordered = df.sort_values(['Patient_ID', 'Hour'])
    truncated = ordered.groupby('Patient_ID', sort=False).head(max_hours)
    return truncated.groupby('Patient_ID')['SepsisLabel'].max()


# ============================================================================
# ENHANCED PREPROCESSOR (missingness + temporal + hours)
# ============================================================================

class EnhancedSepsisPreprocessor:
    def __init__(self, df, feature_cols, max_hours=120, use_missingness=True):
        self.df = df
        self.feature_cols = feature_cols
        self.max_hours = max_hours
        self.use_missingness = use_missingness
        self.feature_means = None
        self.feature_stds = None
        self.miss_cols = []
        if use_missingness:
            raw_candidates = ['HR', 'O2Sat', 'Temp', 'SBP', 'MAP', 'DBP', 'Resp',
                              'EtCO2', 'BaseExcess', 'HCO3', 'FiO2', 'pH',
                              'PaCO2', 'SaO2', 'AST', 'BUN', 'Alkalinephos',
                              'Calcium', 'Chloride', 'Creatinine',
                              'Bilirubin_direct', 'Glucose', 'Lactate',
                              'Magnesium', 'Phosphate', 'Potassium',
                              'Bilirubin_total', 'TroponinI', 'Hct', 'Hgb',
                              'PTT', 'WBC', 'Fibrinogen', 'Platelets']
            self.miss_cols = [c for c in raw_candidates if c in feature_cols]

    def get_total_features(self):
        return len(self.feature_cols) + len(self.miss_cols)

    def get_all_feature_names(self):
        return self.feature_cols + [f'{c}_missing' for c in self.miss_cols]

    def prepare_sequences(self, patient_ids=None):
        if patient_ids is None:
            patient_ids = self.df['Patient_ID'].unique()
        n_features = self.get_total_features()
        sequences, labels, masks, patient_outcomes, pids, hours_list = [], [], [], [], [], []

        print(f"  Pre-grouping {len(self.df)} rows for {len(patient_ids)} patients...")
        t0 = time.time()
        grouped = self.df.groupby('Patient_ID')
        patient_groups = {pid: group.sort_values('Hour') for pid, group in grouped}
        print(f"  Pre-grouping done in {time.time() - t0:.2f}s.")

        for pid in patient_ids:
            if pid not in patient_groups:
                continue
            patient_data = patient_groups[pid]
            X_raw = patient_data[self.feature_cols].values
            y = patient_data['SepsisLabel'].values
            hour_vals = patient_data['Hour'].values

            if self.use_missingness and len(self.miss_cols) > 0:
                miss_idx = [self.feature_cols.index(c) for c in self.miss_cols]
                miss_flags = np.isnan(X_raw[:, miss_idx]).astype(float)
            else:
                miss_flags = np.zeros((len(X_raw), 0))

            X_filled = pd.DataFrame(X_raw, columns=self.feature_cols).ffill().fillna(0).values
            X_combined = np.concatenate([X_filled, miss_flags], axis=1)
            n_hours = min(len(X_combined), self.max_hours)
            patient_outcome = 1 if np.any(y[:n_hours] == 1) else 0

            X_padded = np.zeros((self.max_hours, n_features))
            y_padded = np.zeros(self.max_hours)
            mask = np.zeros(self.max_hours)
            h_padded = np.zeros(self.max_hours)

            X_padded[:n_hours] = X_combined[:n_hours]
            y_padded[:n_hours] = y[:n_hours]
            mask[:n_hours] = 1
            h_padded[:n_hours] = hour_vals[:n_hours]

            sequences.append(X_padded)
            labels.append(y_padded)
            masks.append(mask)
            patient_outcomes.append(patient_outcome)
            pids.append(pid)
            hours_list.append(h_padded)

        return (np.array(sequences), np.array(labels),
                np.array(masks), np.array(patient_outcomes),
                pids, np.array(hours_list))

    def fit_normalization(self, X_train):
        X_flat = X_train.reshape(-1, X_train.shape[2])
        valid_mask = np.abs(X_flat).sum(axis=1) > 0
        X_valid = X_flat[valid_mask]
        X_valid = np.nan_to_num(X_valid, nan=0.0, posinf=0.0, neginf=0.0)
        self.feature_means = np.nan_to_num(np.mean(X_valid, axis=0), nan=0.0)
        self.feature_stds = np.nan_to_num(np.std(X_valid, axis=0), nan=1.0) + 1e-8
        n_base = len(self.feature_cols)
        if self.use_missingness:
            self.feature_means[n_base:] = 0.0
            self.feature_stds[n_base:] = 1.0

    def normalize(self, X):
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        normalized = (X - self.feature_means) / self.feature_stds
        return np.nan_to_num(normalized, nan=0.0, posinf=3.0, neginf=-3.0)


class EnhancedSepsisDataset(Dataset):
    def __init__(self, sequences, labels, masks, patient_outcomes, patient_ids, hours):
        self.sequences = torch.FloatTensor(sequences)
        self.labels = torch.FloatTensor(labels)
        self.masks = torch.FloatTensor(masks)
        self.patient_outcomes = torch.FloatTensor(patient_outcomes)
        self.patient_ids = patient_ids
        self.hours = torch.FloatTensor(hours)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return {
            'x': self.sequences[idx],
            'label': self.labels[idx],
            'mask': self.masks[idx],
            'patient_outcome': self.patient_outcomes[idx],
            'pid': self.patient_ids[idx],
            'hours': self.hours[idx]
        }


# ============================================================================
# CONTINUOUS-TIME POSITIONAL ENCODING (from Paper 1)
# ============================================================================

class ContinuousTimeEncoding(nn.Module):
    def __init__(self, d_model, max_len=200):
        super().__init__()
        self.freq = nn.Parameter(torch.randn(1, 1, d_model // 2) * 0.01)
        self.phase = nn.Parameter(torch.zeros(1, 1, d_model // 2))
        self.linear = nn.Linear(d_model, d_model)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe_fallback', pe)

    def forward(self, x, hours=None):
        if hours is not None:
            t = hours.unsqueeze(-1)
            sin_enc = torch.sin(t * self.freq + self.phase)
            cos_enc = torch.cos(t * self.freq + self.phase)
            time_enc = torch.cat([sin_enc, cos_enc], dim=-1)
            time_enc = self.linear(time_enc)
            return x + time_enc
        else:
            return x + self.pe_fallback[:x.size(1)].unsqueeze(0)


# ============================================================================
# OSTA-TRANSFORMER: ORGAN-SYSTEM-AWARE ARCHITECTURE
# ============================================================================

def _causal_attn_mask(L, device):
    """Causal self-attention mask: True = position may NOT attend (future).
    Applied to organ-temporal and global-temporal encoders so per-timestep
    predictions cannot leak information from later hours."""
    return torch.triu(torch.ones(L, L, dtype=torch.bool, device=device), diagonal=1)


class OrganEncoder(nn.Module):
    """Temporal encoder for a single organ system."""
    def __init__(self, n_features, d_organ, n_heads=4, n_layers=2, dropout=0.15):
        super().__init__()
        self.input_proj = nn.Sequential(
            nn.Linear(n_features, d_organ),
            nn.LayerNorm(d_organ),
            nn.GELU(),
            nn.Dropout(dropout)
        )
        self.pos_encoder = ContinuousTimeEncoding(d_organ)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_organ, nhead=n_heads, dim_feedforward=d_organ * 2,
            dropout=dropout, batch_first=True, norm_first=True
        )
        self.temporal_encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.risk_head = nn.Sequential(
            nn.Linear(d_organ, d_organ // 2), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_organ // 2, 1)
        )

    def forward(self, x, mask=None, hours=None):
        h = self.input_proj(x)
        h = self.pos_encoder(h, hours=hours)
        key_padding_mask = (mask == 0) if mask is not None else None
        organ_repr = self.temporal_encoder(
            h, mask=_causal_attn_mask(h.size(1), h.device),
            src_key_padding_mask=key_padding_mask)
        organ_risk = self.risk_head(organ_repr)
        return organ_repr, organ_risk


class InterOrganAttention(nn.Module):
    """Cross-attention between organ systems at each timestep."""
    def __init__(self, d_organ, n_heads=4, dropout=0.1):
        super().__init__()
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=d_organ, num_heads=n_heads, dropout=dropout, batch_first=True
        )
        self.norm1 = nn.LayerNorm(d_organ)
        self.norm2 = nn.LayerNorm(d_organ)
        self.ffn = nn.Sequential(
            nn.Linear(d_organ, d_organ * 2), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_organ * 2, d_organ), nn.Dropout(dropout)
        )

    def forward(self, organ_reprs):
        normed = self.norm1(organ_reprs)
        attended, attn_weights = self.cross_attention(normed, normed, normed, need_weights=True)
        organ_reprs = organ_reprs + attended
        organ_reprs = organ_reprs + self.ffn(self.norm2(organ_reprs))
        return organ_reprs, attn_weights


class OSTATransformer(nn.Module):
    """Organ-System-Aware Temporal Attention Transformer."""

    def __init__(self, feature_cols, d_organ=64, d_global=256,
                 n_heads_organ=4, n_heads_inter=4,
                 n_layers_organ=2, n_layers_global=2,
                 dropout=0.15, mc_samples=30):
        super().__init__()
        self.mc_samples = mc_samples
        self.feature_cols = feature_cols

        # Build organ mapping
        self.feature_to_organ, self.organ_to_indices = build_feature_to_organ_mapping(feature_cols)
        self.organ_names = list(self.organ_to_indices.keys())
        self.n_organs = len(self.organ_names)

        print(f"\n{'='*60}")
        print(f"OSTA-Transformer Architecture")
        print(f"{'='*60}")
        print(f"Total features: {len(feature_cols)}")
        print(f"Organ systems: {self.n_organs}")
        for organ, indices in self.organ_to_indices.items():
            feat_names = [feature_cols[i] for i in indices]
            print(f"  {organ:20s}: {len(indices):>3} features")
        print(f"{'='*60}\n")

        # 1. Organ-specific encoders
        self.organ_encoders = nn.ModuleDict()
        for organ_name in self.organ_names:
            n_features = len(self.organ_to_indices[organ_name])
            self.organ_encoders[organ_name] = OrganEncoder(
                n_features=n_features, d_organ=d_organ,
                n_heads=n_heads_organ, n_layers=n_layers_organ, dropout=dropout
            )

        # 2. Inter-organ attention
        self.inter_organ_layers = nn.ModuleList([
            InterOrganAttention(d_organ=d_organ, n_heads=n_heads_inter, dropout=dropout)
            for _ in range(n_layers_global)
        ])

        # 3. Global temporal integration
        self.global_proj = nn.Sequential(
            nn.Linear(d_organ * self.n_organs, d_global),
            nn.LayerNorm(d_global), nn.GELU(), nn.Dropout(dropout)
        )
        self.global_pos_encoder = ContinuousTimeEncoding(d_global)
        global_encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_global, nhead=n_heads_inter, dim_feedforward=d_global * 2,
            dropout=dropout, batch_first=True, norm_first=True
        )
        self.global_temporal = nn.TransformerEncoder(global_encoder_layer, num_layers=n_layers_global)

        # 4. Organ risk aggregation
        self.organ_risk_weights = nn.Parameter(torch.ones(self.n_organs) / self.n_organs)

        # 5. Prediction head with MC dropout
        self.prediction_head = nn.Sequential(
            nn.Linear(d_global, d_global // 2), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_global // 2, d_global // 4), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_global // 4, 1)
        )

    def _split_by_organ(self, x):
        return {name: x[:, :, indices] for name, indices in self.organ_to_indices.items()}

    def forward(self, x, mask=None, hours=None, return_interpretability=False):
        B, T, _ = x.shape
        key_padding_mask = (mask == 0) if mask is not None else None

        # 1. Split by organ
        organ_inputs = self._split_by_organ(x)

        # 2. Encode each organ
        organ_representations = {}
        organ_risks = {}
        for organ_name in self.organ_names:
            organ_repr, organ_risk = self.organ_encoders[organ_name](
                organ_inputs[organ_name], mask, hours=hours
            )
            organ_representations[organ_name] = organ_repr
            organ_risks[organ_name] = organ_risk

        # 3. Inter-organ attention (batched over time for efficiency)
        organ_stack = torch.stack(
            [organ_representations[name] for name in self.organ_names], dim=2
        )  # (B, T, n_organs, d_organ)

        # Reshape to process all timesteps at once: (B*T, n_organs, d_organ)
        BT = B * T
        organ_flat = organ_stack.reshape(BT, self.n_organs, -1)
        inter_attn_weights = None
        for layer in self.inter_organ_layers:
            organ_flat, inter_attn_weights = layer(organ_flat)
        organ_stack = organ_flat.reshape(B, T, self.n_organs, -1)

        # 4. Global temporal processing
        organ_concat = organ_stack.reshape(B, T, -1)
        global_repr = self.global_proj(organ_concat)
        global_repr = self.global_pos_encoder(global_repr, hours=hours)
        global_repr = self.global_temporal(
            global_repr, mask=_causal_attn_mask(global_repr.size(1), global_repr.device),
            src_key_padding_mask=key_padding_mask)

        # 5. Final prediction (global pathway)
        logits = self.prediction_head(global_repr).squeeze(-1)

        # 6. Weighted organ risk prediction (organ pathway — always computed)
        risk_weights = F.softmax(self.organ_risk_weights, dim=0)
        organ_risk_stack = torch.stack(
            [organ_risks[name].squeeze(-1) for name in self.organ_names], dim=2
        )  # (B, T, n_organs)
        weighted_organ_logits = (organ_risk_stack * risk_weights.unsqueeze(0).unsqueeze(0)).sum(-1)

        # Combine global + organ pathways (organ pathway provides gradient to weights)
        combined_logits = logits + 0.3 * weighted_organ_logits

        output = {
            'logits': combined_logits,
            'organ_risks': {name: organ_risks[name].squeeze(-1) for name in self.organ_names},
            'organ_risk_weights': risk_weights,  # NOT detached — gradients flow
            'organ_names': self.organ_names,
        }

        if return_interpretability and inter_attn_weights is not None:
            output['inter_organ_attention'] = inter_attn_weights.reshape(B, T, self.n_organs, self.n_organs).detach()

        return output

    def predict_with_uncertainty(self, x, mask=None, hours=None, n_samples=None):
        if n_samples is None:
            n_samples = self.mc_samples
        # Set model to eval, then re-enable ONLY Dropout layers.
        # Functionally identical to self.train() today (no BatchNorm in this
        # model) but BN-future-proof if the architecture is extended.
        self.eval()
        for module in self.modules():
            if isinstance(module, nn.Dropout):
                module.train()
        all_probs = []
        with torch.no_grad():
            for _ in range(n_samples):
                out = self.forward(x, mask, hours=hours, return_interpretability=True)
                probs = torch.sigmoid(out['logits'])
                all_probs.append(probs)
        self.eval()
        all_probs = torch.stack(all_probs, dim=0)
        return {
            'mean_prob': all_probs.mean(dim=0),
            'uncertainty': all_probs.std(dim=0),
            'organ_risks': out['organ_risks'],
            'organ_risk_weights': out['organ_risk_weights'].detach(),
            'organ_names': out['organ_names']
        }


# ============================================================================
# OSTA LOSS FUNCTION (with organ consistency regularisation)
# ============================================================================

def osta_loss(output, targets, masks, organ_consistency_weight=0.1,
              organ_diversity_weight=0.05, early_alpha=0.3, focal_gamma=2.0,
              rank_loss_lambda=None, rank_margin=None):
    if rank_loss_lambda is None:
        rank_loss_lambda = float(os.getenv('OSTA_RANK_LAMBDA', '0.0'))
    if rank_margin is None:
        rank_margin = float(os.getenv('OSTA_RANK_MARGIN', '0.05'))

    logits = output['logits']
    B, T = targets.shape

    # Focal loss
    bce = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
    probs = torch.sigmoid(logits)
    pt = torch.where(targets == 1, probs, 1 - probs)
    focal_weight = (1 - pt) ** focal_gamma
    alpha_t = torch.where(targets == 1,
                          torch.tensor(0.75, device=logits.device),
                          torch.tensor(0.25, device=logits.device))
    focal_loss = alpha_t * focal_weight * bce

    # Time weighting
    time_weights = torch.ones_like(targets)
    for b in range(B):
        sepsis_idx = torch.where(targets[b] == 1)[0]
        if len(sepsis_idx) > 0:
            t_onset = sepsis_idx[0].item()
            for t in range(T):
                if t < t_onset:
                    time_weights[b, t] = torch.exp(torch.tensor(-early_alpha * (t_onset - t)))
                elif t >= t_onset:
                    time_weights[b, t] = 1.5

    main_loss = (focal_loss * time_weights * masks).sum() / (masks.sum() + 1e-8)

    # Organ consistency: each organ risk should track the sepsis label
    if 'organ_risks' in output:
        organ_consistency = torch.tensor(0.0, device=logits.device)
        n_organs = 0
        for organ_name, organ_risk in output['organ_risks'].items():
            organ_bce = F.binary_cross_entropy_with_logits(organ_risk, targets, reduction='none')
            organ_loss = (organ_bce * masks).sum() / (masks.sum() + 1e-8)
            organ_consistency += organ_loss
            n_organs += 1
        if n_organs > 0:
            main_loss += organ_consistency_weight * (organ_consistency / n_organs)

    # Organ weight diversity: penalise uniform weights (encourage differentiation)
    if 'organ_risk_weights' in output:
        weights = output['organ_risk_weights']
        # Negative entropy: maximise entropy = uniform; we want the opposite
        # Use variance of weights as diversity measure (higher = more differentiated)
        weight_variance = weights.var()
        # We want to MAXIMISE variance (differentiation), so SUBTRACT it from loss
        diversity_loss = -torch.log(weight_variance + 1e-8)
        main_loss += organ_diversity_weight * diversity_loss

    # Optional rank-aware patient-level margin loss (discrimination-focused)
    if rank_loss_lambda > 0:
        masked_logits = torch.where(masks > 0, logits, torch.full_like(logits, -1e9))
        patient_scores = torch.sigmoid(masked_logits.max(dim=1).values)
        patient_labels = (targets * masks).max(dim=1).values > 0
        pos_scores = patient_scores[patient_labels]
        neg_scores = patient_scores[~patient_labels]
        if len(pos_scores) > 0 and len(neg_scores) > 0:
            pairwise_margins = rank_margin - (pos_scores[:, None] - neg_scores[None, :])
            rank_loss = F.relu(pairwise_margins).mean()
            main_loss += rank_loss_lambda * rank_loss

    return main_loss


# ============================================================================
# CLINICAL REPORT GENERATOR
# ============================================================================

class ClinicalReportGenerator:
    def __init__(self, model):
        self.model = model

    def generate_patient_report(self, x, mask, hours=None, patient_id="Unknown"):
        self.model.eval()
        device = next(self.model.parameters()).device
        result = self.model.predict_with_uncertainty(
            x.unsqueeze(0).to(device),
            mask.unsqueeze(0).to(device),
            hours=hours.unsqueeze(0).to(device) if hours is not None else None
        )
        valid_len = int(mask.sum().item())

        report = {
            'patient_id': patient_id,
            'valid_hours': valid_len,
            'risk_trajectory': result['mean_prob'][0, :valid_len].cpu().numpy(),
            'uncertainty': result['uncertainty'][0, :valid_len].cpu().numpy(),
            'organ_risks': {},
            'organ_risk_weights': {},
            'deteriorating_organs': [],
            'alerts': [],
        }

        weights = result['organ_risk_weights'].cpu().numpy()
        for i, organ_name in enumerate(result['organ_names']):
            risk = torch.sigmoid(result['organ_risks'][organ_name][0, :valid_len]).cpu().numpy()
            report['organ_risks'][organ_name] = risk
            report['organ_risk_weights'][organ_name] = float(weights[i])

        for organ_name, risk in report['organ_risks'].items():
            if valid_len >= 4:
                recent_trend = np.diff(risk[-4:]).mean()
                if recent_trend > 0.03:
                    report['deteriorating_organs'].append({
                        'organ': organ_name,
                        'trend': float(recent_trend),
                        'current_risk': float(risk[-1])
                    })

        current_risk = report['risk_trajectory'][-1]
        current_uncertainty = report['uncertainty'][-1]

        if current_risk > 0.7 and current_uncertainty < 0.1:
            report['alerts'].append({'level': 'HIGH',
                'message': f'High sepsis risk ({current_risk:.1%}) with high confidence. '
                           f'Consider sepsis workup and empiric antibiotics.'})
        elif current_risk > 0.5 and current_uncertainty < 0.15:
            report['alerts'].append({'level': 'MODERATE',
                'message': f'Moderate sepsis risk ({current_risk:.1%}). '
                           f'Recommend close monitoring and targeted labs.'})
        elif current_risk > 0.5:
            report['alerts'].append({'level': 'UNCERTAIN',
                'message': f'Elevated risk ({current_risk:.1%}) but high uncertainty '
                           f'({current_uncertainty:.1%}). Additional data needed.'})

        return report


# ============================================================================
# EVALUATION FUNCTIONS
# ============================================================================

def compute_auc_metrics(model, dataloader, device):
    model.eval()
    all_ts_probs, all_ts_labels = [], []
    all_pt_probs, all_pt_outcomes = [], []
    all_pt_probs_prefix = []  # C2: max prob up to onset (honest early-warning)
    with torch.no_grad():
        for batch in dataloader:
            x = batch['x'].to(device)
            mask = batch['mask'].to(device)
            hours = batch['hours'].to(device)
            y = batch['label'].cpu().numpy()
            mask_np = batch['mask'].cpu().numpy()
            outcomes = batch['patient_outcome'].cpu().numpy()

            output = model(x, mask, hours=hours)
            logits = output['logits'] if isinstance(output, dict) else output
            probs = torch.sigmoid(logits).cpu().numpy()
            for i in range(len(probs)):
                vl = int(mask_np[i].sum())
                if vl == 0: continue
                all_ts_probs.extend(probs[i, :vl].tolist())
                all_ts_labels.extend(y[i, :vl].tolist())
                all_pt_probs.append(probs[i, :vl].max())
                all_pt_outcomes.append(outcomes[i])
                yi = y[i, :vl]
                if yi.max() > 0:
                    onset = int(np.argmax(yi > 0))
                    all_pt_probs_prefix.append(float(probs[i, :onset + 1].max()))
                else:
                    all_pt_probs_prefix.append(float(probs[i, :vl].max()))

    all_ts_probs = np.array(all_ts_probs)
    all_ts_labels = np.array(all_ts_labels)
    all_pt_probs = np.array(all_pt_probs)
    all_pt_outcomes = np.array(all_pt_outcomes)

    m = {}
    m['timestep_auroc'] = roc_auc_score(all_ts_labels, all_ts_probs) if len(np.unique(all_ts_labels)) > 1 else 0.5
    m['timestep_auprc'] = average_precision_score(all_ts_labels, all_ts_probs) if len(np.unique(all_ts_labels)) > 1 else 0.0
    m['patient_auroc'] = roc_auc_score(all_pt_outcomes, all_pt_probs) if len(np.unique(all_pt_outcomes)) > 1 else 0.5
    m['patient_auprc'] = average_precision_score(all_pt_outcomes, all_pt_probs) if len(np.unique(all_pt_outcomes)) > 1 else 0.0
    _pref = np.array(all_pt_probs_prefix)
    m['patient_auroc_prefix'] = roc_auc_score(all_pt_outcomes, _pref) if len(np.unique(all_pt_outcomes)) > 1 else 0.5
    m['patient_auprc_prefix'] = average_precision_score(all_pt_outcomes, _pref) if len(np.unique(all_pt_outcomes)) > 1 else 0.0
    m['n_pos_ts'] = int(all_ts_labels.sum())
    m['n_total_ts'] = len(all_ts_labels)
    m['n_sepsis_pt'] = int(all_pt_outcomes.sum())
    m['n_total_pt'] = len(all_pt_outcomes)
    m['all_pt_probs'] = all_pt_probs
    m['all_pt_outcomes'] = all_pt_outcomes
    return m


def find_optimal_threshold_on_val(model, val_loader, device):
    model.eval()
    all_probs, all_outcomes = [], []
    with torch.no_grad():
        for batch in val_loader:
            x = batch['x'].to(device)
            mask = batch['mask'].to(device)
            hours = batch['hours'].to(device)
            mask_np = batch['mask'].cpu().numpy()
            outcomes = batch['patient_outcome'].cpu().numpy()
            output = model(x, mask, hours=hours)
            logits = output['logits'] if isinstance(output, dict) else output
            probs = torch.sigmoid(logits).cpu().numpy()
            for i in range(len(probs)):
                vl = int(mask_np[i].sum())
                if vl == 0: continue
                all_probs.append(probs[i, :vl].max())
                all_outcomes.append(outcomes[i])
    all_probs = np.array(all_probs)
    all_outcomes = np.array(all_outcomes)
    best_threshold, best_f2 = 0.5, 0
    for thr in np.arange(0.05, 0.95, 0.02):
        preds = (all_probs >= thr).astype(int)
        tp = np.sum((all_outcomes == 1) & (preds == 1))
        fn = np.sum((all_outcomes == 1) & (preds == 0))
        fp = np.sum((all_outcomes == 0) & (preds == 1))
        tn = np.sum((all_outcomes == 0) & (preds == 0))
        sens = tp / (tp + fn) if (tp + fn) > 0 else 0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        f2 = 5 * prec * sens / (4 * prec + sens) if (prec + sens) > 0 else 0
        if f2 > best_f2 and spec >= 0.70:
            best_f2 = f2
            best_threshold = thr
    return best_threshold


def compute_prediction_utility(labels, predictions,
                               dt_early=-12, dt_optimal=-6, dt_late=3.0,
                               max_u_tp=1, min_u_fn=-2, u_fp=-0.05, u_tn=0):
    if np.any(labels):
        # C5 (verified): standard PhysioNet monotonic step label (1 from onset-6h).
        t_sepsis = np.argmax(labels) - dt_optimal
        is_septic = True
    else:
        t_sepsis = float('inf')
        is_septic = False
    n = len(labels)
    m_1 = max_u_tp / (dt_optimal - dt_early)
    b_1 = -m_1 * dt_early
    m_2 = -max_u_tp / (dt_late - dt_optimal)
    b_2 = -m_2 * dt_late
    m_3 = min_u_fn / (dt_late - dt_optimal)
    b_3 = -m_3 * dt_optimal
    u = np.zeros(n)
    for t in range(n):
        if t <= t_sepsis + dt_late:
            if is_septic and predictions[t]:
                u[t] = max(m_1 * (t - t_sepsis) + b_1, u_fp) if t <= t_sepsis + dt_optimal else m_2 * (t - t_sepsis) + b_2
            elif is_septic and not predictions[t]:
                u[t] = 0 if t <= t_sepsis + dt_optimal else m_3 * (t - t_sepsis) + b_3
            elif not is_septic and predictions[t]:
                u[t] = u_fp
    return np.sum(u)


def compute_normalized_utility(true_labels_list, pred_labels_list):
    observed, best, inaction = [], [], []
    for labels, preds in zip(true_labels_list, pred_labels_list):
        n = len(labels)
        obs = compute_prediction_utility(labels, preds)
        best_preds = np.zeros(n)
        if np.any(labels):
            t_s = np.argmax(labels) + 6
            s_idx = max(0, t_s - 12)
            e_idx = min(t_s + 4, n)
            best_preds[s_idx:e_idx] = 1
        best_u = compute_prediction_utility(labels, best_preds)
        inaction_u = compute_prediction_utility(labels, np.zeros(n))
        observed.append(obs)
        best.append(best_u)
        inaction.append(inaction_u)
    s_o, s_b, s_i = np.sum(observed), np.sum(best), np.sum(inaction)
    return (s_o - s_i) / (s_b - s_i) if s_b != s_i else 0.0, s_o, s_b


def first_alarm_with_gate(p_probs, threshold, min_consecutive=ALARM_MIN_CONSECUTIVE, min_rise=ALARM_MIN_RISE):
    """Return first alarm index after persistence/rise gate; -1 if none."""
    if len(p_probs) == 0:
        return -1
    binary = (p_probs >= threshold).astype(np.int8)
    if min_consecutive <= 1 and min_rise <= 0:
        idx = np.where(binary == 1)[0]
        return int(idx[0]) if len(idx) > 0 else -1

    consec = 0
    start = 0
    for i, flag in enumerate(binary):
        if flag:
            if consec == 0:
                start = i
            consec += 1
            if consec >= min_consecutive:
                if min_rise <= 0 or (p_probs[i] - p_probs[start]) >= min_rise:
                    return int(start)
        else:
            consec = 0
    return -1


def evaluate_patient_level(model, dataloader, device, threshold=0.5):
    model.eval()
    patient_results = []
    true_labels_list, pred_labels_list = [], []
    with torch.no_grad():
        for batch in dataloader:
            x = batch['x'].to(device)
            y = batch['label'].cpu().numpy()
            mask_np = batch['mask'].cpu().numpy()
            patient_outcome = batch['patient_outcome'].cpu().numpy()
            pids = batch['pid']
            mask_t = batch['mask'].to(device)
            hours = batch['hours'].to(device)

            output = model(x, mask_t, hours=hours)
            logits = output['logits'] if isinstance(output, dict) else output
            probs = torch.sigmoid(logits).cpu().numpy()

            for i in range(len(pids)):
                vl = int(mask_np[i].sum())
                p_probs = probs[i, :vl]
                p_labels = y[i, :vl]
                first_alarm = first_alarm_with_gate(p_probs, threshold)
                p_preds = np.zeros_like(p_labels, dtype=int)
                if first_alarm >= 0:
                    p_preds[first_alarm:] = 1
                true_labels_list.append(p_labels)
                pred_labels_list.append(p_preds)
                has_sepsis = patient_outcome[i] == 1
                onset = -1
                if has_sepsis:
                    onset_idx = np.where(p_labels == 1)[0]
                    onset = onset_idx[0] if len(onset_idx) > 0 else -1
                    if onset == -1: has_sepsis = False
                patient_utility = compute_prediction_utility(p_labels, p_preds)
                pid_val = pids[i].item() if isinstance(pids[i], (np.ndarray, torch.Tensor)) else pids[i]
                patient_results.append({
                    'patient_id': str(pid_val), 'has_sepsis': bool(has_sepsis),
                    'detected': bool(first_alarm >= 0) if has_sepsis else None,
                    'hours_early': float(onset - first_alarm) if has_sepsis and first_alarm >= 0 else None,
                    'false_alarm': bool(first_alarm >= 0) if not has_sepsis else None,
                    'max_prob': float(p_probs.max()),
                    'onset_hour': int(onset) if has_sepsis and onset >= 0 else None,
                    'alarm_hour': int(first_alarm) if first_alarm >= 0 else None,
                    'utility': float(patient_utility)
                })

    results_df = pd.DataFrame(patient_results)
    norm_util, obs_util, best_util = compute_normalized_utility(true_labels_list, pred_labels_list)
    sepsis_df = results_df[results_df['has_sepsis'] == True]
    nonsepsis_df = results_df[results_df['has_sepsis'] == False]

    metrics = {'normalized_utility': norm_util, 'observed_utility': obs_util, 'best_utility': best_util}
    if len(sepsis_df) > 0:
        detected_count = sepsis_df['detected'].sum()
        metrics['sensitivity'] = detected_count / len(sepsis_df)
        metrics['missed_sepsis'] = len(sepsis_df) - detected_count
        early = sepsis_df[sepsis_df['hours_early'].notna() & (sepsis_df['hours_early'] > 0)]
        metrics['pct_early'] = len(early) / len(sepsis_df)
        metrics['mean_hours_early'] = early['hours_early'].mean() if len(early) > 0 else 0
        metrics['median_hours_early'] = early['hours_early'].median() if len(early) > 0 else 0
    else:
        metrics.update({'sensitivity': 0, 'missed_sepsis': 0, 'pct_early': 0, 'mean_hours_early': 0, 'median_hours_early': 0})
    if len(nonsepsis_df) > 0:
        metrics['specificity'] = (nonsepsis_df['false_alarm'] == False).sum() / len(nonsepsis_df)
        metrics['false_alarms'] = (nonsepsis_df['false_alarm'] == True).sum()
    else:
        metrics.update({'specificity': 0, 'false_alarms': 0})
    metrics.update({'total_patients': len(results_df), 'sepsis_patients': len(sepsis_df), 'nonsepsis_patients': len(nonsepsis_df)})
    return metrics, results_df


def bootstrap_ci(y_true, y_scores, metric_fn, n_bootstrap=1000, ci=0.95):
    rng = np.random.RandomState(42)
    n = len(y_true)
    scores = []
    for _ in range(n_bootstrap):
        idx = rng.choice(n, n, replace=True)
        if len(np.unique(y_true[idx])) < 2: continue
        try: scores.append(metric_fn(y_true[idx], y_scores[idx]))
        except: continue
    if len(scores) == 0: return 0, 0, 0
    scores = np.array(scores)
    alpha = (1 - ci) / 2
    return np.mean(scores), np.percentile(scores, 100 * alpha), np.percentile(scores, 100 * (1 - alpha))


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_osta_pipeline(df, feature_cols, test_size=0.175, val_size=0.125,
                      epochs=30, batch_size=256):

    print("=" * 75)
    print("OSTA-TRANSFORMER: ORGAN-SYSTEM-AWARE SEPSIS PREDICTION")
    print("=" * 75)

    # Feature engineering
    print("\n[1/8] Feature engineering...")
    base_feature_cols = feature_cols.copy()
    df_eng, eng_cols = engineer_temporal_features(df, base_feature_cols)
    all_feature_cols = base_feature_cols + eng_cols
    print(f"  Base: {len(base_feature_cols)}, Engineered: {len(eng_cols)}, Total: {len(all_feature_cols)}")

    # Data split
    print("\n[2/8] Splitting data...")
    patient_outcomes = patient_outcomes_within_horizon(df_eng, max_hours=120)
    all_pids = df_eng['Patient_ID'].unique()
    train_val_pids, test_pids = train_test_split(
        all_pids,
        test_size=test_size,
        random_state=42,
        stratify=patient_outcomes.loc[all_pids].values,
    )
    tv_outcomes = patient_outcomes.loc[train_val_pids]
    val_frac = val_size / (1 - test_size)
    train_pids, val_pids = train_test_split(train_val_pids, test_size=val_frac, random_state=42, stratify=tv_outcomes.values)
    print(f"  Train: {len(train_pids)}, Val: {len(val_pids)}, Test: {len(test_pids)}")

    # Prepare sequences
    print("\n[3/8] Preparing sequences with missingness indicators...")
    preprocessor = EnhancedSepsisPreprocessor(df_eng, all_feature_cols, max_hours=120, use_missingness=True)
    all_feat_names = preprocessor.get_all_feature_names()
    n_total = preprocessor.get_total_features()
    print(f"  Total features (incl. missingness): {n_total}")

    X_tr, y_tr, m_tr, o_tr, p_tr, h_tr = preprocessor.prepare_sequences(train_pids)
    X_va, y_va, m_va, o_va, p_va, h_va = preprocessor.prepare_sequences(val_pids)
    X_te, y_te, m_te, o_te, p_te, h_te = preprocessor.prepare_sequences(test_pids)

    # Normalize
    print("\n[4/8] Normalizing...")
    preprocessor.fit_normalization(X_tr)
    X_tr = preprocessor.normalize(X_tr)
    X_va = preprocessor.normalize(X_va)
    X_te = preprocessor.normalize(X_te)

    # Dataloaders
    print("\n[5/8] Creating dataloaders...")
    train_loader = DataLoader(EnhancedSepsisDataset(X_tr, y_tr, m_tr, o_tr, p_tr, h_tr), **build_loader_kwargs(batch_size, shuffle=True))
    val_loader = DataLoader(EnhancedSepsisDataset(X_va, y_va, m_va, o_va, p_va, h_va), **build_loader_kwargs(batch_size, shuffle=False))
    test_loader = DataLoader(EnhancedSepsisDataset(X_te, y_te, m_te, o_te, p_te, h_te), **build_loader_kwargs(batch_size, shuffle=False))

    # Model
    print("\n[6/8] Initializing OSTA-Transformer...")
    device = setup_colab_environment()
    model = OSTATransformer(
        feature_cols=all_feat_names,
        d_organ=MODEL_D_ORGAN, d_global=MODEL_D_GLOBAL,
        n_heads_organ=4, n_heads_inter=4,
        n_layers_organ=2, n_layers_global=2,
        dropout=MODEL_DROPOUT, mc_samples=30
    ).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Parameters: {n_params:,}")

    use_amp = torch.cuda.is_available() and not DISABLE_AMP
    scaler = torch.amp.GradScaler('cuda') if use_amp else None
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    # Training
    print("\n[7/8] Training...")
    print(f"{'Epoch':>6} {'Loss':>10} {'Val P-AUC':>11} {'Val T-AUC':>11} {'Time':>8}")
    print("-" * 52)

    best_val_auc = 0
    best_model_state = None
    patience = 7
    wait = 0

    for epoch in range(epochs):
        t0 = time.time()
        model.train()
        total_loss = 0
        for batch in train_loader:
            x = batch['x'].to(device)
            y = batch['label'].to(device)
            mask = batch['mask'].to(device)
            hours = batch['hours'].to(device)
            optimizer.zero_grad()
            with (torch.amp.autocast('cuda', dtype=torch.bfloat16) if use_amp else contextlib.nullcontext()):
                output = model(x, mask, hours=hours, return_interpretability=True)
                loss = osta_loss(output, y, mask)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
        scheduler.step()
        avg_loss = total_loss / len(train_loader)
        elapsed = time.time() - t0

        if (epoch + 1) % 2 == 0:
            val_m = compute_auc_metrics(model, val_loader, device)
            val_pauc = val_m['patient_auroc']
            val_tauc = val_m['timestep_auroc']
            marker = ""
            if val_pauc > best_val_auc:
                best_val_auc = val_pauc
                best_model_state = {k: v.clone() for k, v in model.state_dict().items()}
                wait = 0
                marker = " *best*"
            else:
                wait += 1
            print(f"{epoch+1:6d} {avg_loss:10.4f} {val_pauc:11.4f} {val_tauc:11.4f} {elapsed:7.1f}s{marker}")
            if wait >= patience:
                print(f"\n  Early stopping at epoch {epoch+1}")
                break
        else:
            print(f"{epoch+1:6d} {avg_loss:10.4f} {'--':>11} {'--':>11} {elapsed:7.1f}s")

        if (epoch + 1) % 10 == 0: clear_gpu_memory()

    if best_model_state: model.load_state_dict(best_model_state)
    print(f"\n  Best validation Patient-AUC: {best_val_auc:.4f}")

    # Final evaluation
    print("\n[8/8] Final evaluation...")
    print("\n" + "=" * 75)
    print("FINAL EVALUATION ON TEST SET")
    print("=" * 75)

    test_auc = compute_auc_metrics(model, test_loader, device)
    print(f"\n--- AUC METRICS ---")
    print(f"Patient-level AUROC:    {test_auc['patient_auroc']:.4f}")
    print(f"Patient-level AUPRC:    {test_auc['patient_auprc']:.4f}")
    print(f"Timestep-level AUROC:   {test_auc['timestep_auroc']:.4f}")
    print(f"Timestep-level AUPRC:   {test_auc['timestep_auprc']:.4f}")

    # Bootstrap CIs
    pt_probs = test_auc['all_pt_probs']
    pt_outcomes = test_auc['all_pt_outcomes']
    auroc_mean, auroc_lo, auroc_hi = bootstrap_ci(pt_outcomes, pt_probs, roc_auc_score)
    auprc_mean, auprc_lo, auprc_hi = bootstrap_ci(pt_outcomes, pt_probs, average_precision_score)
    print(f"\n--- BOOTSTRAP 95% CIs ---")
    print(f"  Patient AUROC: {auroc_mean:.4f} ({auroc_lo:.4f} - {auroc_hi:.4f})")
    print(f"  Patient AUPRC: {auprc_mean:.4f} ({auprc_lo:.4f} - {auprc_hi:.4f})")

    # Threshold & clinical metrics
    threshold = find_optimal_threshold_on_val(model, val_loader, device)
    print(f"\nOptimal threshold: {threshold:.3f}")
    final_metrics, test_results = evaluate_patient_level(model, test_loader, device, threshold)

    print(f"\n--- CLINICAL PERFORMANCE ---")
    print(f"Normalized Utility: {final_metrics['normalized_utility']:.4f}")
    n_det = final_metrics['sepsis_patients'] - final_metrics['missed_sepsis']
    print(f"Sensitivity: {100*final_metrics['sensitivity']:.2f}% ({n_det:.0f}/{final_metrics['sepsis_patients']})")
    print(f"Specificity: {100*final_metrics['specificity']:.2f}%")
    print(f"False alarms: {final_metrics['false_alarms']:.0f}/{final_metrics['nonsepsis_patients']}")
    print(f"Early detection: {100*final_metrics['pct_early']:.1f}%")
    print(f"Mean/Median lead time: {final_metrics['mean_hours_early']:.1f}h / {final_metrics['median_hours_early']:.1f}h")

    # Organ system importance
    print(f"\n--- ORGAN SYSTEM IMPORTANCE (Learned Weights) ---")
    model.eval()
    weights = torch.softmax(model.organ_risk_weights, dim=0).detach().cpu().numpy()
    for name, w in sorted(zip(model.organ_names, weights), key=lambda x: -x[1]):
        bar = '█' * int(w * 50)
        print(f"  {name:20s}: {w:.3f} {bar}")

    # Clinical report for example patient
    print(f"\n--- EXAMPLE CLINICAL REPORT ---")
    reporter = ClinicalReportGenerator(model)
    sepsis_results = test_results[test_results['has_sepsis'] == True]
    if len(sepsis_results) > 0:
        example_pid = sepsis_results.iloc[0]['patient_id']
        # Find this patient in test dataset
        for batch in test_loader:
            for i, pid in enumerate(batch['pid']):
                pid_val = pid.item() if isinstance(pid, torch.Tensor) else pid
                if str(pid_val) == example_pid:
                    report = reporter.generate_patient_report(
                        batch['x'][i].cpu(), batch['mask'][i].cpu(),
                        hours=batch['hours'][i].cpu(), patient_id=example_pid
                    )
                    print(f"  Patient: {report['patient_id']}")
                    print(f"  Valid hours: {report['valid_hours']}")
                    print(f"  Final risk: {report['risk_trajectory'][-1]:.4f}")
                    print(f"  Uncertainty: {report['uncertainty'][-1]:.4f}")
                    print(f"  Deteriorating organs: {[d['organ'] for d in report['deteriorating_organs']]}")
                    for alert in report['alerts']:
                        print(f"  ALERT [{alert['level']}]: {alert['message']}")
                    print(f"  Organ risk breakdown:")
                    for organ, risk in sorted(report['organ_risks'].items(), key=lambda x: -x[1][-1]):
                        print(f"    {organ:20s}: {risk[-1]:.3f}")
                    break
            else:
                continue
            break

    # Summary
    print("\n" + "=" * 75)
    print("ALL METRICS SUMMARY")
    print("=" * 75)
    print(f"  Patient AUROC:        {test_auc['patient_auroc']:.4f} ({auroc_lo:.4f}-{auroc_hi:.4f})")
    print(f"  Timestep AUROC:       {test_auc['timestep_auroc']:.4f}")
    print(f"  Patient AUPRC:        {test_auc['patient_auprc']:.4f} ({auprc_lo:.4f}-{auprc_hi:.4f})")
    print(f"  Timestep AUPRC:       {test_auc['timestep_auprc']:.4f}")
    print(f"  Normalized Utility:   {final_metrics['normalized_utility']:.4f}")
    print(f"  Sensitivity:          {100*final_metrics['sensitivity']:.2f}%")
    print(f"  Specificity:          {100*final_metrics['specificity']:.2f}%")
    print(f"  Threshold:            {threshold:.3f}")
    print(f"  Parameters:           {n_params:,}")
    print("=" * 75)

    return model, preprocessor, test_auc, final_metrics, test_results


# ============================================================================
# RUN
# ============================================================================


# ======================================================================

# Cell 4: Combined driver — Train 3 seeds + Ensemble + validation-quantile threshold
# ============================================================================
# This cell does EVERYTHING in one go:
#
#   (1) For each seed in {42, 7, 123}:
#       - Train v5 architecture with epochs=50, patience=10
#       - Save checkpoint with EXPLICIT VERIFY-AND-FSYNC (so Drive actually flushes)
#       - Skip retraining if checkpoint already exists and is valid
#
#   (2) Build 3-model ensemble by averaging test probabilities
#
#   (3) Select a high quantile of negative validation probabilities
#
#   (4) Print final comparison table:
#         - Per-seed mean ± SD
#         - Ensemble (probability-averaged) with bootstrap CIs
#         - Ensemble + validation-quantile threshold
#         - Recorded causal Paper1 reference
#         - Mahmud et al. 2026 (published lightweight RF, utility-only
#           comparison since their AUROC is on a balanced test set)
#
# Why a single combined cell:
#   The previous attempt to split into Stage 1 (training) and Stage 2 (analysis)
#   failed because Stage 1's Drive saves did not persist. By doing everything
#   in one session with explicit checkpoint verification after each save, we
#   eliminate the cross-session checkpoint-loss problem.
#
# Resumability:
#   If the notebook disconnects mid-run, restart it. Already-trained seeds
#   will be loaded from their saved checkpoints (after verifying they're
#   valid), and only missing seeds will be retrained. The ensemble calibration
#   step at the end is fast (~minutes) so it gets re-run each time.
#
# Total compute: ~3.5h on A100 from cold start (3 × ~70min).
# ============================================================================

import os
import json
import random
import math
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
_seeds_env = os.getenv('OSTA_SEEDS', '42,7,123')
SEEDS = [int(s.strip()) for s in _seeds_env.split(',') if s.strip()]
EPOCHS = int(os.getenv('OSTA_EPOCHS', '50'))
PATIENCE = int(os.getenv('OSTA_PATIENCE', '10'))
BATCH_SIZE = int(os.getenv('OSTA_BATCH_SIZE', '256'))
CONFORMAL_ALPHA = float(os.getenv('OSTA_CONFORMAL_ALPHA', '0.10'))
MAX_PATIENTS = int(os.getenv('OSTA_MAX_PATIENTS', '0'))
DISABLE_AMP = os.getenv('OSTA_DISABLE_AMP', '0').strip().lower() in ('1', 'true', 'yes')
MIN_CKPT_VAL_AUC = float(os.getenv('OSTA_MIN_CKPT_VAL_AUC', '0.0'))
LEARNING_RATE = float(os.getenv('OSTA_LR', '5e-4'))
WEIGHT_DECAY = float(os.getenv('OSTA_WEIGHT_DECAY', '1e-4'))
MODEL_D_ORGAN = int(os.getenv('OSTA_D_ORGAN', '64'))
MODEL_D_GLOBAL = int(os.getenv('OSTA_D_GLOBAL', '256'))
MODEL_DROPOUT = float(os.getenv('OSTA_DROPOUT', '0.15'))
ENSEMBLE_WEIGHTING = os.getenv('OSTA_ENSEMBLE_WEIGHTING', 'uniform').strip().lower()
RANK_LOSS_LAMBDA = float(os.getenv('OSTA_RANK_LAMBDA', '0.0'))
RANK_LOSS_MARGIN = float(os.getenv('OSTA_RANK_MARGIN', '0.05'))

def pick_save_dir():
    save_dir = os.getenv('OSTA_SAVE_DIR', 'outputs/osta').strip()
    os.makedirs(save_dir, exist_ok=True)
    return os.path.join(save_dir, ''), False

SAVE_DIR = None
USING_DRIVE = False


# ----------------------------------------------------------------------------
# Hardened checkpoint save — verifies the file landed before continuing
# ----------------------------------------------------------------------------
def save_checkpoint_verified(state_dict, path, max_retries=3):
    """torch.save + fsync + size check. Aborts loudly if save didn't persist."""
    for attempt in range(max_retries):
        try:
            torch.save(state_dict, path)
            # Force OS to flush to disk
            with open(path, 'rb') as f:
                os.fsync(f.fileno())
            # Verify
            if not os.path.isfile(path):
                raise RuntimeError(f"Save succeeded but file missing at {path}")
            sz = os.path.getsize(path)
            if sz < 1000:
                raise RuntimeError(f"Save produced suspicious file size: {sz} bytes")
            # For Drive: small additional sleep so the sync daemon catches up
            if USING_DRIVE:
                time.sleep(2.0)
                if not os.path.isfile(path):
                    raise RuntimeError(f"File vanished after Drive sleep at {path}")
            print(f"    ✓ Checkpoint verified: {path} ({sz/1e6:.1f} MB)")
            return True
        except Exception as e:
            print(f"    ✗ Save attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            raise
    return False


# ----------------------------------------------------------------------------
# Seeding helper
# ----------------------------------------------------------------------------
def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ----------------------------------------------------------------------------
# Build feature_cols and run preprocessing ONCE (split is fixed across seeds)
# ----------------------------------------------------------------------------
def main():
    global SAVE_DIR, USING_DRIVE

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing dataset file: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)

    SAVE_DIR, USING_DRIVE = pick_save_dir()
    print(f"Save directory: {SAVE_DIR}  (Drive: {USING_DRIVE})")
    if not USING_DRIVE:
        print("  Saving to local workspace directory.")

    print("\n" + "=" * 75)
    print("DATA PREPARATION (shared across seeds)")
    print("=" * 75)

    irrelevant_cols = ['Unnamed: 0', '...1', 'datetime', 'ICULOS', 'Unit1', 'Unit2',
                       'Apache_II_Score', 'SOFA_Score', 'SIRS',
                       'Incomplete_qSOFA_Score', 'NEWS_Score',
                       'Shock_Index', 'BUN_Creatinine_Ratio',
                       'Bilirubin_Creatinine_Ratio']
    feature_cols = [c for c in df.columns
                    if c not in ['Patient_ID', 'SepsisLabel', 'Hour'] + irrelevant_cols]
    print(f"Base features: {len(feature_cols)}")

    print("\nFeature engineering...")
    df_eng, eng_cols = engineer_temporal_features(df, feature_cols)
    all_feature_cols = feature_cols + eng_cols
    print(f"  Total features: {len(all_feature_cols)}")

    if MAX_PATIENTS > 0:
        all_outcomes = patient_outcomes_within_horizon(df_eng, max_hours=120)
        pos_ids = all_outcomes[all_outcomes == 1].index.tolist()
        neg_ids = all_outcomes[all_outcomes == 0].index.tolist()
        n_pos = min(len(pos_ids), max(1, int(MAX_PATIENTS * len(pos_ids) / len(all_outcomes))))
        n_neg = min(len(neg_ids), MAX_PATIENTS - n_pos)
        rng = np.random.RandomState(42)
        sel_pos = rng.choice(pos_ids, size=n_pos, replace=False).tolist() if n_pos > 0 else []
        sel_neg = rng.choice(neg_ids, size=n_neg, replace=False).tolist() if n_neg > 0 else []
        keep_ids = set(sel_pos + sel_neg)
        df_eng = df_eng[df_eng['Patient_ID'].isin(keep_ids)].copy()
        print(f"  Using subset for run: {df_eng['Patient_ID'].nunique()} patients")

    print("\nSplitting data (fixed random_state=42)...")
    patient_outcomes = patient_outcomes_within_horizon(df_eng, max_hours=120)
    all_pids = df_eng['Patient_ID'].unique()
    train_val_pids, test_pids = train_test_split(
        all_pids, test_size=0.175, random_state=42,
        stratify=patient_outcomes.loc[all_pids].values
    )
    tv_outcomes = patient_outcomes.loc[train_val_pids]
    val_frac = 0.125 / (1 - 0.175)
    train_pids, val_pids = train_test_split(
        train_val_pids, test_size=val_frac, random_state=42,
        stratify=tv_outcomes.values
    )
    print(f"  Train: {len(train_pids)}, Val: {len(val_pids)}, Test: {len(test_pids)}")

    print("\nPreparing sequences...")
    preprocessor = EnhancedSepsisPreprocessor(
        df_eng, all_feature_cols, max_hours=120, use_missingness=True
    )
    all_feat_names = preprocessor.get_all_feature_names()
    n_total_features = preprocessor.get_total_features()
    print(f"  Total features (incl. missingness): {n_total_features}")

    cache_path = os.path.join(SAVE_DIR, 'v5_preprocessed_cache.npz')
    cache_loaded = False
    if os.path.exists(cache_path):
        try:
            c = np.load(cache_path, allow_pickle=True)
            X_tr, y_tr, m_tr, o_tr, h_tr = c['X_tr'], c['y_tr'], c['m_tr'], c['o_tr'], c['h_tr']
            X_va, y_va, m_va, o_va, h_va = c['X_va'], c['y_va'], c['m_va'], c['o_va'], c['h_va']
            X_te, y_te, m_te, o_te, h_te = c['X_te'], c['y_te'], c['m_te'], c['o_te'], c['h_te']
            p_tr, p_va, p_te = c['p_tr'].tolist(), c['p_va'].tolist(), c['p_te'].tolist()
            preprocessor.feature_means = c['feature_means']
            preprocessor.feature_stds = c['feature_stds']

            o_tr_expected = ((y_tr * m_tr).max(axis=1) > 0).astype(int)
            o_va_expected = ((y_va * m_va).max(axis=1) > 0).astype(int)
            o_te_expected = ((y_te * m_te).max(axis=1) > 0).astype(int)

            valid_cache = (
                X_tr.shape[0] == len(train_pids) and
                X_va.shape[0] == len(val_pids) and
                X_te.shape[0] == len(test_pids) and
                X_tr.shape[2] == n_total_features and
                np.array_equal(np.array(p_tr), np.array(train_pids)) and
                np.array_equal(np.array(p_va), np.array(val_pids)) and
                np.array_equal(np.array(p_te), np.array(test_pids)) and
                np.array_equal(o_tr.astype(int), o_tr_expected) and
                np.array_equal(o_va.astype(int), o_va_expected) and
                np.array_equal(o_te.astype(int), o_te_expected)
            )
            if not valid_cache:
                raise ValueError(
                    f"cache mismatch: got train/val/test={X_tr.shape[0]}/{X_va.shape[0]}/{X_te.shape[0]}, "
                    f"expected {len(train_pids)}/{len(val_pids)}/{len(test_pids)}, features={X_tr.shape[2]} vs {n_total_features}"
                )

            cache_loaded = True
            print(f"  Loaded preprocessed cache: {cache_path}")
        except Exception as e:
            print(f"  Cache load failed ({e}); rebuilding...")

    if not cache_loaded:
        X_tr, y_tr, m_tr, o_tr, p_tr, h_tr = preprocessor.prepare_sequences(train_pids)
        X_va, y_va, m_va, o_va, p_va, h_va = preprocessor.prepare_sequences(val_pids)
        X_te, y_te, m_te, o_te, p_te, h_te = preprocessor.prepare_sequences(test_pids)

        print("\nNormalizing...")
        preprocessor.fit_normalization(X_tr)
        X_tr = preprocessor.normalize(X_tr)
        X_va = preprocessor.normalize(X_va)
        X_te = preprocessor.normalize(X_te)

        np.savez_compressed(
            cache_path,
            X_tr=X_tr, y_tr=y_tr, m_tr=m_tr, o_tr=o_tr, h_tr=h_tr, p_tr=np.array(p_tr, dtype=object),
            X_va=X_va, y_va=y_va, m_va=m_va, o_va=o_va, h_va=h_va, p_va=np.array(p_va, dtype=object),
            X_te=X_te, y_te=y_te, m_te=m_te, o_te=o_te, h_te=h_te, p_te=np.array(p_te, dtype=object),
            feature_means=preprocessor.feature_means, feature_stds=preprocessor.feature_stds
        )
        print(f"  Saved preprocessed cache: {cache_path}")

    # Shared val/test loaders (shuffle=False -> deterministic ordering)
    val_loader = DataLoader(
        EnhancedSepsisDataset(X_va, y_va, m_va, o_va, p_va, h_va),
        **build_loader_kwargs(BATCH_SIZE, shuffle=False)
    )
    test_loader = DataLoader(
        EnhancedSepsisDataset(X_te, y_te, m_te, o_te, p_te, h_te),
        **build_loader_kwargs(BATCH_SIZE, shuffle=False)
    )

    device = setup_colab_environment()


    # ----------------------------------------------------------------------------
    # Helper: build a fresh OSTATransformer
    # ----------------------------------------------------------------------------
    def make_osta_model(feat_names):
        return OSTATransformer(
            feature_cols=feat_names,
            d_organ=MODEL_D_ORGAN, d_global=MODEL_D_GLOBAL,
            n_heads_organ=4, n_heads_inter=4,
            n_layers_organ=2, n_layers_global=2,
            dropout=MODEL_DROPOUT, mc_samples=30
        ).to(device)


    # ----------------------------------------------------------------------------
    # Per-seed training (skip if valid checkpoint exists)
    # ----------------------------------------------------------------------------
    def train_or_load_seed(seed):
        """Train v5 with the given seed and save checkpoint, OR load existing."""
        ckpt_path = os.path.join(SAVE_DIR, f'v5_seed{seed}_model.pt')

        # Try to load existing
        if os.path.isfile(ckpt_path):
            try:
                sz = os.path.getsize(ckpt_path)
                if sz < 1000:
                    raise RuntimeError(f"Existing checkpoint suspiciously small ({sz} bytes)")
                print(f"\n  Loading existing checkpoint: {ckpt_path} ({sz/1e6:.1f} MB)")
                ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
                if ckpt.get('checkpoint_format') != 'causal-v1':
                    raise RuntimeError("checkpoint predates the causal-v1 format")
                if ckpt.get('feature_cols') != all_feat_names:
                    raise RuntimeError("feature_cols mismatch in saved checkpoint")
                ckpt_best_auc = ckpt.get('best_val_auc', None)
                if ckpt_best_auc is not None and ckpt_best_auc < MIN_CKPT_VAL_AUC:
                    raise RuntimeError(
                        f"checkpoint best_val_auc={ckpt_best_auc:.4f} below OSTA_MIN_CKPT_VAL_AUC={MIN_CKPT_VAL_AUC:.4f}"
                    )
                model = make_osta_model(all_feat_names)
                model.load_state_dict(ckpt['model_state_dict'])
                model.eval()
                return {
                    'seed': seed,
                    'model': model,
                    'threshold': ckpt.get('threshold', 0.5),
                    'organ_weights': ckpt.get('organ_weights', {}),
                    'best_val_auc': ckpt.get('best_val_auc', None),
                    'newly_trained': False,
                }
            except Exception as e:
                print(f"  Could not load existing checkpoint ({e}); will retrain.")

        # Train fresh
        print(f"\n  Training seed {seed} (~70 min on A100)...")
        set_seed(seed)
        train_loader = DataLoader(
            EnhancedSepsisDataset(X_tr, y_tr, m_tr, o_tr, p_tr, h_tr),
            **build_loader_kwargs(BATCH_SIZE, shuffle=True)
        )
        model = make_osta_model(all_feat_names)
        n_params = sum(p.numel() for p in model.parameters())
        print(f"    Parameters: {n_params:,}")

        use_amp = torch.cuda.is_available() and not DISABLE_AMP
        optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

        print(f"\n    {'Epoch':>6} {'Loss':>10} {'Val P-AUC':>11} {'Val T-AUC':>11} {'Time':>8}")
        print("    " + "-" * 52)

        best_val_auc = 0
        best_state = None
        wait = 0
        for epoch in range(EPOCHS):
            t0 = time.time()
            model.train()
            total_loss = 0
            for batch in train_loader:
                x = batch['x'].to(device)
                y = batch['label'].to(device)
                mask = batch['mask'].to(device)
                hours = batch['hours'].to(device)
                optimizer.zero_grad()
                with (torch.amp.autocast('cuda', dtype=torch.bfloat16) if use_amp else contextlib.nullcontext()):
                    output = model(x, mask, hours=hours, return_interpretability=True)
                    loss = osta_loss(output, y, mask)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()
            scheduler.step()
            avg_loss = total_loss / len(train_loader)
            elapsed = time.time() - t0

            if (epoch + 1) % 2 == 0:
                val_m = compute_auc_metrics(model, val_loader, device)
                val_pauc = val_m['patient_auroc']
                val_tauc = val_m['timestep_auroc']
                marker = ""
                if val_pauc > best_val_auc:
                    best_val_auc = val_pauc
                    best_state = {k: v.clone() for k, v in model.state_dict().items()}
                    wait = 0
                    marker = " *best*"
                else:
                    wait += 1
                print(f"    {epoch+1:6d} {avg_loss:10.4f} {val_pauc:11.4f} "
                      f"{val_tauc:11.4f} {elapsed:7.1f}s{marker}")
                if wait >= PATIENCE:
                    print(f"\n    Early stopping at epoch {epoch+1}")
                    break
            else:
                print(f"    {epoch+1:6d} {avg_loss:10.4f} {'--':>11} {'--':>11} {elapsed:7.1f}s")

            if (epoch + 1) % 10 == 0:
                clear_gpu_memory()

        if best_state:
            model.load_state_dict(best_state)
        model.eval()
        print(f"\n    Best validation Patient-AUC: {best_val_auc:.4f}")

        threshold = find_optimal_threshold_on_val(model, val_loader, device)
        organ_w = torch.softmax(model.organ_risk_weights, dim=0).detach().cpu().numpy()
        organ_dict = {n: float(w) for n, w in zip(model.organ_names, organ_w)}

        # SAVE WITH VERIFICATION
        save_checkpoint_verified({
            'checkpoint_format': 'causal-v1',
            'seed': seed,
            'model_state_dict': model.state_dict(),
            'feature_cols': all_feat_names,
            'organ_weights': organ_dict,
            'threshold': threshold,
            'best_val_auc': best_val_auc,
        }, ckpt_path)

        return {
            'seed': seed,
            'model': model,
            'threshold': threshold,
            'organ_weights': organ_dict,
            'best_val_auc': best_val_auc,
            'newly_trained': True,
        }


    # ----------------------------------------------------------------------------
    # (1) Train or load all 3 seeds
    # ----------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("STEP 1 — TRAIN OR LOAD ALL 3 SEEDS")
    print("=" * 75)

    results = {}
    for seed in SEEDS:
        print(f"\n### Seed {seed} ###")
        results[seed] = train_or_load_seed(seed)
        # If training was new, give Drive a moment to fully sync before next seed
        if results[seed].get('newly_trained') and USING_DRIVE:
            time.sleep(3)
        clear_gpu_memory()

    print("\n--- All 3 seeds available ---")
    for s in SEEDS:
        r = results[s]
        bv = r['best_val_auc']
        bv_str = f"{bv:.4f}" if bv is not None else "n/a"
        print(f"  seed {s}: threshold={r['threshold']:.3f}, "
              f"best_val_auc={bv_str}, "
              f"newly_trained={r['newly_trained']}")


    # ----------------------------------------------------------------------------
    # (2) Run all 3 models on val + test, collect probabilities
    # ----------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("STEP 2 — COLLECT PROBABILITIES FROM ALL 3 MODELS")
    print("=" * 75)

    def collect_probs(model, loader):
        model.eval()
        items = []
        with torch.no_grad():
            for batch in loader:
                x = batch['x'].to(device)
                mask_t = batch['mask'].to(device)
                hours = batch['hours'].to(device)
                output = model(x, mask_t, hours=hours)
                logits = output['logits'] if isinstance(output, dict) else output
                probs = torch.sigmoid(logits).cpu().numpy()
                mask_np = batch['mask'].cpu().numpy()
                y = batch['label'].cpu().numpy()
                outcomes = batch['patient_outcome'].cpu().numpy()
                pids = batch['pid']
                for i in range(len(pids)):
                    pid_val = pids[i].item() if isinstance(pids[i], torch.Tensor) else pids[i]
                    items.append({
                        'pid': str(pid_val),
                        'probs': probs[i],
                        'labels': y[i],
                        'mask': mask_np[i],
                        'outcome': float(outcomes[i]),
                    })
        return items

    val_probs_per_seed = []
    test_probs_per_seed = []
    for s in SEEDS:
        print(f"  seed {s} ...", end=' ', flush=True)
        val_probs_per_seed.append(collect_probs(results[s]['model'], val_loader))
        test_probs_per_seed.append(collect_probs(results[s]['model'], test_loader))
        print("done.")

    # Sanity check
    pids_ref = [it['pid'] for it in test_probs_per_seed[0]]
    for s_idx, items in enumerate(test_probs_per_seed[1:], start=1):
        assert [it['pid'] for it in items] == pids_ref, \
            f"PID order mismatch at seed index {s_idx}"
    print("  PID ordering consistent ✓")


    # ----------------------------------------------------------------------------
    # (3) Build ensemble probabilities (uniform or validation-weighted)
    # ----------------------------------------------------------------------------
    def _patient_level_from_items(items):
        pt_p, pt_o = [], []
        for it in items:
            vl = int(it['mask'].sum())
            if vl == 0:
                continue
            pt_p.append(float(it['probs'][:vl].max()))
            pt_o.append(float(it['outcome']))
        return np.array(pt_p), np.array(pt_o)


    def _compute_seed_weights():
        mode = ENSEMBLE_WEIGHTING
        n = len(SEEDS)
        if mode == 'uniform':
            w = np.ones(n, dtype=np.float64)
            w /= w.sum()
            print("  Ensemble weighting: uniform")
            return w

        if mode not in {'val_patient_auroc', 'val_patient_auprc'}:
            print(f"  Unknown OSTA_ENSEMBLE_WEIGHTING='{mode}', falling back to uniform")
            w = np.ones(n, dtype=np.float64)
            w /= w.sum()
            return w

        raw_scores = []
        for seed, items in zip(SEEDS, val_probs_per_seed):
            try:
                p, y = _patient_level_from_items(items)
                if mode == 'val_patient_auprc':
                    score = average_precision_score(y, p)
                else:
                    score = roc_auc_score(y, p)
            except Exception:
                score = 0.5
            raw_scores.append(max(float(score), 1e-6))

        w = np.array(raw_scores, dtype=np.float64)
        if np.sum(w) <= 0:
            w = np.ones(n, dtype=np.float64)
        w /= np.sum(w)

        print(f"  Ensemble weighting: {mode}")
        print("    seed scores -> normalized weights:")
        for seed, s, wi in zip(SEEDS, raw_scores, w):
            print(f"      seed {seed}: score={s:.6f}, weight={wi:.4f}")
        return w


    def _safe_logit(p):
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p))


    def average_probs(probs_per_seed, seed_weights=None):
        n_pat = len(probs_per_seed[0])
        out = []
        for i in range(n_pat):
            stack = np.stack([s[i]['probs'] for s in probs_per_seed], axis=0)
            if seed_weights is None:
                agg_probs = stack.mean(axis=0)
            else:
                agg_probs = np.average(stack, axis=0, weights=seed_weights)
            out.append({
                'pid': probs_per_seed[0][i]['pid'],
                'probs': agg_probs,
                'labels': probs_per_seed[0][i]['labels'],
                'mask': probs_per_seed[0][i]['mask'],
                'outcome': probs_per_seed[0][i]['outcome'],
            })
        return out


    def _build_timestep_matrix(probs_per_seed, patient_indices):
        X_blocks, y_blocks = [], []
        base = probs_per_seed[0]
        for i in patient_indices:
            vl = int(base[i]['mask'].sum())
            if vl == 0:
                continue
            seed_probs = np.stack([s[i]['probs'][:vl] for s in probs_per_seed], axis=1)
            X_blocks.append(_safe_logit(seed_probs))
            y_blocks.append(base[i]['labels'][:vl])
        if not X_blocks:
            return np.empty((0, len(probs_per_seed))), np.empty((0,))
        return np.concatenate(X_blocks, axis=0), np.concatenate(y_blocks, axis=0)


    def _apply_stack_model_to_items(probs_per_seed, model):
        n_pat = len(probs_per_seed[0])
        out = []
        for i in range(n_pat):
            seed_probs = np.stack([s[i]['probs'] for s in probs_per_seed], axis=1)
            X = _safe_logit(seed_probs)
            agg_probs = model.predict_proba(X)[:, 1]
            out.append({
                'pid': probs_per_seed[0][i]['pid'],
                'probs': agg_probs,
                'labels': probs_per_seed[0][i]['labels'],
                'mask': probs_per_seed[0][i]['mask'],
                'outcome': probs_per_seed[0][i]['outcome'],
            })
        return out


    def _stacking_oof_ensemble(val_probs_per_seed, test_probs_per_seed):
        n_pat = len(val_probs_per_seed[0])
        outcomes = np.array([it['outcome'] for it in val_probs_per_seed[0]])
        idx_all = np.arange(n_pat)
        idx_a, idx_b = train_test_split(
            idx_all, test_size=0.5, random_state=42, stratify=outcomes
        )

        X_a, y_a = _build_timestep_matrix(val_probs_per_seed, idx_a)
        X_b, y_b = _build_timestep_matrix(val_probs_per_seed, idx_b)

        model_a = LogisticRegression(max_iter=300, class_weight='balanced', n_jobs=1)
        model_b = LogisticRegression(max_iter=300, class_weight='balanced', n_jobs=1)
        model_a.fit(X_a, y_a)
        model_b.fit(X_b, y_b)

        # OOF predictions for validation items
        val_ens = [None] * n_pat
        for src_idx, model in [(idx_b, model_a), (idx_a, model_b)]:
            for i in src_idx:
                seed_probs = np.stack([s[i]['probs'] for s in val_probs_per_seed], axis=1)
                X = _safe_logit(seed_probs)
                agg_probs = model.predict_proba(X)[:, 1]
                val_ens[i] = {
                    'pid': val_probs_per_seed[0][i]['pid'],
                    'probs': agg_probs,
                    'labels': val_probs_per_seed[0][i]['labels'],
                    'mask': val_probs_per_seed[0][i]['mask'],
                    'outcome': val_probs_per_seed[0][i]['outcome'],
                }

        # Final model for test predictions trained on full validation set
        X_full, y_full = _build_timestep_matrix(val_probs_per_seed, idx_all)
        model_full = LogisticRegression(max_iter=300, class_weight='balanced', n_jobs=1)
        model_full.fit(X_full, y_full)
        test_ens = _apply_stack_model_to_items(test_probs_per_seed, model_full)

        coef = model_full.coef_.reshape(-1)
        intercept = float(model_full.intercept_[0])
        print("  Ensemble mode: stack_lr_timestep (OOF on validation, final fit on full validation)")
        print("    seed coefficients (logit space):")
        for seed, c in zip(SEEDS, coef):
            print(f"      seed {seed}: coef={c:.5f}")
        print(f"    intercept: {intercept:.5f}")

        return val_ens, test_ens


    if ENSEMBLE_WEIGHTING == 'stack_lr_timestep':
        if len(SEEDS) < 2:
            print("  stack_lr_timestep requires >=2 seeds; falling back to uniform averaging")
            seed_weights = np.ones(len(SEEDS), dtype=np.float64) / max(len(SEEDS), 1)
            val_ens = average_probs(val_probs_per_seed, seed_weights=seed_weights)
            test_ens = average_probs(test_probs_per_seed, seed_weights=seed_weights)
        else:
            val_ens, test_ens = _stacking_oof_ensemble(val_probs_per_seed, test_probs_per_seed)
    else:
        seed_weights = _compute_seed_weights()
        val_ens = average_probs(val_probs_per_seed, seed_weights=seed_weights)
        test_ens = average_probs(test_probs_per_seed, seed_weights=seed_weights)


    def items_to_arrays(items):
        ts_p, ts_y, pt_p, pt_o = [], [], [], []
        for it in items:
            vl = int(it['mask'].sum())
            if vl == 0:
                continue
            ts_p.extend(it['probs'][:vl].tolist())
            ts_y.extend(it['labels'][:vl].tolist())
            pt_p.append(float(it['probs'][:vl].max()))
            pt_o.append(it['outcome'])
        return np.array(ts_p), np.array(ts_y), np.array(pt_p), np.array(pt_o)


    # Ensemble metrics
    ens_ts_p, ens_ts_y, ens_pt_p, ens_pt_o = items_to_arrays(test_ens)
    ens_pat_auroc = roc_auc_score(ens_pt_o, ens_pt_p)
    ens_pat_auprc = average_precision_score(ens_pt_o, ens_pt_p)
    ens_ts_auroc = roc_auc_score(ens_ts_y, ens_ts_p)
    ens_ts_auprc = average_precision_score(ens_ts_y, ens_ts_p)
    ens_auroc_m, ens_auroc_lo, ens_auroc_hi = bootstrap_ci(ens_pt_o, ens_pt_p, roc_auc_score)
    ens_auprc_m, ens_auprc_lo, ens_auprc_hi = bootstrap_ci(ens_pt_o, ens_pt_p,
                                                            average_precision_score)

    # C2: honest prefix (<=onset) patient discrimination for the ensemble
    _pref_p, _pref_o = [], []
    for it in test_ens:
        vl = int(it['mask'].sum())
        if vl == 0:
            continue
        yi = it['labels'][:vl]
        if yi.max() > 0:
            onset = int(np.argmax(yi > 0))
            _pref_p.append(float(it['probs'][:onset + 1].max()))
        else:
            _pref_p.append(float(it['probs'][:vl].max()))
        _pref_o.append(it['outcome'])
    ens_pat_auroc_prefix = roc_auc_score(_pref_o, _pref_p)
    ens_pat_auprc_prefix = average_precision_score(_pref_o, _pref_p)
    print(f"\n  Ensemble Patient AUROC (whole-stay, optimistic): {ens_pat_auroc:.4f}")
    print(f"  Ensemble Patient AUROC (prefix <=onset, honest): {ens_pat_auroc_prefix:.4f}")
    print(f"  Ensemble Patient AUPRC (prefix <=onset, honest): {ens_pat_auprc_prefix:.4f}")


    # ----------------------------------------------------------------------------
    # Find utility-optimal threshold for ensemble (on val ensemble probs)
    # ----------------------------------------------------------------------------
    val_ts_p, val_ts_y, val_pt_p, val_pt_o = items_to_arrays(val_ens)
    val_patient_probs, val_patient_labels = [], []
    for it in val_ens:
        vl = int(it['mask'].sum())
        if vl == 0:
            continue
        val_patient_probs.append(it['probs'][:vl])
        val_patient_labels.append(it['labels'][:vl])

    utility_sweep_rows = []
    best_thr, best_util = 0.5, -1e9
    for thr in np.arange(0.05, 0.951, 0.01):
        preds = [(p >= thr).astype(int) for p in val_patient_probs]
        norm_util, obs_util, _ = compute_normalized_utility(val_patient_labels, preds)
        utility_sweep_rows.append({'threshold': float(thr), 'normalized_utility': float(norm_util), 'observed_utility': float(obs_util)})
        if norm_util > best_util:
            best_util = norm_util
            best_thr = thr
    ens_threshold = float(best_thr)
    pd.DataFrame(utility_sweep_rows).to_csv(os.path.join(SAVE_DIR, 'v5_validation_utility_sweep.csv'), index=False)


    def evaluate_with_threshold(items, threshold):
        """Compute clinical metrics on ensemble items at a given threshold."""
        true_lst, pred_lst, records = [], [], []
        for it in items:
            vl = int(it['mask'].sum())
            if vl == 0:
                continue
            p_probs = it['probs'][:vl]
            p_labels = it['labels'][:vl]
            first_alarm = first_alarm_with_gate(p_probs, threshold)
            p_preds = np.zeros_like(p_labels, dtype=int)
            if first_alarm >= 0:
                p_preds[first_alarm:] = 1
            true_lst.append(p_labels)
            pred_lst.append(p_preds)
            has_sepsis = it['outcome'] == 1
            onset = -1
            if has_sepsis:
                onset_idx = np.where(p_labels == 1)[0]
                onset = int(onset_idx[0]) if len(onset_idx) > 0 else -1
                if onset == -1:
                    has_sepsis = False
            records.append({
                'patient_id': it['pid'],
                'has_sepsis': bool(has_sepsis),
                'detected': bool(first_alarm >= 0) if has_sepsis else None,
                'hours_early': float(onset - first_alarm) if has_sepsis and first_alarm >= 0 else None,
                'false_alarm': bool(first_alarm >= 0) if not has_sepsis else None,
                'max_prob': float(p_probs.max()),
                'utility': float(compute_prediction_utility(p_labels, p_preds)),
            })
        norm_util, _, _ = compute_normalized_utility(true_lst, pred_lst)
        df_records = pd.DataFrame(records)
        sepsis_df = df_records[df_records['has_sepsis'] == True]
        nonsep_df = df_records[df_records['has_sepsis'] == False]
        sens = sepsis_df['detected'].sum() / len(sepsis_df) if len(sepsis_df) > 0 else 0
        spec = ((nonsep_df['false_alarm'] == False).sum() / len(nonsep_df)
                if len(nonsep_df) > 0 else 0)
        early = sepsis_df[sepsis_df['hours_early'].notna() & (sepsis_df['hours_early'] > 0)]
        pct_early = len(early) / len(sepsis_df) if len(sepsis_df) > 0 else 0
        mean_lead = early['hours_early'].mean() if len(early) > 0 else 0
        med_lead = early['hours_early'].median() if len(early) > 0 else 0
        return {
            'norm_util': norm_util, 'sens': sens, 'spec': spec,
            'pct_early': pct_early, 'mean_lead': mean_lead, 'med_lead': med_lead,
            'records_df': df_records,
        }

    ens_clin = evaluate_with_threshold(test_ens, ens_threshold)
    ens_clin['records_df'].to_csv(os.path.join(SAVE_DIR, 'v5_ensemble_results.csv'), index=False)


    # ----------------------------------------------------------------------------
    # (4) Validation-quantile threshold on the ensemble
    # ----------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print(f"STEP 3 — VALIDATION-QUANTILE THRESHOLD (α = {CONFORMAL_ALPHA})")
    print("=" * 75)

    # This heuristic is not a conformal prediction set and has no coverage guarantee.
    scores_neg = []
    n_pos_cal = 0
    for it in val_ens:
        vl = int(it['mask'].sum())
        for t in range(vl):
            if it['labels'][t] == 1:
                n_pos_cal += 1
            else:
                scores_neg.append(it['probs'][t])
    scores_neg = np.array(scores_neg)
    n_neg_cal = len(scores_neg)
    q = min(np.ceil((n_neg_cal + 1) * (1 - CONFORMAL_ALPHA)) / n_neg_cal, 1.0)
    conformal_threshold = float(np.quantile(scores_neg, q))
    print(f"  Calibration set: {n_pos_cal} positive, {n_neg_cal} negative timesteps")
    print(f"  Validation-quantile threshold: {conformal_threshold:.4f}")

    ens_conf_clin = evaluate_with_threshold(test_ens, conformal_threshold)
    ens_conf_clin['records_df'].to_csv(
        os.path.join(SAVE_DIR, 'v5_ensemble_conformal_results.csv'), index=False
    )

    # Validation-only alpha sweep: require sensitivity >=85%, then maximize specificity.
    alpha_rows = []
    best_alpha_row = None
    for alpha in np.arange(0.05, 0.251, 0.01):
        q_a = min(np.ceil((n_neg_cal + 1) * (1 - alpha)) / n_neg_cal, 1.0)
        thr_a = float(np.quantile(scores_neg, q_a))
        clin_a = evaluate_with_threshold(val_ens, thr_a)  # C4: select alpha on validation
        row = {
            'alpha': float(alpha),
            'threshold': thr_a,
            'sensitivity': float(clin_a['sens']),
            'specificity': float(clin_a['spec']),
            'false_alarms': int((clin_a['records_df']['false_alarm'] == True).sum()),
            'normalized_utility': float(clin_a['norm_util']),
        }
        alpha_rows.append(row)
        if row['sensitivity'] >= 0.85:
            if best_alpha_row is None or row['specificity'] > best_alpha_row['specificity'] or (
                row['specificity'] == best_alpha_row['specificity'] and row['normalized_utility'] > best_alpha_row['normalized_utility']
            ):
                best_alpha_row = row

    alpha_sweep_df = pd.DataFrame(alpha_rows)
    alpha_sweep_df.to_csv(os.path.join(SAVE_DIR, 'v5_conformal_alpha_sweep.csv'), index=False)
    if best_alpha_row is None and alpha_rows:
        best_alpha_row = max(alpha_rows, key=lambda r: r['normalized_utility'])


    # ----------------------------------------------------------------------------
    # (5) Per-seed metrics for the mean ± SD column
    # ----------------------------------------------------------------------------
    per_seed_rows = []
    for s_idx, s in enumerate(SEEDS):
        items = test_probs_per_seed[s_idx]
        ts_p_s, ts_y_s, pt_p_s, pt_o_s = items_to_arrays(items)
        thr_s = results[s]['threshold']
        clin_s = evaluate_with_threshold(items, thr_s)
        per_seed_rows.append({
            'seed': s,
            'patient_auroc': roc_auc_score(pt_o_s, pt_p_s),
            'patient_auprc': average_precision_score(pt_o_s, pt_p_s),
            'timestep_auroc': roc_auc_score(ts_y_s, ts_p_s),
            'timestep_auprc': average_precision_score(ts_y_s, ts_p_s),
            'normalized_utility': clin_s['norm_util'],
            'sensitivity': clin_s['sens'],
            'specificity': clin_s['spec'],
            'threshold': thr_s,
        })
    per_seed_df = pd.DataFrame(per_seed_rows)
    per_seed_df.to_csv(os.path.join(SAVE_DIR, 'v5_per_seed_metrics.csv'), index=False)


    # ----------------------------------------------------------------------------
    # (6) Print final comparison table
    # ----------------------------------------------------------------------------
    print("\n" + "=" * 95)
    print("FINAL COMPARISON — recorded references vs current OSTA run")
    print("=" * 95)

    paper1 = {
        'patient_auroc': 0.7892,
        'patient_auprc': 0.2796,
        'timestep_auroc': 0.7949,
        'timestep_auprc': 0.0865,
        'normalized_utility': 0.0218,
        'sensitivity': 0.8198,
        'specificity': 0.5822,
    }
    # Mahmud et al. 2026 — only utility is comparable (their AUROC is on a balanced
    # test set, not the natural-distribution PhysioNet test set)
    mahmud = {
        'patient_auroc': None,           # not directly comparable
        'patient_auprc': None,
        'timestep_auroc': None,
        'timestep_auprc': None,
        'normalized_utility': 0.466,
        'sensitivity': None,
        'specificity': None,
    }
    ensemble = {
        'patient_auroc': ens_pat_auroc,
        'patient_auprc': ens_pat_auprc,
        'timestep_auroc': ens_ts_auroc,
        'timestep_auprc': ens_ts_auprc,
        'normalized_utility': ens_clin['norm_util'],
        'sensitivity': ens_clin['sens'],
        'specificity': ens_clin['spec'],
    }
    ensemble_conf = {
        'patient_auroc': ens_pat_auroc,    # AUC unchanged — same probs
        'patient_auprc': ens_pat_auprc,
        'timestep_auroc': ens_ts_auroc,
        'timestep_auprc': ens_ts_auprc,
        'normalized_utility': ens_conf_clin['norm_util'],
        'sensitivity': ens_conf_clin['sens'],
        'specificity': ens_conf_clin['spec'],
    }

    def fmt(x, w=10, dec=4):
        if x is None:
            return f"{'n/a':>{w}}"
        return f"{x:>{w}.{dec}f}"

    print(f"\n{'Metric':<22}{'P1 Ref':>10}{'Mahmud Ref':>13}"
          f"{'Per-seed (mean±SD)':>22}{'Ensemble':>11}{'Ens+Conf':>11}")
    print("-" * 95)
    for col, label in [
        ('patient_auroc', 'Patient AUROC'),
        ('patient_auprc', 'Patient AUPRC'),
        ('timestep_auroc', 'Timestep AUROC'),
        ('timestep_auprc', 'Timestep AUPRC'),
        ('normalized_utility', 'Normalized Utility'),
        ('sensitivity', 'Sensitivity'),
        ('specificity', 'Specificity'),
    ]:
        p1 = paper1[col]
        mh = mahmud[col]
        mean = per_seed_df[col].mean()
        std = per_seed_df[col].std()
        e = ensemble[col]
        ec = ensemble_conf[col]
        ms = f"{mean:.4f} ± {std:.4f}"
        print(f"{label:<22}{fmt(p1)}{fmt(mh, 13)}{ms:>22}{e:>11.4f}{ec:>11.4f}")

    print()
    print("Footnotes:")
    print("  Paper 1: causal full CNN-Transformer reference from the matching split.")
    print("  Mahmud 2026: lightweight RF on 7 vital signs. Their AUROC=0.94 appears to be")
    print("    on a balanced test set (50% prevalence) — not directly comparable to OSTA's")
    print("    natural-prevalence (~7%) test set. Utility (0.466) IS comparable since the")
    print("    PhysioNet utility score is invariant to training-set rebalancing.")
    print("  Quantile-threshold AUROC/AUPRC equals the ensemble because only the")
    print("    operating threshold changes, not the probabilities.")

    print(f"\n--- Ensemble bootstrap 95% CIs ---")
    print(f"  Patient AUROC: {ens_auroc_m:.4f} ({ens_auroc_lo:.4f} - {ens_auroc_hi:.4f})")
    print(f"  Patient AUPRC: {ens_auprc_m:.4f} ({ens_auprc_lo:.4f} - {ens_auprc_hi:.4f})")

    print(f"\n--- Operating thresholds ---")
    for s in SEEDS:
        print(f"  seed {s} threshold: {results[s]['threshold']:.3f}")
    print(f"  Ensemble utility-optimal threshold: {ens_threshold:.3f}")
    print(f"  Ensemble validation-quantile threshold (alpha={CONFORMAL_ALPHA:.2f}): {conformal_threshold:.4f}")
    if best_alpha_row is not None:
        print(f"  Best alpha sweep pick: alpha={best_alpha_row['alpha']:.2f}, thr={best_alpha_row['threshold']:.4f}, "
              f"sens={best_alpha_row['sensitivity']:.2%}, spec={best_alpha_row['specificity']:.2%}, "
              f"FP={best_alpha_row['false_alarms']}, util={best_alpha_row['normalized_utility']:.4f}")

    print(f"\n--- Ensemble early detection profile ---")
    print(f"  At F2 threshold: %early={100*ens_clin['pct_early']:.1f}%, "
          f"mean lead={ens_clin['mean_lead']:.2f}h, median lead={ens_clin['med_lead']:.2f}h")
    print(f"  At quantile:     %early={100*ens_conf_clin['pct_early']:.1f}%, "
          f"mean lead={ens_conf_clin['mean_lead']:.2f}h, median lead={ens_conf_clin['med_lead']:.2f}h")

    print(f"\n--- Organ importance per seed (init-sensitive — see paper Discussion) ---")
    for s in SEEDS:
        ow = results[s]['organ_weights']
        if ow:
            top = max(ow.items(), key=lambda kv: kv[1])
            print(f"  seed {s}: top organ = {top[0]} (weight {top[1]:.3f})")


    # ----------------------------------------------------------------------------
    # (7) Save text summary
    # ----------------------------------------------------------------------------
    summary_path = os.path.join(SAVE_DIR, 'v5_combined_summary.txt')
    with open(summary_path, 'w') as f:
        f.write("OSTA v5 — Combined Stage 1+2 Run\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Seeds: {SEEDS}, epochs: {EPOCHS}, patience: {PATIENCE}\n")
        f.write(f"Validation-quantile alpha: {CONFORMAL_ALPHA}\n")
        f.write(f"Save directory: {SAVE_DIR}\n\n")
        f.write("Per-seed metrics:\n")
        f.write(per_seed_df.to_string(index=False, float_format='%.4f') + "\n\n")
        f.write("FINAL COMPARISON:\n")
        f.write(f"{'Metric':<22}{'P1 Ref':>10}{'Mahmud Ref':>10}"
                f"{'Mean±SD':>22}{'Ensemble':>11}{'Ens+Conf':>11}\n")
        f.write("-" * 86 + "\n")
        for col, label in [
            ('patient_auroc', 'Patient AUROC'),
            ('patient_auprc', 'Patient AUPRC'),
            ('timestep_auroc', 'Timestep AUROC'),
            ('timestep_auprc', 'Timestep AUPRC'),
            ('normalized_utility', 'Normalized Utility'),
            ('sensitivity', 'Sensitivity'),
            ('specificity', 'Specificity'),
        ]:
            p1 = paper1[col]
            mh = mahmud[col]
            mean = per_seed_df[col].mean()
            std = per_seed_df[col].std()
            e = ensemble[col]
            ec = ensemble_conf[col]
            ms = f"{mean:.4f} ± {std:.4f}"
            p1_s = f"{p1:.4f}" if p1 is not None else "n/a"
            mh_s = f"{mh:.4f}" if mh is not None else "n/a"
            f.write(f"{label:<22}{p1_s:>10}{mh_s:>10}{ms:>22}{e:>11.4f}{ec:>11.4f}\n")
        f.write(f"\nBootstrap 95% CIs (ensemble):\n")
        f.write(f"  Patient AUROC: {ens_auroc_m:.4f} ({ens_auroc_lo:.4f} - {ens_auroc_hi:.4f})\n")
        f.write(f"  Patient AUPRC: {ens_auprc_m:.4f} ({ens_auprc_lo:.4f} - {ens_auprc_hi:.4f})\n")
        f.write(f"\nThresholds: ensemble utility-optimal = {ens_threshold:.3f}, "
                f"validation-quantile(alpha={CONFORMAL_ALPHA:.2f}) = {conformal_threshold:.4f}\n")
        if best_alpha_row is not None:
            f.write("Best validation-quantile alpha sweep pick:\n")
            f.write(f"  alpha={best_alpha_row['alpha']:.2f}, threshold={best_alpha_row['threshold']:.4f}, "
                    f"sens={best_alpha_row['sensitivity']:.4f}, spec={best_alpha_row['specificity']:.4f}, "
                    f"FP={best_alpha_row['false_alarms']}, util={best_alpha_row['normalized_utility']:.4f}\n")
    print(f"\nSummary saved: {summary_path}")
    print("\nDone.")


    # ======================================================================



if __name__ == "__main__":
    main()
