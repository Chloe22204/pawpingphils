# watcher.py
import time
import sys
import os
import re
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from triage_engine import run_triage
from audio_analyser import analyse_audio
from llm_triage import request_llm_triage, merge_rule_and_llm
from triage_engine import PRIORITY_META

# add extract to path
sys.path.append(str(Path(__file__).parent))

import whisper
import warnings
warnings.filterwarnings("ignore")

from extract.detector.keyword_detector import analyse, print_alert, save_report

# ── load model ONCE at startup ────────────────────────────────
print("⏳ Loading Whisper model...")
model = whisper.load_model("small")
print("✅ Model ready\n")

WATCH_FOLDER = Path("recordings")

PRIORITY_BADGE = {
    "P1": "🔴 CRITICAL",
    "P2": "🟠 HIGH",
    "P3": "🟡 MEDIUM",
    "P4": "🟢 LOW",
}

BENIGN_PHRASES = {
    "bored", "come play", "play with me", "chat with me", "lonely",
    "just calling", "testing", "test only", "no emergency",
    "yay", "won the lottery", "i won", "good news", "talk to you",
}
RISK_TERMS = {
    "help", "pain", "hurt", "fell", "fall", "bleeding", "blood",
    "breathe", "breath", "chest", "stroke", "emergency", "dizzy",
    "cannot", "can't", "fainted", "seizure", "unconscious",
}
IMPACT_CORROBORATION_TERMS = {
    "fall", "fell", "fallen", "hit", "head", "bang", "slip", "trip",
    "pain", "hurt", "injury", "bleeding", "fracture", "cannot get up", "can't get up",
}
GIBBERISH_FILLERS = {
    "uh", "umm", "um", "ah", "eh", "hmm", "mmm", "er", "uhh", "mm",
    "la", "leh", "lor", "bah", "blah", "ba", "da", "na",
}


def _is_benign_transcript(transcript: str) -> bool:
    t = (transcript or "").lower()
    has_benign = any(p in t for p in BENIGN_PHRASES)
    has_risk = any(r in t for r in RISK_TERMS)
    return has_benign and not has_risk


def _stabilize_false_positive_audio_signals(transcript: str, detection: dict, signals: dict) -> dict:
    """Prevent speech-only social utterances from being over-scored by noisy audio features."""
    if detection.get("keywords_found"):
        signals["_benign_guard_applied"] = False
        return signals
    if not _is_benign_transcript(transcript):
        signals["_benign_guard_applied"] = False
        return signals

    adjusted = dict(signals)
    adjusted["_benign_guard_applied"] = True
    if adjusted.get("breathing_state") in {"laboured", "rapid"}:
        adjusted["breathing_state"] = "normal"
    if adjusted.get("vocal_tone") == "distressed":
        adjusted["vocal_tone"] = "calm"
    cues = [c for c in adjusted.get("background_cues", []) if c not in {"impact", "alarm", "water"}]
    adjusted["background_cues"] = cues
    print("   ⚙️ Benign transcript guard applied: de-escalated noisy audio cues")
    return adjusted


def _sanitize_impact_cue(transcript: str, detection: dict, signals: dict) -> dict:
    """
    Keep 'impact' only when corroborated:
    - transcript has injury/fall language, or
    - analyser observed repeated strong impacts.
    """
    if "impact" not in (signals.get("background_cues") or []):
        return signals

    t = (transcript or "").lower()
    has_injury_language = any(term in t for term in IMPACT_CORROBORATION_TERMS)
    keywords = [str(k).lower() for k in detection.get("keywords_found", [])]
    has_risk_keyword = any(
        any(term in kw for term in IMPACT_CORROBORATION_TERMS)
        for kw in keywords
    )
    repeated_impacts = int(signals.get("impact_event_count", 0)) >= 2

    if has_injury_language or has_risk_keyword or repeated_impacts:
        return signals

    adjusted = dict(signals)
    adjusted["background_cues"] = [c for c in adjusted.get("background_cues", []) if c != "impact"]
    print("   ⚙️ Impact cue removed (no injury language and no repeated impacts)")
    return adjusted


def _is_gibberish_transcript(transcript: str, segments: list) -> bool:
    """
    Heuristic detector for incoherent/gibberish speech.
    Designed to catch utterances with poor lexical structure and low ASR confidence.
    """
    t = (transcript or "").lower().strip()
    words = re.findall(r"[a-z']+", t)
    if len(words) < 3:
        return False

    if any(r in t for r in RISK_TERMS):
        return False

    filler_ratio = sum(1 for w in words if w in GIBBERISH_FILLERS) / len(words)
    meaningful_ratio = sum(1 for w in words if len(w) >= 4) / len(words)
    unique_ratio = len(set(words)) / len(words)

    valid_segments = [s for s in (segments or []) if s.get("no_speech_prob", 1.0) < 0.6]
    low_conf_count = 0
    for seg in valid_segments:
        avg_logprob = float(seg.get("avg_logprob", 0.0))
        comp_ratio = float(seg.get("compression_ratio", 0.0))
        if avg_logprob < -1.15 or comp_ratio > 2.35:
            low_conf_count += 1
    low_conf_ratio = (low_conf_count / len(valid_segments)) if valid_segments else 0.0

    filler_driven = filler_ratio > 0.42 and meaningful_ratio < 0.36
    incoherent_structure = meaningful_ratio < 0.30 and unique_ratio < 0.58 and len(words) >= 4
    asr_uncertain = low_conf_ratio > 0.65 and meaningful_ratio < 0.45

    return filler_driven or incoherent_structure or asr_uncertain


def _is_non_human_only_case(detection: dict) -> bool:
    matched = detection.get("matched", {}) if isinstance(detection, dict) else {}
    low = matched.get("low", []) if isinstance(matched, dict) else []
    critical = matched.get("critical", []) if isinstance(matched, dict) else []
    high = matched.get("high", []) if isinstance(matched, dict) else []
    medium = matched.get("medium", []) if isinstance(matched, dict) else []
    return bool(low) and not (critical or high or medium)


def transcribe_and_analyse(audio_path: Path):
    result = model.transcribe(
        str(audio_path),
        task="translate",
        language="zh",
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        condition_on_previous_text=False,
        temperature=0.0,
        beam_size=1,
        best_of=1,
    )

    segments = result.get("segments", [])
    filtered = [
        seg for seg in segments
        if seg.get("no_speech_prob", 1.0) < 0.6 and len(seg.get("text", "").strip()) > 3
    ]
    transcript = " ".join([seg["text"].strip() for seg in filtered])
    transcript = transcript if transcript else "[No speech detected]"

    print(f"\nTranscript: {transcript}")

    # save transcript
    txt_path = str(audio_path).replace(".webm", ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(transcript)
    gibberish_alert = _is_gibberish_transcript(transcript, filtered)

    # ── keyword detection ─────────────────────────────────────────
    detection = analyse(transcript, audio_filename=audio_path.name, audio_path=str(audio_path))
    # ── Phase 2: real audio analysis ─────────────────────────────
    signals = analyse_audio(str(audio_path))
    signals = _stabilize_false_positive_audio_signals(transcript, detection, signals)
    signals = _sanitize_impact_cue(transcript, detection, signals)

    # ── run deterministic rules engine ────────────────────────────
    rule_result = run_triage({
        "audio_present":    signals["audio_present"],
        "breathing_state":  signals["breathing_state"],
        "vocal_tone":       signals["vocal_tone"],
        "matched_keywords": detection["keywords_found"],
        "background_cues":  signals["background_cues"],
    })

    # ── optional LLM triage overlay (never downgrades rules) ─────
    llm_result = request_llm_triage(
        transcript=transcript,
        signals=signals,
        profile=detection.get("profile", {}),
        matched_keywords=detection.get("keywords_found", []),
    )

    # If transcript is clearly social/benign and keywords found nothing risky,
    # prevent HIGH/CRITICAL over-scoring from noisy audio artifacts.
    if (
        signals.get("_benign_guard_applied") and
        not detection.get("keywords_found") and
        not gibberish_alert and
        llm_result.get("ok") and
        llm_result.get("priority_level") in {"P1", "P2"}
    ):
        llm_result["priority_level"] = "P3"
        reason = llm_result.get("reasoning_summary", "")
        llm_result["reasoning_summary"] = (reason + " | Benign transcript guard capped urgency at P3.").strip(" |")

    triage_result = merge_rule_and_llm(rule_result, llm_result)

    if signals.get("_benign_guard_applied") and not gibberish_alert and triage_result.get("priority_level") in {"P1", "P2"}:
        triage_result["priority_level"] = "P3"
        triage_result["priority_label"] = PRIORITY_META["P3"]["label"]
        triage_result["dispatch_action"] = PRIORITY_META["P3"]["dispatch_action"]
        triage_result["response_target"] = PRIORITY_META["P3"]["response_target"]
        triage_result["trigger_path"] = list(triage_result.get("trigger_path", [])) + ["benign_guard_cap_P3"]

    if gibberish_alert:
        triage_result["priority_level"] = "P1"
        triage_result["priority_label"] = PRIORITY_META["P1"]["label"]
        triage_result["dispatch_action"] = PRIORITY_META["P1"]["dispatch_action"]
        triage_result["response_target"] = PRIORITY_META["P1"]["response_target"]
        flags = list(triage_result.get("flags", []))
        if "INCOHERENT_SPEECH_POSSIBLE_CARDIAC" not in flags:
            flags.append("INCOHERENT_SPEECH_POSSIBLE_CARDIAC")
        triage_result["flags"] = flags
        triage_result["decision_source"] = "gibberish_override"
        triage_result["trigger_path"] = list(triage_result.get("trigger_path", [])) + ["gibberish_override_P1"]

    # Final hard override: non-human/property-only cases must stay LOW.
    if _is_non_human_only_case(detection):
        triage_result["priority_level"] = "P4"
        triage_result["priority_label"] = PRIORITY_META["P4"]["label"]
        triage_result["dispatch_action"] = PRIORITY_META["P4"]["dispatch_action"]
        triage_result["response_target"] = PRIORITY_META["P4"]["response_target"]
        flags = list(triage_result.get("flags", []))
        if "NON_HUMAN_CONTEXT" not in flags:
            flags.append("NON_HUMAN_CONTEXT")
        triage_result["flags"] = flags
        triage_result["decision_source"] = "non_human_override"
        triage_result["trigger_path"] = list(triage_result.get("trigger_path", [])) + ["non_human_override_P4"]

    print(f"\n🚨 TRIAGE: {triage_result['priority_level']} — {triage_result['priority_label']}")
    print(f"   Dispatch : {triage_result['dispatch_action']}")
    print(f"   Response : {triage_result['response_target']}")
    if triage_result['flags']:
        print(f"   Flags    : {', '.join(triage_result['flags'])}")
    if triage_result.get("decision_source"):
        print(f"   Source   : {triage_result['decision_source']}")
    if triage_result.get("llm_reasoning_summary"):
        print(f"   LLM Note : {triage_result['llm_reasoning_summary']}")
    if triage_result.get("llm_status"):
        print(f"   LLM      : {triage_result['llm_status']}")
    print(f"   Path     : {' → '.join(triage_result['trigger_path'])}")

    detection["triage"] = triage_result
    detection["priority"] = PRIORITY_BADGE.get(triage_result["priority_level"], detection.get("priority", "🟢 LOW"))
    detection["top_tier"] = triage_result["priority_label"].lower()
    print_alert(detection)
    save_report(detection, str(audio_path))


class AlertHandler(FileSystemEventHandler):
    def on_created(self, event):
        path = Path(event.src_path)
        if path.name.startswith("PAB_Alert_") and path.suffix == ".webm":
            print(f"\n🔴 New alert: {path.name}")
            print("⏳ Transcribing...")
            time.sleep(1)
            transcribe_and_analyse(path)
            print("✅ Done\n")

if __name__ == "__main__":
    WATCH_FOLDER.mkdir(exist_ok=True)
    print(f"👂 Watching {WATCH_FOLDER} for PAB alerts...")
    observer = Observer()
    observer.schedule(AlertHandler(), str(WATCH_FOLDER), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    
