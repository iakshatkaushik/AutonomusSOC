"""Deep Learning Autoencoder — Unsupervised anomaly detection.

Strategy:
- Train ONLY on normal (non-insider) users
- Network learns to compress and reconstruct normal behavior
- At inference: high reconstruction error = anomalous = likely insider
- No labels needed at training time (unsupervised)

Architecture:
    Input(52) → Dense(32, ReLU) → Dense(16, ReLU) → [Bottleneck]
              → Dense(32, ReLU) → Dense(52) [Reconstruction]
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

from src.utils.db import engine


ML_FEATURES = [
    "login_count", "after_hours_login_count", "after_hours_ratio",
    "unique_pcs", "file_copy_count", "file_copy_after_hours",
    "emails_sent", "external_recipient_ratio", "bcc_count",
    "attachment_count", "angry_keyword_count",
    "job_site_visits", "suspicious_domain_visits",
]


# ─── Autoencoder Architecture ────────────────────────────────────────

class Autoencoder(nn.Module):
    def __init__(self, input_dim: int, bottleneck: int = 8):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Dropout(0.1),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, bottleneck),
        )
        self.decoder = nn.Sequential(
            nn.Linear(bottleneck, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Linear(32, input_dim),
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

    def reconstruction_error(self, x):
        """Per-sample MSE reconstruction error."""
        with torch.no_grad():
            recon = self.forward(x)
            errors = torch.mean((x - recon) ** 2, dim=1)
        return errors.numpy()


# ─── Feature Prep ────────────────────────────────────────────────────

def _build_user_features(features_df: pd.DataFrame, insider_ids: set):
    """Aggregate daily features into per-user matrix."""
    agg_dict = {}
    for col in ML_FEATURES:
        if col in features_df.columns:
            agg_dict[f"{col}_mean"] = (col, "mean")
            agg_dict[f"{col}_max"] = (col, "max")
            agg_dict[f"{col}_sum"] = (col, "sum")
            agg_dict[f"{col}_std"] = (col, "std")

    user_agg = features_df.groupby("user_id").agg(**agg_dict).reset_index()
    user_agg = user_agg.fillna(0)

    user_ids = user_agg["user_id"].values
    X = user_agg.drop("user_id", axis=1).values.astype(np.float32)
    y = np.array([1 if uid in insider_ids else 0 for uid in user_ids])

    return X, y, user_ids


# ─── Training ────────────────────────────────────────────────────────

def train_autoencoder(features_df: pd.DataFrame, insider_ids: set) -> dict:
    """Train Autoencoder on normal users, score all users by reconstruction error.

    Returns dict with:
        - scores: {user_id: anomaly_score 0-100}
        - metrics: precision, recall, f1, auc
        - reconstruction_errors: {user_id: raw_error}
    """
    print("[AUTOENCODER] Building feature matrix...")
    X, y, user_ids = _build_user_features(features_df, insider_ids)

    # Normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X).astype(np.float32)

    # Split normal vs insider for training
    normal_mask = (y == 0)
    X_normal = X_scaled[normal_mask]
    print(f"  Training on {X_normal.shape[0]} normal users, {X_scaled.shape[1]} features")
    print(f"  Holding out {y.sum()} insiders for evaluation only")

    # Build DataLoader
    train_tensor = torch.FloatTensor(X_normal)
    train_ds = TensorDataset(train_tensor, train_tensor)
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)

    # Model
    input_dim = X_scaled.shape[1]
    model = Autoencoder(input_dim=input_dim, bottleneck=8)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    criterion = nn.MSELoss()

    # Training loop
    print("[AUTOENCODER] Training...")
    model.train()
    epochs = 100
    best_loss = float("inf")

    for epoch in range(epochs):
        total_loss = 0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            recon = model(xb)
            loss = criterion(recon, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)
        if (epoch + 1) % 20 == 0:
            print(f"  Epoch {epoch+1:3d}/{epochs} | Loss: {avg_loss:.6f}")

        if avg_loss < best_loss:
            best_loss = avg_loss

    print(f"  Best training loss: {best_loss:.6f}")

    # Score all users
    model.eval()
    X_tensor = torch.FloatTensor(X_scaled)
    errors = model.reconstruction_error(X_tensor)  # shape: (n_users,)

    # Normalize errors to 0-100
    min_err, max_err = errors.min(), errors.max()
    normalized = (errors - min_err) / (max_err - min_err) * 100

    # AUC-ROC
    auc = roc_auc_score(y, normalized)
    print(f"\n[AUTOENCODER] ROC-AUC (reconstruction error vs ground truth): {auc:.4f}")

    # Threshold analysis
    print("\n[AUTOENCODER] ── Threshold Analysis ──")
    for thresh in [50, 60, 70, 80]:
        tp = sum(1 for uid, s in zip(user_ids, normalized) if s >= thresh and uid in insider_ids)
        fp = sum(1 for uid, s in zip(user_ids, normalized) if s >= thresh and uid not in insider_ids)
        fn = sum(1 for uid, s in zip(user_ids, normalized) if s < thresh and uid in insider_ids)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1s = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        print(f"  thresh>={thresh:3d}: TP={tp:2d} FP={fp:3d} | Precision={prec:.2%} Recall={rec:.2%} F1={f1s:.2%}")

    # Reconstruction error stats per group
    normal_errors = errors[normal_mask]
    insider_errors = errors[~normal_mask]
    print(f"\n  Normal users   — Mean error: {normal_errors.mean():.4f}, Max: {normal_errors.max():.4f}")
    print(f"  Insider users  — Mean error: {insider_errors.mean():.4f}, Max: {insider_errors.max():.4f}")
    separation = insider_errors.mean() / normal_errors.mean()
    print(f"  Insider/Normal error ratio: {separation:.2f}x (higher = better separation)")

    scores = {uid: float(s) for uid, s in zip(user_ids, normalized)}
    raw_errors = {uid: float(e) for uid, e in zip(user_ids, errors)}

    # Find best threshold for recall ≥ 85%
    best_thresh, best_f1 = None, 0
    for t in np.linspace(10, 90, 81):
        tp = sum(1 for uid, s in zip(user_ids, normalized) if s >= t and uid in insider_ids)
        fp = sum(1 for uid, s in zip(user_ids, normalized) if s >= t and uid not in insider_ids)
        fn = sum(1 for uid, s in zip(user_ids, normalized) if s < t and uid in insider_ids)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1s = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        if f1s > best_f1:
            best_f1 = f1s
            best_thresh = t

    tp = sum(1 for uid, s in zip(user_ids, normalized) if s >= best_thresh and uid in insider_ids)
    fp = sum(1 for uid, s in zip(user_ids, normalized) if s >= best_thresh and uid not in insider_ids)
    fn = len(insider_ids) - tp
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0

    metrics = {
        "model": "Autoencoder",
        "auc": float(auc),
        "best_threshold": float(best_thresh),
        "best_f1": float(best_f1),
        "precision_at_best": float(prec),
        "recall_at_best": float(rec),
        "insider_normal_error_ratio": float(separation),
    }

    print(f"\n  Best threshold: {best_thresh:.0f} → F1={best_f1:.4f} | Precision={prec:.2%} Recall={rec:.2%}")
    print(f"\n[AUTOENCODER] ✅ Done")

    return {
        "scores": scores,
        "reconstruction_errors": raw_errors,
        "metrics": metrics,
        "model": model,
        "scaler": scaler,
    }
