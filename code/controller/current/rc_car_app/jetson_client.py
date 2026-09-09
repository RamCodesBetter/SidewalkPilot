"""Pi-side clients for the Jetson ("Jon") steering server.

Sends the live camera frame to the Jetson and gets back (steering_deg, throttle).
The low-level client is synchronous. Production runtime wraps it in
``AsyncJetsonSteeringClient`` so connect, JPEG encode, send, receive, and status polls
never block controller events or hardware writes.

Protocol (TCP, v2):
    Pi  -> Jon : [1B 0x80|version-len V][V bytes version utf8]
                 [1B history count H][H big-endian float32 steering targets]
                 [4B big-endian JPEG length N][N bytes JPEG]
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

import math
import socket
import struct
import threading
import time
from collections import deque

try:
    import cv2
except ImportError:
    cv2 = None


def _percentile(values, percentile):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * max(0.0, min(100.0, float(percentile))) / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _latency_stats(values):
    samples = list(values)
    if not samples:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "mean": sum(samples) / len(samples),
        "p50": _percentile(samples, 50.0),
        "p95": _percentile(samples, 95.0),
        "p99": _percentile(samples, 99.0),
    }


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
        self.jpeg_encode_ms = 0.0
        self.socket_round_trip_ms = 0.0
        self.inference_request_ms = 0.0
        self.status_round_trip_ms = 0.0
        self.last_jpeg = None       # exact JPEG bytes of the frame last sent to Jon
                                    # (interruption_recorder.py records these verbatim)
        self.bucket_probs = [0.0] * 9   # 9 steering-bucket softmax probs from Jon's last inference

    def connect(self):
        self.close()
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock = s
            return True
        except OSError:
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
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

    def infer(self, frame_bgr, model_version=None, target_history=None):
        """Send one BGR frame (+ desired model version), return (steering_deg, throttle) or None."""
        if cv2 is None:
            return None
        if self.sock is None and not self.connect():
            return None
        request_started = time.perf_counter()
        encode_started = time.perf_counter()
        ok, jpg = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        self.jpeg_encode_ms = (time.perf_counter() - encode_started) * 1000.0
        if not ok:
            return None
        data = jpg.tobytes()
        vbytes = ("" if model_version is None else str(model_version)).encode("utf-8")[:127]
        try:
            history_values = () if target_history is None else target_history
            history = [float(value) for value in history_values][:255]
            if not all(math.isfinite(value) and 0.0 <= value <= 180.0 for value in history):
                raise ValueError("invalid steering history")
            history_payload = struct.pack(f">{len(history)}f", *history) if history else b""
            socket_started = time.perf_counter()
            self.sock.sendall(
                bytes([0x80 | len(vbytes)])
                + vbytes
                + bytes([len(history)])
                + history_payload
                + struct.pack(">I", len(data))
                + data
            )
            self.last_jpeg = data           # exact bytes sent to Jon -> interruption recorder buffers these
            # reply: steering, throttle, jcpu, jgpu, infer_fps, infer_ms + 9 bucket probs (15x f32)
            reply = self._recv_exact(60)
            if reply is None:
                raise OSError("short reply")
            v = struct.unpack(">15f", reply)
            if not all(math.isfinite(value) for value in v):
                raise OSError("non-finite inference reply")
            steering, throttle, jcpu, jgpu, ifps, ims = v[0:6]
            if not 0.0 <= float(steering) <= 180.0:
                raise OSError(f"steering reply outside 0..180 degrees: {steering}")
            self.jon_cpu_temp_c = float(jcpu)
            self.jon_gpu_temp_c = float(jgpu)
            self.infer_fps = float(ifps)
            self.infer_ms = float(ims)
            self.bucket_probs = [float(p) for p in v[6:15]]
            self.socket_round_trip_ms = (
                time.perf_counter() - socket_started
            ) * 1000.0
            self.inference_request_ms = (
                time.perf_counter() - request_started
            ) * 1000.0
            return float(steering), float(throttle)
        except (OSError, TypeError, ValueError):
            self.close()          # drop the socket; next infer() reconnects
            return None

    def poll_status(self) -> bool:
        """Ask Jon for temps + inference rate WITHOUT running inference (sends a
        zero-length frame). Updates jon_cpu_temp_c/jon_gpu_temp_c/infer_fps. Returns
        True on success. Lets the dashboard show Jon's temps even in manual mode."""
        if self.sock is None and not self.connect():
            return False
        try:
            # v2, version-len 0, history-count 0, jpeg-len 0
            status_started = time.perf_counter()
            self.sock.sendall(bytes([0x80, 0]) + struct.pack(">I", 0))
            reply = self._recv_exact(60)
            if reply is None:
                raise OSError("short reply")
            values = struct.unpack(">15f", reply)
            if not all(math.isfinite(value) for value in values):
                raise OSError("non-finite status reply")
            _s, _t, jcpu, jgpu, ifps, ims = values[0:6]
            self.jon_cpu_temp_c = float(jcpu)
            self.jon_gpu_temp_c = float(jgpu)
            self.infer_fps = float(ifps)
            self.infer_ms = float(ims)
            self.status_round_trip_ms = (
                time.perf_counter() - status_started
            ) * 1000.0
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
        history_sample_interval_sec=0.1,
        history_result_max_age_sec=0.25,
        latency_window_size=250,
        client=None,
    ):
        self.client = client or JetsonSteeringClient(
            host,
            port=port,
            jpeg_quality=jpeg_quality,
            timeout=timeout,
        )
        self.status_interval_sec = max(0.1, float(status_interval_sec))
        self.history_sample_interval_sec = max(0.0, float(history_sample_interval_sec))
        self.history_result_max_age_sec = max(0.0, float(history_result_max_age_sec))
        self.latency_window_size = max(1, int(latency_window_size))
        self._condition = threading.Condition()
        self._running = True
        self._request_sequence = 0
        self._processed_sequence = 0
        self._latest_request = None
        self._latest_result = None
        self._latest_result_sequence = 0
        self._latest_result_model = ""
        self._latest_result_time = 0.0
        self._latest_result_source_frame_sequence = 0
        self._sequence_generation = 0
        self._latest_result_generation = -1
        self._autonomous_sequence_active = False
        self.jon_cpu_temp_c = 0.0
        self.jon_gpu_temp_c = 0.0
        self.infer_fps = 0.0
        self.infer_ms = 0.0
        self.jpeg_encode_ms = 0.0
        self.socket_round_trip_ms = 0.0
        self.inference_request_ms = 0.0
        self.submit_to_result_ms = 0.0
        self.capture_to_result_ms = 0.0
        self._latency_samples = {
            name: deque(maxlen=self.latency_window_size)
            for name in (
                "jpeg_encode_ms",
                "socket_round_trip_ms",
                "server_infer_ms",
                "inference_request_ms",
                "capture_to_result_ms",
            )
        }
        self.last_jpeg = None
        self.bucket_probs = [0.0] * 9
        self._target_history = [90.0, 90.0, 90.0]
        self._target_timeline = [(float("-inf"), 90.0)] * 3
        self._last_history_sample_time = 0.0
        self._thread = threading.Thread(
            target=self._run,
            name="sidewalkpilot-jetson-client",
            daemon=True,
        )
        self._thread.start()

    def submit(
        self,
        frame_bgr,
        model_version=None,
        *,
        source_frame_sequence=None,
        captured_at=None,
    ) -> int:
        """Queue one frame with the steering history present at camera capture."""
        if frame_bgr is None:
            return 0
        with self._condition:
            if not self._running:
                return 0
            submitted_at = time.monotonic()
            frame_captured_at = submitted_at if captured_at is None else float(captured_at)
            if (
                not math.isfinite(frame_captured_at)
                or frame_captured_at <= 0.0
                or frame_captured_at > submitted_at
            ):
                frame_captured_at = submitted_at
            self._request_sequence += 1
            sequence = self._request_sequence
            target_history = self._history_at_locked(frame_captured_at)
            self._latest_request = (
                sequence,
                self._sequence_generation,
                submitted_at,
                frame_captured_at,
                int(source_frame_sequence or 0),
                frame_bgr,
                str(model_version or ""),
                target_history,
            )
            self._condition.notify()
            return sequence

    def _history_at_locked(self, sampled_at) -> tuple[float, float, float]:
        values = [
            value
            for timestamp, value in self._target_timeline
            if timestamp <= float(sampled_at) + 1e-9
        ][-3:]
        if len(values) < 3:
            values = ([90.0] * (3 - len(values))) + values
        return tuple(values)

    def _record_target_locked(self, steering_deg, sampled_at, *, force=False) -> bool:
        value = float(steering_deg)
        if not math.isfinite(value):
            return False
        value = max(0.0, min(180.0, value))
        sampled_at = float(sampled_at)
        elapsed = sampled_at - self._last_history_sample_time
        if (
            not force
            and self._last_history_sample_time
            and elapsed + 1e-9 < self.history_sample_interval_sec
        ):
            return False
        if (
            force
            and self._last_history_sample_time
            and elapsed + 1e-9 < self.history_sample_interval_sec
            and abs(self._target_history[-1] - value) < 1e-6
        ):
            return False
        self._target_history = (self._target_history + [value])[-3:]
        self._target_timeline.append((sampled_at, value))
        self._target_timeline = self._target_timeline[-64:]
        self._last_history_sample_time = sampled_at
        return True

    def observe_manual_steering(self, steering_deg, *, sampled_at=None, force=False) -> None:
        """Sample manual targets at the same 10 Hz cadence used by Series 4 training."""
        now = time.monotonic() if sampled_at is None else float(sampled_at)
        with self._condition:
            if self._autonomous_sequence_active:
                self._autonomous_sequence_active = False
                self._sequence_generation += 1
                self._latest_request = None
                self._latest_result = None
                self._latest_result_sequence = 0
                self._latest_result_model = ""
                self._latest_result_time = 0.0
                self._latest_result_source_frame_sequence = 0
                self._latest_result_generation = -1
            self._record_target_locked(steering_deg, now, force=force)

    def begin_autonomous_sequence(self, steering_deg, *, sampled_at=None) -> None:
        """Prime PC/PCF from manual steering and invalidate every older inference."""
        now = time.monotonic() if sampled_at is None else float(sampled_at)
        with self._condition:
            self._record_target_locked(steering_deg, now, force=True)
            self._autonomous_sequence_active = True
            self._sequence_generation += 1
            self._latest_request = None
            self._latest_result = None
            self._latest_result_sequence = 0
            self._latest_result_model = ""
            self._latest_result_time = 0.0
            self._latest_result_source_frame_sequence = 0
            self._latest_result_generation = -1

    def get_latest_sample(self, model_version=None, max_age_sec=0.25):
        """Return a fresh cached result dict, or ``None`` without doing network I/O."""
        expected_model = str(model_version or "")
        now = time.monotonic()
        with self._condition:
            if self._latest_result is None:
                return None
            if self._latest_result_generation != self._sequence_generation:
                return None
            if expected_model and self._latest_result_model != expected_model:
                return None
            if now - self._latest_result_time > max(0.0, float(max_age_sec)):
                return None
            return {
                "sequence": self._latest_result_sequence,
                "source_frame_sequence": self._latest_result_source_frame_sequence,
                "model_version": self._latest_result_model,
                "result": tuple(self._latest_result),
                "age_sec": max(0.0, now - self._latest_result_time),
                "submit_to_result_ms": self.submit_to_result_ms,
                "capture_to_result_ms": self.capture_to_result_ms,
                "inference_request_ms": self.inference_request_ms,
            }

    def get_latency_summary(self):
        """Return rolling successful-request latency percentiles without network I/O."""
        with self._condition:
            samples = {
                name: tuple(values) for name, values in self._latency_samples.items()
            }
        sample_count = len(samples["capture_to_result_ms"])
        return {
            "sample_count": sample_count,
            "window_size": self.latency_window_size,
            **{name: _latency_stats(values) for name, values in samples.items()},
        }

    def _record_latency_locked(self):
        values = {
            "jpeg_encode_ms": self.jpeg_encode_ms,
            "socket_round_trip_ms": self.socket_round_trip_ms,
            "server_infer_ms": self.infer_ms,
            "inference_request_ms": self.inference_request_ms,
            "capture_to_result_ms": self.capture_to_result_ms,
        }
        for name, value in values.items():
            if math.isfinite(value) and value >= 0.0:
                self._latency_samples[name].append(float(value))

    def _copy_client_state(self):
        with self._condition:
            self.jon_cpu_temp_c = float(getattr(self.client, "jon_cpu_temp_c", 0.0))
            self.jon_gpu_temp_c = float(getattr(self.client, "jon_gpu_temp_c", 0.0))
            self.infer_fps = float(getattr(self.client, "infer_fps", 0.0))
            self.infer_ms = float(getattr(self.client, "infer_ms", 0.0))
            self.jpeg_encode_ms = float(getattr(self.client, "jpeg_encode_ms", 0.0))
            self.socket_round_trip_ms = float(
                getattr(self.client, "socket_round_trip_ms", 0.0)
            )
            self.inference_request_ms = float(
                getattr(self.client, "inference_request_ms", 0.0)
            )
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
                (
                    sequence,
                    generation,
                    submitted_at,
                    captured_at,
                    source_frame_sequence,
                    frame_bgr,
                    model_version,
                    target_history,
                ) = request
                try:
                    result = self.client.infer(
                        frame_bgr,
                        model_version=model_version,
                        target_history=target_history,
                    )
                except Exception as exc:
                    print(f"Jetson inference worker error ignored: {exc}", flush=True)
                    result = None
                completed_at = time.monotonic()
                self._copy_client_state()
                with self._condition:
                    self.submit_to_result_ms = max(
                        0.0, (completed_at - submitted_at) * 1000.0
                    )
                    self.capture_to_result_ms = max(
                        0.0, (completed_at - captured_at) * 1000.0
                    )
                    if result is not None:
                        self._record_latency_locked()
                    self._processed_sequence = max(self._processed_sequence, sequence)
                    if generation == self._sequence_generation:
                        self._latest_result = result
                        self._latest_result_sequence = sequence
                        self._latest_result_source_frame_sequence = source_frame_sequence
                        self._latest_result_model = model_version
                        # Freshness starts at camera capture, not after queueing,
                        # reconnecting, loading a model, or completing inference.
                        self._latest_result_time = captured_at
                        self._latest_result_generation = generation
                    result_age_sec = completed_at - captured_at
                    if (
                        result is not None
                        and generation == self._sequence_generation
                        and result_age_sec <= self.history_result_max_age_sec
                    ):
                        steering = max(0.0, min(180.0, float(result[0])))
                        self._record_target_locked(steering, completed_at)
                # A status-only request resets Series 4 temporal history on the
                # Jetson. Keep postponing it while inference frames are active;
                # manual/idle mode still gets a poll after one full idle interval.
                next_status_poll = completed_at + self.status_interval_sec
                continue

            try:
                self.client.poll_status()
            except Exception as exc:
                print(f"Jetson status worker error ignored: {exc}", flush=True)
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
