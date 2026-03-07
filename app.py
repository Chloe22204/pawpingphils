from flask import Flask, request, jsonify, session, render_template
import json
import os
from pathlib import Path

app = Flask(__name__)
app.secret_key = "pab_secret_key_2026"

PROFILE_PATH = Path("user_profile.json")
UPLOAD_FOLDER = Path("recordings")
UPLOAD_FOLDER.mkdir(exist_ok=True)

# ── load all users ────────────────────────────────────────────
def load_users() -> list:
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["users"]

def find_user(user_id: str) -> dict:
    for user in load_users():
        if user["id"] == user_id:
            return user
    return {}

# ── routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("pab-emergency.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    name = data.get("name", "").strip().lower()
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
    safe = {k: v for k, v in user.items() if k != "password"}
    return jsonify(safe)

@app.route("/api/upload", methods=["POST"])
def upload_audio():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "No audio file received"}), 400

    filename = f"PAB_Alert_{user_id}_{audio.filename}"
    save_path = UPLOAD_FOLDER / filename
    audio.save(save_path)

    # save which user triggered this alert alongside the audio
    meta_path = save_path.with_suffix(".meta.json")
    user = find_user(user_id)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in user.items() if k != "password"}, f, indent=2)

    return jsonify({"success": True, "file": filename})

if __name__ == "__main__":
    app.run(debug=True, port=8080)