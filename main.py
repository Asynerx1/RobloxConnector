import os
import subprocess
import json 
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)


OUTPUT_DIR = "runtime"  
FRAMES_PER_STRIP = 10
FPS = 15
RESOLUTION = "320x180"


os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route("/admin")
def admin_panel():
    return render_template("admin.html")

def download_youtube_video(video_url, video_id):
    output_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")
    command = [
        "yt-dlp",
        "-f", "mp4",
        "-o", output_path,
        video_url
    ]
    subprocess.run(command, check=True)
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

    video_id = secure_filename(video_url)[-10:]
    try:
        video_path = download_youtube_video(video_url, video_id)
        strip_dir, strip_count = generate_strips(video_path, video_id)

        config = {
            "video_id": video_id,
            "strip_count": strip_count,
            "frames_per_strip": FRAMES_PER_STRIP,
            "fps": FPS,
            "resolution": RESOLUTION
        }

       
        with open(os.path.join(OUTPUT_DIR, "current.json"), "w") as f:
            json.dump(config, f)

        return jsonify(config)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Processing failed: {e}"}), 500

@app.route("/strips/<video_id>/<filename>")
def serve_strip(video_id, filename):
    return send_from_directory(os.path.join(OUTPUT_DIR, "strips", video_id), filename)

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
