import platform
import subprocess
import json
import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

system_os = platform.system()
current_zoom = 100

def send_uvcc_config(config_dict):
    json_bytes = json.dumps(config_dict).encode('utf-8')
    subprocess.run(["uvcc", "import"], input=json_bytes, check=True)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "connected", "os": system_os})

@app.route('/ptz', methods=['POST'])
def ptz():
    global current_zoom
    p = int(request.args.get('p', 0))
    t = int(request.args.get('t', 0))
    z = int(request.args.get('z', 0))
    
    if system_os == "Darwin":
        # UVC signed mapping: 1 = Right/Up, -1 = Left/Down, 0 = Stop
        pan_action = 1 if p > 0 else (-1 if p < 0 else 0)
        pan_speed = 1 if p != 0 else 0
        
        tilt_action = 1 if t > 0 else (-1 if t < 0 else 0)
        tilt_speed = 1 if t != 0 else 0
        
        if p != 0 or t != 0:
            send_uvcc_config({
                "relative_pan_tilt": [pan_action, pan_speed, tilt_action, tilt_speed]
            })
        
        if z != 0:
            current_zoom = max(100, min(1000, current_zoom + (z * 50)))
            send_uvcc_config({
                "absolute_zoom": current_zoom
            })
    else:
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if cam.isOpened():
            if p: cam.set(cv2.CAP_PROP_PAN, cam.get(cv2.CAP_PROP_PAN) + p)
            if t: cam.set(cv2.CAP_PROP_TILT, cam.get(cv2.CAP_PROP_TILT) + t)
            if z: cam.set(cv2.CAP_PROP_ZOOM, cam.get(cv2.CAP_PROP_ZOOM) + z)
            cam.release()

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print(f"PTZ Bridge running on {system_os} at http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001)
