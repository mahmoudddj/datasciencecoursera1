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

"""
Paper 1 — Enhanced CNN-Transformer for Early Sepsis Prediction
PhysioNet 2019 Challenge Data

Enhancements over Paper 1 baseline:
1.  Missingness indicator features (doubles clinical signal)
2.  Temporal feature engineering (rolling stats, derivatives, interactions)
3.  Learnable continuous-time positional encoding
4.  CNN-Transformer hybrid architecture
5.  Multi-scale temporal attention pooling
6.  Comprehensive ablation study
7.  Attention-based interpretability analysis
8.  Validation-quantile threshold calibration
9.  Bootstrap confidence intervals for all metrics
10. Full comparison with Paper 1 baseline

Run this entire cell as Cell 2 in your Colab notebook.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
import math
import time
import warnings
import copy
import os
import contextlib
import random
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             accuracy_score, f1_score, fbeta_score,
                             precision_recall_curve, roc_curve)
from collections import defaultdict

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
        print("No GPU — training will be slow. Go to Runtime > Change runtime type > GPU")
    return device


def clear_gpu_memory():
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_loader_kwargs(batch_size, shuffle):
    use_cuda = torch.cuda.is_available()
    kwargs = {
        'batch_size': batch_size,
        'shuffle': shuffle,
    }
    if use_cuda:
        kwargs.update({
            'num_workers': min(8, os.cpu_count() or 4),
            'pin_memory': True,
            'persistent_workers': True,
            'prefetch_factor': 4,
        })
    return kwargs


# ============================================================================
# ENHANCEMENT 1: TEMPORAL FEATURE ENGINEERING
# ============================================================================

def engineer_temporal_features(df, base_feature_cols):
    """
    Add clinically-motivated temporal features:
    - Rolling statistics (6h, 12h windows)
    - Rate of change (1st derivative)
    - Time-since-last-measurement (missingness velocity)
    - Multi-scale EMA (2h/6h/12h) for key vitals
    - Cross-feature interactions
    """
    print("  Engineering temporal features...")
    df = df.sort_values(['Patient_ID', 'Hour']).copy()

    # Core raw clinical variables used for missingness-velocity signals
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

    # Pre-compute per-patient grouped object once
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

    # Phase 1.1: Time-since-last-measurement (log1p soft-clipped)
    for var in raw_clinical_vars:
        miss = df[var].isna()
        # count consecutive missing within patient, reset to 0 on measurement
        streak = miss.groupby(df['Patient_ID']).cumsum()
        measured_streak = (~miss).groupby(df['Patient_ID']).cumsum()
        dt_raw = streak - measured_streak.where(miss, 0)
        dt_col = f'{var}_tslm'
        df[dt_col] = np.log1p(np.maximum(dt_raw.values, 0))
        new_cols.append(dt_col)

    # Phase 1.2: EMA features for key vitals (after patient-wise forward-fill)
    ema_windows = [2, 6, 12]
    for var in ['HR', 'SBP', 'MAP', 'Resp', 'O2Sat', 'Temp']:
        if var not in df.columns:
            continue
        filled = pid_group[var].transform(lambda x: x.ffill().fillna(0))
        for w in ema_windows:
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
# ENHANCEMENT 2: MISSINGNESS-AWARE PREPROCESSING
# ============================================================================

class EnhancedSepsisPreprocessor:
    """Preprocessor with missingness indicators and temporal features."""

    def __init__(self, df, feature_cols, max_hours=120, use_missingness=True):
        self.df = df
        self.feature_cols = feature_cols
        self.max_hours = max_hours
        self.use_missingness = use_missingness
        self.feature_means = None
        self.feature_stds = None

        # Determine missingness columns (only for original raw features)
        self.miss_cols = []
        if use_missingness:
            # Only add missingness indicators for original clinical variables,
            # not for engineered features
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

    def prepare_sequences(self, patient_ids=None):
        if patient_ids is None:
            patient_ids = self.df['Patient_ID'].unique()

        n_features = self.get_total_features()
        sequences, labels, masks, patient_outcomes, pids, hours_list, sofa_list = [], [], [], [], [], [], []

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
            sofa_vals = patient_data['SOFA_Score'].values if 'SOFA_Score' in patient_data.columns else np.zeros_like(y)
            sofa_vals = np.nan_to_num(sofa_vals, nan=0.0, posinf=0.0, neginf=0.0)

            # Create missingness indicators BEFORE imputation
            if self.use_missingness and len(self.miss_cols) > 0:
                miss_idx = [self.feature_cols.index(c) for c in self.miss_cols]
                miss_flags = np.isnan(X_raw[:, miss_idx]).astype(float)
            else:
                miss_flags = np.zeros((len(X_raw), 0))

            # Impute: forward-fill then zero-fill
            X_filled = pd.DataFrame(X_raw, columns=self.feature_cols).ffill().fillna(0).values

            # Concatenate features + missingness indicators
            X_combined = np.concatenate([X_filled, miss_flags], axis=1)

            n_hours = min(len(X_combined), self.max_hours)
            patient_outcome = 1 if np.any(y[:n_hours] == 1) else 0

            X_padded = np.zeros((self.max_hours, n_features))
            y_padded = np.zeros(self.max_hours)
            mask = np.zeros(self.max_hours)
            h_padded = np.zeros(self.max_hours)
            sofa_padded = np.zeros(self.max_hours)

            X_padded[:n_hours] = X_combined[:n_hours]
            y_padded[:n_hours] = y[:n_hours]
            mask[:n_hours] = 1
            h_padded[:n_hours] = hour_vals[:n_hours]
            sofa_padded[:n_hours] = sofa_vals[:n_hours]

            sequences.append(X_padded)
            labels.append(y_padded)
            masks.append(mask)
            patient_outcomes.append(patient_outcome)
            pids.append(pid)
            hours_list.append(h_padded)
            sofa_list.append(sofa_padded)

        return (np.array(sequences), np.array(labels),
                np.array(masks), np.array(patient_outcomes),
                pids, np.array(hours_list), np.array(sofa_list))

    def fit_normalization(self, X_train):
        X_flat = X_train.reshape(-1, X_train.shape[2])
        valid_mask = np.abs(X_flat).sum(axis=1) > 0
        X_valid = X_flat[valid_mask]
        X_valid = np.nan_to_num(X_valid, nan=0.0, posinf=0.0, neginf=0.0)
        self.feature_means = np.nan_to_num(np.mean(X_valid, axis=0), nan=0.0)
        self.feature_stds = np.nan_to_num(np.std(X_valid, axis=0), nan=1.0) + 1e-8
        # Don't normalize binary missingness indicators
        n_base = len(self.feature_cols)
        if self.use_missingness:
            self.feature_means[n_base:] = 0.0
            self.feature_stds[n_base:] = 1.0

    def normalize(self, X):
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        normalized = (X - self.feature_means) / self.feature_stds
        return np.nan_to_num(normalized, nan=0.0, posinf=3.0, neginf=-3.0)


# ============================================================================
# DATASET
# ============================================================================

class EnhancedSepsisDataset(Dataset):
    def __init__(self, sequences, labels, masks, patient_outcomes, patient_ids, hours, sofa_targets=None):
        self.sequences = torch.FloatTensor(sequences)
        self.labels = torch.FloatTensor(labels)
        self.masks = torch.FloatTensor(masks)
        self.patient_outcomes = torch.FloatTensor(patient_outcomes)
        self.patient_ids = patient_ids
        self.hours = torch.FloatTensor(hours)
        if sofa_targets is None:
            sofa_targets = np.zeros_like(labels)
        self.sofa_targets = torch.FloatTensor(sofa_targets)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return {
            'x': self.sequences[idx],
            'label': self.labels[idx],
            'mask': self.masks[idx],
            'patient_outcome': self.patient_outcomes[idx],
            'pid': self.patient_ids[idx],
            'hours': self.hours[idx],
            'sofa': self.sofa_targets[idx]
        }


# ============================================================================
# ENHANCEMENT 3: LEARNABLE CONTINUOUS-TIME POSITIONAL ENCODING
# ============================================================================

class ContinuousTimeEncoding(nn.Module):
    """Learnable continuous-time positional encoding.
    Unlike fixed sinusoidal encoding that assumes regular intervals,
    this learns to embed actual timestamps, handling irregular sampling."""

    def __init__(self, d_model, max_len=200):
        super().__init__()
        self.d_model = d_model
        # Learnable frequency and phase parameters
        self.freq = nn.Parameter(torch.randn(1, 1, d_model // 2) * 0.01)
        self.phase = nn.Parameter(torch.zeros(1, 1, d_model // 2))
        self.linear = nn.Linear(d_model, d_model)
        # Fallback: standard positional encoding for initialization
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() *
                             (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe_fallback', pe)

    def forward(self, x, hours=None):
        if hours is not None:
            # Continuous-time encoding using actual timestamps
            t = hours.unsqueeze(-1)  # (B, T, 1)
            sin_enc = torch.sin(t * self.freq + self.phase)  # (B, T, d/2)
            cos_enc = torch.cos(t * self.freq + self.phase)  # (B, T, d/2)
            time_enc = torch.cat([sin_enc, cos_enc], dim=-1)  # (B, T, d)
            time_enc = self.linear(time_enc)
            return x + time_enc
        else:
            return x + self.pe_fallback[:x.size(1)].unsqueeze(0)


# Fixed sinusoidal for baseline/ablation
class FixedPositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=200):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() *
                             (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x, hours=None):
        return x + self.pe[:x.size(1)].unsqueeze(0)


# ============================================================================
# ENHANCEMENT 4: CNN-TRANSFORMER HYBRID MODEL
# ============================================================================

def _causal_attn_mask(L, device):
    """Causal self-attention mask: True = position may NOT attend (future).
    Prevents per-timestep predictions from leaking information from later
    hours (required for a valid early-warning task)."""
    return torch.triu(torch.ones(L, L, dtype=torch.bool, device=device), diagonal=1)


class CausalCNNBlock(nn.Module):
    """1D causal CNN for local temporal pattern extraction."""

    def __init__(self, in_channels, out_channels, kernel_size=3, dilation=1, dropout=0.1):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation  # causal padding
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size,
                              padding=self.padding, dilation=dilation)
        self.norm = nn.BatchNorm1d(out_channels)
        self.activation = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        # Residual connection if dimensions match
        self.residual = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()

    def forward(self, x):
        # x: (B, C, T)
        residual = self.residual(x)
        out = self.conv(x)
        out = out[:, :, :x.size(2)]  # Remove future padding (causal)
        out = self.norm(out)
        out = self.activation(out)
        out = self.dropout(out)
        return out + residual


class MultiScaleTemporalCNN(nn.Module):
    """Multi-scale causal CNN extracting patterns at different time scales."""

    def __init__(self, in_channels, hidden_channels, dropout=0.1):
        super().__init__()
        # Short-range (1-3 hours)
        self.conv_short = CausalCNNBlock(in_channels, hidden_channels, kernel_size=3, dilation=1, dropout=dropout)
        # Medium-range (3-6 hours)
        self.conv_medium = CausalCNNBlock(in_channels, hidden_channels, kernel_size=3, dilation=2, dropout=dropout)
        # Long-range (6-12 hours)
        self.conv_long = CausalCNNBlock(in_channels, hidden_channels, kernel_size=3, dilation=4, dropout=dropout)
        # Fusion
        self.fusion = nn.Sequential(
            nn.Conv1d(hidden_channels * 3, hidden_channels, 1),
            nn.BatchNorm1d(hidden_channels),
            nn.GELU()
        )

    def forward(self, x):
        # x: (B, C, T)
        s = self.conv_short(x)
        m = self.conv_medium(x)
        l = self.conv_long(x)
        fused = torch.cat([s, m, l], dim=1)  # (B, 3*C, T)
        return self.fusion(fused)  # (B, C, T)


class EnhancedSepsisTransformer(nn.Module):
    """CNN-Transformer hybrid with multi-scale temporal attention."""

    def __init__(self, num_features, d_model=256, n_heads=8, num_layers=4,
                 dim_feedforward=512, dropout=0.2, use_cnn=True,
                 use_continuous_time=True):
        super().__init__()
        self.use_cnn = use_cnn
        self.use_continuous_time = use_continuous_time
        self.d_model = d_model

        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(num_features, d_model),
            nn.LayerNorm(d_model),
            nn.Dropout(dropout)
        )

        # Multi-scale CNN for local patterns
        if use_cnn:
            self.cnn = MultiScaleTemporalCNN(d_model, d_model, dropout=dropout * 0.5)
            self.cnn_norm = nn.LayerNorm(d_model)

        # Positional encoding
        if use_continuous_time:
            self.pos_encoder = ContinuousTimeEncoding(d_model)
        else:
            self.pos_encoder = FixedPositionalEncoding(d_model)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads,
            dim_feedforward=dim_feedforward,
            dropout=dropout, batch_first=True, norm_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Prediction head with residual connection
        self.output_head = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(64, 1)
        )
        # Auxiliary organ-severity regression head (SOFA proxy)
        self.sofa_head = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.GELU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(64, 1)
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x, mask=None, hours=None, return_attention=False, return_aux=False):
        # Input projection: (B, T, F) -> (B, T, D)
        h = self.input_proj(x)

        # CNN for local patterns
        if self.use_cnn:
            h_cnn = h.permute(0, 2, 1)  # (B, D, T)
            h_cnn = self.cnn(h_cnn)      # (B, D, T)
            h_cnn = h_cnn.permute(0, 2, 1)  # (B, T, D)
            h = self.cnn_norm(h + h_cnn)  # Residual connection

        # Positional encoding
        h = self.pos_encoder(h, hours=hours)

        # Transformer
        key_padding_mask = (mask == 0) if mask is not None else None
        attn_mask = _causal_attn_mask(h.size(1), h.device)
        h = self.transformer(h, mask=attn_mask, src_key_padding_mask=key_padding_mask)

        # Per-timestep prediction
        logits = self.output_head(h).squeeze(-1)
        if return_aux:
            sofa_pred = self.sofa_head(h).squeeze(-1)
            return logits, sofa_pred
        return logits


# ============================================================================
# PAPER 1 BASELINE MODEL (for comparison)
# ============================================================================

class BaselineSepsisTransformer(nn.Module):
    """Paper 1 architecture (unchanged) for fair comparison."""

    def __init__(self, num_features, d_model=256, n_heads=8, num_layers=4,
                 dim_feedforward=512, dropout=0.2):
        super().__init__()
        self.input_proj = nn.Sequential(
            nn.Linear(num_features, d_model),
            nn.LayerNorm(d_model),
            nn.Dropout(dropout)
        )
        self.pos_encoder = FixedPositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=dim_feedforward,
            dropout=dropout, batch_first=True, norm_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.output_head = nn.Sequential(
            nn.Linear(d_model, 128), nn.LayerNorm(128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, 64), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

    def forward(self, x, mask=None, hours=None, return_attention=False):
        h = self.input_proj(x)
        h = self.pos_encoder(h)
        key_padding_mask = (mask == 0) if mask is not None else None
        attn_mask = _causal_attn_mask(h.size(1), h.device)
        h = self.transformer(h, mask=attn_mask, src_key_padding_mask=key_padding_mask)
        return self.output_head(h).squeeze(-1)


# ============================================================================
# LOSS FUNCTION (same as Paper 1)
# ============================================================================

def improved_sepsis_loss(logits, targets, masks,
                         early_alpha=0.3, focal_gamma=2.0,
                         utility_lambda=0.15, aux_lambda=0.20,
                         sofa_pred=None, sofa_targets=None):
    """
    Focal-time loss + differentiable utility surrogate + optional SOFA aux loss.
    L_total = L_focal - λ*L_utility + 0.2*L_sofa
    """
    logits = torch.nan_to_num(logits, nan=0.0, posinf=20.0, neginf=-20.0)
    targets = torch.nan_to_num(targets, nan=0.0, posinf=1.0, neginf=0.0)
    masks = torch.nan_to_num(masks, nan=0.0, posinf=1.0, neginf=0.0)

    B, T = targets.shape
    device = logits.device

    time_weights = torch.ones_like(targets, device=device)
    for b in range(B):
        sepsis_idx = torch.where(targets[b] == 1)[0]
        if len(sepsis_idx) > 0:
            t_onset = sepsis_idx[0].item()
            t_idx = torch.arange(T, device=device)
            before = t_idx < t_onset
            after = ~before
            time_weights[b, before] = torch.exp(-early_alpha * (t_onset - t_idx[before]).float())
            time_weights[b, after] = 1.5

    bce = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
    probs = torch.sigmoid(logits)
    pt = torch.where(targets == 1, probs, 1 - probs)
    focal_weight = (1 - pt) ** focal_gamma
    alpha_t = torch.where(targets == 1, 0.75, 0.25).to(device)
    focal_loss = (alpha_t * focal_weight * bce * time_weights * masks).sum() / (masks.sum() + 1e-8)

    # Differentiable utility surrogate emphasizing early true positives and penalizing false alarms
    # Rebalanced utility surrogate to avoid trivial all-negative collapse
    reward_tp = torch.where(targets == 1, 1.25, 0.0).to(device)
    reward_tn = torch.where(targets == 0, 0.02, 0.0).to(device)
    penalty_fp = torch.where(targets == 0, 0.02, 0.0).to(device)
    penalty_fn = torch.where(targets == 1, 1.00, 0.0).to(device)
    utility_term = (
        reward_tp * probs +
        reward_tn * (1 - probs) -
        penalty_fp * probs -
        penalty_fn * (1 - probs)
    )
    utility_term = (utility_term * time_weights * masks).sum() / (masks.sum() + 1e-8)

    aux_loss = torch.tensor(0.0, device=device)
    if sofa_pred is not None and sofa_targets is not None:
        sofa_pred = torch.nan_to_num(sofa_pred, nan=0.0, posinf=20.0, neginf=-20.0)
        sofa_targets = torch.nan_to_num(sofa_targets, nan=0.0, posinf=20.0, neginf=0.0)
        aux_loss = ((sofa_pred - sofa_targets) ** 2 * masks).sum() / (masks.sum() + 1e-8)

    total_loss = focal_loss - utility_lambda * utility_term + aux_lambda * aux_loss
    return torch.nan_to_num(total_loss, nan=0.0, posinf=1e3, neginf=-1e3)


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

            logits = model(x, mask, hours=hours)
            probs = torch.nan_to_num(torch.sigmoid(logits), nan=0.0, posinf=1.0, neginf=0.0).cpu().numpy()

            for i in range(len(probs)):
                vl = int(mask_np[i].sum())
                if vl == 0:
                    continue
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
    if len(np.unique(all_ts_labels)) > 1:
        m['timestep_auroc'] = roc_auc_score(all_ts_labels, all_ts_probs)
        m['timestep_auprc'] = average_precision_score(all_ts_labels, all_ts_probs)
    else:
        m['timestep_auroc'] = 0.5
        m['timestep_auprc'] = 0.0

    if len(np.unique(all_pt_outcomes)) > 1:
        m['patient_auroc'] = roc_auc_score(all_pt_outcomes, all_pt_probs)
        m['patient_auprc'] = average_precision_score(all_pt_outcomes, all_pt_probs)
    else:
        m['patient_auroc'] = 0.5
        m['patient_auprc'] = 0.0

    all_pt_probs_prefix = np.array(all_pt_probs_prefix)
    if len(np.unique(all_pt_outcomes)) > 1:
        m['patient_auroc_prefix'] = roc_auc_score(all_pt_outcomes, all_pt_probs_prefix)
        m['patient_auprc_prefix'] = average_precision_score(all_pt_outcomes, all_pt_probs_prefix)
    else:
        m['patient_auroc_prefix'] = 0.5
        m['patient_auprc_prefix'] = 0.0

    m['n_pos_ts'] = int(all_ts_labels.sum())
    m['n_total_ts'] = len(all_ts_labels)
    m['pos_rate'] = all_ts_labels.mean()
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

            logits = model(x, mask, hours=hours)
            probs = torch.sigmoid(logits).cpu().numpy()

            for i in range(len(probs)):
                vl = int(mask_np[i].sum())
                if vl == 0:
                    continue
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


def find_optimal_utility_threshold_on_val(model, val_loader, device):
    """Grid-search threshold directly on normalized utility (0.05..0.95, step 0.01)."""
    model.eval()
    patient_probs, patient_labels = [], []

    with torch.no_grad():
        for batch in val_loader:
            x = batch['x'].to(device, non_blocking=True)
            mask = batch['mask'].to(device, non_blocking=True)
            hours = batch['hours'].to(device, non_blocking=True)
            y = batch['label'].cpu().numpy()
            mask_np = batch['mask'].cpu().numpy()
            logits = model(x, mask, hours=hours)
            probs = torch.sigmoid(logits).cpu().numpy()
            for i in range(len(probs)):
                vl = int(mask_np[i].sum())
                if vl == 0:
                    continue
                patient_probs.append(probs[i, :vl])
                patient_labels.append(y[i, :vl])

    best_thr, best_util = 0.5, -1e9
    sweep_rows = []
    for thr in np.arange(0.05, 0.951, 0.01):
        pred_labels = [(p >= thr).astype(int) for p in patient_probs]
        norm_util, obs_util, _ = compute_normalized_utility(patient_labels, pred_labels)
        sweep_rows.append({'threshold': float(thr), 'normalized_utility': float(norm_util), 'observed_utility': float(obs_util)})
        if norm_util > best_util:
            best_util = norm_util
            best_thr = float(thr)

    return best_thr, pd.DataFrame(sweep_rows).sort_values('threshold')


# ============================================================================
# PHYSIONET UTILITY SCORE
# ============================================================================

def compute_prediction_utility(labels, predictions,
                               dt_early=-12, dt_optimal=-6, dt_late=3.0,
                               max_u_tp=1, min_u_fn=-2, u_fp=-0.05, u_tn=0):
    if np.any(labels):
        is_septic = True
        # C5 (verified): SepsisLabel is the standard PhysioNet monotonic step
        # label (1 starting onset-6h). Official scorer recovers clinical onset
        # as first-positive-index - dt_optimal (= +6h). Labels confirmed
        # monotonic 0..01..1 across all positive patients in the cache.
        t_sepsis = np.argmax(labels) - dt_optimal
    else:
        is_septic = False
        t_sepsis = float('inf')

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
                if t <= t_sepsis + dt_optimal:
                    u[t] = max(m_1 * (t - t_sepsis) + b_1, u_fp)
                elif t <= t_sepsis + dt_late:
                    u[t] = m_2 * (t - t_sepsis) + b_2
            elif is_septic and not predictions[t]:
                if t <= t_sepsis + dt_optimal:
                    u[t] = 0
                elif t <= t_sepsis + dt_late:
                    u[t] = m_3 * (t - t_sepsis) + b_3
            elif not is_septic and predictions[t]:
                u[t] = u_fp
            else:
                u[t] = u_tn
    return np.sum(u)


def compute_normalized_utility(true_labels_list, pred_labels_list):
    dt_early, dt_optimal, dt_late = -12, -6, 3
    max_u_tp, min_u_fn, u_fp, u_tn = 1, -2, -0.05, 0

    observed, best, inaction = [], [], []
    for labels, preds in zip(true_labels_list, pred_labels_list):
        n = len(labels)
        obs = compute_prediction_utility(labels, preds, dt_early, dt_optimal, dt_late,
                                         max_u_tp, min_u_fn, u_fp, u_tn)
        best_preds = np.zeros(n)
        if np.any(labels):
            t_s = np.argmax(labels) - dt_optimal
            s_idx = max(0, t_s + dt_early)
            e_idx = min(t_s + dt_late + 1, n)
            best_preds[s_idx:e_idx] = 1
        best_u = compute_prediction_utility(labels, best_preds, dt_early, dt_optimal, dt_late,
                                            max_u_tp, min_u_fn, u_fp, u_tn)
        inaction_u = compute_prediction_utility(labels, np.zeros(n), dt_early, dt_optimal, dt_late,
                                                max_u_tp, min_u_fn, u_fp, u_tn)
        observed.append(obs)
        best.append(best_u)
        inaction.append(inaction_u)

    sum_obs, sum_best, sum_inact = np.sum(observed), np.sum(best), np.sum(inaction)
    if sum_best == sum_inact:
        return 0.0, sum_obs, sum_best
    return (sum_obs - sum_inact) / (sum_best - sum_inact), sum_obs, sum_best


# ============================================================================
# PATIENT-LEVEL EVALUATION
# ============================================================================

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

            logits = model(x, mask_t, hours=hours)
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

                if has_sepsis:
                    onset_idx = np.where(p_labels == 1)[0]
                    onset = onset_idx[0] if len(onset_idx) > 0 else -1
                    if onset == -1:
                        has_sepsis = False
                else:
                    onset = -1

                patient_utility = compute_prediction_utility(p_labels, p_preds)

                if has_sepsis:
                    detected = first_alarm >= 0
                    hours_early = (onset - first_alarm) if detected else None
                    false_alarm = None
                else:
                    detected = None
                    hours_early = None
                    false_alarm = first_alarm >= 0

                pid_val = pids[i]
                if isinstance(pid_val, (np.ndarray, torch.Tensor)):
                    pid_val = pid_val.item()

                patient_results.append({
                    'patient_id': str(pid_val),
                    'has_sepsis': bool(has_sepsis),
                    'detected': bool(detected) if detected is not None else None,
                    'hours_early': float(hours_early) if hours_early is not None else None,
                    'false_alarm': bool(false_alarm) if false_alarm is not None else None,
                    'max_prob': float(np.nan_to_num(p_probs, nan=0.0, posinf=1.0, neginf=0.0).max()),
                    'onset_hour': int(onset) if has_sepsis and onset >= 0 else None,
                    'alarm_hour': int(first_alarm) if first_alarm >= 0 else None,
                    'utility': float(patient_utility)
                })

    results_df = pd.DataFrame(patient_results)
    norm_util, obs_util, best_util = compute_normalized_utility(true_labels_list, pred_labels_list)

    sepsis_df = results_df[results_df['has_sepsis'] == True]
    nonsepsis_df = results_df[results_df['has_sepsis'] == False]

    metrics = {}
    metrics['normalized_utility'] = norm_util
    metrics['observed_utility'] = obs_util
    metrics['best_utility'] = best_util

    if len(sepsis_df) > 0:
        detected_count = sepsis_df['detected'].sum()
        metrics['sensitivity'] = detected_count / len(sepsis_df)
        metrics['missed_sepsis'] = len(sepsis_df) - detected_count
        early = sepsis_df[sepsis_df['hours_early'].notna() & (sepsis_df['hours_early'] > 0)]
        metrics['pct_early'] = len(early) / len(sepsis_df) if len(sepsis_df) > 0 else 0
        metrics['mean_hours_early'] = early['hours_early'].mean() if len(early) > 0 else 0
        metrics['median_hours_early'] = early['hours_early'].median() if len(early) > 0 else 0
    else:
        metrics['sensitivity'] = metrics['missed_sepsis'] = 0
        metrics['pct_early'] = metrics['mean_hours_early'] = metrics['median_hours_early'] = 0

    if len(nonsepsis_df) > 0:
        tn_count = (nonsepsis_df['false_alarm'] == False).sum()
        metrics['specificity'] = tn_count / len(nonsepsis_df)
        metrics['false_alarms'] = (nonsepsis_df['false_alarm'] == True).sum()
    else:
        metrics['specificity'] = 0
        metrics['false_alarms'] = 0

    metrics['total_patients'] = len(results_df)
    metrics['sepsis_patients'] = len(sepsis_df)
    metrics['nonsepsis_patients'] = len(nonsepsis_df)

    return metrics, results_df


# ============================================================================
# ENHANCEMENT 8: VALIDATION-QUANTILE THRESHOLD
# ============================================================================

class ConformalPredictor:
    """Select a threshold from negative validation probabilities.

    Kept under the historical class name for checkpoint-run compatibility.
    This is not a conformal prediction set and has no coverage guarantee.
    """

    def __init__(self, alpha=0.10):
        self.alpha = alpha
        self.cal_scores = None
        self.threshold = None

    def calibrate(self, model, cal_loader, device):
        """Compute non-conformity scores on calibration set."""
        model.eval()
        scores_pos, scores_neg = [], []

        with torch.no_grad():
            for batch in cal_loader:
                x = batch['x'].to(device)
                mask = batch['mask'].to(device)
                hours = batch['hours'].to(device)
                y = batch['label'].cpu().numpy()
                mask_np = batch['mask'].cpu().numpy()

                logits = model(x, mask, hours=hours)
                probs = torch.nan_to_num(torch.sigmoid(logits), nan=0.0, posinf=1.0, neginf=0.0).cpu().numpy()

                for i in range(len(probs)):
                    vl = int(mask_np[i].sum())
                    for t in range(vl):
                        if y[i, t] == 1:
                            scores_pos.append(1 - probs[i, t])
                        else:
                            scores_neg.append(probs[i, t])

        # Compute a high quantile of negative validation probabilities.
        all_scores = np.nan_to_num(np.array(scores_neg), nan=0.0, posinf=1.0, neginf=0.0)
        n = len(all_scores)
        if n == 0:
            self.threshold = 0.5
            return self.threshold
        q = min(np.ceil((n + 1) * (1 - self.alpha)) / n, 1.0)
        self.threshold = float(np.quantile(all_scores, q))
        print(f"  Validation-quantile threshold (alpha={self.alpha}): {self.threshold:.4f}")
        print(f"  Calibration scores: {len(scores_pos)} positive, {len(scores_neg)} negative")
        return self.threshold

    def predict(self, probs):
        """Apply the selected validation-quantile threshold."""
        return (probs >= self.threshold).astype(int)


def conformal_alpha_sweep(model, val_loader, device,
                          alphas=np.arange(0.05, 0.251, 0.01),
                          min_sensitivity=0.85):
    rows = []
    best = None
    for alpha in alphas:
        conformal = ConformalPredictor(alpha=float(alpha))
        thr = conformal.calibrate(model, val_loader, device)
        # C4: select the operating alpha on VALIDATION (not test) to avoid
        # selection-on-test bias.
        metrics, _ = evaluate_patient_level(model, val_loader, device, thr)
        row = {
            'alpha': float(alpha),
            'threshold': float(thr),
            'sensitivity': float(metrics['sensitivity']),
            'specificity': float(metrics['specificity']),
            'false_alarms': int(metrics['false_alarms']),
            'normalized_utility': float(metrics['normalized_utility']),
        }
        rows.append(row)
        if row['sensitivity'] >= min_sensitivity:
            if best is None or row['specificity'] > best['specificity'] or (
                row['specificity'] == best['specificity'] and row['normalized_utility'] > best['normalized_utility']
            ):
                best = row

    sweep_df = pd.DataFrame(rows)
    if best is None and len(rows) > 0:
        best = max(rows, key=lambda r: r['normalized_utility'])
    return sweep_df, best


# ============================================================================
# ENHANCEMENT 9: BOOTSTRAP CONFIDENCE INTERVALS
# ============================================================================

def bootstrap_ci(y_true, y_scores, metric_fn, n_bootstrap=1000, ci=0.95):
    """Compute bootstrap confidence intervals for a metric."""
    rng = np.random.RandomState(42)
    n = len(y_true)
    scores = []
    for _ in range(n_bootstrap):
        idx = rng.choice(n, n, replace=True)
        if len(np.unique(y_true[idx])) < 2:
            continue
        try:
            scores.append(metric_fn(y_true[idx], y_scores[idx]))
        except:
            continue
    if len(scores) == 0:
        return 0, 0, 0
    scores = np.array(scores)
    alpha = (1 - ci) / 2
    return np.mean(scores), np.percentile(scores, 100 * alpha), np.percentile(scores, 100 * (1 - alpha))


# ============================================================================
# ENHANCEMENT 7: INTERPRETABILITY — FEATURE IMPORTANCE
# ============================================================================

def compute_feature_importance(model, test_loader, device, feature_names, n_samples=200):
    """Permutation-based feature importance.
    For each feature, permute its values across patients and measure
    the drop in patient-level AUROC."""
    print("\n--- FEATURE IMPORTANCE (Permutation) ---")

    model.eval()

    # Get baseline predictions
    baseline_probs, baseline_outcomes = [], []
    all_x, all_mask, all_hours, all_outcomes_list = [], [], [], []

    with torch.no_grad():
        count = 0
        for batch in test_loader:
            x = batch['x']
            mask = batch['mask']
            hours = batch['hours']
            outcomes = batch['patient_outcome'].cpu().numpy()

            logits = model(x.to(device), mask.to(device), hours=hours.to(device))
            probs = torch.nan_to_num(torch.sigmoid(logits), nan=0.0, posinf=1.0, neginf=0.0).cpu().numpy()
            mask_np = mask.cpu().numpy()

            for i in range(len(probs)):
                vl = int(mask_np[i].sum())
                if vl > 0:
                    baseline_probs.append(probs[i, :vl].max())
                    baseline_outcomes.append(outcomes[i])

            all_x.append(x)
            all_mask.append(mask)
            all_hours.append(hours)
            all_outcomes_list.append(outcomes)
            count += len(x)
            if count >= n_samples:
                break

    baseline_probs = np.nan_to_num(np.array(baseline_probs), nan=0.0, posinf=1.0, neginf=0.0)
    baseline_outcomes = np.array(baseline_outcomes)

    if len(np.unique(baseline_outcomes)) < 2:
        print("  Insufficient class diversity for importance analysis")
        return {}

    baseline_auc = roc_auc_score(baseline_outcomes, baseline_probs)

    # Permute each feature and measure AUC drop
    importance = {}
    n_features = min(len(feature_names), 30)  # Top 30 features

    for feat_idx in range(n_features):
        perm_probs, perm_outcomes = [], []

        with torch.no_grad():
            for x, mask, hours, outcomes in zip(all_x, all_mask, all_hours, all_outcomes_list):
                x_perm = x.clone()
                # Permute feature across batch
                perm_idx = torch.randperm(x_perm.size(0))
                x_perm[:, :, feat_idx] = x_perm[perm_idx, :, feat_idx]

                logits = model(x_perm.to(device), mask.to(device), hours=hours.to(device))
                probs = torch.nan_to_num(torch.sigmoid(logits), nan=0.0, posinf=1.0, neginf=0.0).cpu().numpy()
                mask_np = mask.cpu().numpy()

                for i in range(len(probs)):
                    vl = int(mask_np[i].sum())
                    if vl > 0:
                        perm_probs.append(probs[i, :vl].max())
                        perm_outcomes.append(outcomes[i])

        perm_probs = np.nan_to_num(np.array(perm_probs), nan=0.0, posinf=1.0, neginf=0.0)
        perm_outcomes = np.array(perm_outcomes)

        if len(np.unique(perm_outcomes)) >= 2:
            perm_auc = roc_auc_score(perm_outcomes, perm_probs)
            importance[feature_names[feat_idx]] = baseline_auc - perm_auc

    # Sort and display
    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    print(f"\n  Baseline Patient AUROC: {baseline_auc:.4f}")
    print(f"  {'Feature':<30} {'AUC Drop':>10} {'Rank':>6}")
    print("  " + "-" * 48)
    for rank, (feat, drop) in enumerate(sorted_imp[:20], 1):
        bar = '+' * max(1, int(drop * 200))
        print(f"  {feat:<30} {drop:>10.4f} {rank:>6}  {bar}")

    return dict(sorted_imp)


# ============================================================================
# ENHANCEMENT 6: ABLATION STUDY
# ============================================================================

def run_ablation_study(df, base_feature_cols, eng_feature_cols, all_feature_cols,
                       train_pids, val_pids, test_pids,
                       epochs=20, batch_size=256):
    """Systematic ablation study testing each enhancement."""

    print("\n" + "=" * 75)
    print("ABLATION STUDY")
    print("=" * 75)

    device = setup_colab_environment()
    ablation_results = {}

    configs = [
        {
            'name': 'A: Paper1 Baseline (vanilla Transformer)',
            'model_class': BaselineSepsisTransformer,
            'feature_cols': base_feature_cols,
            'use_missingness': False,
            'use_cnn': False,
            'use_continuous_time': False,
        },
        {
            'name': 'B: + Temporal features',
            'model_class': BaselineSepsisTransformer,
            'feature_cols': all_feature_cols,
            'use_missingness': False,
            'use_cnn': False,
            'use_continuous_time': False,
        },
        {
            'name': 'C: + Missingness indicators',
            'model_class': BaselineSepsisTransformer,
            'feature_cols': all_feature_cols,
            'use_missingness': True,
            'use_cnn': False,
            'use_continuous_time': False,
        },
        {
            'name': 'D: + CNN local encoder',
            'model_class': EnhancedSepsisTransformer,
            'feature_cols': all_feature_cols,
            'use_missingness': True,
            'use_cnn': True,
            'use_continuous_time': False,
        },
        {
            'name': 'E: Full model (+ continuous-time PE)',
            'model_class': EnhancedSepsisTransformer,
            'feature_cols': all_feature_cols,
            'use_missingness': True,
            'use_cnn': True,
            'use_continuous_time': True,
        },
    ]

    for cfg in configs:
        print(f"\n{'—' * 60}")
        print(f"  {cfg['name']}")
        print(f"{'—' * 60}")

        clear_gpu_memory()

        # Prepare data
        preprocessor = EnhancedSepsisPreprocessor(
            df, cfg['feature_cols'], max_hours=120,
            use_missingness=cfg['use_missingness']
        )
        n_feat = preprocessor.get_total_features()

        X_train, y_train, m_train, o_train, p_train, h_train, s_train = preprocessor.prepare_sequences(train_pids)
        X_val, y_val, m_val, o_val, p_val, h_val, s_val = preprocessor.prepare_sequences(val_pids)
        X_test, y_test, m_test, o_test, p_test, h_test, s_test = preprocessor.prepare_sequences(test_pids)

        preprocessor.fit_normalization(X_train)
        X_train = preprocessor.normalize(X_train)
        X_val = preprocessor.normalize(X_val)
        X_test = preprocessor.normalize(X_test)

        train_ds = EnhancedSepsisDataset(X_train, y_train, m_train, o_train, p_train, h_train, s_train)
        val_ds = EnhancedSepsisDataset(X_val, y_val, m_val, o_val, p_val, h_val, s_val)
        test_ds = EnhancedSepsisDataset(X_test, y_test, m_test, o_test, p_test, h_test, s_test)

        train_loader = DataLoader(train_ds, **build_loader_kwargs(batch_size, shuffle=True))
        val_loader = DataLoader(val_ds, **build_loader_kwargs(batch_size, shuffle=False))
        test_loader = DataLoader(test_ds, **build_loader_kwargs(batch_size, shuffle=False))

        # Initialize model
        if cfg['model_class'] == EnhancedSepsisTransformer:
            model = EnhancedSepsisTransformer(
                num_features=n_feat, d_model=256, n_heads=8, num_layers=4,
                dim_feedforward=512, dropout=0.2,
                use_cnn=cfg['use_cnn'],
                use_continuous_time=cfg['use_continuous_time']
            ).to(device)
        else:
            model = BaselineSepsisTransformer(
                num_features=n_feat, d_model=256, n_heads=8, num_layers=4,
                dim_feedforward=512, dropout=0.2
            ).to(device)

        n_params = sum(p.numel() for p in model.parameters())
        print(f"  Features: {n_feat}, Parameters: {n_params:,}")

        # Train
        use_amp = torch.cuda.is_available()
        optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        best_val_auc = 0
        best_state = None
        patience_count = 0

        for epoch in range(epochs):
            model.train()
            total_loss = 0
            for batch in train_loader:
                x = batch['x'].to(device, non_blocking=True)
                y = batch['label'].to(device, non_blocking=True)
                mask = batch['mask'].to(device, non_blocking=True)
                hours = batch['hours'].to(device, non_blocking=True)

                optimizer.zero_grad()
                with (torch.amp.autocast('cuda', dtype=torch.bfloat16) if use_amp else contextlib.nullcontext()):
                    logits = model(x, mask, hours=hours)
                    loss = improved_sepsis_loss(logits, y, mask)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

                total_loss += loss.item()
            scheduler.step()

            if (epoch + 1) % 2 == 0:
                val_m = compute_auc_metrics(model, val_loader, device)
                if val_m['patient_auroc'] > best_val_auc:
                    best_val_auc = val_m['patient_auroc']
                    best_state = {k: v.clone() for k, v in model.state_dict().items()}
                    patience_count = 0
                else:
                    patience_count += 1
                if patience_count >= 5:
                    break

        if best_state:
            model.load_state_dict(best_state)

        # Evaluate
        test_m = compute_auc_metrics(model, test_loader, device)
        threshold, _ = find_optimal_utility_threshold_on_val(model, val_loader, device)
        clin_m, _ = evaluate_patient_level(model, test_loader, device, threshold)

        result = {
            'patient_auroc': test_m['patient_auroc'],
            'patient_auprc': test_m['patient_auprc'],
            'timestep_auroc': test_m['timestep_auroc'],
            'timestep_auprc': test_m['timestep_auprc'],
            'utility': clin_m['normalized_utility'],
            'sensitivity': clin_m['sensitivity'],
            'specificity': clin_m['specificity'],
            'n_params': n_params,
        }
        ablation_results[cfg['name']] = result

        print(f"  Patient AUROC: {result['patient_auroc']:.4f}")
        print(f"  Timestep AUROC: {result['timestep_auroc']:.4f}")
        print(f"  Utility: {result['utility']:.4f}")
        print(f"  Sensitivity: {result['sensitivity']:.1%}, Specificity: {result['specificity']:.1%}")

    # Summary table
    print("\n" + "=" * 75)
    print("ABLATION STUDY SUMMARY")
    print("=" * 75)
    print(f"\n{'Configuration':<42} {'P-AUROC':>8} {'T-AUROC':>8} {'P-AUPRC':>8} {'Utility':>8} {'Sens':>7} {'Spec':>7} {'Params':>10}")
    print("-" * 105)
    for name, r in ablation_results.items():
        print(f"{name:<42} {r['patient_auroc']:>8.4f} {r['timestep_auroc']:>8.4f} "
              f"{r['patient_auprc']:>8.4f} {r['utility']:>8.4f} {r['sensitivity']:>6.1%} "
              f"{r['specificity']:>6.1%} {r['n_params']:>10,}")

    return ablation_results


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_enhanced_sepsis_prediction(df, feature_cols, test_size=0.175, val_size=0.125,
                                   epochs=30, batch_size=256,
                                   run_ablation=True, ablation_epochs=20,
                                   utility_lambda=0.15, aux_lambda=0.20):

    output_dir = os.getenv('PAPER1_SAVE_DIR', 'outputs/paper1')
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 75)
    print("PAPER1 CNN-TRANSFORMER FOR EARLY SEPSIS PREDICTION")
    print("=" * 75)

    # --- Feature engineering ---
    print("\n[1/9] Feature engineering...")
    base_feature_cols = feature_cols.copy()
    df_eng, eng_cols = engineer_temporal_features(df, base_feature_cols)
    all_feature_cols = base_feature_cols + eng_cols
    print(f"  Base features: {len(base_feature_cols)}")
    print(f"  Engineered features: {len(eng_cols)}")
    print(f"  Total features: {len(all_feature_cols)}")

    # --- Data validation ---
    print("\n[2/9] Validating data...")
    patient_outcomes = patient_outcomes_within_horizon(df_eng, max_hours=120)
    total_patients = len(patient_outcomes)
    sepsis_count = (patient_outcomes == 1).sum()
    print(f"  Total patients: {total_patients:,}")
    print(f"  Sepsis patients: {sepsis_count:,} ({100*sepsis_count/total_patients:.1f}%)")

    # --- 3-way split ---
    print("\n[3/9] Splitting data (train/val/test)...")
    all_pids = df_eng['Patient_ID'].unique()

    train_val_pids, test_pids = train_test_split(
        all_pids, test_size=test_size, random_state=42,
        stratify=patient_outcomes.loc[all_pids].values
    )
    tv_outcomes = patient_outcomes.loc[train_val_pids]
    val_frac = val_size / (1 - test_size)
    train_pids, val_pids = train_test_split(
        train_val_pids, test_size=val_frac, random_state=42,
        stratify=tv_outcomes.values
    )
    print(f"  Train: {len(train_pids)}, Val: {len(val_pids)}, Test: {len(test_pids)}")
    print(f"  Sepsis — Train: {patient_outcomes.loc[train_pids].sum()}, "
          f"Val: {patient_outcomes.loc[val_pids].sum()}, "
          f"Test: {patient_outcomes.loc[test_pids].sum()}")

    # --- Run ablation study first ---
    if run_ablation:
        ablation_results = run_ablation_study(
            df_eng, base_feature_cols, eng_cols, all_feature_cols,
            train_pids, val_pids, test_pids,
            epochs=ablation_epochs, batch_size=batch_size
        )

    # --- Prepare sequences for full model ---
    print("\n" + "=" * 75)
    print("FULL MODEL TRAINING")
    print("=" * 75)

    print("\n[4/9] Preparing sequences with missingness indicators...")
    preprocessor = EnhancedSepsisPreprocessor(
        df_eng, all_feature_cols, max_hours=120, use_missingness=True
    )
    n_total_features = preprocessor.get_total_features()
    print(f"  Total input features (incl. missingness): {n_total_features}")

    cache_path = os.path.join(output_dir, 'preprocessed_data_cache_paper1.npz')
    cache_loaded = False
    if os.path.exists(cache_path):
        try:
            cache = np.load(cache_path, allow_pickle=True)
            X_train, y_train, m_train, o_train, h_train, s_train = cache['X_tr'], cache['y_tr'], cache['m_tr'], cache['o_tr'], cache['h_tr'], cache['s_tr']
            X_val, y_val, m_val, o_val, h_val, s_val = cache['X_va'], cache['y_va'], cache['m_va'], cache['o_va'], cache['h_va'], cache['s_va']
            X_test, y_test, m_test, o_test, h_test, s_test = cache['X_te'], cache['y_te'], cache['m_te'], cache['o_te'], cache['h_te'], cache['s_te']
            p_train, p_val, p_test = cache['p_tr'].tolist(), cache['p_va'].tolist(), cache['p_te'].tolist()
            preprocessor.feature_means = cache['feature_means']
            preprocessor.feature_stds = cache['feature_stds']

            o_tr_expected = ((y_train * m_train).max(axis=1) > 0).astype(int)
            o_va_expected = ((y_val * m_val).max(axis=1) > 0).astype(int)
            o_te_expected = ((y_test * m_test).max(axis=1) > 0).astype(int)

            valid_cache = (
                X_train.shape[0] == len(train_pids) and
                X_val.shape[0] == len(val_pids) and
                X_test.shape[0] == len(test_pids) and
                X_train.shape[2] == n_total_features and
                np.array_equal(np.array(p_train), np.array(train_pids)) and
                np.array_equal(np.array(p_val), np.array(val_pids)) and
                np.array_equal(np.array(p_test), np.array(test_pids)) and
                np.array_equal(o_train.astype(int), o_tr_expected) and
                np.array_equal(o_val.astype(int), o_va_expected) and
                np.array_equal(o_test.astype(int), o_te_expected)
            )
            if not valid_cache:
                raise ValueError(
                    f"cache mismatch: got train/val/test={X_train.shape[0]}/{X_val.shape[0]}/{X_test.shape[0]}, "
                    f"expected {len(train_pids)}/{len(val_pids)}/{len(test_pids)}, features={X_train.shape[2]} vs {n_total_features}"
                )

            cache_loaded = True
            print(f"  Loaded cache: {cache_path}")
        except Exception as e:
            print(f"  Cache load failed ({e}); rebuilding...")

    if not cache_loaded:
        X_train, y_train, m_train, o_train, p_train, h_train, s_train = preprocessor.prepare_sequences(train_pids)
        X_val, y_val, m_val, o_val, p_val, h_val, s_val = preprocessor.prepare_sequences(val_pids)
        X_test, y_test, m_test, o_test, p_test, h_test, s_test = preprocessor.prepare_sequences(test_pids)

        print("\n[5/9] Normalizing features...")
        preprocessor.fit_normalization(X_train)
        X_train = preprocessor.normalize(X_train)
        X_val = preprocessor.normalize(X_val)
        X_test = preprocessor.normalize(X_test)

        np.savez_compressed(
            cache_path,
            X_tr=X_train, y_tr=y_train, m_tr=m_train, o_tr=o_train, h_tr=h_train, s_tr=s_train, p_tr=np.array(p_train, dtype=object),
            X_va=X_val, y_va=y_val, m_va=m_val, o_va=o_val, h_va=h_val, s_va=s_val, p_va=np.array(p_val, dtype=object),
            X_te=X_test, y_te=y_test, m_te=m_test, o_te=o_test, h_te=h_test, s_te=s_test, p_te=np.array(p_test, dtype=object),
            feature_means=preprocessor.feature_means, feature_stds=preprocessor.feature_stds
        )
        print(f"  Saved cache: {cache_path}")

    print(f"  Train shape: {X_train.shape}")
    print(f"  Sepsis rate — Train: {o_train.mean():.1%}, Val: {o_val.mean():.1%}, Test: {o_test.mean():.1%}")

    # --- Create dataloaders ---
    print("\n[6/9] Creating dataloaders...")
    train_ds = EnhancedSepsisDataset(X_train, y_train, m_train, o_train, p_train, h_train, s_train)
    val_ds = EnhancedSepsisDataset(X_val, y_val, m_val, o_val, p_val, h_val, s_val)
    test_ds = EnhancedSepsisDataset(X_test, y_test, m_test, o_test, p_test, h_test, s_test)

    train_loader = DataLoader(train_ds, **build_loader_kwargs(batch_size, shuffle=True))
    val_loader = DataLoader(val_ds, **build_loader_kwargs(batch_size, shuffle=False))
    test_loader = DataLoader(test_ds, **build_loader_kwargs(batch_size, shuffle=False))

    # --- Initialize full model ---
    print("\n[7/9] Initializing enhanced model...")
    device = setup_colab_environment()

    model = EnhancedSepsisTransformer(
        num_features=n_total_features,
        d_model=256, n_heads=8, num_layers=4,
        dim_feedforward=512, dropout=0.2,
        use_cnn=True,
        use_continuous_time=True
    ).to(device)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Parameters: {n_params:,}")

    disable_amp = os.getenv('PAPER1_DISABLE_AMP', '0').strip().lower() in ('1', 'true', 'yes')
    use_amp = torch.cuda.is_available() and not disable_amp
    if use_amp:
        print("  Using AMP (bf16 mixed precision)")

    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    # --- Training ---
    print("\n[8/9] Training with validation monitoring...")
    print(f"{'Epoch':>6} {'Loss':>10} {'Val P-AUC':>11} {'Val T-AUC':>11} {'Time':>8}")
    print("-" * 52)

    best_val_auc = 0
    best_model_state = None
    patience = 7
    wait = 0
    train_losses = []
    val_aucs = []

    for epoch in range(epochs):
        t0 = time.time()

        model.train()
        total_loss = 0
        for batch in train_loader:
            x = batch['x'].to(device, non_blocking=True)
            y = batch['label'].to(device, non_blocking=True)
            mask = batch['mask'].to(device, non_blocking=True)
            hours = batch['hours'].to(device, non_blocking=True)
            sofa = batch['sofa'].to(device, non_blocking=True)

            optimizer.zero_grad()
            with (torch.amp.autocast('cuda', dtype=torch.bfloat16) if use_amp else contextlib.nullcontext()):
                logits, sofa_pred = model(x, mask, hours=hours, return_aux=True)
                loss = improved_sepsis_loss(
                    logits, y, mask,
                    utility_lambda=utility_lambda,
                    aux_lambda=aux_lambda,
                    sofa_pred=sofa_pred,
                    sofa_targets=sofa
                )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item()

        scheduler.step()
        avg_loss = total_loss / len(train_loader)
        train_losses.append(avg_loss)
        elapsed = time.time() - t0

        if (epoch + 1) % 2 == 0:
            val_m = compute_auc_metrics(model, val_loader, device)
            val_pauc = val_m['patient_auroc']
            val_tauc = val_m['timestep_auroc']
            val_aucs.append({'epoch': epoch+1, 'patient': val_pauc, 'timestep': val_tauc})

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
                print(f"\n  Early stopping at epoch {epoch+1} (no improvement for {patience} checks)")
                break
        else:
            print(f"{epoch+1:6d} {avg_loss:10.4f} {'--':>11} {'--':>11} {elapsed:7.1f}s")

        if (epoch + 1) % 10 == 0:
            clear_gpu_memory()

    if best_model_state:
        model.load_state_dict(best_model_state)
    print(f"\n  Best validation Patient-AUC: {best_val_auc:.4f}")

    # ================================================================
    # FINAL EVALUATION
    # ================================================================
    print("\n[9/9] Final evaluation...")
    print("\n" + "=" * 75)
    print("FINAL EVALUATION ON TEST SET")
    print("=" * 75)

    # AUC metrics
    test_auc = compute_auc_metrics(model, test_loader, device)

    print(f"\n--- AUC METRICS ---")
    print(f"Patient-level AUROC:    {test_auc['patient_auroc']:.4f}  (whole-stay, optimistic)")
    print(f"Patient-level AUPRC:    {test_auc['patient_auprc']:.4f}  (whole-stay, optimistic)")
    print(f"Patient AUROC (prefix): {test_auc['patient_auroc_prefix']:.4f}  (<=onset, honest early-warning)")
    print(f"Patient AUPRC (prefix): {test_auc['patient_auprc_prefix']:.4f}  (<=onset, honest early-warning)")
    print(f"Timestep-level AUROC:   {test_auc['timestep_auroc']:.4f}")
    print(f"Timestep-level AUPRC:   {test_auc['timestep_auprc']:.4f}")
    print(f"Positive timesteps:     {test_auc['n_pos_ts']:,} / {test_auc['n_total_ts']:,} ({100*test_auc['pos_rate']:.2f}%)")
    print(f"Sepsis patients:        {test_auc['n_sepsis_pt']} / {test_auc['n_total_pt']}")

    # Bootstrap CIs
    print(f"\n--- BOOTSTRAP 95% CONFIDENCE INTERVALS (n=1000) ---")
    pt_probs = test_auc['all_pt_probs']
    pt_outcomes = test_auc['all_pt_outcomes']

    auroc_mean, auroc_lo, auroc_hi = bootstrap_ci(pt_outcomes, pt_probs, roc_auc_score)
    auprc_mean, auprc_lo, auprc_hi = bootstrap_ci(pt_outcomes, pt_probs, average_precision_score)
    print(f"  Patient AUROC:  {auroc_mean:.4f} ({auroc_lo:.4f} - {auroc_hi:.4f})")
    print(f"  Patient AUPRC:  {auprc_mean:.4f} ({auprc_lo:.4f} - {auprc_hi:.4f})")

    # Threshold
    print(f"\n--- THRESHOLD SELECTION (utility sweep on validation set) ---")
    optimal_threshold, util_sweep_df = find_optimal_utility_threshold_on_val(model, val_loader, device)
    util_sweep_df.to_csv(os.path.join(output_dir, 'paper1_validation_utility_sweep.csv'), index=False)
    print(f"Optimal threshold (max val utility): {optimal_threshold:.3f}")

    # Clinical metrics
    final_metrics, test_results = evaluate_patient_level(model, test_loader, device, optimal_threshold)

    print(f"\n--- PHYSIONET UTILITY SCORE ---")
    print(f"Normalized Utility:     {final_metrics['normalized_utility']:.4f}")
    print(f"Observed Utility:       {final_metrics['observed_utility']:.2f}")
    print(f"Best Possible Utility:  {final_metrics['best_utility']:.2f}")

    print(f"\n--- DETECTION PERFORMANCE ---")
    n_detected = final_metrics['sepsis_patients'] - final_metrics['missed_sepsis']
    print(f"Sensitivity:            {100*final_metrics['sensitivity']:.2f}%  ({n_detected:.0f}/{final_metrics['sepsis_patients']})")
    print(f"Specificity:            {100*final_metrics['specificity']:.2f}%")
    print(f"False alarms:           {final_metrics['false_alarms']:.0f}/{final_metrics['nonsepsis_patients']}")

    print(f"\n--- EARLY DETECTION ---")
    print(f"% Detected early:       {100*final_metrics['pct_early']:.1f}%")
    print(f"Mean hours early:       {final_metrics['mean_hours_early']:.1f}h")
    print(f"Median hours early:     {final_metrics['median_hours_early']:.1f}h")

    # --- Validation-quantile threshold ---
    print(f"\n--- VALIDATION-QUANTILE THRESHOLD ---")
    conformal = ConformalPredictor(alpha=0.10)
    conformal_threshold = conformal.calibrate(model, val_loader, device)

    conf_metrics, conf_results = evaluate_patient_level(model, test_loader, device, conformal_threshold)
    print(f"  Quantile Sensitivity: {100*conf_metrics['sensitivity']:.2f}%")
    print(f"  Quantile Specificity: {100*conf_metrics['specificity']:.2f}%")
    print(f"  Quantile False Alarms: {conf_metrics['false_alarms']:.0f}/{conf_metrics['nonsepsis_patients']}")
    print(f"  Quantile Utility: {conf_metrics['normalized_utility']:.4f}")

    print(f"\n--- VALIDATION-QUANTILE ALPHA SWEEP (0.05 to 0.25) ---")
    alpha_sweep_df, best_alpha_row = conformal_alpha_sweep(model, val_loader, device)
    alpha_sweep_df.to_csv(os.path.join(output_dir, 'paper1_validation_quantile_sweep.csv'), index=False)
    if best_alpha_row is not None:
        print(f"  Best alpha (sens>=85% then max spec): {best_alpha_row['alpha']:.2f}")
        print(f"    threshold={best_alpha_row['threshold']:.4f}, sens={best_alpha_row['sensitivity']:.2%}, "
              f"spec={best_alpha_row['specificity']:.2%}, FP={best_alpha_row['false_alarms']}, "
              f"utility={best_alpha_row['normalized_utility']:.4f}")

    # --- Feature importance ---
    all_feature_names = all_feature_cols.copy()
    if preprocessor.use_missingness:
        all_feature_names += [f'{c}_missing' for c in preprocessor.miss_cols]
    try:
        importance = compute_feature_importance(model, test_loader, device, all_feature_names)
    except Exception as e:
        print(f"Feature importance skipped due to error: {e}")
        importance = {}

    # Example patients
    print(f"\n--- EXAMPLE PATIENTS ---")
    sepsis_df = test_results[test_results['has_sepsis'] == True]
    if len(sepsis_df) > 0:
        print("\nBest detections:")
        best = sepsis_df.nlargest(min(5, len(sepsis_df)), 'utility')
        print(best[['patient_id', 'onset_hour', 'alarm_hour', 'hours_early', 'utility', 'max_prob']].to_string(index=False))
        print("\nWorst/missed:")
        worst = sepsis_df.nsmallest(min(5, len(sepsis_df)), 'utility')
        print(worst[['patient_id', 'onset_hour', 'alarm_hour', 'hours_early', 'utility', 'max_prob']].to_string(index=False))

    # ================================================================
    # FINAL SUMMARY
    # ================================================================
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
    print(f"  Threshold:            {optimal_threshold:.3f}")
    print(f"  Parameters:           {n_params:,}")
    print(f"  Total features:       {n_total_features}")
    print("=" * 75)

    return model, preprocessor, test_auc, final_metrics, test_results, ablation_results if run_ablation else None


# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    set_seed(42)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing dataset file: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)

    print("=" * 75)
    print("SETUP")
    print("=" * 75)

    SAVE_PATH = os.path.join(os.getenv('PAPER1_SAVE_DIR', 'outputs/paper1'), '')

    # Define base features (same as Paper 1)
    # C3 feature audit: drop the stray duplicate index column ('...1'), the
    # composite deterioration scores that partially encode the target
    # (qSOFA/NEWS/SOFA/SIRS/APACHE), and pre-computed ratio columns that are
    # duplicated by the (causal) engineered shock_index / BUN_Creatinine_ratio.
    irrelevant_cols = ['Unnamed: 0', '...1', 'datetime', 'ICULOS', 'Unit1', 'Unit2',
                       'Apache_II_Score', 'SOFA_Score', 'SIRS',
                       'Incomplete_qSOFA_Score', 'NEWS_Score',
                       'Shock_Index', 'BUN_Creatinine_Ratio',
                       'Bilirubin_Creatinine_Ratio']

    feature_cols = [col for col in df.columns
                    if col not in ['Patient_ID', 'SepsisLabel', 'Hour'] + irrelevant_cols]

    print(f"Base features: {len(feature_cols)}")
    print(f"Total patients: {df['Patient_ID'].nunique():,}")
    print(f"Total rows: {len(df):,}")

    # Optional fast-mode overrides via environment variables
    max_patients = int(os.getenv('PAPER1_MAX_PATIENTS', '0'))
    run_ablation = os.getenv('PAPER1_RUN_ABLATION', '1').strip().lower() not in ('0', 'false', 'no')
    epochs = int(os.getenv('PAPER1_EPOCHS', '30'))
    ablation_epochs = int(os.getenv('PAPER1_ABLATION_EPOCHS', '20'))
    batch_size = int(os.getenv('PAPER1_BATCH_SIZE', '256'))
    utility_lambda = float(os.getenv('PAPER1_UTILITY_LAMBDA', '0.15'))
    aux_lambda = float(os.getenv('PAPER1_AUX_LAMBDA', '0.20'))

    if max_patients > 0:
        outcomes = patient_outcomes_within_horizon(df, max_hours=120)
        pos_ids = outcomes[outcomes == 1].index.tolist()
        neg_ids = outcomes[outcomes == 0].index.tolist()
        n_pos = min(len(pos_ids), max(1, int(max_patients * len(pos_ids) / len(outcomes))))
        n_neg = min(len(neg_ids), max_patients - n_pos)
        rng = np.random.RandomState(42)
        sel_pos = rng.choice(pos_ids, size=n_pos, replace=False).tolist() if n_pos > 0 else []
        sel_neg = rng.choice(neg_ids, size=n_neg, replace=False).tolist() if n_neg > 0 else []
        keep_ids = set(sel_pos + sel_neg)
        df_run = df[df['Patient_ID'].isin(keep_ids)].copy()
        print(f"Using subset for run: {df_run['Patient_ID'].nunique()} patients")
    else:
        df_run = df

    # Run enhanced model with ablation study
    results = run_enhanced_sepsis_prediction(
        df=df_run,
        feature_cols=feature_cols,
        test_size=0.175,
        val_size=0.125,
        epochs=epochs,
        batch_size=batch_size,
        run_ablation=run_ablation,
        ablation_epochs=ablation_epochs,
        utility_lambda=utility_lambda,
        aux_lambda=aux_lambda
    )

    model, preprocessor, auc_metrics, utility_metrics, test_results, ablation_results = results

    # Save results
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else '.', exist_ok=True)

    if test_results is not None:
        test_results.to_csv(SAVE_PATH + 'sepsis_enhanced_patient_results.csv', index=False)
        print(f"\nResults saved to: {SAVE_PATH}sepsis_enhanced_patient_results.csv")

    if ablation_results is not None:
        abl_df = pd.DataFrame(ablation_results).T
        abl_df.to_csv(SAVE_PATH + 'ablation_results.csv')
        print(f"Ablation saved to: {SAVE_PATH}ablation_results.csv")

    if model is not None:
        model_path = SAVE_PATH + 'sepsis_enhanced_transformer.pt'
        os.makedirs(os.path.dirname(model_path) if os.path.dirname(model_path) else '.', exist_ok=True)
        torch.save({
            'checkpoint_format': 'causal-v1',
            'model_state_dict': model.state_dict(),
            'auc_metrics': {k: v for k, v in auc_metrics.items() if k not in ['all_pt_probs', 'all_pt_outcomes']},
            'utility_metrics': utility_metrics,
            'feature_cols': feature_cols,
        }, model_path)
        print(f"Model saved to: {model_path}")

    clear_gpu_memory()
    print("\nDone.")


# ======================================================================

