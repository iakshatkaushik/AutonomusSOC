"""Risk scorer — combines Rule Engine + Isolation Forest + XGBoost into final risk scores and alerts.

Ensemble weighting (when XGBoost is available):
  final_score = rule_score * 0.40 + xgb_score * 0.40 + if_score * 0.20

Rationale:
  - Rules: deterministic, high precision for known CERT scenarios
  - XGBoost: highest AUC model (0.9996), supervised, explainable via SHAP
  - Isolation Forest: complementary unsupervised — catches unknown patterns
  - XGBoost scores now included (previously only Rules + IF were used)
"""
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


def score_and_generate_alerts(
    features_df: pd.DataFrame,
    insider_ids: set,
    xgb_results: dict = None,
):
    """Full scoring pipeline:
    1. Run rule-based detection
    2. Run Isolation Forest
    3. Include XGBoost scores (if provided) in ensemble
    4. Generate ensemble risk scores and alerts to DB

    Args:
        features_df: Per-user-per-day feature DataFrame.
        insider_ids: Set of known insider user IDs.
        xgb_results: Optional dict returned by train_xgboost(). If provided,
                     XGBoost scores are included in the final ensemble.
                     Pass None to use the original Rules+IF-only combination.
    """
    print("=" * 60)
    print("  Risk Scoring & Alert Generation")
    print("=" * 60)

    using_xgb = xgb_results is not None and "scores" in xgb_results
    if using_xgb:
        print("  [SCORER] XGBoost scores provided → using 3-model ensemble")
        xgb_scores = xgb_results["scores"]  # {user_id: 0-100}
    else:
        print("  [SCORER] ⚠️  No XGBoost results — using Rules + IF only (2-model ensemble)")
        xgb_scores = {}

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

    # 3. Combine scores — 3-model ensemble when XGBoost is available
    all_users = set(features_df["user_id"].unique())
    print(f"\n[SCORER] Computing ensemble scores for {len(all_users)} users...")

    if using_xgb:
        # XGBoost is the backbone — highest weight
        # Rules are scenario-specific and high-precision — equal weight to XGBoost
        # IF fills the gap for unknown patterns
        RULE_W  = 0.40
        XGB_W   = 0.40
        IF_W    = 0.20
    else:
        # Legacy 2-model weights (rules dominate)
        RULE_W  = 0.70
        XGB_W   = 0.00
        IF_W    = 0.30

    user_risks = []
    alerts = []

    for uid in all_users:
        rs  = rule_scores.get(uid, 0)
        ifs = if_scores.get(uid, 0) * 100         # Scale 0-1 → 0-100
        xgs = xgb_scores.get(uid, 0)              # Already 0-100

        if rs > 0:
            # User triggered a rule — use full weighted ensemble
            final_score = rs * RULE_W + xgs * XGB_W + ifs * IF_W
        elif xgs > 50:
            # XGBoost flagged but no rule triggered — trust XGBoost signal
            final_score = xgs * 0.70 + ifs * 0.30
        else:
            # Pure unsupervised signal — cap contribution to avoid noise flooding
            final_score = ifs * 0.50

        final_score = min(final_score, 100)
        severity = _severity(final_score)

        user_risks.append({
            "user_id": uid,
            "risk_score": round(final_score, 2),
            "rule_score": round(rs, 2),
            "if_score": round(ifs, 2),
            "xgb_score": round(xgs, 2),
            "alert_count": 1 if uid in rule_data else 0,
            "is_insider": uid in insider_ids,
            "scenario": None,
        })

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
                    alert_data.get("contributing_factors", [
                        f"XGBoost score: {xgs:.1f}",
                        f"Isolation Forest anomaly score: {ifs:.1f}",
                    ])
                ),
                "recommended_actions": json.dumps(
                    alert_data.get("recommended_actions", [
                        "Review user activity logs",
                        "Investigate anomalous patterns",
                    ])
                ),
                "status": "open",
                "created_at": datetime.now(),
            })

    # 4. Store in DB
    print(f"[SCORER] Writing {len(user_risks)} user risk scores...")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM user_risks"))
        conn.execute(text("DELETE FROM alerts"))

    # Add xgb_score column if it doesn't already exist in the schema
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE user_risks ADD COLUMN xgb_score REAL DEFAULT 0"))
    except Exception:
        pass  # Column likely already exists

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
    print(f"  Ensemble mode:          {'Rules+XGBoost+IF (3-model)' if using_xgb else 'Rules+IF (2-model, legacy)'}")
    print("=" * 60)

    return user_risks, alerts
