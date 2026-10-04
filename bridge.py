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
    """Executes uvcc commands with minimal overhead."""
    with uvcc_lock:
        try:
            cmd = ["uvcc"] + command_args
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
            return result.returncode == 0
        except Exception as e:
            print(f"[Bridge Error] uvcc failed: {e}")
            return False

def pulse_ptz(pan=0, tilt=0, zoom=0, duration=0.2):
    """Sends speed vectors and halts movement after the specified duration."""
    try:
        if pan != 0 or tilt != 0:
            # Increase tilt magnitude to 2 to ensure motor friction threshold is passed
            t_val = tilt * 2 if abs(tilt) == 1 else tilt
            run_uvcc(["set", "relative_pan_tilt", str(pan), str(t_val)])
            time.sleep(duration)
            run_uvcc(["set", "relative_pan_tilt", "0", "0"])
        
        if zoom != 0:
            run_uvcc(["set", "zoom_relative", str(zoom)])
            time.sleep(duration)
            run_uvcc(["set", "zoom_relative", "0"])
    except Exception as e:
        print(f"[Bridge Error] Pulse failed: {e}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "connected", "platform": "Raspberry Pi OS"})

@app.route('/ptz', methods=['POST'])
def ptz_control():
    data = request.json or request.args
    pan = int(data.get('pan', 0))
    tilt = int(data.get('tilt', 0))
    zoom = int(data.get('zoom', 0))
    duration = float(data.get('duration', 0.2))

    threading.Thread(target=pulse_ptz, args=(pan, tilt, zoom, duration), daemon=True).start()
    return jsonify({"status": "ok"})

@app.route('/ptz/stop', methods=['POST'])
def ptz_stop():
    threading.Thread(target=lambda: (
        run_uvcc(["set", "relative_pan_tilt", "0", "0"]),
        run_uvcc(["set", "zoom_relative", "0"])
    ), daemon=True).start()
    return jsonify({"status": "stopped"})

def generate_mjpeg_stream():
    """Forces MJPG format on video nodes to fix black video feed on Raspberry Pi."""
    cam_index = 0
    for idx in [0, 1, 2, 4]:
        cap_test = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if cap_test.isOpened():
            cap_test.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            ret, frame = cap_test.read()
            cap_test.release()
            if ret and frame is not None:
                cam_index = idx
                break

    cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
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
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
