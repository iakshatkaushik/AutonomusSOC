"""run_agent.py — Run the LLM Investigation Agent on top-risk alerts.

This script:
1. Loads XGBoost model results + SHAP explanations
2. Takes the top HIGH/CRITICAL alerts
3. Runs the ReAct Agent on each one
4. Stores InvestigationReport in the database

Usage:
  python run_agent.py               # investigate all CRITICAL alerts
  python run_agent.py --top 5       # investigate top 5 by risk score
  python run_agent.py --user ABC123 # investigate a specific user
"""
import argparse
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
warnings.filterwarnings("ignore")

import pandas as pd
from sqlalchemy import text

from src.utils.db import engine, SessionLocal, init_db, Alert, InvestigationReport
from src.agent.react_agent import investigate
from src.detection.xgboost_model import train_xgboost
from src.utils.db import Insider


def get_shap_data() -> dict:
    """Retrain XGBoost to get fresh SHAP explanations."""
    print("[AGENT-RUNNER] Loading features for SHAP computation...")
    features_df = pd.read_sql("SELECT * FROM user_features", engine)

    session = SessionLocal()
    insider_ids = {i.user_id for i in session.query(Insider).all()}
    session.close()

    print("[AGENT-RUNNER] Training XGBoost for SHAP explanations...")
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = train_xgboost(features_df, insider_ids)

    return results.get("shap_explanations", {})


def store_report(report: dict, alert_id: int = None):
    """Store an investigation report in the database."""
    # Create the investigation_reports table if needed
    init_db()

    record = InvestigationReport(
        alert_id=alert_id,
        user_id=report.get("user_id", ""),
        summary=report.get("summary", ""),
        threat_scenario=report.get("threat_scenario", "UNKNOWN"),
        confidence=float(report.get("confidence", 0.5)),
        evidence_chain=json.dumps(report.get("evidence_chain", [])),
        reasoning=report.get("reasoning", ""),
        recommended_action=report.get("recommended_action", "MONITOR"),
        recommended_actions_detail=json.dumps(report.get("recommended_actions_detail", [])),
        correlated_users=json.dumps(report.get("correlated_users", [])),
        risk_score=float(report.get("risk_score", 0)),
        severity=report.get("severity", "MEDIUM"),
        iterations=int(report.get("iterations", 1)),
        llm_model=report.get("llm_model", "unknown"),
        created_at=datetime.now(),
    )

    session = SessionLocal()
    try:
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id
    finally:
        session.close()


def run(top: int = 5, user_id: str = None, severity_filter: str = None):
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         CyberSOC-Agent — LLM Investigation Runner      ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Get SHAP data
    shap_data = get_shap_data()
    print(f"[AGENT-RUNNER] SHAP data ready for {len(shap_data)} users")

    # Get alerts to investigate
    query = "SELECT * FROM alerts WHERE status = 'open'"
    params = {}

    if user_id:
        query += " AND user_id = :uid"
        params["uid"] = user_id
    elif severity_filter:
        query += " AND severity = :sev"
        params["sev"] = severity_filter
    else:
        query += " AND severity IN ('CRITICAL', 'HIGH')"

    query += " ORDER BY risk_score DESC"
    if not user_id:
        query += f" LIMIT {top}"

    alerts_df = pd.read_sql(text(query), engine, params=params)
    print(f"[AGENT-RUNNER] Found {len(alerts_df)} alerts to investigate")

    if alerts_df.empty:
        print("[AGENT-RUNNER] No alerts to investigate. Run run_pipeline.py first.")
        return

    # Run agent on each alert
    reports = []
    for idx, alert in alerts_df.iterrows():
        print()
        print(f"━" * 60)
        print(f"  Investigating {idx + 1}/{len(alerts_df)}: {alert['user_id']} [{alert['severity']}]")
        print(f"━" * 60)

        report = investigate(
            user_id=alert["user_id"],
            alert_type=alert["alert_type"],
            risk_score=float(alert["risk_score"]),
            severity=alert["severity"],
            alert_id=int(alert["id"]),
            shap_data=shap_data,
            max_iterations=8,
        )

        report_id = store_report(report, alert_id=int(alert["id"]))
        reports.append(report)

        print(f"  ✅ Report #{report_id} stored")
        print(f"  Summary: {report.get('summary', '')[:120]}...")
        print(f"  Action:  {report.get('recommended_action', 'MONITOR')}")
        print(f"  Confidence: {report.get('confidence', 0):.0%}")

    # Summary
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                INVESTIGATION COMPLETE                   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Reports generated: {len(reports)}")
    action_counts = {}
    for r in reports:
        action = r.get("recommended_action", "MONITOR")
        action_counts[action] = action_counts.get(action, 0) + 1
    for action, count in sorted(action_counts.items()):
        print(f"  {action:<30} {count}")
    print()
    print("  Start the API server to view results:")
    print("    uvicorn src.api.main:app --reload --port 8000")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CyberSOC-Agent Investigation Runner")
    parser.add_argument("--top", type=int, default=5, help="Top N alerts to investigate")
    parser.add_argument("--user", type=str, default=None, help="Investigate specific user ID")
    parser.add_argument("--severity", type=str, default=None, help="Filter by severity: CRITICAL/HIGH/MEDIUM")
    args = parser.parse_args()
    run(top=args.top, user_id=args.user, severity_filter=args.severity)
