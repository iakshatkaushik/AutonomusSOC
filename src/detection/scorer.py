"""Risk scorer — combines rule-based alerts + Isolation Forest scores into final risk scores and alerts."""
import json
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from src.utils.db import engine, SessionLocal, Alert, UserRisk, init_db
from src.detection.rules import detect_all
from src.detection.isolation_forest import train_and_score


def _severity(score: float) -> str:
    if score >= 90:
        return "CRITICAL"
    elif score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    return "LOW"


def score_and_generate_alerts(features_df: pd.DataFrame, insider_ids: set):
    """Full scoring pipeline:
    1. Run rule-based detection
    2. Run Isolation Forest
    3. Combine into final risk scores
    4. Generate alerts and store in DB
    """
    print("=" * 60)
    print("  Risk Scoring & Alert Generation")
    print("=" * 60)

    # 1. Rule-based detection
    rule_alerts = detect_all(features_df)
    rule_scores = {}  # user_id → highest rule score
    rule_data = {}    # user_id → alert data

    for alert in rule_alerts:
        uid = alert["user_id"]
        if uid not in rule_scores or alert["rule_score"] > rule_scores[uid]:
            rule_scores[uid] = alert["rule_score"]
            rule_data[uid] = alert

    # 2. Isolation Forest scoring
    if_scores = train_and_score(features_df, insider_ids)

    # 3. Combine scores
    all_users = set(features_df["user_id"].unique())
    print(f"\n[SCORER] Combining scores for {len(all_users)} users...")

    user_risks = []
    alerts = []

    for uid in all_users:
        rs = rule_scores.get(uid, 0)
        ifs = if_scores.get(uid, 0) * 100  # Scale to 0-100

        # Weighted combination: rules dominate
        if rs > 0:
            final_score = rs * 0.7 + ifs * 0.3
        else:
            final_score = ifs * 0.5  # Pure IF score capped at 50

        final_score = min(final_score, 100)
        severity = _severity(final_score)

        user_risks.append({
            "user_id": uid,
            "risk_score": round(final_score, 2),
            "rule_score": round(rs, 2),
            "if_score": round(ifs, 2),
            "alert_count": 1 if uid in rule_data else 0,
            "is_insider": uid in insider_ids,
            "scenario": None,
        })

        # Generate alert if score is meaningful
        if final_score >= 30:
            alert_data = rule_data.get(uid, {})
            alerts.append({
                "user_id": uid,
                "alert_type": alert_data.get("alert_type", "ANOMALY"),
                "severity": severity,
                "risk_score": round(final_score, 2),
                "description": alert_data.get(
                    "description",
                    f"User {uid} flagged by anomaly detection with score {final_score:.1f}"
                ),
                "contributing_factors": json.dumps(
                    alert_data.get("contributing_factors", [f"Isolation Forest anomaly score: {ifs:.1f}"])
                ),
                "recommended_actions": json.dumps(
                    alert_data.get("recommended_actions", ["Review user activity logs", "Investigate anomalous patterns"])
                ),
                "status": "open",
                "created_at": datetime.now(),
            })

    # 4. Store in DB
    print(f"[SCORER] Writing {len(user_risks)} user risk scores...")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM user_risks"))
        conn.execute(text("DELETE FROM alerts"))

    with engine.begin() as conn:
        conn.execute(UserRisk.__table__.insert(), user_risks)

    print(f"[SCORER] Writing {len(alerts)} alerts...")
    with engine.begin() as conn:
        conn.execute(Alert.__table__.insert(), alerts)

    # 5. Report
    insider_detected = sum(1 for r in user_risks if r["is_insider"] and r["risk_score"] >= 30)
    total_insiders = sum(1 for r in user_risks if r["is_insider"])

    print()
    print("=" * 60)
    print("  Scoring Complete!")
    print("=" * 60)
    print(f"  Total users scored:     {len(user_risks)}")
    print(f"  Alerts generated:       {len(alerts)}")
    print(f"  CRITICAL alerts:        {sum(1 for a in alerts if a['severity'] == 'CRITICAL')}")
    print(f"  HIGH alerts:            {sum(1 for a in alerts if a['severity'] == 'HIGH')}")
    print(f"  MEDIUM alerts:          {sum(1 for a in alerts if a['severity'] == 'MEDIUM')}")
    print(f"  Insiders detected:      {insider_detected}/{total_insiders}")
    print("=" * 60)

    return user_risks, alerts
