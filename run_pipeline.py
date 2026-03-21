"""AutonomusSOC — Full Pipeline Runner

Runs: Data Ingestion → Feature Engineering → ML Training (XGBoost+SHAP) → Detection → Alert Generation

XGBoost is now fully integrated into the production ensemble scorer.
Data sampling (SMOTE + ClusterCentroids) is applied during XGBoost training.
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.ingest import ingest_all
from src.pipeline.features import compute_features
from src.detection.scorer import score_and_generate_alerts
from src.detection.xgboost_model import train_xgboost
from src.utils.db import engine, SessionLocal, Insider


def get_insider_ids() -> set:
    """Get the set of known insider user IDs from DB."""
    session = SessionLocal()
    try:
        insiders = session.query(Insider).all()
        return {i.user_id for i in insiders}
    finally:
        session.close()


def run(sampling: str = "hybrid", skip_ingest: bool = False):
    """Run the full AutonomusSOC pipeline.

    Args:
        sampling: XGBoost data sampling strategy.
                  Options: "hybrid" (recommended) | "under_only" | "smote_only" | "none"
        skip_ingest: If True, skip data ingestion and feature engineering
                     (use when DB is already built, just re-train models).
    """
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          CyberSOC-Agent — Full Pipeline Run             ║")
    print(f"║  XGBoost Sampling Strategy: {sampling:<28}║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    if not skip_ingest:
        # Phase 1: Ingest data
        print("━" * 60)
        print("  PHASE 1: Data Ingestion")
        print("━" * 60)
        ingest_all(fresh=True)

        # Phase 2: Feature engineering
        print()
        print("━" * 60)
        print("  PHASE 2: Feature Engineering")
        print("━" * 60)
        features_df = compute_features()
    else:
        print("  [PIPELINE] Skipping ingestion — loading features from DB...")
        import pandas as pd
        from sqlalchemy import text
        features_df = pd.read_sql("SELECT * FROM user_features", engine)
        print(f"  [PIPELINE] Loaded {len(features_df)} user-day rows from DB")

    # Get insider ground truth
    insider_ids = get_insider_ids()
    print(f"\n  Known insiders (ground truth): {len(insider_ids)}")

    # Phase 3: Train XGBoost (now with data sampling)
    print()
    print("━" * 60)
    print("  PHASE 3: XGBoost Training with Data Sampling")
    print("━" * 60)
    xgb_results = train_xgboost(features_df, insider_ids, sampling=sampling)
    xgb_metrics = xgb_results["metrics"]
    print(f"\n  XGBoost Results (held-out test set):")
    print(f"    Sampling strategy : {xgb_metrics['sampling_strategy']}")
    print(f"    ROC-AUC           : {xgb_metrics['auc']:.4f}")
    print(f"    PR-AUC            : {xgb_metrics['pr_auc']:.4f}")
    print(f"    F1-Score          : {xgb_metrics['f1']:.4f}")
    print(f"    Recall            : {xgb_metrics['recall']:.4f}")
    print(f"    AUC Gap (overfit) : {xgb_metrics['auc_gap']:.4f}")

    # Phase 4: Detection + Scoring (3-model ensemble)
    print()
    print("━" * 60)
    print("  PHASE 4: Detection & Risk Scoring (Rules + XGBoost + IF)")
    print("━" * 60)
    user_risks, alerts = score_and_generate_alerts(features_df, insider_ids, xgb_results=xgb_results)

    # Final summary
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                  PIPELINE COMPLETE                      ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("  Next: run the API server with:")
    print("    uvicorn src.api.main:app --reload --port 8000")
    print()
    print("  Or run a different sampling strategy, e.g.:")
    print("    python run_pipeline.py --sampling under_only")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the AutonomusSOC pipeline.")
    parser.add_argument(
        "--sampling",
        choices=["hybrid", "under_only", "smote_only", "none"],
        default="hybrid",
        help="XGBoost data sampling strategy (default: hybrid)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip data ingestion and feature engineering — re-train models only.",
    )
    args = parser.parse_args()
    run(sampling=args.sampling, skip_ingest=args.skip_ingest)
