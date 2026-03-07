import json
from pathlib import Path

def load_profile(audio_path: str) -> dict:
    """Load the user profile saved alongside the audio file."""
    meta_path = Path(audio_path).with_suffix("").with_suffix(".meta.json")
    if not meta_path.exists():
        print(f"⚠️  No profile found at {meta_path}")
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)

def format_profile_block(profile: dict) -> str:
    if not profile:
        return "  [No user profile found]\n"
    lines = []
    lines.append(f"  Name              : {profile.get('name', 'Unknown')}")
    lines.append(f"  Age               : {profile.get('age', 'Unknown')}")
    lines.append(f"  Contact           : {profile.get('contact', 'Unknown')}")
    ec = profile.get("emergency_contact", {})
    if ec:
        lines.append(f"  Emergency Contact : {ec.get('name','')} — {ec.get('number','')}")
    lines.append(f"  Address           : {profile.get('address', 'Unknown')}")
    lines.append(f"  Mobility          : {profile.get('mobility', 'Unknown')}")
    lines.append(f"  Language          : {profile.get('language', 'Unknown')}")
    med_history = profile.get("medical_history", [])
    if med_history:
        lines.append(f"  Medical History   : {', '.join(med_history)}")
    medications = profile.get("current_medications", [])
    if medications:
        lines.append("  Current Medications:")
        for med in medications:
            lines.append(f"    - {med}")
    allergies = profile.get("allergies", [])
    if allergies:
        lines.append(f"  ⚠️  Allergies      : {', '.join(allergies)}")
    return "\n".join(lines)