"""Rule-based insider threat detection engine.

Three scenario-specific detectors matching the CERT r4.2 threat patterns.
Each returns alerts with human-readable 'why flagged?' explanations.
"""
import json
from collections import defaultdict

import pandas as pd
from sqlalchemy import text

from src.utils.db import engine


def detect_scenario_1(features_df: pd.DataFrame) -> list[dict]:
    """Scenario 1: Data exfiltration — after-hours login + suspicious domains + USB copies.

    Pattern: after_hours_login AND (wikileaks/espionage visits) AND usb_copy_burst
    """
    alerts = []

    # Aggregate per user across all days
    user_agg = features_df.groupby("user_id").agg(
        total_after_hours=("after_hours_login_count", "sum"),
        total_suspicious_domains=("suspicious_domain_visits", "sum"),
        total_file_copies=("file_copy_count", "sum"),
        total_file_after_hours=("file_copy_after_hours", "sum"),
        days_active=("date", "count"),
    ).reset_index()

    for _, user in user_agg.iterrows():
        score = 0
        factors = []

        # After-hours activity is significant
        if user["total_after_hours"] > 3:
            score += 30
            factors.append(f"After-hours logins: {user['total_after_hours']}")

        # Suspicious domain visits (wikileaks, spectorsoft)
        if user["total_suspicious_domains"] > 0:
            score += 40
            factors.append(f"Suspicious domain visits: {user['total_suspicious_domains']}")

        # USB file copies during after-hours
        if user["total_file_after_hours"] > 2:
            score += 30
            factors.append(f"After-hours USB file copies: {user['total_file_after_hours']}")
        elif user["total_file_copies"] > 50:
            # High total file copies even during hours
            score += 15
            factors.append(f"High USB file copy count: {user['total_file_copies']}")

        if score >= 60:
            alerts.append({
                "user_id": user["user_id"],
                "alert_type": "DATA_EXFILTRATION",
                "rule_score": min(score, 100),
                "description": (
                    f"User {user['user_id']} shows data exfiltration pattern: "
                    f"after-hours access with suspicious browsing and USB activity."
                ),
                "contributing_factors": factors,
                "recommended_actions": [
                    "Review USB file copy logs for sensitive documents",
                    "Check browsing history for espionage-related sites",
                    "Investigate after-hours logon patterns",
                    "Verify if user has active resignation or termination notice",
                ],
            })

    return alerts


def detect_scenario_2(features_df: pd.DataFrame) -> list[dict]:
    """Scenario 2: Job hunting — repeated job-site visits over multi-day period.

    Pattern: job_site_visits > threshold over multiple days
    """
    alerts = []

    # Count days with job-site visits
    job_activity = features_df[features_df["job_site_visits"] > 0]
    user_job_days = job_activity.groupby("user_id").agg(
        days_with_job_visits=("date", "nunique"),
        total_job_visits=("job_site_visits", "sum"),
    ).reset_index()

    for _, user in user_job_days.iterrows():
        score = 0
        factors = []

        # Multiple days of job-site browsing
        if user["days_with_job_visits"] >= 5:
            score += 50
            factors.append(f"Job-site browsing on {user['days_with_job_visits']} separate days")
        elif user["days_with_job_visits"] >= 2:
            score += 25
            factors.append(f"Job-site browsing on {user['days_with_job_visits']} days")

        # High total visits
        if user["total_job_visits"] >= 10:
            score += 30
            factors.append(f"Total job-site page views: {user['total_job_visits']}")
        elif user["total_job_visits"] >= 3:
            score += 15
            factors.append(f"Job-site page views: {user['total_job_visits']}")

        if score >= 40:
            alerts.append({
                "user_id": user["user_id"],
                "alert_type": "JOB_HUNTING",
                "rule_score": min(score, 100),
                "description": (
                    f"User {user['user_id']} shows disengagement pattern: "
                    f"repeatedly visiting job-seeking sites over {user['days_with_job_visits']} days."
                ),
                "contributing_factors": factors,
                "recommended_actions": [
                    "Review employee engagement and satisfaction metrics",
                    "Check for recent performance review issues",
                    "Monitor for potential data exfiltration before departure",
                    "Consider conducting a retention conversation",
                ],
            })

    return alerts


def detect_scenario_3(features_df: pd.DataFrame) -> list[dict]:
    """Scenario 3: Disgruntled sabotage — angry emails + spyware/keylogger site visits.

    Pattern: angry_email_keywords AND spyware_site_visit
    """
    alerts = []

    user_agg = features_df.groupby("user_id").agg(
        total_angry_keywords=("angry_keyword_count", "sum"),
        days_with_angry=("angry_keyword_count", lambda x: (x > 0).sum()),
        total_suspicious_domains=("suspicious_domain_visits", "sum"),
    ).reset_index()

    for _, user in user_agg.iterrows():
        score = 0
        factors = []

        # Angry email content
        if user["total_angry_keywords"] >= 10:
            score += 40
            factors.append(f"Threatening/disgruntled email keywords: {user['total_angry_keywords']} instances")
        elif user["total_angry_keywords"] >= 3:
            score += 20
            factors.append(f"Disgruntled email keywords: {user['total_angry_keywords']} instances")

        # Suspicious domain visits (spectorsoft = keylogger)
        if user["total_suspicious_domains"] > 0:
            score += 40
            factors.append(f"Keylogger/spyware site visits: {user['total_suspicious_domains']}")

        # Days with angry emails
        if user["days_with_angry"] >= 2:
            score += 20
            factors.append(f"Multiple days with threatening content ({user['days_with_angry']} days)")

        if score >= 50:
            alerts.append({
                "user_id": user["user_id"],
                "alert_type": "DISGRUNTLED_SABOTAGE",
                "rule_score": min(score, 100),
                "description": (
                    f"User {user['user_id']} shows sabotage risk: "
                    f"disgruntled email communications combined with suspicious browsing."
                ),
                "contributing_factors": factors,
                "recommended_actions": [
                    "Escalate to HR for immediate review",
                    "Check for keylogger or malware installation",
                    "Review recent system access for sabotage indicators",
                    "Consider restricting system privileges pending investigation",
                ],
            })

    return alerts


def detect_all(features_df: pd.DataFrame) -> list[dict]:
    """Run all detection rules and return combined alerts."""
    print("[RULES] Running scenario 1 (data exfiltration)...")
    s1 = detect_scenario_1(features_df)
    print(f"  → {len(s1)} alerts")

    print("[RULES] Running scenario 2 (job hunting)...")
    s2 = detect_scenario_2(features_df)
    print(f"  → {len(s2)} alerts")

    print("[RULES] Running scenario 3 (disgruntled sabotage)...")
    s3 = detect_scenario_3(features_df)
    print(f"  → {len(s3)} alerts")

    all_alerts = s1 + s2 + s3
    print(f"[RULES] ✅ Total rule-based alerts: {len(all_alerts)}")
    return all_alerts
