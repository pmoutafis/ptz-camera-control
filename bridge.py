import platform
import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

system_os = platform.system()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "connected", "os": system_os})

@app.route('/ptz', methods=['POST'])
def ptz():
    p = int(request.args.get('p', 0))
    t = int(request.args.get('t', 0))
    z = int(request.args.get('z', 0))
    
    # Open camera on-demand for command execution
    backend = cv2.CAP_DSHOW if system_os == "Windows" else cv2.CAP_AVFOUNDATION
    cam = cv2.VideoCapture(0, backend)
    
    if p: cam.set(cv2.CAP_PROP_PAN, cam.get(cv2.CAP_PROP_PAN) + p)
    if t: cam.set(cv2.CAP_PROP_TILT, cam.get(cv2.CAP_PROP_TILT) + t)
    if z: cam.set(cv2.CAP_PROP_ZOOM, cam.get(cv2.CAP_PROP_ZOOM) + z)
    
    cam.release()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print(f"PTZ Bridge running on {system_os} at http://localhost:5000")
    app.run(port=5000)
