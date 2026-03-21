"""XGBoost + SHAP — Supervised insider threat detection.

Strategy:
- Build labeled dataset: 70 insiders = 1, 930 normal = 0
- Use per-user aggregated features
- Handle class imbalance with scale_pos_weight (XGBoost native)
- Train XGBoost classifier
- Use SHAP to explain individual predictions
"""
import json
import numpy as np
import pandas as pd
import xgboost as xgb
import shap
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_score,
    recall_score, f1_score, confusion_matrix
)
from sklearn.preprocessing import StandardScaler

from src.utils.db import engine


# Features used (same as Isolation Forest for fair comparison)
ML_FEATURES = [
    "login_count", "after_hours_login_count", "after_hours_ratio",
    "unique_pcs", "file_copy_count", "file_copy_after_hours",
    "emails_sent", "external_recipient_ratio", "bcc_count",
    "attachment_count", "angry_keyword_count",
    "job_site_visits", "suspicious_domain_visits",
]


def _build_user_feature_matrix(features_df: pd.DataFrame, insider_ids: set) -> tuple:
    """Aggregate daily features into per-user matrix and build labels."""
    agg_dict = {}
    for col in ML_FEATURES:
        if col in features_df.columns:
            agg_dict[f"{col}_mean"] = (col, "mean")
            agg_dict[f"{col}_max"] = (col, "max")
            agg_dict[f"{col}_sum"] = (col, "sum")
            agg_dict[f"{col}_std"] = (col, "std")

    user_agg = features_df.groupby("user_id").agg(**agg_dict).reset_index()
    user_agg = user_agg.fillna(0)

    X = user_agg.drop("user_id", axis=1).values.astype(np.float32)
    y = np.array([1 if uid in insider_ids else 0 for uid in user_agg["user_id"]])
    feature_names = [c for c in user_agg.columns if c != "user_id"]

    return X, y, user_agg["user_id"].values, feature_names


def train_xgboost(features_df: pd.DataFrame, insider_ids: set) -> dict:
    """Train XGBoost classifier and return results + SHAP explanations.

    Returns dict with:
        - scores: {user_id: probability_score}
        - shap_values: per-user SHAP explanations
        - metrics: precision, recall, f1, auc
        - feature_importance: top features
    """
    print("[XGBOOST] Building user feature matrix...")
    X, y, user_ids, feature_names = _build_user_feature_matrix(features_df, insider_ids)

    n_pos = y.sum()
    n_neg = len(y) - n_pos
    print(f"  Class distribution: {n_pos} insiders, {n_neg} normal users")

    # XGBoost handles imbalance via scale_pos_weight
    scale_pos_weight = n_neg / n_pos
    print(f"  scale_pos_weight = {scale_pos_weight:.1f}")

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    # Cross-validation for honest metrics
    print("[XGBOOST] Running 5-fold stratified cross-validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_auc = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
    cv_recall = cross_val_score(model, X, y, cv=cv, scoring="recall")
    print(f"  CV AUC:    {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")
    print(f"  CV Recall: {cv_recall.mean():.4f} ± {cv_recall.std():.4f}")

    # Train on full data for final scores
    print("[XGBOOST] Training on full dataset...")
    model.fit(X, y)

    # Get probability scores (class=1 = insider)
    proba = model.predict_proba(X)[:, 1]
    preds = (proba >= 0.5).astype(int)

    # Final metrics on training data
    print("\n[XGBOOST] ── Full Dataset Metrics ──")
    print(classification_report(y, preds, target_names=["Normal", "Insider"]))
    auc = roc_auc_score(y, proba)
    print(f"  ROC-AUC: {auc:.4f}")

    metrics = {
        "model": "XGBoost",
        "cv_auc_mean": float(cv_auc.mean()),
        "cv_auc_std": float(cv_auc.std()),
        "cv_recall_mean": float(cv_recall.mean()),
        "auc": float(auc),
        "precision": float(precision_score(y, preds)),
        "recall": float(recall_score(y, preds)),
        "f1": float(f1_score(y, preds)),
        "confusion_matrix": confusion_matrix(y, preds).tolist(),
    }

    # SHAP explanations
    print("\n[XGBOOST] Computing SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)  # shape: (n_users, n_features)

    # Build per-user SHAP explanation dict
    shap_explanations = {}
    for i, uid in enumerate(user_ids):
        user_shap = shap_values[i]
        # Top 5 contributing features
        top_idx = np.argsort(np.abs(user_shap))[::-1][:5]
        shap_explanations[uid] = [
            {"feature": feature_names[j], "shap_value": float(user_shap[j])}
            for j in top_idx
        ]

    # Feature importance from SHAP
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    fi_sorted = sorted(zip(feature_names, mean_abs_shap), key=lambda x: x[1], reverse=True)
    print("\n[XGBOOST] Top 10 most important features (SHAP):")
    for feat, importance in fi_sorted[:10]:
        bar = "█" * int(importance * 20)
        print(f"  {feat:35s} {importance:.4f} {bar}")

    # Score dict: user_id → 0-100 risk
    scores = {uid: float(p * 100) for uid, p in zip(user_ids, proba)}

    # Threshold analysis
    print("\n[XGBOOST] ── Threshold Analysis ──")
    for thresh in [0.3, 0.5, 0.7]:
        fp = sum(1 for uid, p in zip(user_ids, proba) if p >= thresh and uid not in insider_ids)
        tp = sum(1 for uid, p in zip(user_ids, proba) if p >= thresh and uid in insider_ids)
        fn = sum(1 for uid, p in zip(user_ids, proba) if p < thresh and uid in insider_ids)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1s = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        print(f"  thresh={thresh}: TP={tp:2d} FP={fp:3d} | Precision={prec:.2%} Recall={rec:.2%} F1={f1s:.2%}")

    print(f"\n[XGBOOST] ✅ Done")

    return {
        "scores": scores,
        "shap_explanations": shap_explanations,
        "metrics": metrics,
        "feature_importance": fi_sorted,
        "model": model,
        "feature_names": feature_names,
    }
