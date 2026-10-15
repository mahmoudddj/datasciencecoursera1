"""Architecture classes retained from the supplied v8 embedded OSTA code.
Training and evaluation use the common v9 protocol in v9_train.py.
"""
import math
import torch
from torch import nn
import torch.nn.functional as F

def build_feature_to_organ_mapping(names):
    from v9_models import organ_mapping
    return organ_mapping(names)

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
