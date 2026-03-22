"""FastAPI backend — serves the React dashboard and exposes agent results.

Endpoints:
  GET  /api/v1/dashboard/overview      → alert counts, top risks, key metrics
  GET  /api/v1/alerts                  → all alerts (filter: severity, status)
  GET  /api/v1/alerts/{id}             → alert detail + investigation report
  PATCH /api/v1/alerts/{id}/status     → update alert status
  GET  /api/v1/users                   → all users with risk scores
  GET  /api/v1/users/{id}              → user profile + features + SHAP
  GET  /api/v1/users/{id}/logs         → raw event logs for user
  POST /api/v1/investigate/{alert_id}  → trigger LLM agent investigation
  GET  /api/v1/reports/{alert_id}      → get investigation report
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text, func
from sqlalchemy.orm import Session

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.db import (
    get_db, engine, SessionLocal, init_db,
    Alert, UserRisk, UserFeature, InvestigationReport,
    LogonEvent, FileEvent, EmailEvent, HttpEvent,
)

# ─── App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="CyberSOC-Agent API",
    description="Autonomous AI-Powered SOC — Insider Threat Detection",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure tables exist on startup
init_db()


# ─── Pydantic Schemas ─────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: str  # open / acknowledged / dismissed / escalated


class AlertOut(BaseModel):
    id: int
    user_id: str
    alert_type: str
    severity: str
    risk_score: float
    description: Optional[str] = None
    contributing_factors: Optional[list] = None
    recommended_actions: Optional[list] = None
    status: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class UserRiskOut(BaseModel):
    id: int
    user_id: str
    risk_score: float
    rule_score: float
    if_score: float
    alert_count: int
    is_insider: bool
    scenario: Optional[int] = None

    class Config:
        from_attributes = True


class ReportOut(BaseModel):
    id: int
    alert_id: Optional[int] = None
    user_id: str
    summary: Optional[str] = None
    threat_scenario: Optional[str] = None
    confidence: Optional[float] = None
    evidence_chain: Optional[list] = None
    reasoning: Optional[str] = None
    recommended_action: Optional[str] = None
    recommended_actions_detail: Optional[list] = None
    correlated_users: Optional[list] = None
    risk_score: Optional[float] = None
    severity: Optional[str] = None
    iterations: Optional[int] = None
    llm_model: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Helpers ───────────────────────────────────────────────────────────

def _safe_json(val):
    """Parse a JSON string field, return list/dict or empty list."""
    if val is None:
        return []
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _alert_to_dict(a: Alert) -> dict:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "risk_score": a.risk_score,
        "description": a.description,
        "contributing_factors": _safe_json(a.contributing_factors),
        "recommended_actions": _safe_json(a.recommended_actions),
        "status": a.status,
        "created_at": str(a.created_at) if a.created_at else None,
    }


def _report_to_dict(r: InvestigationReport) -> dict:
    return {
        "id": r.id,
        "alert_id": r.alert_id,
        "user_id": r.user_id,
        "summary": r.summary,
        "threat_scenario": r.threat_scenario,
        "confidence": r.confidence,
        "evidence_chain": _safe_json(r.evidence_chain),
        "reasoning": r.reasoning,
        "recommended_action": r.recommended_action,
        "recommended_actions_detail": _safe_json(r.recommended_actions_detail),
        "correlated_users": _safe_json(r.correlated_users),
        "risk_score": r.risk_score,
        "severity": r.severity,
        "iterations": r.iterations,
        "llm_model": r.llm_model,
        "created_at": str(r.created_at) if r.created_at else None,
    }


# ─── 1. Dashboard Overview ────────────────────────────────────────────

@app.get("/api/v1/dashboard/overview")
def dashboard_overview(db: Session = Depends(get_db)):
    """Alert counts by severity, top riskiest users, investigation stats."""

    # Alert counts by severity
    severity_counts = {}
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = db.query(func.count(Alert.id)).filter(Alert.severity == sev).scalar()
        severity_counts[sev] = count or 0

    total_alerts = sum(severity_counts.values())
    open_alerts = db.query(func.count(Alert.id)).filter(Alert.status == "open").scalar() or 0

    # Investigation stats
    total_investigated = db.query(func.count(InvestigationReport.id)).scalar() or 0

    # Top 10 riskiest users
    top_users = (
        db.query(UserRisk)
        .order_by(UserRisk.risk_score.desc())
        .limit(10)
        .all()
    )
    top_users_list = [
        {
            "user_id": u.user_id,
            "risk_score": u.risk_score,
            "is_insider": u.is_insider,
            "alert_count": u.alert_count,
        }
        for u in top_users
    ]

    # Recent alerts (last 20)
    recent_alerts = (
        db.query(Alert)
        .order_by(Alert.risk_score.desc())
        .limit(20)
        .all()
    )
    recent_list = [_alert_to_dict(a) for a in recent_alerts]

    # Total users
    total_users = db.query(func.count(UserRisk.id)).scalar() or 0

    return {
        "severity_counts": severity_counts,
        "total_alerts": total_alerts,
        "open_alerts": open_alerts,
        "total_investigated": total_investigated,
        "total_users": total_users,
        "top_risky_users": top_users_list,
        "recent_alerts": recent_list,
    }


# ─── 2. Alerts ────────────────────────────────────────────────────────

@app.get("/api/v1/alerts")
def list_alerts(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List all alerts with optional filters."""
    q = db.query(Alert)
    if severity:
        q = q.filter(Alert.severity == severity.upper())
    if status:
        q = q.filter(Alert.status == status.lower())
    if alert_type:
        q = q.filter(Alert.alert_type == alert_type.upper())

    total = q.count()
    alerts = q.order_by(Alert.risk_score.desc()).offset(offset).limit(limit).all()

    # Check which alerts have investigation reports
    alert_ids = [a.id for a in alerts]
    investigated_ids = set()
    if alert_ids:
        investigated = (
            db.query(InvestigationReport.alert_id)
            .filter(InvestigationReport.alert_id.in_(alert_ids))
            .all()
        )
        investigated_ids = {r.alert_id for r in investigated}

    result = []
    for a in alerts:
        d = _alert_to_dict(a)
        d["has_investigation"] = a.id in investigated_ids
        result.append(d)

    return {"total": total, "alerts": result}


@app.get("/api/v1/alerts/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Get alert detail + attached investigation report."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    result = _alert_to_dict(alert)

    # Attach investigation report if exists
    report = (
        db.query(InvestigationReport)
        .filter(InvestigationReport.alert_id == alert_id)
        .order_by(InvestigationReport.created_at.desc())
        .first()
    )
    result["investigation_report"] = _report_to_dict(report) if report else None

    return result


@app.patch("/api/v1/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, body: StatusUpdate, db: Session = Depends(get_db)):
    """Update alert status."""
    valid = {"open", "acknowledged", "dismissed", "escalated"}
    if body.status.lower() not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = body.status.lower()
    db.commit()
    return {"message": "Status updated", "alert_id": alert_id, "status": alert.status}


# ─── 3. Users ─────────────────────────────────────────────────────────

@app.get("/api/v1/users")
def list_users(
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """All users with risk scores."""
    total = db.query(func.count(UserRisk.id)).scalar() or 0
    users = (
        db.query(UserRisk)
        .order_by(UserRisk.risk_score.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "users": [
            {
                "id": u.id,
                "user_id": u.user_id,
                "risk_score": u.risk_score,
                "rule_score": u.rule_score,
                "if_score": u.if_score,
                "alert_count": u.alert_count,
                "is_insider": u.is_insider,
                "scenario": u.scenario,
            }
            for u in users
        ],
    }


@app.get("/api/v1/users/{user_id}")
def get_user(user_id: str, db: Session = Depends(get_db)):
    """User profile + feature summary."""
    risk = db.query(UserRisk).filter(UserRisk.user_id == user_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="User not found")

    # Feature summary (aggregated)
    features = (
        db.query(UserFeature)
        .filter(UserFeature.user_id == user_id)
        .order_by(UserFeature.date.desc())
        .limit(60)
        .all()
    )

    feature_summary = {}
    if features:
        cols = [
            "login_count", "after_hours_login_count", "after_hours_ratio",
            "unique_pcs", "file_copy_count", "file_copy_after_hours",
            "emails_sent", "external_recipient_ratio", "bcc_count",
            "attachment_count", "angry_keyword_count",
            "job_site_visits", "suspicious_domain_visits",
        ]
        for col in cols:
            vals = [getattr(f, col, 0) or 0 for f in features]
            feature_summary[col] = {
                "total": sum(vals),
                "avg": round(sum(vals) / len(vals), 2) if vals else 0,
                "max": max(vals) if vals else 0,
            }

    # Alerts for this user
    alerts = db.query(Alert).filter(Alert.user_id == user_id).order_by(Alert.risk_score.desc()).all()

    # Investigation reports for this user
    reports = (
        db.query(InvestigationReport)
        .filter(InvestigationReport.user_id == user_id)
        .order_by(InvestigationReport.created_at.desc())
        .all()
    )

    return {
        "user_id": risk.user_id,
        "risk_score": risk.risk_score,
        "rule_score": risk.rule_score,
        "if_score": risk.if_score,
        "alert_count": risk.alert_count,
        "is_insider": risk.is_insider,
        "scenario": risk.scenario,
        "feature_summary": feature_summary,
        "alerts": [_alert_to_dict(a) for a in alerts],
        "investigation_reports": [_report_to_dict(r) for r in reports],
    }


@app.get("/api/v1/users/{user_id}/logs")
def get_user_logs(
    user_id: str,
    log_type: str = Query("all", description="logon, file, email, http, or all"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Raw event logs for a user."""
    result = {}

    if log_type in ("logon", "all"):
        logons = (
            db.query(LogonEvent)
            .filter(LogonEvent.user_id == user_id)
            .order_by(LogonEvent.timestamp.desc())
            .limit(limit)
            .all()
        )
        result["logon_events"] = [
            {"id": e.id, "timestamp": str(e.timestamp), "pc": e.pc, "activity": e.activity}
            for e in logons
        ]

    if log_type in ("file", "all"):
        files = (
            db.query(FileEvent)
            .filter(FileEvent.user_id == user_id)
            .order_by(FileEvent.timestamp.desc())
            .limit(limit)
            .all()
        )
        result["file_events"] = [
            {"id": e.id, "timestamp": str(e.timestamp), "pc": e.pc, "filename": e.filename}
            for e in files
        ]

    if log_type in ("email", "all"):
        emails = (
            db.query(EmailEvent)
            .filter(EmailEvent.user_id == user_id)
            .order_by(EmailEvent.timestamp.desc())
            .limit(limit)
            .all()
        )
        result["email_events"] = [
            {
                "id": e.id, "timestamp": str(e.timestamp),
                "to_addrs": e.to_addrs, "bcc_addrs": e.bcc_addrs,
                "attachments": e.attachments, "content": (e.content or "")[:200],
            }
            for e in emails
        ]

    if log_type in ("http", "all"):
        https = (
            db.query(HttpEvent)
            .filter(HttpEvent.user_id == user_id)
            .order_by(HttpEvent.timestamp.desc())
            .limit(limit)
            .all()
        )
        result["http_events"] = [
            {"id": e.id, "timestamp": str(e.timestamp), "url": e.url}
            for e in https
        ]

    return {"user_id": user_id, "logs": result}


# ─── 4. Investigation ─────────────────────────────────────────────────

@app.post("/api/v1/investigate/{alert_id}")
def trigger_investigation(alert_id: int, db: Session = Depends(get_db)):
    """Trigger LLM agent investigation on an alert.

    The agent uses its own tools to query the DB for logs, risk profiles,
    peer comparisons, etc.  We do NOT re-train XGBoost here — the agent's
    get_shap_explanation tool already reads pre-computed feature data.
    """
    import traceback

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        # Import agent — lazy so the server starts even if deps are missing
        from src.agent.react_agent import investigate

        # Run the ReAct agent (all evidence gathering happens via its tools)
        report = investigate(
            user_id=alert.user_id,
            alert_type=alert.alert_type,
            risk_score=float(alert.risk_score),
            severity=alert.severity,
            shap_data={},           # Agent tools query DB directly
            max_iterations=8,
        )

        # Store the investigation report
        record = InvestigationReport(
            alert_id=alert_id,
            user_id=report.get("user_id", alert.user_id),
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
        db.add(record)
        db.commit()
        db.refresh(record)

        # Update alert status
        alert.status = "acknowledged"
        db.commit()

        return _report_to_dict(record)

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@app.get("/api/v1/reports/{alert_id}")
def get_report(alert_id: int, db: Session = Depends(get_db)):
    """Get investigation report for an alert."""
    report = (
        db.query(InvestigationReport)
        .filter(InvestigationReport.alert_id == alert_id)
        .order_by(InvestigationReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="No investigation report for this alert")

    return _report_to_dict(report)


# ─── 5. PDF Report Generation ─────────────────────────────────────────

@app.get("/api/v1/reports/{alert_id}/pdf")
def download_pdf_report(alert_id: int, db: Session = Depends(get_db)):
    """Generate and download a dark-themed PDF incident report."""
    from fastapi.responses import Response

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert_data = _alert_to_dict(alert)

    # Get investigation report if exists
    report = (
        db.query(InvestigationReport)
        .filter(InvestigationReport.alert_id == alert_id)
        .order_by(InvestigationReport.created_at.desc())
        .first()
    )
    report_data = _report_to_dict(report) if report else None

    try:
        from src.api.pdf_report import generate_incident_pdf
        pdf_bytes = generate_incident_pdf(alert_data, report_data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    filename = f"CyberSOC_Report_Alert_{alert_id}_{alert_data['user_id']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Model Evaluation ──────────────────────────────────────────────────

_eval_cache = None

@app.get("/api/v1/evaluation")
def get_evaluation_metrics():
    """Run all model evaluations and return metrics. Results are cached."""
    global _eval_cache
    if _eval_cache is not None:
        return _eval_cache

    import numpy as np
    import pandas as pd
    import xgboost as xgb_lib
    import torch
    import torch.nn as tnn
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedKFold, train_test_split
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score, average_precision_score, confusion_matrix
    )
    from src.utils.db import Insider

    ML_FEATURES = [
        "login_count", "after_hours_login_count", "after_hours_ratio",
        "unique_pcs", "file_copy_count", "file_copy_after_hours",
        "emails_sent", "external_recipient_ratio", "bcc_count",
        "attachment_count", "angry_keyword_count",
        "job_site_visits", "suspicious_domain_visits",
    ]

    # Load data
    features_df = pd.read_sql("SELECT * FROM user_features", engine)
    session = SessionLocal()
    insiders = {i.user_id for i in session.query(Insider).all()}
    session.close()

    # aggregate per user
    agg_dict = {}
    for col in ML_FEATURES:
        if col in features_df.columns:
            agg_dict[f"{col}_mean"] = (col, "mean")
            agg_dict[f"{col}_max"] = (col, "max")
            agg_dict[f"{col}_sum"] = (col, "sum")
            agg_dict[f"{col}_std"] = (col, "std")
    user_agg = features_df.groupby("user_id").agg(**agg_dict).reset_index().fillna(0)
    X = user_agg.drop("user_id", axis=1).values.astype(np.float32)
    y = np.array([1 if uid in insiders else 0 for uid in user_agg["user_id"]])

    results = {"models": [], "dataset_info": {
        "total_users": int(len(y)),
        "insiders": int(y.sum()),
        "normal": int(len(y) - y.sum()),
        "features": len([c for c in user_agg.columns if c != "user_id"]),
        "imbalance_ratio": f"1:{int((len(y) - y.sum()) / max(y.sum(), 1))}",
    }}

    # ── 1. XGBoost ──────────────────────────────────────────────────────
    try:
        n_pos, n_neg = int(y.sum()), int(len(y) - y.sum())
        spw = n_neg / max(n_pos, 1)
        model_xgb = xgb_lib.XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, scale_pos_weight=spw,
            eval_metric="logloss", random_state=42, n_jobs=-1
        )
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_aucs = []
        for train_ix, val_ix in cv.split(X, y):
            model_xgb.fit(X[train_ix], y[train_ix])
            cv_aucs.append(float(roc_auc_score(y[val_ix], model_xgb.predict_proba(X[val_ix])[:, 1])))

        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
        model_xgb.fit(X_tr, y_tr)
        te_probs = model_xgb.predict_proba(X_te)[:, 1]
        te_preds = (te_probs >= 0.5).astype(int)
        tr_probs = model_xgb.predict_proba(X_tr)[:, 1]
        cm = confusion_matrix(y_te, te_preds).tolist()

        results["models"].append({
            "name": "XGBoost + SHAP",
            "type": "Supervised",
            "icon": "xgboost",
            "accuracy": float(accuracy_score(y_te, te_preds)),
            "precision": float(precision_score(y_te, te_preds, zero_division=0)),
            "recall": float(recall_score(y_te, te_preds, zero_division=0)),
            "f1": float(f1_score(y_te, te_preds, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_te, te_probs)),
            "pr_auc": float(average_precision_score(y_te, te_probs)),
            "cv_auc_mean": float(np.mean(cv_aucs)),
            "cv_auc_std": float(np.std(cv_aucs)),
            "train_auc": float(roc_auc_score(y_tr, tr_probs)),
            "specificity": float(cm[0][0] / (cm[0][0] + cm[0][1])) if (cm[0][0] + cm[0][1]) > 0 else 0,
            "confusion_matrix": cm,
        })
    except Exception as e:
        print(f"XGBoost eval error: {e}")

    # ── 2. Autoencoder ──────────────────────────────────────────────────
    try:
        scaler = StandardScaler()
        X_s = scaler.fit_transform(X).astype(np.float32)
        normal_mask = (y == 0)
        X_normal = X_s[normal_mask]

        class AE(tnn.Module):
            def __init__(self, dim):
                super().__init__()
                self.enc = tnn.Sequential(tnn.Linear(dim,32), tnn.ReLU(), tnn.BatchNorm1d(32), tnn.Dropout(0.1), tnn.Linear(32,16), tnn.ReLU(), tnn.Linear(16,8))
                self.dec = tnn.Sequential(tnn.Linear(8,16), tnn.ReLU(), tnn.Linear(16,32), tnn.ReLU(), tnn.BatchNorm1d(32), tnn.Linear(32,dim))
            def forward(self, x): return self.dec(self.enc(x))

        loader = DataLoader(TensorDataset(torch.FloatTensor(X_normal), torch.FloatTensor(X_normal)), batch_size=64, shuffle=True)
        ae = AE(X_s.shape[1])
        opt = torch.optim.Adam(ae.parameters(), lr=1e-3)
        crit = tnn.MSELoss()
        ae.train()
        for _ in range(50):
            for xb, yb in loader:
                opt.zero_grad()
                crit(ae(xb), yb).backward()
                opt.step()

        ae.eval()
        with torch.no_grad():
            recon = ae(torch.FloatTensor(X_s))
            errors = torch.mean((torch.FloatTensor(X_s) - recon)**2, dim=1).numpy()
            normal_recon = ae(torch.FloatTensor(X_normal))
            train_errs = torch.mean((torch.FloatTensor(X_normal) - normal_recon)**2, dim=1).numpy()

        train_max = float(np.max(train_errs))
        probs_ae = np.clip(errors / (train_max * 2), 0, 1)
        preds_ae = (probs_ae >= 0.5).astype(int)
        cm_ae = confusion_matrix(y, preds_ae).tolist()

        results["models"].append({
            "name": "Deep Autoencoder",
            "type": "Unsupervised",
            "icon": "autoencoder",
            "accuracy": float(accuracy_score(y, preds_ae)),
            "precision": float(precision_score(y, preds_ae, zero_division=0)),
            "recall": float(recall_score(y, preds_ae, zero_division=0)),
            "f1": float(f1_score(y, preds_ae, zero_division=0)),
            "roc_auc": float(roc_auc_score(y, probs_ae)) if len(np.unique(y)) > 1 else 0,
            "pr_auc": float(average_precision_score(y, probs_ae)) if len(np.unique(y)) > 1 else 0,
            "cv_auc_mean": 0,
            "cv_auc_std": 0,
            "train_auc": 0,
            "specificity": float(cm_ae[0][0] / (cm_ae[0][0] + cm_ae[0][1])) if (cm_ae[0][0] + cm_ae[0][1]) > 0 else 0,
            "confusion_matrix": cm_ae,
        })
    except Exception as e:
        print(f"Autoencoder eval error: {e}")

    # ── 3. Ensemble (Rules + Isolation Forest) ──────────────────────────
    try:
        risks_df = pd.read_sql("SELECT * FROM user_risks", engine)
        y_ens = np.array([1 if uid in insiders else 0 for uid in risks_df["user_id"]])
        probs_ens = (risks_df["risk_score"] / 100.0).values
        preds_ens = (probs_ens >= 0.3).astype(int)
        cm_ens = confusion_matrix(y_ens, preds_ens).tolist()

        results["models"].append({
            "name": "Ensemble (Rules + IF)",
            "type": "Hybrid",
            "icon": "ensemble",
            "accuracy": float(accuracy_score(y_ens, preds_ens)),
            "precision": float(precision_score(y_ens, preds_ens, zero_division=0)),
            "recall": float(recall_score(y_ens, preds_ens, zero_division=0)),
            "f1": float(f1_score(y_ens, preds_ens, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_ens, probs_ens)) if len(np.unique(y_ens)) > 1 else 0,
            "pr_auc": float(average_precision_score(y_ens, probs_ens)) if len(np.unique(y_ens)) > 1 else 0,
            "cv_auc_mean": 0,
            "cv_auc_std": 0,
            "train_auc": 0,
            "specificity": float(cm_ens[0][0] / (cm_ens[0][0] + cm_ens[0][1])) if (cm_ens[0][0] + cm_ens[0][1]) > 0 else 0,
            "confusion_matrix": cm_ens,
        })
    except Exception as e:
        print(f"Ensemble eval error: {e}")

    _eval_cache = results
    return results


# ─── Health ────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ─── Serve React SPA (production) ──────────────────────────────────────

dist_dir = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"
if dist_dir.exists():
    from starlette.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="static")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Serve actual files if they exist, otherwise serve index.html (SPA)
        file_path = dist_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(dist_dir / "index.html"))
