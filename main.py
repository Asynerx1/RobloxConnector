import os
import subprocess
import json
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

OUTPUT_DIR = "/tmp/runtime"
FRAMES_PER_STRIP = 1
FPS = 15
RESOLUTION = "320x180"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
        "-f", "mp4",
        "-o", output_path,
        video_url
    ]
    subprocess.run(command, check=True)
    return output_path

def generate_strips(video_path, video_id):
    strip_dir = os.path.join(OUTPUT_DIR, "strips", video_id)
    os.makedirs(strip_dir, exist_ok=True)
    output_pattern = os.path.join(strip_dir, "strip_%03d.jpg")
    command = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps={FPS},scale={RESOLUTION}",
        output_pattern
    ]
    subprocess.run(command, check=True)
    return strip_dir, len(os.listdir(strip_dir))

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if request.method == "POST":
        video_url = request.form.get("url")
        if not video_url:
            return "No URL provided", 400
        video_id = extract_video_id(video_url)
        try:
            video_path = download_youtube_video(video_url, video_id)
            _, strip_count = generate_strips(video_path, video_id)
            config = {
                "video_id": video_id,
                "strip_count": strip_count,
                "frames_per_strip": FRAMES_PER_STRIP,
                "fps": FPS,
                "resolution": RESOLUTION
            }
            with open(os.path.join(OUTPUT_DIR, "current.json"), "w") as f:
                json.dump(config, f)
            return redirect("/admin")
        except subprocess.CalledProcessError as e:
            return f"Processing failed: {e}", 500

    # GET method
    return '''
        <form method="post">
            <input name="url" placeholder="YouTube URL">
            <button type="submit">Process</button>
        </form>
    '''

@app.route("/strips/<video_id>/<filename>")
def serve_strip(video_id, filename):
    path = os.path.join(OUTPUT_DIR, "strips", video_id)
    full_path = os.path.join(path, filename)
    if not os.path.exists(full_path):
        return jsonify({
            "error": "File not found",
            "folder_contents": os.listdir(path) if os.path.exists(path) else None,
            "path_checked": full_path
        }), 404
    return send_from_directory(path, filename)

@app.route("/current", methods=["GET"])
def current():
    config_path = os.path.join(OUTPUT_DIR, "current.json")
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
