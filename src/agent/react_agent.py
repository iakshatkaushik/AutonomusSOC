"""ReAct Agent — LLM-powered investigation loop for insider threat alerts.

Architecture: Reason → Act → Observe → Repeat → Final Answer

Upgrades from v1:
  1. Memory-first: Searches past incidents BEFORE investigation begins
  2. Expanded toolset: 11 tools including 4 active-response write tools
  3. Confidence-gated actions: Agent may escalate/flag autonomously if confidence >= 0.85
  4. Post-investigation: Stores report to RAG memory for future cross-alert correlation

LLM Provider is swappable via .env:
  LLM_PROVIDER=gemini   → uses google-generativeai (free tier)
  LLM_PROVIDER=openai   → uses OpenAI API
"""
import json
import os
import re
from datetime import datetime

from src.agent.tools import (
    TOOL_REGISTRY,
    get_user_logs, get_user_risk_profile,
    get_shap_explanation, compare_to_peers,
    get_correlated_users, get_alert_history,
    search_past_incidents,
    flag_user_for_review, escalate_to_hr,
    suppress_false_positive, quarantine_alert,
)
from src.utils.config import PROJECT_ROOT
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")


# ─── LLM Abstraction ──────────────────────────────────────────────────

def _call_llm(system_prompt: str, user_message: str) -> str:
    """Call the configured LLM provider. Handles rate-limiting and model fallbacks."""
    import time
    import requests as _requests
    import re as _re

    if LLM_PROVIDER == "gemini":
        models_to_try = [LLM_MODEL]
        for fallback in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        combined_text = f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\n---\n\nUSER REQUEST:\n{user_message}"
        last_err = None

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={LLM_API_KEY}"
            payload = {"contents": [{"parts": [{"text": combined_text}]}]}

            for attempt in range(3):
                try:
                    resp = _requests.post(url, json=payload, timeout=60)

                    if resp.status_code == 200:
                        data = resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]

                    elif resp.status_code == 429:
                        wait = 15
                        try:
                            err_data = resp.json()
                            for d in err_data.get("error", {}).get("details", []):
                                if "retryDelay" in d:
                                    match = _re.search(r"([\d.]+)", d["retryDelay"])
                                    if match:
                                        wait = min(int(float(match.group(1))) + 2, 65)
                        except Exception:
                            pass
                        print(f"  [LLM] Rate-limited on {model_name} (attempt {attempt+1}/3), waiting {wait}s...")
                        time.sleep(wait)
                        last_err = Exception(f"429 RESOURCE_EXHAUSTED on {model_name}")

                    elif resp.status_code == 404:
                        print(f"  [LLM] Model {model_name} not found, trying next...")
                        last_err = Exception(f"404 Model {model_name} not found")
                        break

                    else:
                        raise Exception(f"Gemini API error {resp.status_code}: {resp.text[:300]}")

                except _requests.exceptions.Timeout:
                    last_err = Exception("Request timed out")
                    print(f"  [LLM] Request timed out (attempt {attempt+1}/3)")
                    time.sleep(5)
                except _requests.exceptions.ConnectionError as e:
                    raise Exception(f"Cannot connect to Gemini API: {e}")

        if last_err:
            raise last_err
        raise Exception("All LLM models failed")

    elif LLM_PROVIDER == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=LLM_API_KEY)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}. Use 'gemini' or 'openai'.")


# ─── System Prompt ────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an autonomous SOC (Security Operations Center) investigation agent for CyberSOC-Agent.
You have just received an insider threat alert from our XGBoost detection system.
Your job is to investigate the user thoroughly and produce a final investigation report.

═══════════════════════════════════
AVAILABLE TOOLS
═══════════════════════════════════

READ TOOLS (gather evidence):
  get_user_logs(user_id, log_type)        — Raw activity logs. log_type: logon/file/email/http/all
  get_user_risk_profile(user_id)          — Full risk score and behavioral feature summary (includes XGBoost score)
  get_shap_explanation(user_id)           — XGBoost SHAP explanation: WHY this user was flagged
  compare_to_peers(user_id)               — Z-score comparison to normal population (flags >2σ)
  get_correlated_users(user_id)           — Other high-risk users with similar patterns
  get_alert_history(user_id)              — All past alerts for this user
  search_past_incidents(query)            — Search memory for similar historical threats (ALWAYS call this first)

WRITE TOOLS (active response — use only when confidence >= 0.85):
  flag_user_for_review(user_id, reason, confidence)        — Flag for immediate human SOC review
  escalate_to_hr(user_id, report_summary, confidence)      — Create formal HR escalation record
  suppress_false_positive(alert_id, justification, confidence) — Mark as false positive (feeds retraining)
  quarantine_alert(alert_id, reason)                        — Lock alert while investigating

═══════════════════════════════════
INVESTIGATION PROTOCOL
═══════════════════════════════════

STEP 1 — MEMORY (MANDATORY FIRST STEP):
  Call search_past_incidents() with a natural language description of the alert pattern.
  Use any historical context found to inform your investigation.

STEP 2 — PROFILE + SHAP:
  Call get_user_risk_profile() and get_shap_explanation() to understand why the model flagged this user.

STEP 3 — EVIDENCE GATHERING:
  Query logs relevant to the alert type:
  - DATA_EXFILTRATION → check file (USB copies)+ logon (after-hours) + http (wikileaks)
  - JOB_HUNTING → check http (monster.com, craigslist)
  - DISGRUNTLED_SABOTAGE → check email (angry keywords) + http (spectorsoft)

STEP 4 — PEER COMPARISON:
  Call compare_to_peers() to establish statistical significance.

STEP 5 — CORRELATIONS:
  Call get_correlated_users() to detect coordinated campaigns.

STEP 6 — TAKE ACTION (if confidence >= 0.85):
  Based on your findings, call ONE write tool:
  - CONFIRMED THREAT → escalate_to_hr() or flag_user_for_review()
  - FALSE POSITIVE → suppress_false_positive()

STEP 7 — FINAL ANSWER

═══════════════════════════════════
RESPONSE FORMAT
═══════════════════════════════════

Use EXACTLY this format for each step:
THOUGHT: [your reasoning about what to do next and what you've observed so far]
ACTION: tool_name(user_id="value", log_type="value")
---
Wait for the OBSERVATION, then continue with the next THOUGHT/ACTION.

When completely done, write:
FINAL_ANSWER: {
  "summary": "1-2 sentence summary of what happened",
  "threat_scenario": "DATA_EXFILTRATION or JOB_HUNTING or DISGRUNTLED_SABOTAGE or UNKNOWN",
  "confidence": 0.0 to 1.0,
  "evidence_chain": ["timestamp: event1", "timestamp: event2", ...],
  "reasoning": "detailed step-by-step reasoning including peer Z-scores and SHAP values",
  "recommended_action": "ESCALATE_TO_HR or ESCALATE_TO_SECURITY or MONITOR or DISMISS",
  "recommended_actions_detail": ["step 1", "step 2", ...],
  "correlated_users": ["user1", "user2"],
  "actions_taken": ["e.g. flagged user for review", "e.g. no autonomous action (confidence < 0.85)"]
}

Be thorough but evidence-based. Reference Z-scores and SHAP values in your reasoning.
Do not fabricate evidence. Do not skip the memory search.
"""


# ─── Tool Execution ───────────────────────────────────────────────────

def _parse_and_execute_action(action_line: str, user_id: str, shap_data: dict) -> str:
    """Parse an ACTION line and execute the corresponding tool."""
    action_line = action_line.strip()
    if not action_line:
        return "No action specified."

    match = re.match(r"(\w+)\((.*)\)", action_line, re.DOTALL)
    if not match:
        return f"Could not parse action: {action_line}"

    tool_name = match.group(1).strip()
    args_str = match.group(2).strip()

    # Parse kwargs — always inject user_id as default
    kwargs = {"user_id": user_id}

    for kv in re.findall(r'(\w+)\s*=\s*"([^"]*)"', args_str):
        kwargs[kv[0]] = kv[1]
    for kv in re.findall(r'(\w+)\s*=\s*(\d+\.?\d*)', args_str):
        try:
            kwargs[kv[0]] = float(kv[1]) if '.' in kv[1] else int(kv[1])
        except ValueError:
            pass

    # Special injection: shap_data must come from our cache
    if tool_name == "get_shap_explanation":
        kwargs["shap_data"] = shap_data

    if tool_name not in TOOL_REGISTRY:
        return f"Unknown tool: {tool_name}. Available: {list(TOOL_REGISTRY.keys())}"

    try:
        result = TOOL_REGISTRY[tool_name](**kwargs)
        return str(result)[:3000]  # Cap output to avoid token explosion
    except Exception as e:
        return f"Tool error ({tool_name}): {str(e)}"


# ─── ReAct Loop ───────────────────────────────────────────────────────

def investigate(
    user_id: str,
    alert_type: str,
    risk_score: float,
    severity: str,
    alert_id: int = None,
    shap_data: dict = None,
    max_iterations: int = 8,
    store_to_memory: bool = True,
) -> dict:
    """Run the full ReAct investigation loop.

    Args:
        user_id: The user being investigated
        alert_type: DATA_EXFILTRATION / JOB_HUNTING / DISGRUNTLED_SABOTAGE
        risk_score: 0-100 risk score from XGBoost
        severity: CRITICAL / HIGH / MEDIUM
        alert_id: DB alert ID (optional, for write tools like quarantine/suppress)
        shap_data: Dict of per-user SHAP explanations (optional)
        max_iterations: Max ReAct iterations before forcing conclusion (default 8, was 5)
        store_to_memory: If True, store the final report in ChromaDB for future retrieval

    Returns:
        InvestigationReport dict
    """
    if shap_data is None:
        shap_data = {}

    print(f"\n[AGENT] Investigating user {user_id} (score={risk_score:.1f}, type={alert_type})")

    # Quarantine the alert immediately to prevent parallel work
    if alert_id is not None:
        quarantine_alert(alert_id, "Agent investigation in progress")

    # Build initial context
    initial_message = f"""ALERT RECEIVED:
User ID:     {user_id}
Alert ID:    {alert_id or 'N/A'}
Risk Score:  {risk_score:.1f}/100
Severity:    {severity}
Alert Type:  {alert_type}
Timestamp:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

IMPORTANT: Begin by calling search_past_incidents() to check if we have seen similar patterns
before. Then follow the Investigation Protocol above.
Begin your investigation now."""

    # ReAct loop state
    conversation = initial_message
    iterations = 0
    actions_taken = []

    while iterations < max_iterations:
        iterations += 1
        print(f"  [AGENT] Iteration {iterations}/{max_iterations}...")

        response = _call_llm(SYSTEM_PROMPT, conversation)
        print(f"  [AGENT] LLM response received ({len(response)} chars)")

        # Check for FINAL_ANSWER
        if "FINAL_ANSWER:" in response:
            json_match = re.search(r"FINAL_ANSWER:\s*(\{.*\})", response, re.DOTALL)
            if json_match:
                try:
                    report_data = json.loads(json_match.group(1))
                    report_data["user_id"] = user_id
                    report_data["alert_id"] = alert_id
                    report_data["risk_score"] = risk_score
                    report_data["severity"] = severity
                    report_data["iterations"] = iterations
                    report_data["llm_model"] = LLM_MODEL
                    report_data["actions_taken"] = actions_taken

                    print(f"  [AGENT] ✅ Investigation complete after {iterations} iterations")

                    # Store to memory for future cross-alert correlation
                    if store_to_memory:
                        try:
                            from src.agent.memory import store_report
                            store_report(report_data)
                        except Exception as mem_err:
                            print(f"  [AGENT] Memory store skipped: {mem_err}")

                    return report_data
                except json.JSONDecodeError as e:
                    print(f"  [AGENT] ⚠️  JSON parse error: {e}. Trying to continue...")

        # Extract ACTION line and execute tool
        action_match = re.search(r"ACTION:\s*(.+?)(?:\n|$)", response)
        if action_match:
            action_line = action_match.group(1).strip()
            print(f"  [AGENT] Executing: {action_line[:80]}...")
            observation = _parse_and_execute_action(action_line, user_id, shap_data)

            # Track write tool actions
            for write_tool in ["flag_user_for_review", "escalate_to_hr", "suppress_false_positive"]:
                if write_tool in action_line:
                    actions_taken.append(f"{write_tool} called")

            observations_append = f"OBSERVATION:\n{observation}"
            conversation = f"{conversation}\n\n{response}\n\n{observations_append}\n\nContinue your investigation."
        else:
            conversation = f"{conversation}\n\n{response}\n\nPlease either use a tool (ACTION: ...) or provide FINAL_ANSWER."

    # Fallback if max iterations reached
    print(f"  [AGENT] ⚠️  Max iterations reached, generating fallback report")
    fallback = {
        "user_id": user_id,
        "alert_id": alert_id,
        "risk_score": risk_score,
        "severity": severity,
        "summary": f"User {user_id} flagged by XGBoost with {risk_score:.1f}/100 risk score for {alert_type}.",
        "threat_scenario": alert_type,
        "confidence": risk_score / 100,
        "evidence_chain": [f"XGBoost detected {alert_type} pattern with score {risk_score:.1f}"],
        "reasoning": "Investigation could not complete within iteration limit. Manual review required.",
        "recommended_action": "MONITOR",
        "recommended_actions_detail": ["Review user logs manually", "Consult security team"],
        "correlated_users": [],
        "actions_taken": actions_taken,
        "iterations": iterations,
        "llm_model": LLM_MODEL,
    }

    if store_to_memory:
        try:
            from src.agent.memory import store_report
            store_report(fallback)
        except Exception:
            pass

    return fallback
