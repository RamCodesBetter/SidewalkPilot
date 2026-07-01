"""jetson_client.py — Pi-side client for the Jetson ("Jon") steering server.

Sends the live camera frame to the Jetson and gets back (steering_deg, throttle).
Pairs with code/jetson_inference_server.py. Non-blocking-friendly: infer() returns
None on any network hiccup (and lazily reconnects next call) so the control loop is
never wedged by the Jetson — the runtime can fall back to the local model.

Protocol (TCP):
    Pi  -> Jon : [1B version-len V][V bytes version utf8][4B big-endian len N][N bytes JPEG]
    Jon -> Pi  : 20 bytes = struct '>fffff' (steering_deg 0..180, throttle 0..1,
                 jon_cpu_temp_c, jon_gpu_temp_c, infer_fps)

The version string is the Pi's active model choice (e.g. "3.0b"). Jon hot-swaps to
that model when it changes — so picking a model on the Pi's dashboard model page
switches the model Jon runs, with no separate control message.

Usage in runtime:
    jon = JetsonSteeringClient("192.168.x.x")
    result = jon.infer(frame_bgr, model_version="3.0b")   # (steering, throttle) or None
    if result: steering_deg, throttle = result

Standalone test (from a machine with a test image):
    python3 jetson_client.py --host 192.168.x.x --image frame.jpg
"""

import socket
import struct

try:
    import cv2
except ImportError:
    cv2 = None


class JetsonSteeringClient:
    def __init__(self, host, port=8770, jpeg_quality=80, timeout=0.4):
        self.host = host
        self.port = int(port)
        self.jpeg_quality = int(jpeg_quality)
        self.timeout = float(timeout)
        self.sock = None
        # latest telemetry Jon reports back with each inference (for the dashboard)
        self.jon_cpu_temp_c = 0.0
        self.jon_gpu_temp_c = 0.0
        self.infer_fps = 0.0

    def connect(self):
        self.close()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock = s
            return True
        except OSError:
            self.sock = None
            return False

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def infer(self, frame_bgr, model_version=None):
        """Send one BGR frame (+ desired model version), return (steering_deg, throttle) or None."""
        if cv2 is None:
            return None
        if self.sock is None and not self.connect():
            return None
        ok, jpg = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        if not ok:
            return None
        data = jpg.tobytes()
        vbytes = ("" if model_version is None else str(model_version)).encode("utf-8")[:255]
        try:
            self.sock.sendall(bytes([len(vbytes)]) + vbytes + struct.pack(">I", len(data)) + data)
            # reply: steering, throttle, jon_cpu_temp_c, jon_gpu_temp_c, infer_fps (5x f32)
            reply = self._recv_exact(20)
            if reply is None:
                raise OSError("short reply")
            steering, throttle, jcpu, jgpu, ifps = struct.unpack(">fffff", reply)
            self.jon_cpu_temp_c = float(jcpu)
            self.jon_gpu_temp_c = float(jgpu)
            self.infer_fps = float(ifps)
            return float(steering), float(throttle)
        except OSError:
            self.close()          # drop the socket; next infer() reconnects
            return None

    def poll_status(self) -> bool:
        """Ask Jon for temps + inference rate WITHOUT running inference (sends a
        zero-length frame). Updates jon_cpu_temp_c/jon_gpu_temp_c/infer_fps. Returns
        True on success. Lets the dashboard show Jon's temps even in manual mode."""
        if self.sock is None and not self.connect():
            return False
        try:
            self.sock.sendall(bytes([0]) + struct.pack(">I", 0))  # version-len 0, jpeg-len 0
            reply = self._recv_exact(20)
            if reply is None:
                raise OSError("short reply")
            _s, _t, jcpu, jgpu, ifps = struct.unpack(">fffff", reply)
            self.jon_cpu_temp_c = float(jcpu)
            self.jon_gpu_temp_c = float(jgpu)
            self.infer_fps = float(ifps)
            return True
        except OSError:
            self.close()
            return False


def _main():
    import argparse
    ap = argparse.ArgumentParser(description="Test the Jetson steering client")
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--image", required=True, help="a test JPEG to send")
    args = ap.parse_args()
    if cv2 is None:
        raise SystemExit("opencv-python required")
    frame = cv2.imread(args.image)
    if frame is None:
        raise SystemExit(f"could not read {args.image}")
    jon = JetsonSteeringClient(args.host, args.port)
    result = jon.infer(frame)
    if result is None:
        print("FAILED to reach Jon / no reply")
    else:
        print(f"steering={result[0]:.2f} deg, throttle={result[1]:.3f}")
    jon.close()


if __name__ == "__main__":
    _main()
