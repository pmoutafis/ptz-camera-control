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
CAM_INDEX = 0
current_zoom = 100

def init_camera():
    """Scans for the active camera node to survive reboots."""
    global VIDEO_DEV, CAM_INDEX
    print("[Bridge] Scanning for active camera node...")
    for idx in [0, 1, 2, 4]:
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                CAM_INDEX = idx
                VIDEO_DEV = f"/dev/video{idx}"
                print(f"[Bridge] Locked camera to {VIDEO_DEV}")
                return
    print("[Bridge] Warning: No active camera found, defaulting to /dev/video0")

init_camera()

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
        if zoom_dir != 0:
            current_zoom = max(100, min(1000, current_zoom + (zoom_dir * 100)))
            run_v4l2("zoom_absolute", current_zoom)
            
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
    return jsonify({"status": "connected", "node": VIDEO_DEV})

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
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_V4L2)
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
    run_v4l2("pan_speed", 0)
    run_v4l2("tilt_speed", 0)
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
