"""
llm_triage.py  —  Optional LLM annotation layer for PAB alerts.

Architecture role
─────────────────
This module is the LAST layer in the pipeline. By the time it runs:
  - keyword_detector has already run exact matching + AI-1/AI-2 canonical signals
  - triage_engine has already produced a deterministic rule-based priority

The LLM here outputs:
  - priority_level: P1..P4 (can override rules, but guarded by confidence + floor)
  - flags: extra contextual observations (e.g. "patient has cardiac history")
  - reasoning_summary: a human-readable note for the responder
  - confidence: 0.0..1.0

Merge policy
────────────
- Rules result is always the floor — LLM can never downgrade below rule priority.
- LLM can upgrade priority only if confidence >= LLM_CONFIDENCE_THRESHOLD (0.75).
- If LLM is unavailable or returns garbage, rules result is used as-is.
- LLM flags are always merged in (additive, not priority-setting).
"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from typing import Any

from openai import OpenAI

from triage_engine import PRIORITY_META, PRIORITY_RANK

logger = logging.getLogger(__name__)

# ── shared client ──────────────────────────────────────────────────────────────
# For Alibaba Model Studio, set:
#   OPENAI_API_KEY   = your Alibaba DashScope API key
#   OPENAI_BASE_URL  = https://dashscope.aliyuncs.com/compatible-mode/v1
# The OpenAI-compatible client picks both up automatically.
_openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)

DEFAULT_MODEL = os.getenv("TRIAGE_LLM_MODEL", "qwen-plus")

VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}

# LLM override is accepted only when confidence clears this bar.
LLM_CONFIDENCE_THRESHOLD = float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.75"))


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPT
#  Now explicitly requests priority_level so the LLM actually returns it.
# ═══════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """\
You are a triage annotation assistant for a Personal Alert Button emergency system.

A deterministic rules engine has already assigned an initial priority level.
Your job is to review the transcript and context, then output:
  1. priority_level — one of exactly: P1, P2, P3, P4
       P1 = CRITICAL  (immediate life threat)
       P2 = HIGH      (urgent, rapid response needed)
       P3 = MEDIUM    (non-urgent but needs attention)
       P4 = LOW       (routine / false alarm)
  2. flags — short contextual notes the rules engine may have missed
       (max 5 flags, max 60 characters each)
  3. reasoning_summary — max 2 sentences for the human responder
  4. confidence — how confident you are in your priority_level (0.0 to 1.0)

Output ONLY valid JSON. No markdown fences. No explanation outside the JSON.

Required format (all fields mandatory):
{
  "priority_level": "P1" | "P2" | "P3" | "P4",
  "flags": ["<short note>", ...],
  "reasoning_summary": "<max 2 sentences>",
  "confidence": 0.0
}

Hard rules:
- priority_level MUST be one of: P1, P2, P3, P4 — no other values accepted.
- Do NOT give medical diagnoses or treatment advice.
- If uncertain, default to matching current_rule_priority rather than escalating.
- flags must each be under 60 characters.
"""


def request_llm_triage(
    transcript: str,
    signals: dict[str, Any],
    profile: dict[str, Any],
    matched_keywords: list[str],
    rule_priority_level: str = "P4",
) -> dict[str, Any]:
    """
    Ask the LLM for a priority assessment, contextual flags, and a reasoning summary.

    Returns dict with:
      ok: bool
      priority_level: str  (always a valid P1..P4, falls back to rule level)
      flags: list[str]
      confidence: float
      reasoning_summary: str
      model: str
      error: str  (only when ok=False)
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY not set"}

    model = os.getenv("TRIAGE_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout = float(os.getenv("TRIAGE_LLM_TIMEOUT_SEC", "8"))

    context = {
        "transcript": transcript[:1800],
        "current_rule_priority": rule_priority_level,
        "signals": {
            "audio_present":   signals.get("audio_present"),
            "breathing_state": signals.get("breathing_state"),
            "vocal_tone":      signals.get("vocal_tone"),
            "background_cues": signals.get("background_cues", []),
        },
        "matched_keywords": matched_keywords,
        "profile": {
            "name":                profile.get("name"),
            "age":                 profile.get("age"),
            "medical_history":     profile.get("medical_history", []),
            "allergies":           profile.get("allergies", []),
            "current_medications": profile.get("current_medications", []),
            "mobility":            profile.get("mobility"),
        },
    }

    user_msg = (
        "Annotate this alert. Return JSON only.\n"
        + json.dumps(context, ensure_ascii=False)
    )

    try:
        response = _openai_client.chat.completions.create(
            model=model,
            temperature=0.1,
            max_tokens=300,
            timeout=timeout,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        )
        raw = response.choices[0].message.content.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.strip("`")
            parts = raw.split("\n", 1)
            if len(parts) == 2 and parts[0].lower().strip() in {"json", "javascript"}:
                raw = parts[1]
        raw = raw.strip()

        data = json.loads(raw)

    except Exception as exc:
        logger.warning("LLM triage call failed (non-fatal): %s", exc)
        return {"ok": False, "error": str(exc)}

    # ── Validate and extract — never trust raw LLM output ─────────────────────

    # priority_level: must be one of P1..P4, else fall back to rule level
    raw_priority = str(data.get("priority_level", "")).strip().upper()
    priority = raw_priority if raw_priority in VALID_PRIORITIES else rule_priority_level

    if raw_priority not in VALID_PRIORITIES:
        logger.warning(
            "LLM returned invalid priority_level %r — falling back to rule level %s",
            raw_priority, rule_priority_level,
        )

    # flags: list of short strings
    raw_flags = data.get("flags") if isinstance(data.get("flags"), list) else []
    flags = [str(f).strip()[:60] for f in raw_flags if str(f).strip()][:5]

    # confidence: float clamped 0..1
    try:
        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except Exception:
        confidence = 0.0

    reasoning = str(data.get("reasoning_summary", "")).strip()[:320]

    return {
        "ok":               True,
        "priority_level":   priority,
        "flags":            flags,
        "confidence":       confidence,
        "reasoning_summary": reasoning,
        "model":            model,
    }


def merge_rule_and_llm(
    rule_result: dict[str, Any],
    llm_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge policy
    ────────────
    - Rules result is always the base.
    - LLM can override priority UP (more urgent) only if confidence >= threshold.
    - LLM can NEVER downgrade priority below the rule result (rules are the floor).
    - LLM flags and reasoning are always merged in regardless.
    - If LLM is unavailable, rules result is returned as-is.
    """
    final = deepcopy(rule_result)
    final["rule_priority_level"] = rule_result.get("priority_level")
    final["decision_source"]     = "rules_only"

    if not llm_result.get("ok"):
        final["llm_status"] = llm_result.get("error", "unavailable")
        return final

    # ── Always merge flags (additive, safe) ───────────────────────────────────
    existing_flags = list(final.get("flags", []))
    for flag in llm_result.get("flags", []):
        if flag not in existing_flags:
            existing_flags.append(flag)
    final["flags"] = existing_flags

    # ── Always store reasoning for display ────────────────────────────────────
    final["llm_reasoning_summary"] = llm_result.get("reasoning_summary", "")
    final["llm_confidence"]        = llm_result.get("confidence", 0.0)
    final["llm_model"]             = llm_result.get("model")

    # ── Priority resolution ───────────────────────────────────────────────────
    rule_priority = str(rule_result.get("priority_level", "P4"))
    rule_rank     = PRIORITY_RANK.get(rule_priority, 4)

    # Safe fallback: if llm_result somehow missing priority_level, use rule level
    llm_priority = str(llm_result.get("priority_level", rule_priority)).strip().upper()
    if llm_priority not in VALID_PRIORITIES:
        llm_priority = rule_priority
    llm_rank = PRIORITY_RANK.get(llm_priority, 4)

    confidence = llm_result.get("confidence", 0.0)

    # LLM override accepted only if:
    #   (a) LLM priority is more urgent (lower rank number) than rules
    #   (b) LLM confidence clears the threshold
    # LLM can NEVER downgrade (if llm_rank > rule_rank, we keep rule priority)
    llm_wants_upgrade = llm_rank < rule_rank
    llm_confident     = confidence >= LLM_CONFIDENCE_THRESHOLD

    if llm_wants_upgrade and llm_confident:
        meta = PRIORITY_META[llm_priority]
        final["priority_level"]  = llm_priority
        final["priority_label"]  = meta["label"]
        final["dispatch_action"] = meta["dispatch_action"]
        final["response_target"] = meta["response_target"]
        final["escalated"]       = True
        final["trigger_path"]    = list(final.get("trigger_path", [])) + [
            f"llm_upgraded_{rule_priority}_to_{llm_priority}"
        ]
        final["decision_source"] = "hybrid_llm_override"

    elif llm_wants_upgrade and not llm_confident:
        # LLM wanted to escalate but wasn't confident enough — rules hold
        logger.info(
            "LLM suggested %s but confidence %.2f < threshold %.2f — rules hold at %s",
            llm_priority, confidence, LLM_CONFIDENCE_THRESHOLD, rule_priority,
        )
        final["trigger_path"]    = list(final.get("trigger_path", [])) + [
            f"llm_suggested_{llm_priority}_low_confidence_rules_held"
        ]
        final["decision_source"] = "hybrid_rules_held"

    else:
        # LLM agreed with rules or suggested downgrade — either way, rules hold
        final["trigger_path"]    = list(final.get("trigger_path", [])) + [
            "llm_review_no_escalation"
        ]
        final["decision_source"] = "hybrid_rules_held"

    final["llm_priority_level"] = llm_priority
    return final