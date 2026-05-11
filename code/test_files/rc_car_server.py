#!/usr/bin/env python3
import os, cv2, socket, threading, json, time, datetime, subprocess
import RPi.GPIO as GPIO
from picamera2 import Picamera2

# --- CONFIGURATION ---
Z2W_HOST     = "zero2w.local"
SSH_USER     = "Ram"
HOTSPOT_SSID = "RaspberryPi5"
HOTSPOT_PSK  = "rcode@2012"
# Command & Stream ports
CMD_PORT     = 9999
STREAM_PORT  = 8000
# ----------------------

# Bring up hotspot (ensure nm-cli connection exists named 'rpi5_hotspot')
subprocess.run(["nmcli","connection","up","rpi5_hotspot"], check=False)

# GPIO setup
GPIO.setmode(GPIO.BCM)
# Headlights (white) on pin 4
GPIO.setup(4, GPIO.OUT); headlight = GPIO.PWM(4,1000); headlight.start(0)
# Indicators on 17/18
GPIO.setup(17,GPIO.OUT); indL = GPIO.PWM(17,2); indL.start(0)
GPIO.setup(18,GPIO.OUT); indR = GPIO.PWM(18,2); indR.start(0)
# Brake lights on 26
GPIO.setup(26,GPIO.OUT); brakeL = GPIO.PWM(26,1000); brakeL.start(0)
# Horn on 21 (A4, 440Hz)
GPIO.setup(21,GPIO.OUT); horn = GPIO.PWM(21,440); horn.start(0)

# Create photos folder
os.makedirs("/home/Ram/Documents/photos", exist_ok=True)

# Picamera2 init
picam2 = Picamera2()
cfg = picam2.create_preview_configuration(main={"size":(640,480)})
picam2.configure(cfg)
picam2.start()

# Shared control state
state = {
    "steer": 0.0, "throttle": 0.0, "brake": False,
    "lights": False, "indicators": "off", "horn": False
}
speed_mph = 0.0  # TODO: replace with real sensor

def update_gpio():
    headlight.ChangeDutyCycle(100 if state["lights"] else 0)
    brakeL.ChangeDutyCycle(100 if state["brake"] else 0)
    indL.ChangeDutyCycle(100 if state["indicators"]=="left" else 0)
    indR.ChangeDutyCycle(100 if state["indicators"]=="right" else 0)
    horn.ChangeDutyCycle(50 if state["horn"] else 0)

# MJPEG streaming handler
from http.server import BaseHTTPRequestHandler, HTTPServer
class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/stream.mjpg":
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type","multipart/x-mixed-replace; boundary=FRAME")
        self.end_headers()
        try:
            while True:
                frame = picam2.capture_array()
                ret, jpg = cv2.imencode('.jpg', frame)
                if not ret: continue
                self.wfile.write(b"--FRAME\r\n")
                self.send_header("Content-Type","image/jpeg")
                self.send_header("Content-Length",str(len(jpg)))
                self.end_headers()
                self.wfile.write(jpg.tobytes())
                time.sleep(0.05)
        except Exception:
            pass

def video_thread():
    srv = HTTPServer(("", STREAM_PORT), StreamHandler)
    print(f"Streaming on port {STREAM_PORT}")
    srv.serve_forever()

def cmd_thread():
    global speed_mph
    sock = socket.socket(); sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", CMD_PORT)); sock.listen(1)
    print(f"Waiting for Z2W on port {CMD_PORT}…")
    conn, addr = sock.accept()
    print("Z2W connected:", addr)

    # Launch GUI on Z2W via SSH
    subprocess.Popen([
        "ssh", f"{SSH_USER}@{Z2W_HOST}",
        "DISPLAY=:0 python3 /home/Ram/Documents/z2w_gui.py"
    ])

    with conn:
        while True:
            data = conn.recv(4096)
            if not data: break
            cmd = json.loads(data.decode())
            state.update({
                "steer": float(cmd.get("steer",0.0)),
                "throttle": float(cmd.get("throttle",0.0)),
                "brake": bool(cmd.get("brake",False)),
                "lights": bool(cmd.get("lights",False)),
                "indicators": cmd.get("indicators","off"),
                "horn": bool(cmd.get("horn",False))
            })
            if cmd.get("capture",False):
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = f"/home/Ram/Documents/photos/photo_{ts}.jpg"
                frame = picam2.capture_array()
                cv2.imwrite(fn, frame)
                print("Saved", fn)
            update_gpio()
            # TODO: motor/servo control with state["steer"], state["throttle"]
            conn.sendall(json.dumps({"speed":speed_mph}).encode())

if __name__=="__main__":
    # Start threads
    threading.Thread(target=video_thread,daemon=True).start()
    cmd_thread()
    # Cleanup
    picam2.stop()
    for pwm in (headlight, indL, indR, brakeL, horn):
        pwm.stop()
    GPIO.cleanup()
