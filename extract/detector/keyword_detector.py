from datetime import datetime
from pathlib import Path

# ── keyword tiers ────────────────────────────────────────────
# CRITICAL (3 pts) — immediate life threat
CRITICAL = [
    "fire", "burning", "flames",
    "heart attack", "chest pain", "can't breathe", "cannot breathe", "not breathing",
    "stroke", "unconscious", "not responding", "collapsed",
    "bleeding", "blood", "stabbed", "attacked",
    "drowning", "choking",
    "help me", "help", "emergency", "call ambulance", "call 995"
]

# HIGH (2 pts) — serious but not immediately life-threatening
HIGH = [
    "fell down", "fallen", "fall", "can't get up", "cannot get up",
    "broken", "fracture", "injured", "injury",
    "dizzy", "fainted", "faint", "nausea", "vomiting",
    "pain", "hurts", "hurting", "ache",
    "alone", "no one", "nobody home",
    "confused", "disoriented", "lost",
]

# MEDIUM (1 pt) — worth noting, may need follow-up
MEDIUM = [
    "scared", "afraid", "frightened", "worried",
    "unwell", "sick", "not feeling well", "weak", "tired",
    "medicine", "medication", "forgot", "missed dose",
    "stuck", "trapped", "locked",
    "wet", "soiled",
]

# ── priority labels ──────────────────────────────────────────
def get_priority(score):
    if score >= 3:   return "🔴 CRITICAL"
    elif score >= 2: return "🟠 HIGH"
    elif score >= 1: return "🟡 MEDIUM"
    else:            return "🟢 LOW"

# ── main detector ────────────────────────────────────────────
def analyse(transcript: str, audio_filename: str = "unknown") -> dict:
    text = transcript.lower()
    matched = {"critical": [], "high": [], "medium": []}
    score = 0

    for kw in CRITICAL:
        if kw in text:
            matched["critical"].append(kw)
            score += 3

    for kw in HIGH:
        if kw in text:
            matched["high"].append(kw)
            score += 2

    for kw in MEDIUM:
        if kw in text:
            matched["medium"].append(kw)
            score += 1

    priority = get_priority(score)
    all_matched = matched["critical"] + matched["high"] + matched["medium"]

    result = {
        "file":      audio_filename,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "transcript": transcript,
        "priority":  priority,
        "score":     score,
        "matched":   matched,
        "keywords_found": all_matched,
    }

    return result

# ── print alert to terminal ──────────────────────────────────
def print_alert(result: dict):
    print("\n" + "="*52)
    print(f"  {result['priority']}  —  Score: {result['score']}")
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

# ── save risk report ─────────────────────────────────────────
def save_report(result: dict, audio_path: str):
    report_path = audio_path.replace(".webm", "_risk_report.txt")
    with open(report_path, "w") as f:
        f.write(f"PAB RISK REPORT\n")
        f.write(f"{'='*40}\n")
        f.write(f"File      : {result['file']}\n")
        f.write(f"Timestamp : {result['timestamp']}\n")
        f.write(f"Priority  : {result['priority']}\n")
        f.write(f"Score     : {result['score']}\n")
        f.write(f"\nTranscript:\n{result['transcript']}\n")
        f.write(f"\nKeywords Detected:\n")
        if result["matched"]["critical"]:
            f.write(f"  CRITICAL : {', '.join(result['matched']['critical'])}\n")
        if result["matched"]["high"]:
            f.write(f"  HIGH     : {', '.join(result['matched']['high'])}\n")
        if result["matched"]["medium"]:
            f.write(f"  MEDIUM   : {', '.join(result['matched']['medium'])}\n")
        if not result["keywords_found"]:
            f.write("  None detected.\n")
    print(f"  Risk report saved to: {report_path}")