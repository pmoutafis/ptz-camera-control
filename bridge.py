import os
import time
import subprocess
import threading
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import cv2

app = Flask(__name__)
CORS(app)

v4l2_lock = threading.Lock()
VIDEO_DEV = "/dev/video0"
current_zoom = 100  # Camera default zoom_absolute is 100

def run_v4l2(control, value):
    """Executes instant native Linux hardware commands."""
    with v4l2_lock:
        try:
            subprocess.run(["v4l2-ctl", "-d", VIDEO_DEV, "-c", f"{control}={value}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Bridge Error] v4l2-ctl failed: {e}")

def pulse_ptz(pan=0, tilt=0, zoom_dir=0, duration=0.1):
    """Sends native speed vectors and halts exactly after duration."""
    global current_zoom
    try:
        # 1. Handle Absolute Zoom (Min 100, Max 1000)
        if zoom_dir != 0:
            current_zoom = max(100, min(1000, current_zoom + (zoom_dir * 100)))
            run_v4l2("zoom_absolute", current_zoom)
            
        # 2. Handle Relative Pan/Tilt Speed
        if pan != 0 or tilt != 0:
            if pan != 0: run_v4l2("pan_speed", pan)
            if tilt != 0: run_v4l2("tilt_speed", tilt)
            
            time.sleep(duration)
            
            if pan != 0: run_v4l2("pan_speed", 0)
            if tilt != 0: run_v4l2("tilt_speed", 0)
            
    except Exception as e:
        print(f"[Bridge Error] Pulse failed: {e}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "connected", "platform": "Native Linux V4L2"})

@app.route('/ptz', methods=['POST'])
def ptz_control():
    data = request.json or request.args
    pan = int(data.get('pan', 0))
    tilt = int(data.get('tilt', 0))
    zoom = int(data.get('zoom', 0))
    duration = float(data.get('duration', 0.1))

    threading.Thread(target=pulse_ptz, args=(pan, tilt, zoom, duration), daemon=True).start()
    return jsonify({"status": "ok"})

@app.route('/ptz/stop', methods=['POST'])
def ptz_stop():
    run_v4l2("pan_speed", 0)
    run_v4l2("tilt_speed", 0)
    return jsonify({"status": "stopped"})

def generate_mjpeg_stream():
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    while True:
        success, frame = cap.read()
        if not success or frame is None:
            time.sleep(0.03)
            continue
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    cap.release()

@app.route('/video_feed')
def video_feed():
    return Response(generate_mjpeg_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Ensure motors are stopped on startup
    run_v4l2("pan_speed", 0)
    run_v4l2("tilt_speed", 0)
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
