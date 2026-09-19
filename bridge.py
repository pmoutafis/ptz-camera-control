import platform
import subprocess
import json
import time
import threading
import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

system_os = platform.system()
uvc_lock = threading.Lock()

# Recalibrated physical end-stop limits (120ms pulse steps from Center)
MAX_PAN_STEPS = 20
MAX_TILT_STEPS = 12

# Cumulative offset tracking from Center (0, 0, 100)
current_state = {"pan": 0, "tilt": 0, "zoom": 100}

def send_uvcc_config(config_dict):
    """Executes uvcc import safely with non-overlapping process handles."""
    try:
        json_bytes = json.dumps(config_dict).encode('utf-8')
        subprocess.run(["uvcc", "import"], input=json_bytes, check=True, timeout=3)
    except Exception as e:
        print(f"UVC warning: {e}")

def reset_hardware():
    global current_state
    with uvc_lock:
        if system_os == "Darwin":
            # 1. Smooth continuous Pan return
            pan_steps = current_state["pan"]
            if pan_steps != 0:
                direction = -1 if pan_steps > 0 else 1
                sweep_duration = abs(pan_steps) * 0.12
                send_uvcc_config({"relative_pan_tilt": [direction, 1, 0, 0]})
                time.sleep(sweep_duration)
                send_uvcc_config({"relative_pan_tilt": [0, 0, 0, 0]})
                time.sleep(0.1)

            # 2. Smooth continuous Tilt return
            tilt_steps = current_state["tilt"]
            if tilt_steps != 0:
                direction = -1 if tilt_steps > 0 else 1
                sweep_duration = abs(tilt_steps) * 0.12
                send_uvcc_config({"relative_pan_tilt": [0, 0, direction, 1]})
                time.sleep(sweep_duration)
                send_uvcc_config({"relative_pan_tilt": [0, 0, 0, 0]})
                time.sleep(0.1)

            # 3. Reset Optical Zoom to 100 (1x)
            send_uvcc_config({"absolute_zoom": 100})
            time.sleep(0.1)
        else:
            cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if cam.isOpened():
                cam.set(cv2.CAP_PROP_PAN, 0)
                cam.set(cv2.CAP_PROP_TILT, 0)
                cam.set(cv2.CAP_PROP_ZOOM, 100)
                cam.release()

        current_state = {"pan": 0, "tilt": 0, "zoom": 100}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "connected", "os": system_os, "state": current_state})

@app.route('/reset', methods=['POST'])
def reset():
    reset_hardware()
    return jsonify({"status": "ok", "state": current_state})

@app.route('/ptz', methods=['POST'])
def ptz():
    global current_state
    
    if not uvc_lock.acquire(blocking=False):
        return jsonify({"status": "busy", "state": current_state}), 429

    try:
        p = int(request.args.get('p', 0))
        t = int(request.args.get('t', 0))
        z = int(request.args.get('z', 0))

        if system_os == "Darwin":
            # Strict boundary enforcement to prevent over-clicking at physical stops
            if p > 0 and current_state["pan"] >= MAX_PAN_STEPS: p = 0
            if p < 0 and current_state["pan"] <= -MAX_PAN_STEPS: p = 0
            if t > 0 and current_state["tilt"] >= MAX_TILT_STEPS: t = 0
            if t < 0 and current_state["tilt"] <= -MAX_TILT_STEPS: t = 0

            pan_action = 1 if p > 0 else (-1 if p < 0 else 0)
            tilt_action = 1 if t > 0 else (-1 if t < 0 else 0)
            
            if p != 0 or t != 0:
                send_uvcc_config({
                    "relative_pan_tilt": [pan_action, 1 if p != 0 else 0, tilt_action, 1 if t != 0 else 0]
                })
                time.sleep(0.12)
                send_uvcc_config({"relative_pan_tilt": [0, 0, 0, 0]})
                time.sleep(0.05)
                
                if p != 0: current_state["pan"] += pan_action
                if t != 0: current_state["tilt"] += tilt_action
            
            if z != 0:
                new_zoom = max(100, min(1000, current_state["zoom"] + (z * 50)))
                send_uvcc_config({"absolute_zoom": new_zoom})
                current_state["zoom"] = new_zoom

        else:
            current_state["pan"] += p
            current_state["tilt"] += t
            current_state["zoom"] = max(100, min(1000, current_state["zoom"] + (z * 50)))
            cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if cam.isOpened():
                if p: cam.set(cv2.CAP_PROP_PAN, current_state["pan"])
                if t: cam.set(cv2.CAP_PROP_TILT, current_state["tilt"])
                if z: cam.set(cv2.CAP_PROP_ZOOM, current_state["zoom"])
                cam.release()

        return jsonify({"status": "ok", "state": current_state})
    finally:
        uvc_lock.release()

if __name__ == '__main__':
    print(f"PTZ Bridge running on {system_os} at http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001)
