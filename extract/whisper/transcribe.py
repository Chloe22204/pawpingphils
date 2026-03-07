import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# import the detector
sys.path.append(str(Path(__file__).parents[1]))
from detector.keyword_detector import analyse, print_alert, save_report  # noqa: E402

import whisper  # noqa: E402

# ── load model ───────────────────────────────────────────────
model: whisper.Whisper = whisper.load_model("medium")

# ── get audio file from argument ─────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python transcribe.py <audio_file>")
    sys.exit(1)

audio_file: str = sys.argv[1]

# ── transcribe ───────────────────────────────────────────────
result: dict = model.transcribe(
    audio_file,
    task="translate",
    language=None,
    no_speech_threshold=0.6,
    logprob_threshold=-1.0,
    compression_ratio_threshold=2.4,
    condition_on_previous_text=False,
    temperature=0.0,
    beam_size=5,
    best_of=5,
)

# ── filter noise ─────────────────────────────────────────────
segments: list = result.get("segments", [])
filtered_segments: list = [
    seg for seg in segments
    if seg.get("no_speech_prob", 1.0) < 0.6 and len(seg.get("text", "").strip()) > 3
]

transcript: str = " ".join([seg["text"].strip() for seg in filtered_segments])
transcript = transcript if transcript else "[No speech detected]"

print(f"\nTranscript: {transcript}")

# ── save transcript ───────────────────────────────────────────
output_path: str = audio_file.replace(".webm", ".txt")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(transcript)

print(f"Transcript saved to: {output_path}")

# ── keyword detection + ranking ───────────────────────────────
detection: dict = analyse(transcript, audio_filename=os.path.basename(audio_file))
print_alert(detection)
save_report(detection, audio_file)