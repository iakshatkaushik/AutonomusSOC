# 🤖 LLM Prompt — AutonomusSOC

> **Copy everything below the line into any LLM to get a full execution plan.**

---

```
You are a senior full-stack AI/ML + cybersecurity engineer. I'm going to describe my hackathon project in full — the dataset I have (with exact schemas, row counts, and file sizes from my analysis), the architecture I'm building, and what I need. Your job is to fully understand it and generate a complete, actionable execution plan.

---

## PROJECT: AutonomusSOC
**Explainable Insider Threat Detection Engine with Behavioral Rules + Lightweight ML**

- **Hackathon:** AI-Powered Insider Threat Detection — Techkriti'26 at IIT Kanpur
- **Solo developer**
- **Status:** Dataset extracted and analyzed. Architecture finalized. No code written yet.

---

## THE DATASET: CERT Insider Threat r4.2 (CMU)

Already downloaded and extracted. Everything below is verified from actual files.

### Key Facts
- 1,000 employees, each with an assigned PC + 100 shared lab machines
- ~501 days of activity (Jan 2010 → May 2011)
- **70 malicious insiders** across 3 scenarios
- 930 normal users
- "Dense needles" dataset — artificially high malicious density, clean patterns

### Files (exact sizes and schemas)

**`logon.csv` — 56 MB, 854,860 rows**
Fields: `id, date, user, pc, activity` (Logon/Logoff)
- Date format: `MM/DD/YYYY HH:MM:SS`
- After-hours logons are explicitly significant (per readme)
- Screen unlocks = Logon; screen locks NOT recorded
- Some logons intentionally missing (dirty data)
- Employee terminations = no new logon from that day

**`email.csv` — 1.1 GB, 2,318,899 rows**
Fields: `id, date, user, pc, to, cc, bcc, from, size, attachments, content`
- Internal emails: `@dtaa.com`; external: other domains
- `content` = space-separated topic keywords (NOT actual body)
- Multiple recipients (semicolon-separated)

**`file.csv` — 184 MB, 445,582 rows**
Fields: `id, date, user, pc, filename, content`
- **Every row = a file copy to USB/removable media**
- `content` = hex file header + keywords
- Each user has a normal daily copy count; deviations = significant

**`http.csv` — 14 GB, ~28M+ rows**
Fields: `id, date, user, pc, url, content`
- **TOO LARGE to load in memory**
- We will handle this via `grep` filtering for only target domains

**`psychometric.csv` — 44 KB, 1,001 rows** → ❌ SKIPPING (unrealistic in real SOC)

**⚠️ No `device.csv` exists.** USB connect/disconnect events only appear in answer key files. `file.csv` is the USB activity proxy.

### Ground Truth: The 70 Insiders

Master index: `answers/insiders.csv`
Fields: `dataset, scenario, details, user, start, end`

**Scenario 1 — Espionage / USB Data Theft (30 insiders)**
Pattern: After-hours login → browses wikileaks.org (keywords: spy, covert, top-secret, clandestine, surveillance) → USB file copy burst → logoff
Example: User AAM0658 logged in at 1:34 AM, browsed wikileaks, used USB, logged off at 6:28 AM.

**Scenario 2 — Job Hunting / Disengagement (30 insiders)**
Pattern: Repeatedly visits job sites (monster.com, craigslist.org, jobhuntersbible.com) with resume/job keywords over multi-week period.
Example: User AAF0535 browsed monster.com + craigslist from Jun 28 to Aug 20, 2010.

**Scenario 3 — Disgruntled Employee Sabotage (10 insiders)**
Pattern: Sends threatening emails (keywords: "i may leave", "fed up", "company will suffer", "angry") → downloads keylogger (spectorsoft.com).
Example: User BBS0039 sent angry emails then browsed keylogger download site same day.

Each insider has a CSV in `answers/r4.2-{scenario}/` with their exact malicious log entries.

---

## CRITICAL ARCHITECTURAL DECISIONS (ALREADY MADE)

Based on honest analysis of the dataset and time constraints:

### What We CUT and Why
| Cut | Why |
|---|---|
| LSTM | Sequence prep/padding/tuning too slow; dataset patterns don't need it |
| Autoencoder | Reconstruction error thresholding is non-trivial; adds noise |
| SHAP/LIME | Slow, hard to integrate, zero demo value |
| psychometric.csv | Big Five personality scores don't exist in real SOCs |
| Docker | Zero demo value; adds setup overhead |
| WebSockets | Overkill; static alerts are fine |
| 5 dashboard pages | More pages = more bugs; 3 is plenty |
| Full http.csv loading | 14GB can't fit in memory; grep-filter for target domains instead |

### What We KEEP and Why
| Keep | Why |
|---|---|
| **Rule-based detector** | PRIMARY engine — will genuinely outperform ML on this dataset |
| **Isolation Forest** | Lightweight ML layer — adds "AI" credibility for judges |
| **Feature engineering** | Core analytical value |
| **Explainability** | Every alert says exactly "why flagged?" with evidence |
| **SQLite** | Zero setup, fast enough, perfect for demo |
| **FastAPI** | Quick backend |
| **React dashboard (3 pages)** | Overview, alert queue, user investigation |

### Why Rules > ML Here
This is a "dense needles" toy dataset with obvious, clean patterns:
- wikileaks browsing → espionage (it's literally in the URL)
- monster.com visits → job hunting
- "fed up" emails + spectorsoft.com → sabotage

ML will just rediscover these obvious rules. A rule engine will be faster, more accurate, and fully explainable. The Isolation Forest adds a legitimate ML layer on top for anomaly scoring.

---

## WHAT I'M BUILDING

### Architecture
```
logon.csv + file.csv + email.csv + grep-filtered http.csv
    → SQLite storage
    → Feature engineering (per-user-per-day)
    → Rule Engine (catches scenarios 1/2/3)
    → Isolation Forest (anomaly scores on feature vectors)
    → Combined risk score (rules × 0.7 + IF × 0.3) → 0-100
    → Alert generation with explainable "why flagged?"
    → FastAPI backend serves alerts + user data
    → React dashboard displays everything
```

### http.csv Strategy
Instead of loading 14GB, do:
```bash
grep -i "wikileaks\|monster\.com\|craigslist\|jobhuntersbible\|spectorsoft" http.csv > http_filtered.csv
```
This gives us ONLY the rows we care about. Fast, simple, sufficient.

### Rule-Based Detection Engine (Primary)
```python
# Scenario 1: Data exfiltration
if after_hours_login AND (wikileaks_visit OR espionage_keywords) AND usb_copy_burst:
    → DATA_EXFILTRATION alert (CRITICAL)

# Scenario 2: Job hunting
if job_site_visits > threshold over multi-day window:
    → JOB_HUNTING alert (HIGH)

# Scenario 3: Sabotage
if angry_email_keywords AND spyware_site_visit:
    → DISGRUNTLED_SABOTAGE alert (CRITICAL)
```
Each alert includes human-readable contributing factors.

### Isolation Forest (Secondary ML Layer)
- Train on feature vectors of 930 normal users
- Score all 1,000 users → anomaly score
- Users flagged by BOTH rules + IF get higher confidence

### Risk Scoring
```python
risk_score = rule_confidence * 0.7 + if_anomaly_score * 0.3
# Severity: CRITICAL (90-100), HIGH (70-89), MEDIUM (40-69), LOW (0-39)
```

### Feature Engineering (per-user-per-day)
**From logon.csv:**
- Login count, after-hours login ratio, unique PCs used, session duration estimates, weekend activity

**From file.csv (USB):**
- Daily file copy count, deviation from user baseline, after-hours copy ratio

**From email.csv:**
- External recipient ratio, BCC usage, angry keyword count, attachment count, email volume

**From http_filtered.csv:**
- Job-site visit count, suspicious domain count, espionage keyword count

### Backend API (FastAPI + SQLite)
```
GET  /api/v1/alerts              — list alerts (filter: severity, type, user)
GET  /api/v1/alerts/{id}         — alert detail with evidence + explanation
PATCH /api/v1/alerts/{id}/status — update status (ack/dismiss/escalate)
GET  /api/v1/users               — all users with risk scores
GET  /api/v1/users/{id}          — user profile + risk + behavioral features
GET  /api/v1/dashboard/overview  — summary stats (alert counts, top risks)
```

### Frontend Dashboard (React + Vite, 3 pages)
1. **Overview** — alert count by severity, top 10 risky users, key metrics
2. **Alert Queue** — sortable/filterable table, severity badges, click-to-investigate
3. **User Investigation** — risk gauge, event timeline, evidence chain, "why flagged?" explanation

### Tech Stack (Final)
| Layer | Tech |
|---|---|
| Language | Python 3.10+ |
| ML | Scikit-learn (Isolation Forest only) |
| Data | Pandas, NumPy |
| Backend | FastAPI, Uvicorn |
| Database | SQLite |
| Frontend | React 18 + Vite, Recharts, Tailwind CSS |

---

## WHAT I NEED FROM YOU

Generate a **COMPLETE, ORDERED EXECUTION PLAN** to build everything above. The architecture is final — don't second-guess the decisions. Just tell me HOW to build it, step by step.

### PHASES (in order):
1. **Project Setup** — directory structure, virtualenv, requirements.txt, SQLite schema
2. **Data Ingestion** — load CSVs, grep-filter http.csv, parse insiders.csv, store in SQLite
3. **Feature Engineering** — compute per-user-per-day features from all data sources
4. **Detection Engine** — implement 3 scenario rules + Isolation Forest + combined risk scoring
5. **Alert Generation** — create alerts with full explainability for all detected insiders
6. **Backend API** — FastAPI app serving all endpoints from SQLite
7. **Frontend Dashboard** — React app with 3 pages wired to API
8. **Integration & Demo** — end-to-end test, verify detection of 70 insiders, demo script

For EACH phase give me:
- 📋 Ordered sub-tasks (concrete, codeable)
- 📁 Files to create (filename + what goes in each)
- 🔑 Key code snippets for the hard parts
- ⚠️ Pitfalls to avoid
- ✅ "Done" checkpoint to verify before moving on
- Biggest risk and how to dodge it

Be thorough and actionable. I want to sit down and follow this like a recipe.
```

---

> **Usage:** Copy everything inside the code block above and paste into any LLM.
