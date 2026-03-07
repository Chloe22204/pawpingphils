"""
test_triage_engine.py
─────────────────────
Unit tests for triage_engine.py covering 6 required scenarios + extras.
Run with: python3 test_triage_engine.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from triage_engine import run_triage

PASS = "✅ PASS"
FAIL = "❌ FAIL"

results = []

def test(name, inputs, expected_priority, expected_flags=None, expected_escalated=None):
    result = run_triage(inputs)
    ok     = result["priority_level"] == expected_priority

    if expected_flags is not None:
        for flag in expected_flags:
            if flag not in result["flags"]:
                ok = False

    if expected_escalated is not None:
        if result["escalated"] != expected_escalated:
            ok = False

    status = PASS if ok else FAIL
    results.append(ok)

    print(f"{status}  {name}")
    print(f"       Expected : {expected_priority}  |  Got: {result['priority_level']}")
    print(f"       Flags    : {result['flags']}")
    print(f"       Path     : {' → '.join(result['trigger_path'])}")
    print(f"       Dispatch : {result['dispatch_action']}")
    if not ok:
        print(f"       ⚠ MISMATCH — full result: {result}")
    print()


print("=" * 60)
print("  PAB TRIAGE ENGINE — UNIT TESTS")
print("=" * 60 + "\n")

# ── TEST 1: No audio detected → AUTO P1 ──────────────────────
test(
    name             = "Scenario 1 — No audio / recording failure",
    inputs           = {
        "audio_present":    False,
        "breathing_state":  "normal",
        "vocal_tone":       "calm",
        "matched_keywords": [],
        "background_cues":  [],
    },
    expected_priority = "P1",
    expected_flags    = ["NO_AUDIO"],
)

# ── TEST 2: Agonal breathing → P1 ────────────────────────────
test(
    name             = "Scenario 2 — Agonal breathing detected",
    inputs           = {
        "audio_present":    True,
        "breathing_state":  "agonal",
        "vocal_tone":       "calm",
        "matched_keywords": [],
        "background_cues":  [],
    },
    expected_priority = "P1",
    expected_flags    = ["BREATHING_EMERGENCY"],
)

# ── TEST 3: Slurred speech → P1 + STROKE_PROTOCOL ────────────
test(
    name             = "Scenario 3 — Slurred / dysarthric speech",
    inputs           = {
        "audio_present":    True,
        "breathing_state":  "normal",
        "vocal_tone":       "slurred",
        "matched_keywords": [],
        "background_cues":  [],
    },
    expected_priority = "P1",
    expected_flags    = ["STROKE_PROTOCOL"],
)

# ── TEST 4: Fall keyword → P2 ─────────────────────────────────
test(
    name             = "Scenario 4 — Fall keyword detected",
    inputs           = {
        "audio_present":    True,
        "breathing_state":  "normal",
        "vocal_tone":       "calm",
        "matched_keywords": ["fell down", "can't get up"],
        "background_cues":  [],
    },
    expected_priority = "P2",
)

# ── TEST 5: Accidental activation → P4 ───────────────────────
test(
    name             = "Scenario 5 — Accidental button press",
    inputs           = {
        "audio_present":    True,
        "breathing_state":  "normal",
        "vocal_tone":       "calm",
        "matched_keywords": ["sorry", "wrong button", "i'm fine"],
        "background_cues":  [],
    },
    expected_priority = "P4",
    expected_flags    = ["ACCIDENTAL"],
)

# ── TEST 6: Background escalation ────────────────────────────
test(
    name              = "Scenario 6 — Background impact escalates P2 → P1",
    inputs            = {
        "audio_present":    True,
        "breathing_state":  "normal",
        "vocal_tone":       "calm",
        "matched_keywords": ["fell down"],
        "background_cues":  ["impact"],
    },
    expected_priority  = "P1",
    expected_escalated = True,
)

# ── BONUS TEST 7: Cardiac keywords → P1 + CARDIAC_PROTOCOL ───
test(
    name             = "Bonus 7 — Chest pain keyword",
    inputs           = {
        "audio_present":    True,
        "breathing_state":  "normal",
        "vocal_tone":       "distressed",
        "matched_keywords": ["chest pain"],
        "background_cues":  [],
    },
    expected_priority = "P1",
    expected_flags    = ["CARDIAC_PROTOCOL"],
)

# ── BONUS TEST 8: Smoke alarm override ────────────────────────
test(
    name             = "Bonus 8 — Smoke alarm overrides P3 → P1",
    inputs           = {
        "audio_present":    True,
        "breathing_state":  "normal",
        "vocal_tone":       "calm",
        "matched_keywords": ["help"],
        "background_cues":  ["alarm"],
    },
    expected_priority  = "P1",
    expected_escalated = True,
)

# ── BONUS TEST 9: No keywords → default P3 ───────────────────
test(
    name             = "Bonus 9 — No keywords detected, default medium",
    inputs           = {
        "audio_present":    True,
        "breathing_state":  "normal",
        "vocal_tone":       "calm",
        "matched_keywords": [],
        "background_cues":  [],
    },
    expected_priority = "P3",
)

# ── BONUS TEST 10: Laboured breathing → P1 ───────────────────
test(
    name             = "Bonus 10 — Laboured breathing",
    inputs           = {
        "audio_present":    True,
        "breathing_state":  "laboured",
        "vocal_tone":       "calm",
        "matched_keywords": [],
        "background_cues":  [],
    },
    expected_priority = "P1",
    expected_flags    = ["BREATHING_EMERGENCY"],
)

# ── Summary ───────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
print("=" * 60)
print(f"  RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("  🎉 All tests passed!")
else:
    print(f"  ⚠  {total - passed} test(s) failed — review output above")
print("=" * 60)
