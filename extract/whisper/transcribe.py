import sys
import whisper
import numpy as np

model = whisper.load_model("medium")  # upgrade from base for better accuracy

audio_file = sys.argv[1]

result = model.transcribe(
    audio_file,
    task="translate",
    language=None,

    # ── noise filtering ──────────────────────────────────
    no_speech_threshold=0.6,       # ← skip segments that are likely just noise (0.0–1.0, higher = stricter)
    logprob_threshold=-1.0,        # ← discard low-confidence segments
    compression_ratio_threshold=2.4,  # ← discard repetitive/garbled output

    # ── better accuracy ──────────────────────────────────
    condition_on_previous_text=False,  # ← prevents hallucination chaining
    temperature=0.0,               # ← deterministic output, less random guessing
    beam_size=5,                   # ← more careful word selection
    best_of=5,
)

# filter out empty or very short segments
filtered_segments = [
    seg for seg in result["segments"]
    if seg["no_speech_prob"] < 0.6 and len(seg["text"].strip()) > 3
]

transcript = " ".join([seg["text"].strip() for seg in filtered_segments])

print(transcript if transcript else "[No speech detected]")

# save transcript
output_path = audio_file.replace(".webm", ".txt")
with open(output_path, "w") as f:
    f.write(transcript if transcript else "[No speech detected]")

print(f"Transcript saved to: {output_path}")