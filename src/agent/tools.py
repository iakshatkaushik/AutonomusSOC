"""Agent tools — functions the LLM agent can call to investigate a user.

Each tool queries the SQLite database and returns a clean text summary
that the LLM can reason over in the ReAct loop.

Tools are grouped into two categories:
  READ  tools — query evidence from the database (safe, no side effects)
  WRITE tools — take reversible actions (flag, escalate, suppress) stored in DB
               Write actions are only called by the agent when confidence >= 0.85
"""
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text

from src.utils.db import engine


# ─── READ TOOLS ──────────────────────────────────────────────────────────────

def get_user_logs(user_id: str, days: int = 14, log_type: str = "all") -> str:
    """Get raw event logs for a user over the last N days.

    Args:
        user_id: The user ID to investigate
        days: How many days back to look (default 14)
        log_type: 'logon', 'file', 'email', 'http', or 'all'

    Returns:
        Formatted text summary of the user's logs
    """
    results = []

    if log_type in ("logon", "all"):
        df = pd.read_sql(
            text("SELECT timestamp, pc, activity FROM logon_events "
                 "WHERE user_id = :uid ORDER BY timestamp DESC LIMIT 50"),
            engine, params={"uid": user_id}
        )
        if not df.empty:
            after_hours = df[pd.to_datetime(df["timestamp"]).dt.hour.lt(7) |
                            pd.to_datetime(df["timestamp"]).dt.hour.ge(19)]
            results.append(
                f"LOGON EVENTS ({len(df)} total, {len(after_hours)} after-hours):\n" +
                df.head(10).to_string(index=False)
            )

    if log_type in ("file", "all"):
        df = pd.read_sql(
            text("SELECT timestamp, pc, filename FROM file_events "
                 "WHERE user_id = :uid ORDER BY timestamp DESC LIMIT 30"),
            engine, params={"uid": user_id}
        )
        if not df.empty:
            results.append(
                f"\nUSB FILE COPIES ({len(df)} total):\n" +
                df.head(10).to_string(index=False)
            )

    if log_type in ("email", "all"):
        df = pd.read_sql(
            text("SELECT timestamp, to_addrs, bcc_addrs, attachments, content "
                 "FROM email_events WHERE user_id = :uid ORDER BY timestamp DESC LIMIT 20"),
            engine, params={"uid": user_id}
        )
        if not df.empty:
            external = df[df["to_addrs"].str.contains("@dtaa.com", na=False) == False]
            results.append(
                f"\nEMAILS SENT ({len(df)} total, {len(external)} to external):\n" +
                df.head(8).to_string(index=False)
            )

    if log_type in ("http", "all"):
        df = pd.read_sql(
            text("SELECT timestamp, url FROM http_events "
                 "WHERE user_id = :uid ORDER BY timestamp DESC LIMIT 30"),
            engine, params={"uid": user_id}
        )
        if not df.empty:
            results.append(
                f"\nSUSPICIOUS WEB VISITS ({len(df)} flagged domains):\n" +
                df.head(10).to_string(index=False)
            )

    if not results:
        return f"No logs found for user {user_id}."

    return f"=== LOGS FOR USER {user_id} ===\n" + "\n".join(results)


def get_user_risk_profile(user_id: str) -> str:
    """Get the user's full risk profile: score, alert type, feature summary."""
    risk = pd.read_sql(
        text("SELECT * FROM user_risks WHERE user_id = :uid"),
        engine, params={"uid": user_id}
    )
    if risk.empty:
        return f"No risk profile found for user {user_id}."

    r = risk.iloc[0]
    features = pd.read_sql(
        text("SELECT * FROM user_features WHERE user_id = :uid ORDER BY date DESC LIMIT 30"),
        engine, params={"uid": user_id}
    )

    # Show xgb_score if present in DB
    xgb_line = ""
    if "xgb_score" in r.index:
        xgb_line = f"XGBoost Score: {r['xgb_score']:.1f}/100\n"

    summary = f"""=== RISK PROFILE: {user_id} ===
Risk Score:  {r['risk_score']:.1f}/100
Rule Score:  {r['rule_score']:.1f}/100
IF Score:    {r['if_score']:.1f}/100
{xgb_line}Is Insider:  {bool(r['is_insider'])}
Alert Count: {r['alert_count']}

BEHAVIORAL FEATURE SUMMARY (last 30 days):
  After-hours logins:      {features['after_hours_login_count'].sum():.0f} total, ratio avg {features['after_hours_ratio'].mean():.1%}
  USB file copies:         {features['file_copy_count'].sum():.0f} total
  After-hours USB copies:  {features['file_copy_after_hours'].sum():.0f}
  Emails sent:             {features['emails_sent'].sum():.0f} total
  External email ratio:    {features['external_recipient_ratio'].mean():.1%} avg
  BCC usage:               {features['bcc_count'].sum():.0f} times
  Angry keywords:          {features['angry_keyword_count'].sum():.0f}
  Job site visits:         {features['job_site_visits'].sum():.0f}
  Suspicious domain visits:{features['suspicious_domain_visits'].sum():.0f}
"""
    return summary


def get_shap_explanation(user_id: str, shap_data: dict) -> str:
    """Get XGBoost SHAP explanation for this user's risk score.

    Args:
        user_id: User ID
        shap_data: Dict from xgboost_model results {user_id: [{feature, shap_value}]}
    """
    if user_id not in shap_data:
        return f"No SHAP explanation available for user {user_id}."

    contributions = shap_data[user_id]
    lines = [f"=== XGBoost SHAP EXPLANATION: {user_id} ==="]
    lines.append("Top features driving the risk score (positive = increases risk):")
    for item in contributions:
        direction = "↑ RISK" if item["shap_value"] > 0 else "↓ risk"
        lines.append(f"  {item['feature']:40s} {item['shap_value']:+.3f} ({direction})")
    return "\n".join(lines)


def compare_to_peers(user_id: str) -> str:
    """Compare user's behavior to the normal user population."""
    user_feats = pd.read_sql(
        text("SELECT * FROM user_features WHERE user_id = :uid"),
        engine, params={"uid": user_id}
    )
    if user_feats.empty:
        return f"No feature data for {user_id}."

    all_feats = pd.read_sql("SELECT * FROM user_features", engine)

    numeric_cols = [
        "after_hours_login_count", "after_hours_ratio", "file_copy_count",
        "file_copy_after_hours", "emails_sent", "external_recipient_ratio",
        "bcc_count", "angry_keyword_count", "job_site_visits", "suspicious_domain_visits"
    ]

    lines = [f"=== PEER COMPARISON: {user_id} ==="]
    lines.append(f"{'Feature':<35} {'This User':>12} {'Pop. Avg':>12} {'Z-Score':>10}")
    lines.append("-" * 75)

    for col in numeric_cols:
        if col not in user_feats.columns:
            continue
        user_val = user_feats[col].mean()
        pop_mean = all_feats[col].mean()
        pop_std = all_feats[col].std()
        if pop_std > 0:
            z = (user_val - pop_mean) / pop_std
            flag = " 🚨" if abs(z) > 2 else ""
        else:
            z = 0
            flag = ""
        lines.append(f"  {col:<33} {user_val:>12.2f} {pop_mean:>12.2f} {z:>+9.2f}σ{flag}")

    return "\n".join(lines)


def get_correlated_users(user_id: str, top_n: int = 5) -> str:
    """Find other users with similar suspicious patterns."""
    high_risk = pd.read_sql(
        text("SELECT user_id, alert_type, severity, risk_score FROM alerts "
             "WHERE severity IN ('CRITICAL', 'HIGH') AND user_id != :uid "
             "ORDER BY risk_score DESC LIMIT :n"),
        engine, params={"uid": user_id, "n": top_n}
    )

    if high_risk.empty:
        return "No correlated high-risk users found."

    lines = ["=== CORRELATED HIGH-RISK USERS ==="]
    lines.append(f"Other users with CRITICAL/HIGH alerts (excluding {user_id}):")
    for _, row in high_risk.iterrows():
        lines.append(
            f"  {row['user_id']:10s}  {row['severity']:8s}  "
            f"score={row['risk_score']:.1f}  type={row['alert_type']}"
        )
    return "\n".join(lines)


def get_alert_history(user_id: str) -> str:
    """Get all alerts for this user."""
    alerts = pd.read_sql(
        text("SELECT alert_type, severity, risk_score, status, created_at "
             "FROM alerts WHERE user_id = :uid ORDER BY created_at DESC"),
        engine, params={"uid": user_id}
    )

    if alerts.empty:
        return f"No alert history for {user_id}."

    lines = [f"=== ALERT HISTORY: {user_id} ==="]
    for _, row in alerts.iterrows():
        lines.append(
            f"  [{row['severity']:8s}] {row['alert_type']:25s} "
            f"score={row['risk_score']:.1f}  status={row['status']}"
        )
    return "\n".join(lines)


def search_past_incidents(query: str, top_n: int = 3) -> str:
    """Search past investigation reports for similar threat patterns.

    Uses ChromaDB semantic search to find historically similar incidents.
    Falls back gracefully if memory module is not initialized.

    Args:
        query: Natural language description of the pattern to search for.
        top_n: Number of similar incidents to return.
    """
    try:
        from src.agent.memory import search_similar_incidents
        results = search_similar_incidents(query, top_n=top_n)
        if not results:
            return "No similar past incidents found in memory."
        lines = ["=== SIMILAR PAST INCIDENTS ==="]
        for r in results:
            lines.append(
                f"  [{r.get('severity','?')}] user={r.get('user_id','?')} "
                f"type={r.get('threat_scenario','?')} confidence={r.get('confidence',0):.2f}\n"
                f"    Summary: {r.get('summary','N/A')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Memory search unavailable ({e}). Proceeding without historical context."


# ─── WRITE TOOLS (Active Response) ───────────────────────────────────────────
# These tools modify the database. They should only be called by the agent
# when confidence >= CONFIDENCE_THRESHOLD (0.85).
# All actions are reversible (no external system calls — DB only).

CONFIDENCE_THRESHOLD = 0.85


def flag_user_for_review(user_id: str, reason: str, confidence: float) -> str:
    """Flag a user for immediate SOC analyst review.

    This writes a FLAGGED status to the alerts table and creates a visible
    notification in the dashboard. Safe and reversible — no system access.

    Args:
        user_id: The user to flag.
        reason: Short explanation of why the flag was raised.
        confidence: Agent's confidence score (0-1). Must be >= 0.85 to flag.
    """
    if confidence < CONFIDENCE_THRESHOLD:
        return (
            f"⚠️  Confidence {confidence:.2f} < threshold {CONFIDENCE_THRESHOLD}. "
            f"Flag NOT applied. Recommend human review instead."
        )
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE alerts
                    SET status = 'FLAGGED_FOR_REVIEW',
                        description = description || ' | AGENT FLAG: ' || :reason
                    WHERE user_id = :uid AND status = 'open'
                """),
                {"uid": user_id, "reason": reason}
            )
        return (
            f"✅ User {user_id} flagged for immediate SOC review.\n"
            f"   Reason: {reason}\n"
            f"   Confidence: {confidence:.2f}\n"
            f"   Status set to FLAGGED_FOR_REVIEW in dashboard."
        )
    except Exception as e:
        return f"Error flagging user: {e}"


def escalate_to_hr(user_id: str, report_summary: str, confidence: float) -> str:
    """Generate a formal HR escalation record with evidence chain.

    Creates a new HIGH-SEVERITY alert of type HR_ESCALATION in the database.
    The dashboard shows this prominently to HR-linked analyst roles.

    Args:
        user_id: The user being escalated.
        report_summary: 1-2 sentence summary of the threat evidence.
        confidence: Agent's confidence score. Must be >= 0.85 to escalate.
    """
    if confidence < CONFIDENCE_THRESHOLD:
        return (
            f"⚠️  Confidence {confidence:.2f} < threshold {CONFIDENCE_THRESHOLD}. "
            f"HR Escalation NOT triggered. Recommend MONITOR status instead."
        )
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO alerts (user_id, alert_type, severity, risk_score,
                        description, contributing_factors, recommended_actions,
                        status, created_at)
                    VALUES (:uid, 'HR_ESCALATION', 'CRITICAL', 95.0,
                        :desc, '["Agent autonomous escalation"]',
                        '["Contact HR", "Restrict system access", "Preserve evidence"]',
                        'HR_ESCALATED', :ts)
                """),
                {
                    "uid": user_id,
                    "desc": f"[AGENT ESCALATION] {report_summary}",
                    "ts": datetime.now().isoformat(),
                }
            )
        return (
            f"✅ HR Escalation record created for user {user_id}.\n"
            f"   Summary: {report_summary}\n"
            f"   Confidence: {confidence:.2f}\n"
            f"   Alert type: HR_ESCALATION (CRITICAL) — visible on dashboard."
        )
    except Exception as e:
        return f"Error creating HR escalation: {e}"


def suppress_false_positive(alert_id: int, justification: str, confidence: float) -> str:
    """Mark an alert as a false positive with agent-generated justification.

    This feeds the feedback loop — suppressed alerts are logged for model re-weighting.

    Args:
        alert_id: The alert ID to suppress.
        justification: Why this is a false positive.
        confidence: Agent's confidence that this is benign. Must be >= 0.85.
    """
    if confidence < CONFIDENCE_THRESHOLD:
        return (
            f"⚠️  Confidence {confidence:.2f} < threshold {CONFIDENCE_THRESHOLD}. "
            f"False positive suppression NOT applied. Leave for human review."
        )
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE alerts
                    SET status = 'FALSE_POSITIVE',
                        description = description || ' | AGENT SUPPRESSED: ' || :j
                    WHERE id = :aid
                """),
                {"aid": alert_id, "j": justification}
            )
        return (
            f"✅ Alert {alert_id} suppressed as FALSE_POSITIVE.\n"
            f"   Justification: {justification}\n"
            f"   This will be logged to the feedback module for model improvement."
        )
    except Exception as e:
        return f"Error suppressing alert: {e}"


def quarantine_alert(alert_id: int, reason: str) -> str:
    """Lock an alert under investigation — prevents parallel analyst actions.

    Sets alert status to UNDER_INVESTIGATION. Any other agent or analyst
    querying this alert will see it is already being handled.

    Args:
        alert_id: Alert ID to quarantine.
        reason: Why it's being quarantined (usually 'Agent investigation in progress').
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE alerts
                    SET status = 'UNDER_INVESTIGATION'
                    WHERE id = :aid AND status = 'open'
                """),
                {"aid": alert_id}
            )
        return f"✅ Alert {alert_id} locked as UNDER_INVESTIGATION. Reason: {reason}"
    except Exception as e:
        return f"Error quarantining alert: {e}"


# ─── Registry — maps tool name string to function (for ReAct parser) ─────────
TOOL_REGISTRY = {
    # Read tools
    "get_user_logs": get_user_logs,
    "get_user_risk_profile": get_user_risk_profile,
    "get_shap_explanation": get_shap_explanation,
    "compare_to_peers": compare_to_peers,
    "get_correlated_users": get_correlated_users,
    "get_alert_history": get_alert_history,
    "search_past_incidents": search_past_incidents,
    # Write tools (active response)
    "flag_user_for_review": flag_user_for_review,
    "escalate_to_hr": escalate_to_hr,
    "suppress_false_positive": suppress_false_positive,
    "quarantine_alert": quarantine_alert,
}
