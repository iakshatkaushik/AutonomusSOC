import numpy as np
import pandas as pd
import xgboost as xgb
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix
)
from sklearn.calibration import calibration_curve

from src.utils.db import engine, SessionLocal, Insider

ML_FEATURES = [
    "login_count", "after_hours_login_count", "after_hours_ratio",
    "unique_pcs", "file_copy_count", "file_copy_after_hours",
    "emails_sent", "external_recipient_ratio", "bcc_count",
    "attachment_count", "angry_keyword_count",
    "job_site_visits", "suspicious_domain_visits",
]

def load_data():
    features_df = pd.read_sql("SELECT * FROM user_features", engine)
    session = SessionLocal()
    insiders = {i.user_id for i in session.query(Insider).all()}
    session.close()
    
    agg_dict = {}
    for col in ML_FEATURES:
        if col in features_df.columns:
            agg_dict[f"{col}_mean"] = (col, "mean")
            agg_dict[f"{col}_max"] = (col, "max")
            agg_dict[f"{col}_sum"] = (col, "sum")
            agg_dict[f"{col}_std"] = (col, "std")

    user_agg = features_df.groupby("user_id").agg(**agg_dict).reset_index().fillna(0)
    X = user_agg.drop("user_id", axis=1).values.astype(np.float32)
    y = np.array([1 if uid in insiders else 0 for uid in user_agg["user_id"]])
    return X, y

def expected_calibration_error(y_true, y_prob, n_bins=10):
    try:
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)
        return np.mean(np.abs(prob_true - prob_pred))
    except:
        return 0.0

def print_metrics(name, y_true, y_pred, y_prob, val_auc_std=0, train_auc=None, test_auc=None, ece=0):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    prec_0 = tn / (tn + fn) if (tn + fn) > 0 else 0
    rec_0 = tn / (tn + fp) if (tn + fp) > 0 else 0
    macro_prec = (precision + prec_0) / 2
    macro_rec = (recall + rec_0) / 2
    
    # only compute auc if pos/neg present
    test_auc = roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0
    pr_auc = average_precision_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0
    conf_score = np.mean(y_prob[y_pred == 1]) if sum(y_pred) > 0 else 0
    
    print(f"==== {name} TEST METRICS =====")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall / Sensitivity: {recall:.4f}")
    print(f"Specificity: {specificity:.4f}")
    print(f"F1-Score: {f1:.4f}")
    print(f"Macro Precision: {macro_prec:.4f}")
    print(f"Macro Recall: {macro_rec:.4f}")
    print(f"ROC-AUC: {test_auc:.4f}")
    print(f"PR-AUC: {pr_auc:.4f}")
    print(f"Confidence Score: {conf_score:.4f}")
    print(f"\n===== OVERFITTING ({name}) =====")
    if train_auc is not None:
        print(f"Train-Val AUC Gap: {train_auc - test_auc:.4f}")
    else:
        print(f"Train-Val AUC Gap: N/A (Unsupervised)")
    print(f"ECE: {ece:.4f}")
    print(f"Val AUC Stability STD: {val_auc_std:.4f}\n")

# Model definitions
class Autoencoder(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(input_dim,32), nn.ReLU(), nn.BatchNorm1d(32), nn.Dropout(0.1), nn.Linear(32,16), nn.ReLU(), nn.Linear(16,8))
        self.dec = nn.Sequential(nn.Linear(8,16), nn.ReLU(), nn.Linear(16,32), nn.ReLU(), nn.BatchNorm1d(32), nn.Linear(32,input_dim))
    def forward(self, x): return self.dec(self.enc(x))

def get_ae_errors(model, X):
    model.eval()
    with torch.no_grad():
        recon = model(torch.FloatTensor(X))
        errs = torch.mean((torch.FloatTensor(X) - recon)**2, dim=1).numpy()
    return errs

def eval_autoencoder():
    X, y = load_data()
    scaler = StandardScaler()
    X_s = scaler.fit_transform(X).astype(np.float32)
    
    normal_mask = (y == 0)
    X_normal = X_s[normal_mask]
    
    train_tensor = torch.FloatTensor(X_normal)
    loader = DataLoader(TensorDataset(train_tensor, train_tensor), batch_size=64, shuffle=True)
    
    model = Autoencoder(X_s.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    crit = nn.MSELoss()
    model.train()
    for _ in range(50):
        for xb, yb in loader:
            opt.zero_grad()
            crit(model(xb), yb).backward()
            opt.step()
            
    errors = get_ae_errors(model, X_s)
    # normalize to probabilities [0, 1] based on train max
    train_max = np.max(get_ae_errors(model, X_normal))
    probs = np.clip(errors / (train_max * 2), 0, 1) # heuristic
    preds = (probs >= 0.5).astype(int)
    
    ece = expected_calibration_error(y, probs)
    print_metrics("AUTOENCODER", y, preds, probs, val_auc_std=0, train_auc=None, ece=ece)

def eval_ensemble():
    risks_df = pd.read_sql("SELECT * FROM user_risks", engine)
    session = SessionLocal()
    insiders = {i.user_id for i in session.query(Insider).all()}
    session.close()
    
    y = np.array([1 if uid in insiders else 0 for uid in risks_df["user_id"]])
    probs = (risks_df["risk_score"] / 100.0).values
    preds = (probs >= 0.3).astype(int) # threshold = 30 from scorer.py
    
    ece = expected_calibration_error(y, probs)
    print_metrics("ENSEMBLE (Rules + Isolation Forest)", y, preds, probs, val_auc_std=0, train_auc=None, ece=ece)

def eval_xgboost():
    X, y = load_data()
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0
    
    model = xgb.XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, scale_pos_weight=scale_pos_weight,
        eval_metric="logloss", random_state=42, n_jobs=-1
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_aucs = []
    for train_ix, val_idx in cv.split(X, y):
        model.fit(X[train_ix], y[train_ix])
        cv_aucs.append(roc_auc_score(y[val_idx], model.predict_proba(X[val_idx])[:, 1]))
    val_std = np.std(cv_aucs)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    model.fit(X_train, y_train)
    tr_probs = model.predict_proba(X_train)[:,1]
    te_probs = model.predict_proba(X_test)[:,1]
    
    ece = expected_calibration_error(y_test, te_probs)
    print_metrics("XGBOOST", y_test, (te_probs>=0.5).astype(int), te_probs, val_std, roc_auc_score(y_train, tr_probs), ece=ece)

if __name__ == '__main__':
    import warnings
    warnings.filterwarnings("ignore")
    eval_xgboost()
    eval_autoencoder()
    eval_ensemble()
