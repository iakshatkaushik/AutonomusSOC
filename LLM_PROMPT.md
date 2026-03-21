# 🤖 LLM Prompt — CyberSOC-Agent: Agentic AI Insider Threat System

> **Copy everything below the line into any LLM to get a complete execution plan.**

---

```
You are a senior full-stack AI/ML + cybersecurity engineer. I am going to describe my project in full detail. Your job is to fully understand it and generate a complete, actionable execution plan.

---

## PROJECT: CyberSOC-Agent
**An Agentic AI-powered Insider Threat Detection System**

This is NOT a simple dashboard or risk-scoring tool.

This is a system where:
1. A **Machine Learning engine** (XGBoost + Rules) continuously scores every user's behavior from organizational logs
2. When a HIGH/CRITICAL threat is detected, an **LLM-powered Investigation Agent** is triggered
3. The Agent autonomously investigates — it uses **tools** to query raw logs, explain model decisions, correlate with other users — and iterates in a **ReAct loop** (Reason → Act → Observe → Repeat)
4. The Agent produces a **structured Investigation Report** with evidence, reasoning, and recommended actions
5. Everything is shown on an **Analyst Dashboard** where a human SOC analyst reviews Agent findings and makes final decisions

This makes it genuinely agentic: the AI doesn't just score — it **investigates**.

---

## WHAT IS ALREADY BUILT (DO NOT REDO THIS)

### ✅ Data Pipeline (complete)
- `logon.csv` (854,859 rows), `file.csv` (445,581 rows), `email.csv` (2,318,899 rows)
- `http.csv` (14GB) — grep-filtered for target domains → 157,357 rows
- All stored in SQLite via SQLAlchemy ORM (swappable to PostgreSQL via `.env`)
- 70 ground truth insiders across 3 scenarios, labeled in `answers/insiders.csv`

### ✅ Feature Engineering (complete)
- 330,268 user-day feature rows × 17 behavioral columns
- Features: login_count, after_hours_login_count, after_hours_ratio, unique_pcs, file_copy_count, file_copy_after_hours, emails_sent, external_recipient_ratio, bcc_count, attachment_count, angry_keyword_count, job_site_visits, suspicious_domain_visits

### ✅ Detection Models (3 models trained, XGBoost chosen)

| Model | AUC | F1 | Decision |
|---|---|---|---|
| Rule Engine | N/A | 100%* | ✅ Keep as first-pass filter |
| Isolation Forest | 0.84 | 44% | ❌ Replaced |
| Autoencoder (PyTorch) | 0.93 | 73% | ✅ Keep as corroborating signal |
| **XGBoost + SHAP** | **1.00** | **100%** | ✅ **PRIMARY MODEL** |

XGBoost trained with `scale_pos_weight=13.3` for class imbalance. SHAP TreeExplainer provides per-user feature contributions.

Top SHAP features: `file_copy_count_max`, `suspicious_domain_visits_mean`, `unique_pcs_sum`, `emails_sent_std`

### ✅ File Structure (already exists)
```
AutonomusSOC/
├── src/
│   ├── pipeline/
│   │   ├── ingest.py       # Data loading
│   │   └── features.py     # Feature engineering
│   ├── detection/
│   │   ├── rules.py              # Rule-based 3-scenario detector
│   │   ├── isolation_forest.py   # IF baseline
│   │   ├── xgboost_model.py      # XGBoost + SHAP (PRIMARY)
│   │   ├── autoencoder_model.py  # PyTorch autoencoder (SECONDARY)
│   │   └── scorer.py             # Combines all models → alerts
│   ├── api/
│   │   └── main.py         # FastAPI (to be built)
│   └── utils/
│       ├── config.py       # Paths + DATABASE_URL
│       └── db.py           # SQLAlchemy models
├── data/raw/r4.2/          # CERT dataset CSVs
├── data/processed/
│   └── autonomussoc.db     # SQLite database
├── run_pipeline.py         # Full pipeline runner
└── .env                    # DATABASE_URL config
```

---

## THE 3 INSIDER THREAT SCENARIOS (CERT r4.2)

### Scenario 1 — Data Exfiltration (30 insiders)
Pattern: After-hours login → wikileaks.org browsing (keywords: spy, covert, top-secret) → USB file copy burst → logoff

### Scenario 2 — Job Hunting / Disengagement (30 insiders)
Pattern: Repeated visits to monster.com, craigslist, jobhuntersbible.com over multi-week period

### Scenario 3 — Disgruntled Sabotage (10 insiders)
Pattern: Sends threatening emails (fed up, angry, company will suffer) → visits spectorsoft.com (keylogger site)

---

## WHAT NEEDS TO BE BUILT NOW

### 1. LLM Investigation Agent (`src/agent/`)

This is the core new component. When XGBoost detects a HIGH/CRITICAL alert, the agent is triggered.

**Agent Architecture — ReAct Loop:**
```python
while not investigation_complete:
    thought = llm.reason(context, observations_so_far)
    action = parse_action(thought)       # which tool to call
    observation = execute_tool(action)   # actually call the tool
    context.append(observation)
    if thought.contains("FINAL ANSWER"):
        break
```

**Agent Tools (functions the LLM can call):**

```python
def get_user_logs(user_id: str, start_date: str, end_date: str, log_type: str) -> str:
    """Query raw events for a user in a date range. log_type: logon/file/email/http"""

def get_shap_explanation(user_id: str) -> str:
    """Get XGBoost SHAP feature contributions for this user"""

def get_user_risk_profile(user_id: str) -> str:
    """Get full risk score, feature history, and behavioral baseline"""

def compare_to_peers(user_id: str) -> str:
    """Compare user's behavior to the 930 normal users (statistical deviation)"""

def get_correlated_users(pattern: str) -> str:
    """Find other users with similar suspicious patterns"""

def get_alert_history(user_id: str) -> str:
    """Check if this user had previous alerts"""
```

**Agent Output (InvestigationReport):**
```python
class InvestigationReport:
    user_id: str
    alert_id: int
    summary: str            # 1-2 sentence summary of what happened
    evidence_chain: list    # Ordered list of evidence items with timestamps
    reasoning: str          # LLM's step-by-step reasoning
    threat_scenario: str    # DATA_EXFILTRATION / JOB_HUNTING / SABOTAGE / UNKNOWN
    confidence: float       # 0-1 confidence in the assessment
    recommended_action: str # ESCALATE_TO_HR / ESCALATE_TO_SECURITY / MONITOR / DISMISS
    recommended_actions_detail: list  # Specific steps for analyst
    correlated_users: list  # Other users with similar patterns
    investigation_steps: list  # What tools the agent used and what it found
```

**LLM System Prompt for the Agent:**
```
You are an autonomous SOC (Security Operations Center) investigation agent.
You have just received an insider threat alert. Your job is to investigate thoroughly using available tools, then produce a structured investigation report.

You must:
1. Use tools to gather evidence
2. Think step by step about what the evidence means
3. Look for corroborating signals
4. Check for correlated suspicious users
5. Provide a clear, evidence-backed assessment

Available tools: get_user_logs, get_shap_explanation, get_user_risk_profile, compare_to_peers, get_correlated_users, get_alert_history

Format your investigation as:
THOUGHT: [your reasoning]
ACTION: tool_name(args)
OBSERVATION: [tool result]
... repeat ...
FINAL ANSWER: [structured JSON report]
```

**LLM Choice — use ONE of these (in order of preference):**
1. `openai` — GPT-4o-mini (cheap, fast, great for tool calling)
2. `google.generativeai` — Gemini 1.5 Flash (free tier, fast)
3. `anthropic` — Claude 3 Haiku (fast, good reasoning)

Design the agent code so LLM provider is swappable via `.env`:
```
LLM_PROVIDER=openai  # or gemini or anthropic
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

### 2. Investigation Report Storage

Add to SQLite (via SQLAlchemy):
```sql
CREATE TABLE investigation_reports (
    id INTEGER PRIMARY KEY,
    alert_id INTEGER,
    user_id TEXT,
    summary TEXT,
    evidence_chain JSON,
    reasoning TEXT,
    threat_scenario TEXT,
    confidence FLOAT,
    recommended_action TEXT,
    recommended_actions_detail JSON,
    correlated_users JSON,
    investigation_steps JSON,
    llm_model TEXT,
    tokens_used INTEGER,
    created_at DATETIME
);
```

### 3. FastAPI Backend (`src/api/main.py`)

Build endpoints that serve the dashboard AND expose agent results:

```
GET  /api/v1/dashboard/overview          → alert counts, top risks, key metrics
GET  /api/v1/alerts                      → all alerts (filter: severity, type)
GET  /api/v1/alerts/{id}                 → alert detail + investigation report
PATCH /api/v1/alerts/{id}/status         → update status
GET  /api/v1/users                       → all users with risk scores
GET  /api/v1/users/{id}                  → user profile + features + SHAP
GET  /api/v1/users/{id}/logs             → raw event logs for user
POST /api/v1/investigate/{alert_id}      → trigger LLM agent investigation
GET  /api/v1/reports/{alert_id}          → get investigation report
```

### 4. React Dashboard (3 pages)

**Page 1: Overview**
- Alert counts by severity (CRITICAL/HIGH/MEDIUM/LOW)
- Top 10 riskiest users with risk scores
- "Agent investigated X alerts" stat
- Live alert feed

**Page 2: Alert Queue**
- Table of all alerts with severity badge, user ID, alert type, score
- "Investigated" vs "Pending investigation" status
- Click → User Investigation page

**Page 3: User Investigation**
- Risk score gauge (big number, 0-100)
- XGBoost detection reason (SHAP top features)
- **Agent Investigation Report panel** — the LLM's full reasoning and evidence chain
- Raw event timeline (chronological log entries for that user)
- Recommended actions from the Agent
- "Override" button for analyst

---

## TECH STACK (Final)

| Layer | Tech |
|---|---|
| ML | XGBoost + SHAP, Scikit-learn (IF), PyTorch (Autoencoder) |
| LLM Agent | OpenAI API / Gemini API / Anthropic (swappable) |
| Agent Framework | Custom ReAct loop (no LangChain — too heavy) |
| Backend | FastAPI + Uvicorn |
| Database | SQLite (swappable to PostgreSQL via DATABASE_URL in .env) |
| Frontend | React 18 + Vite, Recharts, Tailwind CSS |
| Serialization | joblib for XGBoost model, torch.save for Autoencoder |

---

## WHAT I NEED FROM YOU

Generate a COMPLETE execution plan for building the **3 remaining components** listed above, in order:
1. LLM Investigation Agent (`src/agent/`)
2. FastAPI Backend (`src/api/main.py`)
3. React Dashboard (3 pages)

For EACH component give me:
- 📁 Files to create and what goes in each
- 🔑 Key code snippets (especially the ReAct agent loop + tool definitions)
- ⚠️ Pitfalls to avoid
- ✅ "Done" checkpoint

Constraints:
- DO NOT redo the detection models or pipeline — they're done and working
- Agent must work with at least ONE real LLM API (OpenAI or Gemini preferred)
- Keep it buildable and demo-ready
- SQLAlchemy for all DB access — no raw SQL
```

---

> **Usage:** Copy everything inside the code block.
