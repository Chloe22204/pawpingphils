"""
Optional LLM-assisted triage for PAB alerts.

Design goals:
- Never block core flow: failures fall back to rules-only triage.
- Never downgrade urgency from deterministic rules.
- Keep outputs structured for audit and downstream display.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any
from urllib import error, request

from triage_engine import PRIORITY_META, PRIORITY_RANK


API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4o-mini"


def _extract_text(response_json: dict[str, Any]) -> str:
    """Best-effort extraction of text from Responses API payload."""
    if isinstance(response_json.get("output_text"), str) and response_json["output_text"].strip():
        return response_json["output_text"].strip()

    output = response_json.get("output") or []
    for item in output:
        for content in item.get("content", []):
            text_val = content.get("text")
            if isinstance(text_val, str) and text_val.strip():
                return text_val.strip()
    return ""


def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # handle optional language marker e.g. "json\n{...}"
        parts = text.split("\n", 1)
        if len(parts) == 2 and parts[0].lower().strip() in {"json", "javascript"}:
            text = parts[1]
    return text.strip()


def request_llm_triage(
    transcript: str,
    signals: dict[str, Any],
    profile: dict[str, Any],
    matched_keywords: list[str],
) -> dict[str, Any]:
    """
    Ask OpenAI for a triage opinion.
    Returns dict with:
      ok: bool
      priority_level: P1..P4 (when ok=True)
      flags: list[str]
      confidence: float
      reasoning_summary: str
      error: str (when ok=False)
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY not set"}

    model = os.getenv("TRIAGE_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout = float(os.getenv("TRIAGE_LLM_TIMEOUT_SEC", "8"))

    context = {
        "transcript": transcript[:1800],
        "signals": {
            "audio_present": signals.get("audio_present"),
            "breathing_state": signals.get("breathing_state"),
            "vocal_tone": signals.get("vocal_tone"),
            "background_cues": signals.get("background_cues", []),
        },
        "matched_keywords": matched_keywords,
        "profile": {
            "name": profile.get("name"),
            "age": profile.get("age"),
            "medical_history": profile.get("medical_history", []),
            "allergies": profile.get("allergies", []),
            "current_medications": profile.get("current_medications", []),
            "mobility": profile.get("mobility"),
        },
        "policy": {
            "priority_levels": {
                "P1": "Critical, immediate life threat",
                "P2": "High, urgent clinical risk",
                "P3": "Medium, non-immediate but requires follow-up",
                "P4": "Low, likely accidental/non-urgent",
            }
        },
    }

    system_prompt = (
        "You are an emergency triage assistant for senior citizen panic-alert calls. "
        "Be conservative: if uncertain, choose the more urgent category. "
        "Return only valid JSON with keys: priority_level, flags, confidence, reasoning_summary. "
        "priority_level must be one of P1,P2,P3,P4. confidence must be 0..1."
    )

    user_prompt = (
        "Classify this alert and return JSON only.\n"
        + json.dumps(context, ensure_ascii=False)
    )

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
        "temperature": 0.1,
        "max_output_tokens": 250,
    }

    req = request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"HTTP {e.code}: {detail[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        resp_json = json.loads(body)
        text = _extract_text(resp_json)
        if not text:
            return {"ok": False, "error": "No text output from model"}
        data = json.loads(_clean_json_text(text))
    except Exception as e:
        return {"ok": False, "error": f"Invalid model JSON: {e}"}

    priority = str(data.get("priority_level", "")).upper().strip()
    if priority not in PRIORITY_RANK:
        return {"ok": False, "error": f"Invalid priority_level: {priority}"}

    raw_flags = data.get("flags") if isinstance(data.get("flags"), list) else []
    flags = [str(f).strip() for f in raw_flags if str(f).strip()]

    try:
        confidence = float(data.get("confidence", 0.0))
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    reasoning = str(data.get("reasoning_summary", "")).strip()[:320]

    return {
        "ok": True,
        "priority_level": priority,
        "flags": flags,
        "confidence": confidence,
        "reasoning_summary": reasoning,
        "model": model,
    }


def merge_rule_and_llm(rule_result: dict[str, Any], llm_result: dict[str, Any]) -> dict[str, Any]:
    """
    Merge policy:
    - Keep rule result if LLM unavailable.
    - If LLM is more urgent, escalate.
    - Never downgrade below rule priority.
    """
    final = deepcopy(rule_result)
    final["rule_priority_level"] = rule_result.get("priority_level")
    final["decision_source"] = "rules_only"

    if not llm_result.get("ok"):
        final["llm_status"] = llm_result.get("error", "unavailable")
        return final

    llm_priority = llm_result["priority_level"]
    final["llm_priority_level"] = llm_priority
    final["llm_confidence"] = llm_result.get("confidence", 0.0)
    final["llm_reasoning_summary"] = llm_result.get("reasoning_summary", "")
    final["llm_flags"] = llm_result.get("flags", [])
    final["llm_model"] = llm_result.get("model")

    existing_flags = list(final.get("flags", []))
    for flag in llm_result.get("flags", []):
        if flag not in existing_flags:
            existing_flags.append(flag)
    final["flags"] = existing_flags

    rule_rank = PRIORITY_RANK.get(str(rule_result.get("priority_level", "P4")), 4)
    llm_rank = PRIORITY_RANK.get(llm_priority, 4)

    if llm_rank < rule_rank:
        meta = PRIORITY_META[llm_priority]
        final["priority_level"] = llm_priority
        final["priority_label"] = meta["label"]
        final["dispatch_action"] = meta["dispatch_action"]
        final["response_target"] = meta["response_target"]
        final["escalated"] = True
        final["trigger_path"] = list(final.get("trigger_path", [])) + [f"llm_escalated_to_{llm_priority}"]
        final["decision_source"] = "hybrid_llm_escalated"
    else:
        final["trigger_path"] = list(final.get("trigger_path", [])) + ["llm_review_no_escalation"]
        final["decision_source"] = "hybrid_rules_held"

    return final
