"""Architecture classes retained from the supplied v8 embedded CNN code.
Training and evaluation use the common v9 protocol in v9_train.py.
"""
import math
import torch
from torch import nn
import torch.nn.functional as F

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
        return self.fusion(fused)

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
