from flask import Flask, request, jsonify, send_from_directory
import os
import tempfile
import yt_dlp
import subprocess
import uuid
from pathlib import Path

app = Flask(__name__)

TEMP_DIR = os.path.join(tempfile.gettempdir(), "roblox_strips")
os.makedirs(TEMP_DIR, exist_ok=True)

CURRENT_VIDEO_CONFIG = None  # in-memory

def slice_video(video_url, video_id):
    video_dir = os.path.join(TEMP_DIR, video_id)
    os.makedirs(video_dir, exist_ok=True)

    output_path = os.path.join(video_dir, "video.mp4")

    # Download using yt-dlp
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestvideo[ext=mp4]+bestaudio/best',
        'quiet': True,
        'merge_output_format': 'mp4',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    # Use ffmpeg to create strip frames
    # Output: strip_000.jpg, strip_001.jpg, etc.
    strip_pattern = os.path.join(video_dir, "strip_%03d.jpg")
    fps = 15
    cmd = [
        "ffmpeg", "-y", "-i", output_path,
        "-vf", f"fps={fps},scale=320:180",
        strip_pattern
    ]
    subprocess.run(cmd, check=True)

    # Count generated strips
    strip_count = len(list(Path(video_dir).glob("strip_*.jpg")))

    return {
        "video_id": video_id,
        "fps": fps,
        "resolution": "320x180",
        "frames_per_strip": 1,
        "strip_count": strip_count
    }

@app.route("/current", methods=["GET", "POST"])
def current():
    global CURRENT_VIDEO_CONFIG

    if request.method == "POST":
        data = request.json
        video_url = data.get("video_url")
        if not video_url:
            return "Missing 'video_url'", 400

        video_id = video_url.split("v=")[-1].split("&")[0]
        config = slice_video(video_url, video_id)
        CURRENT_VIDEO_CONFIG = config
        return jsonify(config)

    elif request.method == "GET":
        if CURRENT_VIDEO_CONFIG:
            return jsonify(CURRENT_VIDEO_CONFIG)
        else:
            return "No video loaded", 404

@app.route("/strips/<video_id>/<filename>")
def serve_strip(video_id, filename):
    video_dir = os.path.join(TEMP_DIR, video_id)
    full_path = os.path.join(video_dir, filename)

    if not os.path.exists(full_path):
        return f"{filename} not found", 404

    return send_from_directory(video_dir, filename)

@app.route("/")
def index():
    return "✅ Roblox Video Server running!"
