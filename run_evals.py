import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score

from src.utils.db import engine, SessionLocal, Insider
from src.detection.xgboost_model import train_xgboost
from src.detection.autoencoder_model import train_autoencoder

def get_data():
    features_df = pd.read_sql("SELECT * FROM user_features", engine)
    session = SessionLocal()
    insiders = session.query(Insider).all()
    session.close()
    insider_ids = {i.user_id for i in insiders}
    return features_df, insider_ids

def evaluate_ensemble(insider_ids):
    # The pipeline already wrote the final ensemble scores to user_risks table
    risks_df = pd.read_sql("SELECT * FROM user_risks", engine)
    y_true = [1 if uid in insider_ids else 0 for uid in risks_df["user_id"]]
    # In scorer.py, threshold is 30 for an alert
    y_pred = [1 if score >= 30 else 0 for score in risks_df["risk_score"]]
    
    p = precision_score(y_true, y_pred)
    r = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    acc = accuracy_score(y_true, y_pred)
    
    print("\n[ENSEMBLE (Rules + IF)] ── Final Pipeline Metrics ──")
    print(f"  Precision: {p:.4f}")
    print(f"  Recall:    {r:.4f}")
    print(f"  F1-Score:  {f1:.4f}")
    print(f"  Accuracy:  {acc:.4f}\n")

if __name__ == "__main__":
    features_df, insider_ids = get_data()
    print(f"Loaded {len(features_df)} feature rows for {len(set(features_df['user_id']))} users.")
    
    # 1. Ensemble (already ran during pipeline)
    evaluate_ensemble(insider_ids)
    
    # 2. XGBoost
    try:
        xgb_res = train_xgboost(features_df, insider_ids)
    except Exception as e:
        print(f"XGBoost Error: {e}")
        
    # 3. Autoencoder
    try:
        ae_res = train_autoencoder(features_df, insider_ids)
    except Exception as e:
        print(f"Autoencoder Error: {e}")
