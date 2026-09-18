import platform
import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

system_os = platform.system()

# Maintain coordinate state in memory
current_state = {"pan": 0, "tilt": 0, "zoom": 0}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "connected", "os": system_os})

@app.route('/ptz', methods=['POST'])
def ptz():
    p = int(request.args.get('p', 0))
    t = int(request.args.get('t', 0))
    z = int(request.args.get('z', 0))
    
    current_state["pan"] += p
    current_state["tilt"] += t
    current_state["zoom"] += z

    backend = cv2.CAP_DSHOW if system_os == "Windows" else cv2.CAP_AVFOUNDATION
    cam = cv2.VideoCapture(0, backend)
    
    opened = cam.isOpened()
    pan_success = False
    tilt_success = False
    zoom_success = False

    if opened:
        # Read a dummy frame to wake up hardware buffers
        cam.read()
        
        if p: pan_success = cam.set(cv2.CAP_PROP_PAN, current_state["pan"])
        if t: tilt_success = cam.set(cv2.CAP_PROP_TILT, current_state["tilt"])
        if z: zoom_success = cam.set(cv2.CAP_PROP_ZOOM, current_state["zoom"])
        
        cam.release()

    return jsonify({
        "status": "ok",
        "device_opened": opened,
        "pan_applied": pan_success,
        "tilt_applied": tilt_success,
        "zoom_applied": zoom_success,
        "state": current_state
    })

if __name__ == '__main__':
    print(f"PTZ Bridge running on {system_os} at http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001)
