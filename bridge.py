import os
import time
import subprocess
import threading
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import cv2

app = Flask(__name__)
CORS(app)

uvcc_lock = threading.Lock()

def run_uvcc(command_args):
    """Executes a uvcc command safely via Linux subprocess."""
    with uvcc_lock:
        try:
            cmd = ["uvcc"] + command_args
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
            return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
        except Exception as e:
            return False, str(e)

def pulse_ptz(pan=0, tilt=0, zoom=0, duration=0.2):
    """Sends relative PTZ pulses and stops movement automatically."""
    try:
        if pan != 0 or tilt != 0:
            run_uvcc(["set", "relative_pan_tilt", str(pan), str(tilt)])
            time.sleep(duration)
            run_uvcc(["set", "relative_pan_tilt", "0", "0"])
        
        if zoom != 0:
            # Logitech UVC Zoom accepts relative steps (+1 / -1)
            run_uvcc(["set", "zoom_relative", str(zoom)])
            time.sleep(duration)
            run_uvcc(["set", "zoom_relative", "0"])
    except Exception as e:
        print(f"[Bridge Error] Pulse failed: {e}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "connected",
        "platform": "Raspberry Pi OS (Linux)",
        "driver": "uvcc (UVC Relative)",
        "timestamp": time.time()
    })

@app.route('/ptz', methods=['POST'])
def ptz_control():
    data = request.json or request.args
    pan = int(data.get('pan', 0))
    tilt = int(data.get('tilt', 0))
    zoom = int(data.get('zoom', 0))
    duration = float(data.get('duration', 0.2))

    threading.Thread(target=pulse_ptz, args=(pan, tilt, zoom, duration)).start()
    return jsonify({"status": "ok", "action": {"pan": pan, "tilt": tilt, "zoom": zoom, "duration": duration}})

@app.route('/ptz/stop', methods=['POST'])
def ptz_stop():
    run_uvcc(["set", "relative_pan_tilt", "0", "0"])
    run_uvcc(["set", "zoom_relative", "0"])
    return jsonify({"status": "stopped"})

def find_working_camera_index():
    """Scans video nodes to find the active camera stream."""
    for idx in [0, 2, 4, 1, 3]:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                print(f"[Bridge] Found working video stream at /dev/video{idx}")
                return idx
    return 0

def generate_mjpeg_stream():
    cam_index = find_working_camera_index()
    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    while True:
        success, frame = cap.read()
        if not success:
            time.sleep(0.1)
            continue
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    cap.release()

@app.route('/video_feed')
def video_feed():
    return Response(generate_mjpeg_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("=========================================")
    print("  Raspberry Pi PTZ Control Server")
    print("  Running at: http://127.0.0.1:5001")
    print("=========================================")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
