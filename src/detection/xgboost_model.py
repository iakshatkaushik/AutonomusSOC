"""XGBoost + SHAP — Supervised insider threat detection.

Strategy:
- Build labeled dataset: 70 insiders = 1, ~930 normal = 0
- Use per-user aggregated features (mean/max/sum/std per ML_FEATURE)
- Apply HYBRID data sampling BEFORE training to fix geometric class imbalance:
    → ClusterCentroids under-sample normals to representative prototypes
    → BorderlineSMOTE over-sample insiders near the decision boundary
- Evaluate ONLY on the held-out original test set (never on SMOTE-generated samples)
- Train XGBoost classifier on balanced data
- Use SHAP to explain individual predictions
"""
import json
import numpy as np
import pandas as pd
import xgboost as xgb
import shap
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_score,
    recall_score, f1_score, confusion_matrix, average_precision_score,
)
from sklearn.preprocessing import StandardScaler

from src.utils.db import engine
from src.detection.sampling import resample, SamplingStrategy


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


def train_xgboost(
    features_df: pd.DataFrame,
    insider_ids: set,
    sampling: SamplingStrategy = "hybrid",
) -> dict:
    """Train XGBoost classifier and return results + SHAP explanations.

    Args:
        features_df: Per-user-per-day feature DataFrame.
        insider_ids: Set of known insider user IDs.
        sampling: Data sampling strategy — "none"|"under_only"|"smote_only"|"hybrid".
                  'none' falls back to scale_pos_weight (original behaviour).

    Returns dict with:
        - scores: {user_id: probability_score 0-100}
        - shap_values: per-user SHAP explanations
        - metrics: precision, recall, f1, auc, pr_auc
        - feature_importance: top features
        - model: the trained XGBClassifier
    """
    print("[XGBOOST] Building user feature matrix...")
    X, y, user_ids, feature_names = _build_user_feature_matrix(features_df, insider_ids)

    n_pos = y.sum()
    n_neg = len(y) - n_pos
    print(f"  Class distribution: {n_pos} insiders, {n_neg} normal users (ratio 1:{n_neg/max(n_pos,1):.1f})")

    # ─── CRITICAL: Split BEFORE any resampling ──────────────────────────────
    # We evaluate only on the original held-out set, not on synthetic samples.
    # Use stratify=y to ensure both classes appear in train/test.
    X_train, X_test, y_train, y_test, ids_train, ids_test = train_test_split(
        X, y, user_ids,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )
    print(f"  Train: {len(X_train)} samples ({y_train.sum()} insiders)")
    print(f"  Test : {len(X_test)} samples ({y_test.sum()} insiders) — held-out, no SMOTE")

    # ─── Apply sampling ONLY to training set ────────────────────────────────
    if sampling != "none":
        X_train_res, y_train_res = resample(X_train, y_train, strategy=sampling)
    else:
        X_train_res, y_train_res = X_train, y_train

    # ─── XGBoost config ─────────────────────────────────────────────────────
    # If using 'none' (no resampling), keep scale_pos_weight as the imbalance fix.
    # If using sampling, the data is already balanced — set scale_pos_weight=1.
    n_pos_train = int(y_train_res.sum())
    n_neg_train = int(len(y_train_res) - n_pos_train)
    spw = (n_neg_train / max(n_pos_train, 1)) if sampling == "none" else 1.0

    print(f"\n[XGBOOST] Training with sampling='{sampling}', scale_pos_weight={spw:.2f}")

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    # ─── Cross-validation on RESAMPLED training data ─────────────────────────
    print("[XGBOOST] Running 5-fold stratified cross-validation (on training set)...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_auc = cross_val_score(model, X_train_res, y_train_res, cv=cv, scoring="roc_auc")
    cv_recall = cross_val_score(model, X_train_res, y_train_res, cv=cv, scoring="recall")
    print(f"  CV AUC:    {cv_auc.mean():.4f} ± {cv_auc.std():.4f}  (train set CV, not held-out)")
    print(f"  CV Recall: {cv_recall.mean():.4f} ± {cv_recall.std():.4f}")

    # ─── Train final model on full resampled training set ─────────────────────
    print("[XGBOOST] Training final model on full resampled training set...")
    model.fit(X_train_res, y_train_res)

    # ─── Evaluate on the ORIGINAL held-out test set ──────────────────────────
    proba_test = model.predict_proba(X_test)[:, 1]
    preds_test = (proba_test >= 0.5).astype(int)

    print("\n[XGBOOST] ── Held-out Test Set Metrics (UNSAMPLED — honest evaluation) ──")
    print(classification_report(y_test, preds_test, target_names=["Normal", "Insider"]))
    auc_test = roc_auc_score(y_test, proba_test) if y_test.sum() > 0 else 0.0
    pr_auc_test = average_precision_score(y_test, proba_test) if y_test.sum() > 0 else 0.0
    print(f"  Held-out ROC-AUC : {auc_test:.4f}")
    print(f"  Held-out PR-AUC  : {pr_auc_test:.4f}  ← key metric for imbalanced data")

    # Train/val AUC gap (overfitting check)
    proba_train_full = model.predict_proba(X_train)[:, 1]
    auc_train = roc_auc_score(y_train, proba_train_full) if y_train.sum() > 0 else 0.0
    print(f"  Train AUC gap    : {auc_train:.4f} (train) vs {auc_test:.4f} (test) = gap {abs(auc_train - auc_test):.4f}")

    metrics = {
        "model": "XGBoost",
        "sampling_strategy": sampling,
        "cv_auc_mean": float(cv_auc.mean()),
        "cv_auc_std": float(cv_auc.std()),
        "cv_recall_mean": float(cv_recall.mean()),
        "auc": float(auc_test),
        "pr_auc": float(pr_auc_test),
        "train_auc": float(auc_train),
        "auc_gap": float(abs(auc_train - auc_test)),
        "precision": float(precision_score(y_test, preds_test, zero_division=0)),
        "recall": float(recall_score(y_test, preds_test, zero_division=0)),
        "f1": float(f1_score(y_test, preds_test, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, preds_test).tolist(),
    }

    # ─── Score ALL users (for production risk scoring) ───────────────────────
    print("\n[XGBOOST] Scoring all users for production use...")
    proba_all = model.predict_proba(X)[:, 1]

    # ─── SHAP explanations on original (unsampled) full dataset ──────────────
    print("[XGBOOST] Computing SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)  # shape: (n_users, n_features)

    shap_explanations = {}
    for i, uid in enumerate(user_ids):
        user_shap = shap_values[i]
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
    scores = {uid: float(p * 100) for uid, p in zip(user_ids, proba_all)}

    # ─── Threshold analysis on held-out test set ─────────────────────────────
    print("\n[XGBOOST] ── Threshold Analysis (held-out test set) ──")
    for thresh in [0.3, 0.5, 0.7]:
        tp = sum(1 for p, lbl in zip(proba_test, y_test) if p >= thresh and lbl == 1)
        fp = sum(1 for p, lbl in zip(proba_test, y_test) if p >= thresh and lbl == 0)
        fn = sum(1 for p, lbl in zip(proba_test, y_test) if p < thresh and lbl == 1)
        prec_t = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec_t = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1s = 2 * prec_t * rec_t / (prec_t + rec_t) if (prec_t + rec_t) > 0 else 0
        print(f"  thresh={thresh}: TP={tp:2d} FP={fp:3d} | Precision={prec_t:.2%} Recall={rec_t:.2%} F1={f1s:.2%}")

    print(f"\n[XGBOOST] ✅ Done — sampling='{sampling}', held-out AUC={auc_test:.4f}, PR-AUC={pr_auc_test:.4f}")

    return {
        "scores": scores,
        "shap_explanations": shap_explanations,
        "metrics": metrics,
        "feature_importance": fi_sorted,
        "model": model,
        "feature_names": feature_names,
    }
