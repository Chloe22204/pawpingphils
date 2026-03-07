import time
import subprocess
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── config ──────────────────────────────────────────────
WATCH_FOLDER   = Path.home() / "Downloads"        # where browser saves files
TRANSCRIBE_SCRIPT = Path("extract/whisper/transcribe.py")  # your whisper script
# ────────────────────────────────────────────────────────

class AlertHandler(FileSystemEventHandler):
    def on_created(self, event):
        path = Path(event.src_path)
        if path.name.startswith("PAB_Alert_") and path.suffix == ".webm":
            print(f"\n🔴 New alert detected: {path.name}")
            print("⏳ Transcribing with Whisper...")
            time.sleep(1)  # wait briefly so file finishes writing
            subprocess.run([sys.executable, str(TRANSCRIBE_SCRIPT), str(path)])
            print("✅ Transcription complete!\n")

if __name__ == "__main__":
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