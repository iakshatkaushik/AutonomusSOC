"""Data ingestion pipeline for CERT r4.2 dataset.

Loads logon.csv, file.csv, email.csv into SQLite via SQLAlchemy.
Filters http.csv (14GB) via subprocess grep for target domains only.
Parses insiders.csv for ground truth labels.
"""
import subprocess
import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils.config import RAW_DATA_DIR, ANSWERS_DIR, PROCESSED_DIR
from src.utils.db import (
    engine, SessionLocal, init_db, drop_db,
    LogonEvent, EmailEvent, FileEvent, HttpEvent, Insider
)


def parse_cert_datetime(dt_str: str) -> datetime:
    """Parse CERT date format: 'MM/DD/YYYY HH:MM:SS'"""
    try:
        return datetime.strptime(dt_str.strip(), "%m/%d/%Y %H:%M:%S")
    except (ValueError, AttributeError):
        return None


# ─── Insiders ─────────────────────────────────────────────────────────

def ingest_insiders():
    """Parse insiders.csv → extract r4.2 insider user IDs + time windows."""
    insiders_path = ANSWERS_DIR / "insiders.csv"
    print(f"[INGEST] Loading insiders from {insiders_path}")

    records = []
    with open(insiders_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Only r4.2 entries
            if not row["dataset"].strip().startswith("4.2"):
                continue
            records.append(Insider(
                user_id=row["user"].strip(),
                scenario=int(row["scenario"].strip()),
                start_time=parse_cert_datetime(row["start"]),
                end_time=parse_cert_datetime(row["end"]),
                details_file=row["details"].strip(),
            ))

    session = SessionLocal()
    try:
        session.bulk_save_objects(records)
        session.commit()
        print(f"[INGEST] ✅ Loaded {len(records)} insider records")
    finally:
        session.close()

    return len(records)


# ─── Logon Events ─────────────────────────────────────────────────────

def ingest_logon(batch_size: int = 50000):
    """Load logon.csv (56MB, 854K rows) into DB."""
    logon_path = RAW_DATA_DIR / "logon.csv"
    print(f"[INGEST] Loading logon events from {logon_path}")

    total = 0
    for chunk in pd.read_csv(logon_path, chunksize=batch_size):
        records = []
        for _, row in chunk.iterrows():
            ts = parse_cert_datetime(row["date"])
            if ts is None:
                continue
            records.append({
                "event_id": row["id"],
                "timestamp": ts,
                "user_id": row["user"],
                "pc": row["pc"],
                "activity": row["activity"],
            })

        if records:
            with engine.begin() as conn:
                conn.execute(LogonEvent.__table__.insert(), records)
            total += len(records)
            print(f"  ... {total} logon events loaded")

    print(f"[INGEST] ✅ Loaded {total} logon events")
    return total


# ─── File (USB) Events ────────────────────────────────────────────────

def ingest_file(batch_size: int = 50000):
    """Load file.csv (184MB, 445K rows) into DB."""
    file_path = RAW_DATA_DIR / "file.csv"
    print(f"[INGEST] Loading file/USB events from {file_path}")

    total = 0
    for chunk in pd.read_csv(file_path, chunksize=batch_size):
        records = []
        for _, row in chunk.iterrows():
            ts = parse_cert_datetime(row["date"])
            if ts is None:
                continue
            records.append({
                "event_id": row["id"],
                "timestamp": ts,
                "user_id": row["user"],
                "pc": row["pc"],
                "filename": str(row.get("filename", "")),
                "content": "",  # Skip content to save space; we don't need it for detection
            })

        if records:
            with engine.begin() as conn:
                conn.execute(FileEvent.__table__.insert(), records)
            total += len(records)
            print(f"  ... {total} file events loaded")

    print(f"[INGEST] ✅ Loaded {total} file events")
    return total


# ─── Email Events ─────────────────────────────────────────────────────

def ingest_email(batch_size: int = 50000):
    """Load email.csv (1.1GB, 2.3M rows) into DB in chunks."""
    email_path = RAW_DATA_DIR / "email.csv"
    print(f"[INGEST] Loading email events from {email_path}")

    total = 0
    for chunk in pd.read_csv(email_path, chunksize=batch_size, low_memory=False):
        records = []
        for _, row in chunk.iterrows():
            ts = parse_cert_datetime(row["date"])
            if ts is None:
                continue
            records.append({
                "event_id": row["id"],
                "timestamp": ts,
                "user_id": row["user"],
                "pc": row["pc"],
                "to_addrs": str(row.get("to", "")),
                "cc_addrs": str(row.get("cc", "")),
                "bcc_addrs": str(row.get("bcc", "")),
                "from_addr": str(row.get("from", "")),
                "size": int(row["size"]) if pd.notna(row.get("size")) else 0,
                "attachments": int(row["attachments"]) if pd.notna(row.get("attachments")) else 0,
                "content": str(row.get("content", "")),
            })

        if records:
            with engine.begin() as conn:
                conn.execute(EmailEvent.__table__.insert(), records)
            total += len(records)
            print(f"  ... {total} email events loaded")

    print(f"[INGEST] ✅ Loaded {total} email events")
    return total


# ─── HTTP Events (grep-filtered) ─────────────────────────────────────

TARGET_DOMAINS = [
    "wikileaks",
    "monster\\.com",
    "craigslist",
    "jobhuntersbible",
    "spectorsoft",
]


def ingest_http_filtered():
    """Filter http.csv (14GB) via grep for target domains only, then load.

    This avoids loading 14GB into memory. grep runs in seconds.
    """
    http_path = RAW_DATA_DIR / "http.csv"
    filtered_path = PROCESSED_DIR / "http_filtered.csv"

    if not http_path.exists():
        print(f"[INGEST] ⚠️  http.csv not found at {http_path}, skipping HTTP ingestion")
        return 0

    # Step 1: grep for target domains
    pattern = "\\|".join(TARGET_DOMAINS)
    print(f"[INGEST] Filtering http.csv for domains: {TARGET_DOMAINS}")

    # Get header first
    with open(http_path, "r") as f:
        header = f.readline()

    # grep the matching rows
    result = subprocess.run(
        ["grep", "-i", pattern, str(http_path)],
        capture_output=True, text=True
    )

    if result.returncode not in (0, 1):  # 1 = no matches (fine)
        print(f"[INGEST] ⚠️  grep failed: {result.stderr}")
        return 0

    # Write filtered CSV
    with open(filtered_path, "w") as f:
        f.write(header)
        f.write(result.stdout)

    # Step 2: load the filtered CSV (should be small now)
    if result.stdout.strip() == "":
        print("[INGEST] ⚠️  No matching HTTP events found")
        return 0

    df = pd.read_csv(filtered_path)
    print(f"[INGEST] Filtered HTTP: {len(df)} rows (from ~28M+)")

    records = []
    for _, row in df.iterrows():
        ts = parse_cert_datetime(row["date"])
        if ts is None:
            continue
        records.append({
            "event_id": row["id"],
            "timestamp": ts,
            "user_id": row["user"],
            "pc": row["pc"],
            "url": str(row.get("url", "")),
            "content": str(row.get("content", "")),
        })

    if records:
        session = SessionLocal()
        try:
            with engine.begin() as conn:
                conn.execute(HttpEvent.__table__.insert(), records)
            print(f"[INGEST] ✅ Loaded {len(records)} filtered HTTP events")
        finally:
            session.close()

    return len(records)


# ─── Run All ──────────────────────────────────────────────────────────

def ingest_all(fresh: bool = True):
    """Run the full ingestion pipeline."""
    print("=" * 60)
    print("  AutonomusSOC — Data Ingestion Pipeline")
    print("=" * 60)

    if fresh:
        print("[INGEST] Dropping existing tables...")
        drop_db()

    print("[INGEST] Creating tables...")
    init_db()

    counts = {}
    counts["insiders"] = ingest_insiders()
    counts["logon"] = ingest_logon()
    counts["file"] = ingest_file()
    counts["email"] = ingest_email()
    counts["http"] = ingest_http_filtered()

    print()
    print("=" * 60)
    print("  Ingestion Complete!")
    print("=" * 60)
    for name, count in counts.items():
        print(f"  {name:>10}: {count:>12,} rows")
    print("=" * 60)

    return counts


if __name__ == "__main__":
    ingest_all()
