import os
import json
import glob
from flask import Flask, request, jsonify, session, render_template, send_from_directory
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "pab_secret_key_2026"

PROFILE_PATH  = Path("user_profile.json")
UPLOAD_FOLDER = Path("recordings")
UPLOAD_FOLDER.mkdir(exist_ok=True)

def load_users() -> list:
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["users"]

def find_user(user_id: str) -> dict:
    for user in load_users():
        if user["id"] == user_id:
            return user
    return {}

# ── parse a risk report .txt into a structured dict ──────────
def parse_risk_report(report_path: Path) -> dict | None:
    try:
        text = report_path.read_text(encoding="utf-8")
        data = {}

        # extract fields
        for line in text.splitlines():
            if line.strip().startswith("Priority"):
                raw = line.split(":", 1)[-1].strip()
                if "CRITICAL" in raw:   data["urgency"] = "HIGH"
                elif "HIGH" in raw:     data["urgency"] = "HIGH"
                elif "MEDIUM" in raw:   data["urgency"] = "MODERATE"
                elif "LOW" in raw:      data["urgency"] = "LOW"
                else:                   data["urgency"] = "LOW"
                data["priority_raw"] = raw
            elif line.strip().startswith("Timestamp"):
                data["timestamp"] = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("File"):
                data["audioFile"] = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("Name"):
                data["name"] = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("Age"):
                try: data["age"] = int(line.split(":", 1)[-1].strip())
                except: data["age"] = 0
            elif line.strip().startswith("Address"):
                data["address"] = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("Contact"):
                data["contact"] = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("Emergency Contact"):
                data["emergency_contact"] = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("Medical History"):
                data["conditions"] = [c.strip() for c in line.split(":", 1)[-1].split(",")]
            elif line.strip().startswith("CRITICAL :"):
                data["keywords_critical"] = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("HIGH :"):
                data["keywords_high"] = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("MEDIUM :"):
                data["keywords_medium"] = line.split(":", 1)[-1].strip()

        # extract transcript block
        if "TRANSCRIPT" in text and "KEYWORDS" in text:
            transcript_block = text.split("TRANSCRIPT")[1].split("KEYWORDS")[0]
            lines = [l.strip() for l in transcript_block.splitlines() if l.strip() and "---" not in l]
            data["transcript"] = " ".join(lines)

        # build keywords summary
        kw_parts = []
        if data.get("keywords_critical"): kw_parts.append(f"🔴 {data['keywords_critical']}")
        if data.get("keywords_high"):     kw_parts.append(f"🟠 {data['keywords_high']}")
        if data.get("keywords_medium"):   kw_parts.append(f"🟡 {data['keywords_medium']}")
        data["keywords_summary"] = " | ".join(kw_parts) if kw_parts else "None detected"

        # generate a stable case ID from filename
        stem = report_path.stem.replace("_risk_report", "")
        data["id"] = stem[-8:].upper()
        status_path = report_path.with_suffix(".status")
        if status_path.exists():
            data["status"] = status_path.read_text(encoding="utf-8").strip() or "pending"
        else:
            data["status"] = "pending"
        data["report_file"] = str(report_path)

        # parse time display
        ts = data.get("timestamp", "")
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            data["time"] = dt.strftime("%I:%M %p")
            data["elapsed_seconds"] = int((datetime.now() - dt).total_seconds())
        except:
            data["time"] = ts
            data["elapsed_seconds"] = 0

        return data if data.get("name") else None

    except Exception as e:
        print(f"Error parsing {report_path}: {e}")
        return None

# ── API: get all alerts from risk reports ────────────────────
@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    reports = sorted(UPLOAD_FOLDER.glob("*_risk_report.txt"), reverse=True)
    alerts = []
    for r in reports:
        parsed = parse_risk_report(r)
        if parsed:
            alerts.append(parsed)
    return jsonify(alerts)

# ── API: update alert status ─────────────────────────────────
@app.route("/api/alerts/status", methods=["POST"])
def update_status():
    data = request.json
    report_file = data.get("report_file")
    new_status  = data.get("status")
    # store status in a sidecar .status file
    status_path = Path(report_file).with_suffix(".status")
    status_path.write_text(new_status)
    return jsonify({"success": True})

# ── serve responder dashboard ────────────────────────────────
@app.route("/responder")
def responder():
    return render_template("responder.html")

# ── existing routes unchanged below ─────────────────────────
@app.route("/")
def index():
    return render_template("pab-emergency.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    name     = data.get("name", "").strip().lower()
    password = data.get("password", "").strip()
    for user in load_users():
        if user["name"].lower() == name and user["password"] == password:
            session["user_id"] = user["id"]
            return jsonify({"success": True, "name": user["name"], "id": user["id"]})
    return jsonify({"success": False, "message": "Name or password incorrect"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/profile", methods=["GET"])
def get_profile():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    user = find_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({k: v for k, v in user.items() if k != "password"})

@app.route("/api/upload", methods=["POST"])
def upload_audio():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "No audio file received"}), 400
    filename  = f"PAB_Alert_{user_id}_{audio.filename}"
    save_path = UPLOAD_FOLDER / filename
    audio.save(save_path)
    meta_path = save_path.with_suffix(".meta.json")
    user = find_user(user_id)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in user.items() if k != "password"}, f, indent=2)
    return jsonify({"success": True, "file": filename})

if __name__ == "__main__":
    app.run(debug=True, port=8080)
