from datetime import datetime
import os

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
def analyse(transcript: str, audio_filename: str = "unknown") -> dict:
    text = transcript.lower()
    matched: dict = {"critical": [], "high": [], "medium": []}

    # collect unique matches only — duplicates are ignored
    for kw in CRITICAL:
        if kw in text and kw not in matched["critical"]:
            matched["critical"].append(kw)

    for kw in HIGH:
        if kw in text and kw not in matched["high"]:
            matched["high"].append(kw)

    for kw in MEDIUM:
        if kw in text and kw not in matched["medium"]:
            matched["medium"].append(kw)

    # ── urgency based on HIGHEST tier found, not cumulative score ──
    if matched["critical"]:
        top_tier = "critical"
    elif matched["high"]:
        top_tier = "high"
    elif matched["medium"]:
        top_tier = "medium"
    else:
        top_tier = "low"

    return {
        "file":           audio_filename,
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "transcript":     transcript,
        "priority":       get_priority(top_tier),
        "top_tier":       top_tier,
        "matched":        matched,
        "keywords_found": matched["critical"] + matched["high"] + matched["medium"],
    }

# ── print alert to terminal ───────────────────────────────────
def print_alert(result: dict) -> None:
    print("\n" + "="*52)
    print(f"  {result['priority']}")
    print("="*52)
    print(f"  File      : {result['file']}")
    print(f"  Time      : {result['timestamp']}")
    print(f"  Transcript: {result['transcript']}")
    print()
    if result["matched"]["critical"]:
        print(f"  🔴 Critical keywords : {', '.join(result['matched']['critical'])}")
    if result["matched"]["high"]:
        print(f"  🟠 High keywords     : {', '.join(result['matched']['high'])}")
    if result["matched"]["medium"]:
        print(f"  🟡 Medium keywords   : {', '.join(result['matched']['medium'])}")
    if not result["keywords_found"]:
        print("  No risk keywords detected.")
    print("="*52 + "\n")

# ── save risk report ──────────────────────────────────────────
def save_report(result: dict, audio_path: str) -> None:
    report_path = audio_path.replace(".webm", "_risk_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("PAB RISK REPORT\n")
        f.write(f"{'='*40}\n")
        f.write(f"File      : {result['file']}\n")
        f.write(f"Timestamp : {result['timestamp']}\n")
        f.write(f"Priority  : {result['priority']}\n")
        f.write(f"\nTranscript:\n{result['transcript']}\n")
        f.write("\nKeywords Detected:\n")
        if result["matched"]["critical"]:
            f.write(f"  CRITICAL : {', '.join(result['matched']['critical'])}\n")
        if result["matched"]["high"]:
            f.write(f"  HIGH     : {', '.join(result['matched']['high'])}\n")
        if result["matched"]["medium"]:
            f.write(f"  MEDIUM   : {', '.join(result['matched']['medium'])}\n")
        if not result["keywords_found"]:
            f.write("  None detected.\n")
    print(f"  Risk report saved to: {report_path}")