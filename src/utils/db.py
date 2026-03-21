"""Database connection and SQLAlchemy models.

Uses SQLAlchemy ORM so the DB is swappable:
  SQLite (dev):    sqlite:///data/processed/autonomussoc.db
  PostgreSQL (prod): postgresql://user:pass@host:5432/autonomussoc

Change DATABASE_URL in .env — no other code changes needed.
"""
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, DateTime, Text, Boolean,
    ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from src.utils.config import DATABASE_URL

# Engine — for SQLite, need check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db() -> Session:
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Models ───────────────────────────────────────────────────────────

class LogonEvent(Base):
    __tablename__ = "logon_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    user_id = Column(String, index=True)
    pc = Column(String)
    activity = Column(String)  # Logon / Logoff


class EmailEvent(Base):
    __tablename__ = "email_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    user_id = Column(String, index=True)
    pc = Column(String)
    to_addrs = Column(Text)
    cc_addrs = Column(Text)
    bcc_addrs = Column(Text)
    from_addr = Column(String)
    size = Column(Integer)
    attachments = Column(Integer)
    content = Column(Text)


class FileEvent(Base):
    __tablename__ = "file_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    user_id = Column(String, index=True)
    pc = Column(String)
    filename = Column(String)
    content = Column(Text)


class HttpEvent(Base):
    __tablename__ = "http_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    user_id = Column(String, index=True)
    pc = Column(String)
    url = Column(Text)
    content = Column(Text)


class Insider(Base):
    __tablename__ = "insiders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)
    scenario = Column(Integer)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    details_file = Column(String)


class UserFeature(Base):
    __tablename__ = "user_features"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)
    date = Column(String, index=True)  # YYYY-MM-DD
    # Logon features
    login_count = Column(Integer, default=0)
    logoff_count = Column(Integer, default=0)
    after_hours_login_count = Column(Integer, default=0)
    after_hours_ratio = Column(Float, default=0.0)
    unique_pcs = Column(Integer, default=0)
    weekend_login = Column(Boolean, default=False)
    # File/USB features
    file_copy_count = Column(Integer, default=0)
    file_copy_after_hours = Column(Integer, default=0)
    # Email features
    emails_sent = Column(Integer, default=0)
    external_recipient_ratio = Column(Float, default=0.0)
    bcc_count = Column(Integer, default=0)
    attachment_count = Column(Integer, default=0)
    angry_keyword_count = Column(Integer, default=0)
    # HTTP features
    job_site_visits = Column(Integer, default=0)
    suspicious_domain_visits = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_user_date", "user_id", "date", unique=True),
    )


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)
    alert_type = Column(String)  # DATA_EXFILTRATION / JOB_HUNTING / DISGRUNTLED_SABOTAGE / ANOMALY
    severity = Column(String)  # CRITICAL / HIGH / MEDIUM / LOW
    risk_score = Column(Float)
    description = Column(Text)
    contributing_factors = Column(Text)  # JSON string
    recommended_actions = Column(Text)  # JSON string
    status = Column(String, default="open")  # open / acknowledged / dismissed / escalated
    created_at = Column(DateTime)


class UserRisk(Base):
    __tablename__ = "user_risks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, index=True)
    risk_score = Column(Float, default=0.0)
    rule_score = Column(Float, default=0.0)
    if_score = Column(Float, default=0.0)
    alert_count = Column(Integer, default=0)
    is_insider = Column(Boolean, default=False)  # Ground truth (for evaluation)
    scenario = Column(Integer, nullable=True)


class InvestigationReport(Base):
    """LLM agent investigation report — one per alert investigated."""
    __tablename__ = "investigation_reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, index=True, nullable=True)
    user_id = Column(String, index=True)
    summary = Column(Text)
    threat_scenario = Column(String)
    confidence = Column(Float)
    evidence_chain = Column(Text)            # JSON list
    reasoning = Column(Text)
    recommended_action = Column(String)      # ESCALATE_TO_HR / ESCALATE_TO_SECURITY / MONITOR / DISMISS
    recommended_actions_detail = Column(Text)  # JSON list
    correlated_users = Column(Text)          # JSON list
    risk_score = Column(Float)
    severity = Column(String)
    iterations = Column(Integer)
    llm_model = Column(String)
    created_at = Column(DateTime)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(engine)


def drop_db():
    """Drop all tables (for re-ingestion)."""
    Base.metadata.drop_all(engine)
