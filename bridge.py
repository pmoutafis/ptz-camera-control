import platform
import subprocess
import json
import time
import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

system_os = platform.system()

# Cumulative offset tracking from Center (0, 0, 0)
current_state = {"pan": 0, "tilt": 0, "zoom": 0}
current_zoom = 100  # Default 1x zoom (range: 100 - 1000)

def send_uvcc_config(config_dict):
    try:
        json_bytes = json.dumps(config_dict).encode('utf-8')
        subprocess.run(["uvcc", "import"], input=json_bytes, check=True)
    except Exception as e:
        print(f"UVC error: {e}")

def reset_hardware():
    global current_zoom, current_state
    current_state = {"pan": 0, "tilt": 0, "zoom": 0}
    current_zoom = 100
    
    if system_os == "Darwin":
        send_uvcc_config({"pantilt_reset": 1})
        send_uvcc_config({"relative_pan_tilt": [0, 0, 0, 0]})
        send_uvcc_config({"absolute_zoom": 100})
    else:
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if cam.isOpened():
            cam.set(cv2.CAP_PROP_PAN, 0)
            cam.set(cv2.CAP_PROP_TILT, 0)
            cam.set(cv2.CAP_PROP_ZOOM, 100)
            cam.release()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "connected", "os": system_os, "state": current_state})

@app.route('/reset', methods=['POST'])
def reset():
    reset_hardware()
    return jsonify({"status": "ok", "state": current_state})

@app.route('/ptz', methods=['POST'])
def ptz():
    global current_zoom
    p = int(request.args.get('p', 0))
    t = int(request.args.get('t', 0))
    z = int(request.args.get('z', 0))
    
    if request.args.get('reset') == 'true':
        reset_hardware()
        return jsonify({"status": "ok", "state": current_state})

    if system_os == "Darwin":
        pan_action = 1 if p > 0 else (-1 if p < 0 else 0)
        pan_speed = 1 if p != 0 else 0
        
        tilt_action = 1 if t > 0 else (-1 if t < 0 else 0)
        tilt_speed = 1 if t != 0 else 0
        
        if p != 0 or t != 0:
            # 120ms movement pulse followed by stop command
            send_uvcc_config({
                "relative_pan_tilt": [pan_action, pan_speed, tilt_action, tilt_speed]
            })
            time.sleep(0.12)
            send_uvcc_config({
                "relative_pan_tilt": [0, 0, 0, 0]
            })
            
            current_state["pan"] += (1 if p > 0 else (-1 if p < 0 else 0))
            current_state["tilt"] += (1 if t > 0 else (-1 if t < 0 else 0))
        
        if z != 0:
            current_zoom = max(100, min(1000, current_zoom + (z * 25)))
            send_uvcc_config({"absolute_zoom": current_zoom})
            current_state["zoom"] = (current_zoom - 100) // 25

    else:
        current_state["pan"] += p
        current_state["tilt"] += t
        current_state["zoom"] += z
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if cam.isOpened():
            if p: cam.set(cv2.CAP_PROP_PAN, current_state["pan"])
            if t: cam.set(cv2.CAP_PROP_TILT, current_state["tilt"])
            if z: cam.set(cv2.CAP_PROP_ZOOM, current_state["zoom"])
            cam.release()

    return jsonify({"status": "ok", "state": current_state})

if __name__ == '__main__':
    try:
        reset_hardware()
    except Exception:
        pass
    print(f"PTZ Bridge running on {system_os} at http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001)
