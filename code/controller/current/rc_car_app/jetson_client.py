"""Pi-side clients for the Jetson ("Jon") steering server.

Sends the live camera frame to the Jetson and gets back (steering_deg, throttle).
The low-level client is synchronous. Production runtime wraps it in
``AsyncJetsonSteeringClient`` so connect, JPEG encode, send, receive, and status polls
never block controller events or hardware writes.

Protocol (TCP):
    Pi  -> Jon : [1B version-len V][V bytes version utf8][4B big-endian len N][N bytes JPEG]
    Jon -> Pi  : 60 bytes = struct '>15f' (steering_deg, throttle, telemetry,
                 and nine steering-bucket probabilities)

The version string is the Pi's active model choice (e.g. "3.0b"). Jon hot-swaps to
that model when it changes — so picking a model on the Pi's dashboard model page
switches the model Jon runs, with no separate control message.

Usage in runtime:
    jon = AsyncJetsonSteeringClient("10.42.0.2")
    jon.submit(frame_bgr, model_version="3.4")
    sample = jon.get_latest_sample(model_version="3.4")
    if sample: steering_deg, throttle = sample["result"]

Standalone test (from a machine with a test image):
    python3 jetson_client.py --host 192.168.x.x --image frame.jpg
"""

import socket
import struct
import threading
import time

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
        self.infer_ms = 0.0
        self.last_jpeg = None       # exact JPEG bytes of the frame last sent to Jon
                                    # (interruption_recorder.py records these verbatim)
        self.bucket_probs = [0.0] * 9   # 9 steering-bucket softmax probs from Jon's last inference

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
            self.last_jpeg = data           # exact bytes sent to Jon -> interruption recorder buffers these
            # reply: steering, throttle, jcpu, jgpu, infer_fps, infer_ms + 9 bucket probs (15x f32)
            reply = self._recv_exact(60)
            if reply is None:
                raise OSError("short reply")
            v = struct.unpack(">15f", reply)
            steering, throttle, jcpu, jgpu, ifps, ims = v[0:6]
            self.jon_cpu_temp_c = float(jcpu)
            self.jon_gpu_temp_c = float(jgpu)
            self.infer_fps = float(ifps)
            self.infer_ms = float(ims)
            self.bucket_probs = [float(p) for p in v[6:15]]
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
            reply = self._recv_exact(60)
            if reply is None:
                raise OSError("short reply")
            _s, _t, jcpu, jgpu, ifps, ims = struct.unpack(">15f", reply)[0:6]
            self.jon_cpu_temp_c = float(jcpu)
            self.jon_gpu_temp_c = float(jgpu)
            self.infer_fps = float(ifps)
            self.infer_ms = float(ims)
            return True
        except OSError:
            self.close()
            return False


class AsyncJetsonSteeringClient:
    """Latest-frame asynchronous wrapper around :class:`JetsonSteeringClient`.

    ``submit`` and ``get_latest_sample`` only acquire an in-process lock. The worker
    owns the TCP client and discards superseded frame requests, preventing a backlog
    when camera FPS is higher than inference FPS. While no frame is pending, the same
    worker polls Jon telemetry; a powered-off Jon can therefore consume its complete
    socket timeout without pausing the car's control loop.
    """

    def __init__(
        self,
        host,
        port=8770,
        jpeg_quality=80,
        timeout=0.4,
        status_interval_sec=1.0,
        client=None,
    ):
        self.client = client or JetsonSteeringClient(
            host,
            port=port,
            jpeg_quality=jpeg_quality,
            timeout=timeout,
        )
        self.status_interval_sec = max(0.1, float(status_interval_sec))
        self._condition = threading.Condition()
        self._running = True
        self._request_sequence = 0
        self._processed_sequence = 0
        self._latest_request = None
        self._latest_result = None
        self._latest_result_sequence = 0
        self._latest_result_model = ""
        self._latest_result_time = 0.0
        self.jon_cpu_temp_c = 0.0
        self.jon_gpu_temp_c = 0.0
        self.infer_fps = 0.0
        self.infer_ms = 0.0
        self.last_jpeg = None
        self.bucket_probs = [0.0] * 9
        self._thread = threading.Thread(
            target=self._run,
            name="sidewalkpilot-jetson-client",
            daemon=True,
        )
        self._thread.start()

    def submit(self, frame_bgr, model_version=None) -> int:
        """Replace any pending frame and return immediately with its sequence ID."""
        if frame_bgr is None:
            return 0
        with self._condition:
            if not self._running:
                return 0
            self._request_sequence += 1
            sequence = self._request_sequence
            self._latest_request = (sequence, frame_bgr, str(model_version or ""))
            self._condition.notify()
            return sequence

    def get_latest_sample(self, model_version=None, max_age_sec=0.25):
        """Return a fresh cached result dict, or ``None`` without doing network I/O."""
        expected_model = str(model_version or "")
        now = time.monotonic()
        with self._condition:
            if self._latest_result is None:
                return None
            if expected_model and self._latest_result_model != expected_model:
                return None
            if now - self._latest_result_time > max(0.0, float(max_age_sec)):
                return None
            return {
                "sequence": self._latest_result_sequence,
                "model_version": self._latest_result_model,
                "result": tuple(self._latest_result),
                "age_sec": max(0.0, now - self._latest_result_time),
            }

    def _copy_client_state(self):
        with self._condition:
            self.jon_cpu_temp_c = float(getattr(self.client, "jon_cpu_temp_c", 0.0))
            self.jon_gpu_temp_c = float(getattr(self.client, "jon_gpu_temp_c", 0.0))
            self.infer_fps = float(getattr(self.client, "infer_fps", 0.0))
            self.infer_ms = float(getattr(self.client, "infer_ms", 0.0))
            self.last_jpeg = getattr(self.client, "last_jpeg", None)
            probs = list(getattr(self.client, "bucket_probs", [0.0] * 9))
            self.bucket_probs = probs[:9] + [0.0] * max(0, 9 - len(probs))

    def _run(self):
        next_status_poll = time.monotonic() + self.status_interval_sec
        while True:
            request = None
            with self._condition:
                while self._running:
                    if (
                        self._latest_request is not None
                        and self._request_sequence > self._processed_sequence
                    ):
                        request = self._latest_request
                        break
                    wait_sec = max(0.0, next_status_poll - time.monotonic())
                    if wait_sec <= 0.0:
                        break
                    self._condition.wait(timeout=wait_sec)
                if not self._running:
                    break

            if request is not None:
                sequence, frame_bgr, model_version = request
                result = self.client.infer(frame_bgr, model_version=model_version)
                completed_at = time.monotonic()
                self._copy_client_state()
                with self._condition:
                    self._processed_sequence = max(self._processed_sequence, sequence)
                    self._latest_result = result
                    self._latest_result_sequence = sequence
                    self._latest_result_model = model_version
                    self._latest_result_time = completed_at
                # A status-only request resets Series 4 temporal history on the
                # Jetson. Keep postponing it while inference frames are active;
                # manual/idle mode still gets a poll after one full idle interval.
                next_status_poll = completed_at + self.status_interval_sec
                continue

            self.client.poll_status()
            self._copy_client_state()
            next_status_poll = time.monotonic() + self.status_interval_sec

    def close(self):
        with self._condition:
            self._running = False
            self._condition.notify_all()
        self.client.close()
        self._thread.join(timeout=max(1.0, float(getattr(self.client, "timeout", 0.4)) + 0.5))
        self.client.close()


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
