import time
import subprocess
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_FOLDER      = Path("recordings")
TRANSCRIBE_SCRIPT = Path("extract/whisper/transcribe.py")

class AlertHandler(FileSystemEventHandler):
    def on_created(self, event):
        path = Path(event.src_path)
        if path.name.startswith("PAB_Alert_") and path.suffix == ".webm":
            print(f"\n🔴 New alert: {path.name}")
            print("⏳ Transcribing...")
            time.sleep(1)
            subprocess.run([sys.executable, str(TRANSCRIBE_SCRIPT), str(path)])
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