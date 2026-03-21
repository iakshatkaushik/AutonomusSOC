"""Feature engineering — extract per-user-per-day behavioral features from CERT data.

Reads from SQLite/PostgreSQL via SQLAlchemy, computes features, writes back to user_features table.
"""
from datetime import datetime
from collections import defaultdict

import pandas as pd
from sqlalchemy import text

from src.utils.db import engine, SessionLocal, UserFeature, init_db

# Keywords for detection
ANGRY_KEYWORDS = {
    "fed up", "i may leave", "i will leave", "complaints", "company will suffer",
    "angry", "outraged", "not my fault", "exacerbated", "bad things",
    "two faced", "take me seriously", "i am irreplaceable",
    "no gratitude", "my work not appreciated", "too much",
}

JOB_SITE_DOMAINS = {"monster.com", "craigslist", "jobhuntersbible"}
SUSPICIOUS_DOMAINS = {"wikileaks", "spectorsoft"}


def _is_after_hours(hour: int) -> bool:
    """Before 7 AM or after 7 PM."""
    return hour < 7 or hour >= 19


def _is_weekend(dt: datetime) -> bool:
    return dt.weekday() >= 5  # Saturday=5, Sunday=6


def _count_keywords(text_content: str, keyword_set: set) -> int:
    """Count how many keywords from the set appear in the text."""
    if not text_content or pd.isna(text_content):
        return 0
    text_lower = text_content.lower()
    count = 0
    for kw in keyword_set:
        count += text_lower.count(kw)
    return count


def _is_external_email(addr: str) -> bool:
    """External = NOT @dtaa.com"""
    if not addr or pd.isna(addr):
        return False
    return "@dtaa.com" not in addr.lower()


def compute_features() -> pd.DataFrame:
    """Compute all per-user-per-day features and store in DB.

    Returns the feature DataFrame.
    """
    print("[FEATURES] Computing per-user-per-day features...")

    # ─── 1. Load raw events from DB ─────────────────────────────────
    print("  Loading logon events...")
    logon_df = pd.read_sql("SELECT timestamp, user_id, pc, activity FROM logon_events", engine)
    logon_df["timestamp"] = pd.to_datetime(logon_df["timestamp"])
    logon_df["date"] = logon_df["timestamp"].dt.date.astype(str)
    logon_df["hour"] = logon_df["timestamp"].dt.hour

    print("  Loading file events...")
    file_df = pd.read_sql("SELECT timestamp, user_id FROM file_events", engine)
    file_df["timestamp"] = pd.to_datetime(file_df["timestamp"])
    file_df["date"] = file_df["timestamp"].dt.date.astype(str)
    file_df["hour"] = file_df["timestamp"].dt.hour

    print("  Loading email events...")
    email_df = pd.read_sql(
        "SELECT timestamp, user_id, to_addrs, cc_addrs, bcc_addrs, from_addr, attachments, content "
        "FROM email_events", engine
    )
    email_df["timestamp"] = pd.to_datetime(email_df["timestamp"])
    email_df["date"] = email_df["timestamp"].dt.date.astype(str)

    print("  Loading HTTP events...")
    http_df = pd.read_sql("SELECT timestamp, user_id, url, content FROM http_events", engine)
    http_df["timestamp"] = pd.to_datetime(http_df["timestamp"])
    http_df["date"] = http_df["timestamp"].dt.date.astype(str)

    # ─── 2. Get all user-date pairs ─────────────────────────────────
    all_users = set(logon_df["user_id"].unique())
    all_dates = sorted(set(logon_df["date"].unique()))
    print(f"  Users: {len(all_users)}, Date range: {all_dates[0]} to {all_dates[-1]}")

    # ─── 3. Compute logon features ──────────────────────────────────
    print("  Computing logon features...")
    logon_logins = logon_df[logon_df["activity"] == "Logon"]

    logon_features = logon_logins.groupby(["user_id", "date"]).agg(
        login_count=("activity", "count"),
        after_hours_login_count=("hour", lambda x: sum(_is_after_hours(h) for h in x)),
        unique_pcs=("pc", "nunique"),
    ).reset_index()

    logon_features["after_hours_ratio"] = (
        logon_features["after_hours_login_count"] / logon_features["login_count"].clip(lower=1)
    )

    logoff_counts = logon_df[logon_df["activity"] == "Logoff"].groupby(
        ["user_id", "date"]
    ).size().reset_index(name="logoff_count")

    logon_features = logon_features.merge(logoff_counts, on=["user_id", "date"], how="left")
    logon_features["logoff_count"] = logon_features["logoff_count"].fillna(0).astype(int)

    # Weekend flag
    logon_features["weekend_login"] = logon_features["date"].apply(
        lambda d: datetime.strptime(d, "%Y-%m-%d").weekday() >= 5
    )

    # ─── 4. Compute file/USB features ───────────────────────────────
    print("  Computing file/USB features...")
    file_features = file_df.groupby(["user_id", "date"]).agg(
        file_copy_count=("user_id", "count"),
        file_copy_after_hours=("hour", lambda x: sum(_is_after_hours(h) for h in x)),
    ).reset_index()

    # ─── 5. Compute email features ──────────────────────────────────
    print("  Computing email features...")

    # Only sent emails (where user_id matches from_addr pattern)
    # In CERT data, user sends = row's user_id is the sender
    email_sent = email_df.copy()

    email_agg = defaultdict(lambda: {
        "emails_sent": 0,
        "external_recipient_count": 0,
        "total_recipient_count": 0,
        "bcc_count": 0,
        "attachment_count": 0,
        "angry_keyword_count": 0,
    })

    for _, row in email_sent.iterrows():
        key = (row["user_id"], row["date"])
        agg = email_agg[key]
        agg["emails_sent"] += 1
        agg["attachment_count"] += int(row["attachments"]) if pd.notna(row["attachments"]) else 0

        # Count recipients
        for field in ["to_addrs", "cc_addrs"]:
            if pd.notna(row[field]) and row[field]:
                addrs = str(row[field]).split(";")
                agg["total_recipient_count"] += len(addrs)
                agg["external_recipient_count"] += sum(1 for a in addrs if _is_external_email(a))

        # BCC
        if pd.notna(row["bcc_addrs"]) and str(row["bcc_addrs"]).strip():
            agg["bcc_count"] += 1

        # Angry keywords in content
        agg["angry_keyword_count"] += _count_keywords(row["content"], ANGRY_KEYWORDS)

    email_records = []
    for (user_id, date), agg in email_agg.items():
        total_recip = max(agg["total_recipient_count"], 1)
        email_records.append({
            "user_id": user_id,
            "date": date,
            "emails_sent": agg["emails_sent"],
            "external_recipient_ratio": agg["external_recipient_count"] / total_recip,
            "bcc_count": agg["bcc_count"],
            "attachment_count": agg["attachment_count"],
            "angry_keyword_count": agg["angry_keyword_count"],
        })

    email_features = pd.DataFrame(email_records) if email_records else pd.DataFrame(
        columns=["user_id", "date", "emails_sent", "external_recipient_ratio",
                 "bcc_count", "attachment_count", "angry_keyword_count"]
    )

    # ─── 6. Compute HTTP features ───────────────────────────────────
    print("  Computing HTTP features...")

    http_agg = defaultdict(lambda: {"job_site_visits": 0, "suspicious_domain_visits": 0})

    for _, row in http_df.iterrows():
        key = (row["user_id"], row["date"])
        url = str(row.get("url", "")).lower()
        if any(d in url for d in JOB_SITE_DOMAINS):
            http_agg[key]["job_site_visits"] += 1
        if any(d in url for d in SUSPICIOUS_DOMAINS):
            http_agg[key]["suspicious_domain_visits"] += 1

    http_records = [
        {"user_id": uid, "date": date, **counts}
        for (uid, date), counts in http_agg.items()
    ]
    http_features = pd.DataFrame(http_records) if http_records else pd.DataFrame(
        columns=["user_id", "date", "job_site_visits", "suspicious_domain_visits"]
    )

    # ─── 7. Merge all features ──────────────────────────────────────
    print("  Merging all features...")
    features = logon_features.copy()

    features = features.merge(file_features, on=["user_id", "date"], how="left")
    features = features.merge(email_features, on=["user_id", "date"], how="left")
    features = features.merge(http_features, on=["user_id", "date"], how="left")

    # Fill NaN with 0
    numeric_cols = [
        "login_count", "logoff_count", "after_hours_login_count", "after_hours_ratio",
        "unique_pcs", "file_copy_count", "file_copy_after_hours",
        "emails_sent", "external_recipient_ratio", "bcc_count", "attachment_count",
        "angry_keyword_count", "job_site_visits", "suspicious_domain_visits",
    ]
    for col in numeric_cols:
        if col in features.columns:
            features[col] = features[col].fillna(0)

    features["weekend_login"] = features["weekend_login"].fillna(False)

    print(f"  Feature matrix: {features.shape[0]} user-day rows, {features.shape[1]} columns")

    # ─── 8. Write to DB ─────────────────────────────────────────────
    print("  Writing features to database...")
    # Clear existing features
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM user_features"))

    records = features.to_dict(orient="records")
    batch_size = 10000
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        with engine.begin() as conn:
            conn.execute(UserFeature.__table__.insert(), batch)
        print(f"    ... {min(i + batch_size, len(records))}/{len(records)} feature rows written")

    print(f"[FEATURES] ✅ Computed and stored {len(records)} user-day feature rows")
    return features


if __name__ == "__main__":
    compute_features()
