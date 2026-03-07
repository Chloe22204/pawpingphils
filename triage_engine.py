"""
triage_engine.py
────────────────
PAB Triage Scoring Engine — Phase 1
Accepts structured signal inputs and outputs a triage priority level (P1–P4).

Designed so that when Phase 2 audio analysis is complete, mock input values
are simply replaced with real audio feature values — no restructuring needed.
"""

# ── Priority level definitions ────────────────────────────────────────────────
PRIORITY_META = {
    "P1": {
        "label":           "CRITICAL",
        "dispatch_action": "Dispatch ALS + Emergency Services immediately.",
        "response_target": "< 8 minutes",
    },
    "P2": {
        "label":           "HIGH",
        "dispatch_action": "Dispatch BLS unit urgently.",
        "response_target": "< 15 minutes",
    },
    "P3": {
        "label":           "MEDIUM",
        "dispatch_action": "Dispatch community responder for assessment.",
        "response_target": "< 30 minutes",
    },
    "P4": {
        "label":           "LOW",
        "dispatch_action": "Schedule welfare call or telehealth check-in.",
        "response_target": "< 2 hours",
    },
}

# ── Keyword category mappings (feeds from existing keyword_detector.py) ───────
# Maps keyword strings to (priority, flag) tuples
KEYWORD_RULES = {
    # Cardiac / Respiratory → P1 + CARDIAC_PROTOCOL
    "chest pain":      ("P1", "CARDIAC_PROTOCOL"),
    "can't breathe":   ("P1", "CARDIAC_PROTOCOL"),
    "cannot breathe":  ("P1", "CARDIAC_PROTOCOL"),
    "arm pain":        ("P1", "CARDIAC_PROTOCOL"),
    "heart attack":    ("P1", "CARDIAC_PROTOCOL"),
    "heart":           ("P1", "CARDIAC_PROTOCOL"),
    "not breathing":   ("P1", "CARDIAC_PROTOCOL"),

    # Neurological → P2 + NEURO_PROTOCOL
    "confused":        ("P2", "NEURO_PROTOCOL"),
    "dizzy":           ("P2", "NEURO_PROTOCOL"),
    "can't speak":     ("P2", "NEURO_PROTOCOL"),
    "stroke":          ("P2", "NEURO_PROTOCOL"),
    "numb":            ("P2", "NEURO_PROTOCOL"),
    "disoriented":     ("P2", "NEURO_PROTOCOL"),

    # Fall / Trauma → P2
    "fallen":          ("P2", None),
    "fell down":       ("P2", None),
    "fell":            ("P2", None),
    "can't get up":    ("P2", None),
    "cannot get up":   ("P2", None),
    "hurt":            ("P2", None),
    "pain":            ("P2", None),
    "injured":         ("P2", None),
    "bleeding":        ("P2", None),

    # General distress → P3
    "help":            ("P3", None),
    "help me":         ("P3", None),
    "something's wrong": ("P3", None),
    "not well":        ("P3", None),
    "unwell":          ("P3", None),
    "emergency":       ("P3", None),

    # Accidental / Minor → P4
    "sorry":           ("P4", "ACCIDENTAL"),
    "accident":        ("P4", "ACCIDENTAL"),
    "wrong button":    ("P4", "ACCIDENTAL"),
    "i'm fine":        ("P4", "ACCIDENTAL"),
    "im fine":         ("P4", "ACCIDENTAL"),
    "okay":            ("P4", "ACCIDENTAL"),
    "by accident":     ("P4", "ACCIDENTAL"),
}

# Priority rank for comparison (lower = more urgent)
PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


# ── STEP 1: Audio Presence Check ──────────────────────────────────────────────
def check_audio_presence(audio_present: bool) -> dict | None:
    """
    STEP 1 — If no audio detected, immediately return P1 CRITICAL.
    Silence or recording failure is treated as a worst-case scenario.
    Returns a result dict if P1 triggered, otherwise None to continue.
    """
    if not audio_present:
        return {
            "priority_level": "P1",
            "trigger_path":   ["no_audio_detected"],
            "flags":          ["NO_AUDIO"],
        }
    return None  # audio present — continue to step 2


# ── STEP 2: Breathing Pattern ─────────────────────────────────────────────────
def assess_breathing(breathing_state: str) -> dict | None:
    """
    STEP 2 — Classify breathing pattern.
    Phase 2 will replace this mock input with librosa RMS/pitch analysis.

    Accepted values: "absent", "agonal", "laboured", "rapid", "normal"
    Returns result dict if score determined, otherwise None to continue.
    """
    breathing_state = (breathing_state or "normal").lower().strip()

    # Absent or agonal → P1 immediately
    if breathing_state in ("absent", "agonal", "gasping"):
        return {
            "priority_level": "P1",
            "trigger_path":   ["audio_present", f"breathing_{breathing_state}"],
            "flags":          ["BREATHING_EMERGENCY"],
        }

    # Laboured / stridor / wheezing → P1
    if breathing_state == "laboured":
        return {
            "priority_level": "P1",
            "trigger_path":   ["audio_present", "breathing_laboured"],
            "flags":          ["BREATHING_EMERGENCY"],
        }

    # Rapid or shallow → P2
    if breathing_state == "rapid":
        return {
            "priority_level": "P2",
            "trigger_path":   ["audio_present", "breathing_rapid"],
            "flags":          [],
        }

    # Normal → continue to step 3
    return None


# ── STEP 3: Vocal Tone & Pitch ────────────────────────────────────────────────
def assess_vocal_tone(vocal_tone: str) -> dict | None:
    """
    STEP 3 — Classify vocal tone from audio features.
    Phase 2 will replace this mock input with librosa F0 + MFCC analysis.

    Accepted values: "screaming", "slurred", "weak", "distressed", "calm"
    Returns result dict if score determined, otherwise None to continue.
    """
    vocal_tone = (vocal_tone or "calm").lower().strip()

    # Screaming → P1
    if vocal_tone == "screaming":
        return {
            "priority_level": "P1",
            "trigger_path":   ["audio_present", "breathing_normal", "vocal_screaming"],
            "flags":          [],
        }

    # Slurred / dysarthric → P1 + STROKE flag
    if vocal_tone == "slurred":
        return {
            "priority_level": "P1",
            "trigger_path":   ["audio_present", "breathing_normal", "vocal_slurred"],
            "flags":          ["STROKE_PROTOCOL"],
        }

    # Weak / barely audible → P2
    if vocal_tone == "weak":
        return {
            "priority_level": "P2",
            "trigger_path":   ["audio_present", "breathing_normal", "vocal_weak"],
            "flags":          [],
        }

    # Distressed or calm → continue to step 4
    return None


# ── STEP 4: Keyword Analysis ──────────────────────────────────────────────────
def assess_keywords(matched_keywords: list) -> dict:
    """
    STEP 4 — Score based on keyword matches from the existing keyword_detector.py.
    Accepts the list of matched keywords already produced by the system.

    Uses highest-urgency keyword found (same logic as existing detector —
    no score stacking, highest tier wins).
    """
    best_priority = "P3"   # default: medium if no keywords match
    flags         = []
    matched_rules = []

    # separate accidental keywords from clinical keywords
    accidental_keywords = []
    clinical_keywords   = []

    for kw in matched_keywords:
        kw_lower = kw.lower().strip()
        if kw_lower in KEYWORD_RULES:
            priority, flag = KEYWORD_RULES[kw_lower]
            if priority == "P4":
                accidental_keywords.append((kw_lower, flag))
            else:
                clinical_keywords.append((kw_lower, priority, flag))

    # if ONLY accidental keywords present and no clinical keywords → P4
    if accidental_keywords and not clinical_keywords:
        best_priority = "P4"
        for kw_lower, flag in accidental_keywords:
            if flag and flag not in flags:
                flags.append(flag)
            matched_rules.append(kw_lower)
    else:
        # score only clinical keywords — accidental keywords are ignored
        # when clinical keywords are also present
        for kw_lower, priority, flag in clinical_keywords:
            if PRIORITY_RANK[priority] < PRIORITY_RANK[best_priority]:
                best_priority = priority
            if flag and flag not in flags:
                flags.append(flag)
            matched_rules.append(kw_lower)

    trigger = "keyword_" + best_priority.lower()

    # check for accidental activation
    if best_priority == "P4":
        trigger = "keyword_accidental"

    # no keywords at all → P3 default
    if not matched_keywords:
        trigger = "keyword_none_default_medium"

    return {
        "priority_level": best_priority,
        "trigger_path":   [
            "audio_present", "breathing_normal",
            "vocal_tone_assessed", trigger
        ],
        "flags": flags,
    }


# ── STEP 5: Background Sound Modifier ────────────────────────────────────────
def apply_background_modifiers(
    current_priority: str,
    background_cues: list,
    trigger_path: list,
    flags: list
) -> tuple[str, list, list, bool]:
    """
    STEP 5 — Apply background sound modifiers to escalate priority.
    Phase 2 will replace mock inputs with real audio segmentation.

    P1 overrides: "alarm", "silence"
    +1 level escalation: "impact", "water", "moaning"
    No escalation: "carer_present" (logged only)

    Returns: (final_priority, updated_trigger_path, updated_flags, escalated_bool)
    """
    escalated        = False
    modifiers_applied = []

    for cue in (background_cues or []):
        cue = cue.lower().strip()

        # Hard overrides → P1 regardless of current score
        if cue in ("alarm", "silence"):
            if current_priority != "P1":
                current_priority = "P1"
                escalated        = True
                modifiers_applied.append(f"bg_{cue}_override_P1")

        # +1 level escalation
        elif cue in ("impact", "water", "moaning"):
            rank = PRIORITY_RANK.get(current_priority, 4)
            if rank > 1:  # can't escalate beyond P1
                new_rank     = rank - 1
                new_priority = [k for k, v in PRIORITY_RANK.items() if v == new_rank][0]
                current_priority = new_priority
                escalated        = True
                modifiers_applied.append(f"bg_{cue}_escalated_to_{new_priority}")

        # Carer present — note only, no escalation
        elif cue == "carer_present":
            modifiers_applied.append("bg_carer_present_noted")

    trigger_path.extend(modifiers_applied)
    return current_priority, trigger_path, flags, escalated


# ── MAIN ENTRY POINT ──────────────────────────────────────────────────────────
def run_triage(inputs: dict) -> dict:
    """
    Main triage function. Single entry point for the scoring engine.

    Expected inputs dict:
    {
        "audio_present":     bool,         # True if audio detected
        "breathing_state":   str,          # "absent"|"agonal"|"laboured"|"rapid"|"normal"
        "vocal_tone":        str,          # "screaming"|"slurred"|"weak"|"distressed"|"calm"
        "matched_keywords":  list[str],    # from existing keyword_detector.py
        "background_cues":   list[str],    # "impact"|"alarm"|"water"|"moaning"|"silence"|"carer_present"
    }

    Returns structured result dict with priority, flags, dispatch info, and audit trail.
    """
    flags        = []
    trigger_path = []

    # ── STEP 1: Audio presence ──────────────────────────────────────────────
    result = check_audio_presence(inputs.get("audio_present", True))
    if result:
        priority     = result["priority_level"]
        trigger_path = result["trigger_path"]
        flags        = result["flags"]
        # still apply background modifiers even with no audio
        priority, trigger_path, flags, escalated = apply_background_modifiers(
            priority, inputs.get("background_cues", []), trigger_path, flags
        )
        return _build_result(priority, trigger_path, flags, escalated, inputs.get("background_cues", []))

    trigger_path.append("audio_present")

    # ── STEP 2: Breathing ───────────────────────────────────────────────────
    result = assess_breathing(inputs.get("breathing_state", "normal"))
    if result:
        priority     = result["priority_level"]
        trigger_path = result["trigger_path"]
        flags        = result["flags"]
        priority, trigger_path, flags, escalated = apply_background_modifiers(
            priority, inputs.get("background_cues", []), trigger_path, flags
        )
        return _build_result(priority, trigger_path, flags, escalated, inputs.get("background_cues", []))

    trigger_path.append("breathing_normal")

    # ── STEP 3: Vocal tone ──────────────────────────────────────────────────
    result = assess_vocal_tone(inputs.get("vocal_tone", "calm"))
    if result:
        priority     = result["priority_level"]
        trigger_path = result["trigger_path"]
        flags        = result.get("flags", [])
        priority, trigger_path, flags, escalated = apply_background_modifiers(
            priority, inputs.get("background_cues", []), trigger_path, flags
        )
        return _build_result(priority, trigger_path, flags, escalated, inputs.get("background_cues", []))

    trigger_path.append("vocal_tone_assessed")

    # ── STEP 4: Keywords ────────────────────────────────────────────────────
    result   = assess_keywords(inputs.get("matched_keywords", []))
    priority = result["priority_level"]
    trigger_path.extend([s for s in result["trigger_path"] if s not in trigger_path])
    flags.extend([f for f in result["flags"] if f not in flags])

    # ── STEP 5: Background modifiers ────────────────────────────────────────
    priority, trigger_path, flags, escalated = apply_background_modifiers(
        priority, inputs.get("background_cues", []), trigger_path, flags
    )

    return _build_result(priority, trigger_path, flags, escalated, inputs.get("background_cues", []))


# ── Result builder ─────────────────────────────────────────────────────────────
def _build_result(
    priority: str,
    trigger_path: list,
    flags: list,
    escalated: bool,
    background_cues: list
) -> dict:
    """Assemble the final structured result object."""
    meta = PRIORITY_META[priority]
    return {
        "priority_level":       priority,
        "priority_label":       meta["label"],
        "dispatch_action":      meta["dispatch_action"],
        "response_target":      meta["response_target"],
        "flags":                flags,
        "trigger_path":         trigger_path,
        "background_modifiers": background_cues or [],
        "escalated":            escalated,
    }