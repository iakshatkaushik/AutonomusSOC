"""Isolation Forest anomaly detector — lightweight ML layer.

Trains on per-user aggregated features (normal users).
Scores all users for anomaly detection.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from src.utils.db import engine


# Feature columns used for ML
ML_FEATURES = [
    "login_count", "after_hours_login_count", "after_hours_ratio",
    "unique_pcs", "file_copy_count", "file_copy_after_hours",
    "emails_sent", "external_recipient_ratio", "bcc_count",
    "attachment_count", "angry_keyword_count",
    "job_site_visits", "suspicious_domain_visits",
]


def _aggregate_user_features(features_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily features into per-user summary statistics."""
    agg_dict = {}
    for col in ML_FEATURES:
        if col in features_df.columns:
            agg_dict[f"{col}_mean"] = (col, "mean")
            agg_dict[f"{col}_max"] = (col, "max")
            agg_dict[f"{col}_sum"] = (col, "sum")

    user_agg = features_df.groupby("user_id").agg(**agg_dict).reset_index()
    return user_agg


def train_and_score(features_df: pd.DataFrame, insider_ids: set) -> dict[str, float]:
    """Train Isolation Forest on normal users, score all users.

    Args:
        features_df: per-user-per-day feature DataFrame
        insider_ids: set of known insider user IDs (for train/test split only)

    Returns:
        dict mapping user_id → anomaly_score (0 to 1, higher = more anomalous)
    """
    print("[IF] Aggregating per-user features...")
    user_agg = _aggregate_user_features(features_df)

    # Feature matrix
    feature_cols = [c for c in user_agg.columns if c != "user_id"]
    X = user_agg[feature_cols].fillna(0).values
    user_ids = user_agg["user_id"].values

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train Isolation Forest on ALL users
    # (in unsupervised anomaly detection, we don't exclude insiders from training —
    #  the model should find them as anomalies naturally)
    print(f"[IF] Training Isolation Forest on {len(X_scaled)} users, {X_scaled.shape[1]} features...")
    model = IsolationForest(
        n_estimators=200,
        contamination=0.1,  # Expect ~10% anomalies (70/1000 = 7%)
        max_features=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # Score all users
    # decision_function: negative = anomaly, positive = normal
    raw_scores = model.decision_function(X_scaled)

    # Convert to 0-1 scale where higher = more anomalous
    # decision_function returns negative for anomalies, so we negate and normalize
    anomaly_scores = -raw_scores
    min_score = anomaly_scores.min()
    max_score = anomaly_scores.max()
    if max_score > min_score:
        normalized = (anomaly_scores - min_score) / (max_score - min_score)
    else:
        normalized = np.zeros_like(anomaly_scores)

    scores = {uid: float(score) for uid, score in zip(user_ids, normalized)}

    # Report
    flagged = sum(1 for s in scores.values() if s > 0.5)
    insider_flagged = sum(1 for uid in insider_ids if scores.get(uid, 0) > 0.5)
    print(f"[IF] ✅ Scored {len(scores)} users")
    print(f"  Flagged as anomalous (>0.5): {flagged}")
    print(f"  Known insiders flagged: {insider_flagged}/{len(insider_ids)}")

    return scores
