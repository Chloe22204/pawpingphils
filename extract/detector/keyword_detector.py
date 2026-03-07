from datetime import datetime
from extract.detector.profile_loader import load_profile, format_profile_block

# ── keyword tiers ────────────────────────────────────────────
CRITICAL = [
    "fire", "burning", "flames",
    "heart attack", "chest pain", "can't breathe", "cannot breathe", "not breathing",
    "stroke", "unconscious", "not responding", "collapsed",
    "bleeding", "blood", "stabbed", "attacked",
    "drowning", "choking",
    "help me", "help", "emergency", "call ambulance", "call 995"
]

HIGH = [
    "fell down", "fallen", "fall", "can't get up", "cannot get up",
    "broken", "fracture", "injured", "injury",
    "dizzy", "fainted", "faint", "nausea", "vomiting",
    "pain", "hurts", "hurting", "ache",
    "alone", "no one", "nobody home",
    "confused", "disoriented", "lost",
]

MEDIUM = [
    "scared", "afraid", "frightened", "worried",
    "unwell", "sick", "not feeling well", "weak", "tired",
    "medicine", "medication", "forgot", "missed dose",
    "stuck", "trapped", "locked",
    "wet", "soiled",
]

# ── priority labels ───────────────────────────────────────────
def get_priority(tier: str) -> str:
    return {
        "critical": "🔴 CRITICAL",
        "high":     "🟠 HIGH",
        "medium":   "🟡 MEDIUM",
        "low":      "🟢 LOW",
    }.get(tier, "🟢 LOW")

# ── main detector ─────────────────────────────────────────────
def analyse(transcript: str, audio_filename: str = "unknown", audio_path: str = "") -> dict:
    text = transcript.lower()
    matched: dict = {"critical": [], "high": [], "medium": []}

    for kw in CRITICAL:
        if kw in text and kw not in matched["critical"]:
            matched["critical"].append(kw)
    for kw in HIGH:
        if kw in text and kw not in matched["high"]:
            matched["high"].append(kw)
    for kw in MEDIUM:
        if kw in text and kw not in matched["medium"]:
            matched["medium"].append(kw)

    if matched["critical"]:
        top_tier = "critical"
    elif matched["high"]:
        top_tier = "high"
    elif matched["medium"]:
        top_tier = "medium"
    else:
        top_tier = "low"

    # load profile at analysis time
    profile = load_profile(audio_path)

    return {
        "file":           audio_filename,
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "transcript":     transcript,
        "priority":       get_priority(top_tier),
        "top_tier":       top_tier,
        "matched":        matched,
        "keywords_found": matched["critical"] + matched["high"] + matched["medium"],
        "profile":        profile,   # ← attach profile to result
    }

def print_alert(result: dict) -> None:
    profile_block = format_profile_block(result.get("profile", {}))
    print("\n" + "="*52)
    print(f"  {result['priority']}")
    print("="*52)
    print(f"  File      : {result['file']}")
    print(f"  Time      : {result['timestamp']}")
    print()
    print("  PATIENT INFORMATION")
    print("  " + "-"*40)
    print(profile_block)
    print()
    print("  TRANSCRIPT")
    print("  " + "-"*40)
    print(f"  {result['transcript']}")
    print()
    print("  KEYWORDS DETECTED")
    print("  " + "-"*40)
    if result["matched"]["critical"]:
        print(f"  🔴 Critical : {', '.join(result['matched']['critical'])}")
    if result["matched"]["high"]:
        print(f"  🟠 High     : {', '.join(result['matched']['high'])}")
    if result["matched"]["medium"]:
        print(f"  🟡 Medium   : {', '.join(result['matched']['medium'])}")
    if not result["keywords_found"]:
        print("  No risk keywords detected.")
    print("="*52 + "\n")

def save_report(result: dict, audio_path: str) -> None:
    profile_block = format_profile_block(result.get("profile", {}))
    report_path = audio_path.replace(".webm", "_risk_report.txt")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 52 + "\n")
        f.write("  PAB EMERGENCY RISK REPORT\n")
        f.write("=" * 52 + "\n\n")

        f.write(f"  Priority  : {result['priority']}\n")
        f.write(f"  File      : {result['file']}\n")
        f.write(f"  Timestamp : {result['timestamp']}\n\n")

        f.write("  PATIENT INFORMATION\n")
        f.write("  " + "-" * 40 + "\n")
        f.write(profile_block + "\n\n")

        f.write("  TRANSCRIPT\n")
        f.write("  " + "-" * 40 + "\n")
        f.write(f"  {result['transcript']}\n\n")

        f.write("  KEYWORDS DETECTED\n")
        f.write("  " + "-" * 40 + "\n")
        if result["matched"]["critical"]:
            f.write(f"  CRITICAL : {', '.join(result['matched']['critical'])}\n")
        if result["matched"]["high"]:
            f.write(f"  HIGH     : {', '.join(result['matched']['high'])}\n")
        if result["matched"]["medium"]:
            f.write(f"  MEDIUM   : {', '.join(result['matched']['medium'])}\n")
        if not result["keywords_found"]:
            f.write("  None detected.\n")

        f.write("\n" + "=" * 52 + "\n")

    print(f"  Risk report saved to: {report_path}")


