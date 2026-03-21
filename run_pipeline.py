"""AutonomusSOC — Full Pipeline Runner

Runs: Data Ingestion → Feature Engineering → Detection (Rules + IF) → Alert Generation
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.ingest import ingest_all
from src.pipeline.features import compute_features
from src.detection.scorer import score_and_generate_alerts
from src.utils.db import engine, SessionLocal, Insider


def get_insider_ids() -> set:
    """Get the set of known insider user IDs from DB."""
    session = SessionLocal()
    try:
        insiders = session.query(Insider).all()
        return {i.user_id for i in insiders}
    finally:
        session.close()


def run():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          AutonomusSOC — Full Pipeline Run               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

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

    # Phase 3: Detection + Scoring
    print()
    print("━" * 60)
    print("  PHASE 3: Detection & Risk Scoring")
    print("━" * 60)
    insider_ids = get_insider_ids()
    print(f"  Known insiders (ground truth): {len(insider_ids)}")

    user_risks, alerts = score_and_generate_alerts(features_df, insider_ids)

    # Final summary
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                  PIPELINE COMPLETE                      ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("  Next: run the API server with:")
    print("    uvicorn src.api.main:app --reload --port 8000")
    print()


if __name__ == "__main__":
    run()
