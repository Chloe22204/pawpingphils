# watcher.py
import time
import sys
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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

def transcribe_and_analyse(audio_path: Path):
    result = model.transcribe(
        str(audio_path),
        task="translate",
        language=None,
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

    # keyword detection
    detection = analyse(transcript, audio_filename=audio_path.name, audio_path=str(audio_path))
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