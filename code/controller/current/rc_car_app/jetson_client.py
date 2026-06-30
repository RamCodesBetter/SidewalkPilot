"""jetson_client.py — Pi-side client for the Jetson ("Jon") steering server.

Sends the live camera frame to the Jetson and gets back (steering_deg, throttle).
Pairs with code/jetson_inference_server.py. Non-blocking-friendly: infer() returns
None on any network hiccup (and lazily reconnects next call) so the control loop is
never wedged by the Jetson — the runtime can fall back to the local model.

Protocol (TCP):
    Pi  -> Jon : [1B version-len V][V bytes version utf8][4B big-endian len N][N bytes JPEG]
    Jon -> Pi  : 8 bytes = struct '>ff' (steering_deg 0..180, throttle 0..1)

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
            reply = self._recv_exact(8)
            if reply is None:
                raise OSError("short reply")
            steering, throttle = struct.unpack(">ff", reply)
            return float(steering), float(throttle)
        except OSError:
            self.close()          # drop the socket; next infer() reconnects
            return None


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
