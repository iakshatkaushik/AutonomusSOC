"""ReAct Agent — LLM-powered investigation loop for insider threat alerts.

Architecture: Reason → Act → Observe → Repeat → Final Answer

The agent:
1. Receives an alert context (user_id, risk score, alert type)
2. Reasons about what to investigate
3. Calls tools to gather evidence from the database
4. Iterates until it has enough to write a full investigation report
5. Outputs a structured InvestigationReport

LLM Provider is swappable via .env:
  LLM_PROVIDER=gemini   → uses google-generativeai (free tier)
  LLM_PROVIDER=openai   → uses OpenAI API
"""
import json
import os
import re
from datetime import datetime

from src.agent.tools import (
    TOOL_REGISTRY, get_user_logs, get_user_risk_profile,
    get_shap_explanation, compare_to_peers, get_correlated_users, get_alert_history
)
from src.utils.config import PROJECT_ROOT
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")


# ─── LLM Abstraction ──────────────────────────────────────────────────

def _call_llm(system_prompt: str, user_message: str) -> str:
    """Call the configured LLM provider via REST API.
    Extracts retryDelay from Gemini 429 responses and waits accordingly.
    """
    import time
    import requests as _requests
    import re as _re

    if LLM_PROVIDER == "gemini":
        # Models to try in order of preference
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
                        # Extract retryDelay from Google's response
                        wait = 15  # default
                        try:
                            err_data = resp.json()
                            err_details = err_data.get("error", {}).get("details", [])
                            for d in err_details:
                                if "retryDelay" in d:
                                    delay_str = d["retryDelay"]
                                    # Parse "24s" or "24.5s"
                                    match = _re.search(r"([\d.]+)", delay_str)
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
                        break  # Skip to next model

                    else:
                        err_msg = resp.text[:300]
                        raise Exception(f"Gemini API error {resp.status_code}: {err_msg}")

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

SYSTEM_PROMPT = """You are an autonomous SOC (Security Operations Center) investigation agent.
You have just received an insider threat alert from our XGBoost detection system.
Your job is to investigate the user thoroughly using the available tools, then produce a final investigation report.

AVAILABLE TOOLS:
- get_user_logs(user_id, log_type) — get raw activity logs. log_type: logon/file/email/http/all
- get_user_risk_profile(user_id) — get full risk score and behavioral feature summary
- get_shap_explanation(user_id) — get XGBoost model explanation for why this user was flagged
- compare_to_peers(user_id) — compare this user's behavior to the normal population (Z-scores)
- get_correlated_users(user_id) — find other high-risk users with similar patterns
- get_alert_history(user_id) — get all alerts for this user

INVESTIGATION PROTOCOL:
1. Start by getting the risk profile and SHAP explanation to understand why the model flagged this user
2. Then query relevant logs based on the alert type
3. Compare to peers to understand statistical significance
4. Look for correlated users
5. Produce your final report

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
THOUGHT: [your step-by-step reasoning about what to do next]
ACTION: tool_name(user_id="value", log_type="value")
---
Then wait for the OBSERVATION, then continue with THOUGHT/ACTION until you have enough evidence.
When you are done investigating, write:
FINAL_ANSWER: {
  "summary": "1-2 sentence summary of what happened",
  "threat_scenario": "DATA_EXFILTRATION or JOB_HUNTING or DISGRUNTLED_SABOTAGE or UNKNOWN",
  "confidence": 0.0 to 1.0,
  "evidence_chain": ["timestamp: event1", "timestamp: event2", ...],
  "reasoning": "detailed step-by-step reasoning",
  "recommended_action": "ESCALATE_TO_HR or ESCALATE_TO_SECURITY or MONITOR or DISMISS",
  "recommended_actions_detail": ["step 1", "step 2", ...],
  "correlated_users": ["user1", "user2"]
}

Be thorough but concise. Use the tools. Do not make up evidence.
"""


# ─── Tool Execution ───────────────────────────────────────────────────

def _parse_and_execute_action(action_line: str, user_id: str, shap_data: dict) -> str:
    """Parse an ACTION line and execute the corresponding tool."""
    # Extract tool name
    action_line = action_line.strip()
    if not action_line:
        return "No action specified."

    # Match: tool_name(args)
    match = re.match(r"(\w+)\((.*)\)", action_line, re.DOTALL)
    if not match:
        return f"Could not parse action: {action_line}"

    tool_name = match.group(1).strip()
    args_str = match.group(2).strip()

    # Parse kwargs
    kwargs = {"user_id": user_id}  # Always inject user_id as default

    for kv in re.findall(r'(\w+)\s*=\s*"([^"]*)"', args_str):
        kwargs[kv[0]] = kv[1]
    for kv in re.findall(r'(\w+)\s*=\s*(\d+)', args_str):
        kwargs[kv[0]] = int(kv[1])

    # Special injection: shap_data needs to come from our cache
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
    shap_data: dict = None,
    max_iterations: int = 5,
) -> dict:
    """Run the full ReAct investigation loop.

    Args:
        user_id: The user being investigated
        alert_type: DATA_EXFILTRATION / JOB_HUNTING / DISGRUNTLED_SABOTAGE
        risk_score: 0-100 risk score from XGBoost
        severity: CRITICAL / HIGH / MEDIUM
        shap_data: Dict of per-user SHAP explanations (optional)
        max_iterations: Max ReAct iterations before forcing conclusion

    Returns:
        InvestigationReport dict
    """
    if shap_data is None:
        shap_data = {}

    print(f"\n[AGENT] Investigating user {user_id} (score={risk_score:.1f}, type={alert_type})")

    # Build initial context
    initial_message = f"""ALERT RECEIVED:
User ID:     {user_id}
Risk Score:  {risk_score:.1f}/100
Severity:    {severity}
Alert Type:  {alert_type}
Timestamp:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please investigate this user thoroughly and produce an investigation report.
Begin your investigation now."""

    # ReAct loop state
    conversation = initial_message
    observations = []
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        print(f"  [AGENT] Iteration {iterations}/{max_iterations}...")

        # LLM reasons and acts
        response = _call_llm(SYSTEM_PROMPT, conversation)
        print(f"  [AGENT] LLM response received ({len(response)} chars)")

        # Check for FINAL_ANSWER
        if "FINAL_ANSWER:" in response:
            # Extract the JSON
            json_match = re.search(r"FINAL_ANSWER:\s*(\{.*\})", response, re.DOTALL)
            if json_match:
                try:
                    report_data = json.loads(json_match.group(1))
                    report_data["user_id"] = user_id
                    report_data["risk_score"] = risk_score
                    report_data["severity"] = severity
                    report_data["iterations"] = iterations
                    report_data["llm_model"] = LLM_MODEL
                    print(f"  [AGENT] ✅ Investigation complete after {iterations} iterations")
                    return report_data
                except json.JSONDecodeError as e:
                    print(f"  [AGENT] ⚠️  JSON parse error: {e}. Trying to continue...")

        # Extract ACTION line and execute tool
        action_match = re.search(r"ACTION:\s*(.+?)(?:\n|$)", response)
        if action_match:
            action_line = action_match.group(1).strip()
            print(f"  [AGENT] Executing tool: {action_line[:60]}...")
            observation = _parse_and_execute_action(action_line, user_id, shap_data)
            observations.append(f"OBSERVATION:\n{observation}")

            # Append to conversation for next iteration
            conversation = f"{conversation}\n\n{response}\n\nOBSERVATION:\n{observation}\n\nContinue your investigation."
        else:
            # No action, no final answer — nudge the LLM
            conversation = f"{conversation}\n\n{response}\n\nPlease either use a tool (ACTION: ...) or provide FINAL_ANSWER."

    # Fallback if max iterations reached without FINAL_ANSWER
    print(f"  [AGENT] ⚠️  Max iterations reached, generating fallback report")
    fallback = {
        "user_id": user_id,
        "risk_score": risk_score,
        "severity": severity,
        "summary": f"User {user_id} flagged by XGBoost with {risk_score:.1f}/100 risk score for {alert_type}.",
        "threat_scenario": alert_type,
        "confidence": risk_score / 100,
        "evidence_chain": [f"XGBoost detected {alert_type} pattern with score {risk_score:.1f}"],
        "reasoning": "Investigation could not be completed within iteration limit. Manual review required.",
        "recommended_action": "MONITOR",
        "recommended_actions_detail": ["Review user logs manually", "Consult security team"],
        "correlated_users": [],
        "iterations": iterations,
        "llm_model": LLM_MODEL,
    }
    return fallback
