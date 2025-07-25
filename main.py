import os
import subprocess
import json
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

OUTPUT_DIR = "/tmp/runtime"
FRAMES_PER_STRIP = 10
FPS = 15
RESOLUTION = "320x180"

os.makedirs(OUTPUT_DIR, exist_ok=True)

import shutil

@app.route("/debug/binaries")
def debug_binaries():
    return jsonify({
        "yt-dlp": shutil.which("yt-dlp"),
        "ffmpeg": shutil.which("ffmpeg")
    })

@app.route("/admin")
def admin_panel():
    return render_template("admin.html")

def extract_video_id(url):
    try:
        if "youtube.com" in url:
            return parse_qs(urlparse(url).query).get("v", [""])[0]
        elif "youtu.be" in url:
            return urlparse(url).path.strip("/")
    except:
        pass
    return "unknown"

def download_youtube_video(video_url, video_id):
    output_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")

    command = [
        "yt-dlp",
        "--verbose",
        "-f", "mp4",
        "-o", output_path,
        video_url
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    print("yt-dlp STDOUT:", result.stdout)
    print("yt-dlp STDERR:", result.stderr)
    result.check_returncode()  

    return output_path



def generate_strips(video_path, video_id):
    strip_dir = os.path.join(OUTPUT_DIR, "strips", video_id)
    os.makedirs(strip_dir, exist_ok=True)

    command = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps={FPS},scale={RESOLUTION},tile={FRAMES_PER_STRIP}x1",
        f"{strip_dir}/strip_%03d.jpg"
    ]
    subprocess.run(command, check=True)

    strip_files = sorted(f for f in os.listdir(strip_dir) if f.endswith(".jpg"))
    return strip_dir, len(strip_files)

@app.route("/process", methods=["POST"])
def process_video():
    data = request.json
    video_url = data.get("url")
    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    video_id = extract_video_id(video_url)
    if not video_id or video_id == "unknown":
        return jsonify({"error": "Invalid YouTube URL"}), 400

    try:
        video_path = download_youtube_video(video_url, video_id)
        strip_dir, strip_count = generate_strips(video_path, video_id)

        config = {
            "video_id": video_id,
            "strip_count": strip_count,
            "frames_per_strip": FRAMES_PER_STRIP,
            "fps": FPS,
            "resolution": RESOLUTION,
            "base_url": f"/strips/{video_id}/strip_{{index}}.jpg"
        }

        with open(os.path.join(OUTPUT_DIR, "current.json"), "w") as f:
            json.dump(config, f)

        return jsonify(config)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Processing failed: {e}"}), 500

@app.route("/strips/<video_id>/<filename>")
def serve_strip(video_id, filename):
    folder = os.path.join(OUTPUT_DIR, "strips", video_id)
    full_path = os.path.join(folder, filename)
    if not os.path.exists(full_path):
        return jsonify({"error": "File not found", "folder_contents": os.listdir(folder) if os.path.exists(folder) else None, "path_checked": full_path}), 404
    return send_from_directory(folder, filename)

@app.route("/current", methods=["GET", "POST"])
def current():
    config_path = os.path.join(OUTPUT_DIR, "current.json")

    if request.method == "POST":
        data = request.get_json()
        with open(config_path, "w") as f:
            json.dump(data, f)
        return jsonify({"status": "ok"})

    elif request.method == "GET":
        try:
            with open(config_path, "r") as f:
                return jsonify(json.load(f))
        except FileNotFoundError:
            return jsonify({"error": "No current video"}), 404

@app.route("/")
def index():
    return "✅ Server is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
