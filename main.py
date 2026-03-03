from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp, os, json, cv2, uuid
from PIL import Image
import numpy as np

app = Flask(__name__)
CORS(app)

VIDEO_DIR = "videos"
FRAME_DIR = "frames"
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(FRAME_DIR, exist_ok=True)

latest_pixel_frame = None  # Unified frame storage for both JSON + PNG uploads

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    video_id = str(uuid.uuid4())
    video_path = os.path.join(VIDEO_DIR, f"{video_id}.mp4")

    try:
        with yt_dlp.YoutubeDL({
            "format": "mp4",
            "quiet": True,
            "outtmpl": video_path
        }) as ydl:
            ydl.download([url])
    except Exception as e:
        return jsonify({"error": f"Download failed: {e}"}), 500

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    max_frames = 300

    width, height = 150, 100
    frames = []
    frame_idx = 0

    while frame_idx < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % int(max(fps / 15, 1)) == 0:
            resized = cv2.resize(frame, (width, height))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            frame_data = rgb.tolist()

            json_path = os.path.join(FRAME_DIR, f"{video_id}_frame_{len(frames):03}.json")
            with open(json_path, "w") as f:
                json.dump(frame_data, f)

            frames.append(f"/frame/{video_id}/{len(frames):03}")

        frame_idx += 1

    cap.release()

    return jsonify({
        "video_id": video_id,
        "fps": 15,
        "frame_count": len(frames),
        "width": width,
        "height": height,
        "frame_urls": frames
    })

@app.route("/frame/<video_id>/<int:frame_index>")
def get_frame(video_id, frame_index):
    frame_file = os.path.join(FRAME_DIR, f"{video_id}_frame_{frame_index:03d}.json")
    
    if not os.path.exists(frame_file):
        return jsonify({"error": "Frame not found"}), 404

    with open(frame_file, "r") as f:
        frame_data = json.load(f)

    os.remove(frame_file)
    return jsonify(frame_data)

@app.route("/upload_screenshare", methods=["POST"])
def upload_screenshare():
    global latest_pixel_frame
    frame = request.get_json()
    if not frame:
        return jsonify({"error": "No frame provided"}), 400

    latest_pixel_frame = frame
    return jsonify({"status": "ok"})

@app.route("/upload_screenshare_file", methods=["POST"])
def upload_screenshare_file():
    global latest_pixel_frame

    if 'frame' not in request.files:
        return "Missing frame file", 400

    try:
        file = request.files['frame']
        img = Image.open(file).convert("RGB")
        arr = np.array(img)
        latest_pixel_frame = arr.tolist()
        return "OK", 200

    except Exception as e:
        return f"Error: {e}", 500

@app.route("/screenshare_frame")
def get_screenshare_frame():
    if latest_pixel_frame is None:
        return jsonify({"error": "No frame available"}), 404
    return jsonify(latest_pixel_frame)

@app.route("/")
def root():
    return "✅ Video Pixel Server Active"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=24195)
