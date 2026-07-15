#!/usr/bin/env python3
"""
jetson_inference_server.py  —  "Jon" (Jetson Orin Nano) steering inference service.

Runs a SidewalkPilot model on the Jetson and answers steering requests from the Pi 5
over TCP. Accepts .onnx, .pt (TorchScript), or .pth (state-dict) — and is generic
across Series 1/2/3/4:

  * Series 1/2 (SteeringAutonomyV2): 1 output, already in DEGREES (90 + scale*tanh).
  * Series 3.0/3.0b (regression):    2 outputs in UNIT controls (steer,throttle in
                                     [-1,1]); decoded steer=90+90*u, throttle=(u+1)/2.
  * Series 3.1+ (hybrid head):       19 outputs = 9 steering-class logits + 9 within-
                                     bucket offsets + 1 throttle; decoded via argmax
                                     bucket + sigmoid(offset) -> degrees.
  * Series 4 PC/CF/PCF:              [batch,horizon,18] outputs. Horizon 0 is the live
                                     steering target; each horizon has 9 class logits
                                     + 9 offsets and no throttle. PC/PCF ONNX models
                                     also take target_history=[previous 3 targets].
  Output shape and ONNX input metadata select the contract automatically. Series 4
  target history is autoregressive on Jon and resets to [90,90,90] on model switches,
  reconnects, and status-only/manual periods.

Preprocessing MATCHES rc_car_app/vision.py exactly:
  BGR -> [optional CLAHE] -> resize(W,H, INTER_AREA) -> /255 -> (x-0.5)/0.5
      -> HWC->CHW -> NCHW float32
Input size W,H comes from the ONNX itself, or from the detected arch for torch
(S1/2 = 200x66, S3 = 320x180), or --width/--height.

Wire protocol (TCP, persistent connection, one round-trip per frame):
    Pi  -> Jon : [1-byte version length V][V bytes UTF-8 model version]
                 [4-byte big-endian JPEG length N][N bytes JPEG]
    Jon -> Pi  : 60 bytes = struct '>15f' (steering, throttle, temperatures,
                 inference timing, and 9 current-horizon bucket probabilities)

Run on the Jetson:
    python3 jetson_inference_server.py --model SidewalkPilot-v3.0b.onnx
    python3 jetson_inference_server.py --model SidewalkPilot-v4.0p.onnx
    python3 jetson_inference_server.py --model SidewalkPilot-v2.4b.pth          # S1/2 state-dict
    python3 jetson_inference_server.py --model model.pt                          # TorchScript

Deps on the Jetson: numpy, opencv-python, and onnxruntime(-gpu) and/or torch
(whichever your model format needs).
"""

import argparse
import re
import socket
import struct
import time
from pathlib import Path

import numpy as np

# code/ai_models (released) + series_3_and_4 (fresh training output) — searched by version
_CODE_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_MODEL_DIRS = [_CODE_DIR / "ai_models", _CODE_DIR / "ai_models_datasets" / "series_3_and_4"]


def _version_key(version):
    """Sort numeric versions first, then a release suffix (3.4 < 3.4b < 4.0a...)."""
    v = str(version).strip().lower()
    match = re.fullmatch(r"(\d+)\.(\d+)([a-z]*)", v)
    if match is None:
        return (-1, -1, "")
    return (int(match.group(1)), int(match.group(2)), match.group(3))


def resolve_model_path(spec, extra_dir=None):
    """Accept a path (.onnx/.pt/.pth), a version like '3.0b'/'2.4', or the keyword
    'highest'/'latest' (greatest available version). Resolves to
    SidewalkPilot-v<version>.{onnx,pt,pth} (onnx preferred) in the model dirs."""
    dirs = ([Path(extra_dir).expanduser()] if extra_dir else []) + _DEFAULT_MODEL_DIRS

    if str(spec).strip().lower() in ("highest", "latest", "newest", "max"):
        found = {}  # version -> first matching path (onnx preferred via ext order)
        for d in dirs:
            for ext in (".onnx", ".pt", ".pth"):
                for cand in sorted(d.glob(f"SidewalkPilot-v*{ext}")):
                    ver = cand.stem[len("SidewalkPilot-v"):]
                    found.setdefault(ver, str(cand))
        if not found:
            raise SystemExit(f"[jon] no SidewalkPilot-v* models in {[str(d) for d in dirs]}")
        best = max(found, key=_version_key)
        print(f"[jon] --model highest -> v{best}", flush=True)
        return found[best]

    p = Path(spec).expanduser()
    if p.suffix.lower() in (".onnx", ".pt", ".pth"):
        if not p.exists():
            raise SystemExit(f"[jon] model file not found: {p}")
        return str(p)
    for d in dirs:
        for ext in (".onnx", ".pt", ".pth"):
            cand = d / f"SidewalkPilot-v{spec}{ext}"
            if cand.exists():
                return str(cand)
    raise SystemExit(f"[jon] model '{spec}' not found: no such file, and no "
                     f"SidewalkPilot-v{spec}.(onnx|pt|pth) in {[str(d) for d in dirs]}")


# Per-model preprocessing policy -- MIRRORS the Pi's vision.py (steering_uses_clahe /
# steering_output_scale_deg). The Pi sends only a version string each frame, so Jon must
# apply the SAME CLAHE + output-scale the model was trained with, not a fixed startup flag.
_CLAHE_VERSIONS = {"2.0", "2.0b"}          # the only HSV-CLAHE-trained models (see vision.py)


def _version_from_path(model_path):
    """'.../SidewalkPilot-v2.0b.onnx' -> '2.0b'. None if the filename isn't a versioned model."""
    stem = Path(model_path).stem
    prefix = "SidewalkPilot-v"
    return stem[len(prefix):] if stem.startswith(prefix) else None


def _preproc_policy_for_version(version):
    """version like '2.0b'/'3.2' -> (use_clahe, steer_scale_deg), mirroring the Pi.
    CLAHE only for 2.0/2.0b; Series-2 output scale = 85, Series-1 = 86 (Series-3 ignores
    scale -- it's decoded by output length)."""
    v = str(version).strip().lower()
    use_clahe = v in _CLAHE_VERSIONS
    steer_scale = 85.0 if v.startswith("2.") else 86.0
    return use_clahe, steer_scale


try:
    import cv2
except ImportError:
    cv2 = None
try:
    import onnxruntime as ort
except ImportError:
    ort = None
try:
    import torch
    import torch.nn as nn
except ImportError:
    torch = None
    nn = None


# --- bundled model archs (so a raw .pth state-dict loads standalone on the Jetson) ---
if torch is not None:
    class SteeringAutonomyV2(nn.Module):  # Series 1/2 — 1 output, degrees
        def __init__(self, output_scale_deg=86.0):
            super().__init__()
            self.output_scale_deg = float(output_scale_deg)
            self.backbone = nn.Sequential(
                nn.Conv2d(3, 24, 5, stride=2), nn.BatchNorm2d(24), nn.ELU(inplace=True),
                nn.Conv2d(24, 36, 5, stride=2), nn.BatchNorm2d(36), nn.ELU(inplace=True),
                nn.Conv2d(36, 48, 5, stride=2), nn.BatchNorm2d(48), nn.ELU(inplace=True),
                nn.Conv2d(48, 64, 3, stride=1), nn.BatchNorm2d(64), nn.ELU(inplace=True),
                nn.Conv2d(64, 64, 3, stride=1), nn.BatchNorm2d(64), nn.ELU(inplace=True),
            )
            self.head = nn.Sequential(
                nn.AdaptiveAvgPool2d((4, 8)), nn.Flatten(),
                nn.Linear(64 * 4 * 8, 256), nn.ELU(inplace=True), nn.Dropout(p=0.10),
                nn.Linear(256, 64), nn.ELU(inplace=True),
                nn.Linear(64, 1), nn.Tanh(),
            )

        def forward(self, x):
            return 90.0 + self.output_scale_deg * self.head(self.backbone(x))

    class SidewalkPilotV3(nn.Module):  # Series 3 — 2 outputs, unit controls
        def __init__(self):
            super().__init__()
            self.backbone = nn.Sequential(
                nn.Conv2d(3, 32, 5, stride=2, padding=2), nn.BatchNorm2d(32), nn.ELU(inplace=True),
                nn.Conv2d(32, 48, 5, stride=2, padding=2), nn.BatchNorm2d(48), nn.ELU(inplace=True),
                nn.Conv2d(48, 64, 5, stride=2, padding=2), nn.BatchNorm2d(64), nn.ELU(inplace=True),
                nn.Conv2d(64, 96, 3, stride=2, padding=1), nn.BatchNorm2d(96), nn.ELU(inplace=True),
                nn.Conv2d(96, 128, 3, stride=1, padding=1), nn.BatchNorm2d(128), nn.ELU(inplace=True),
                nn.Conv2d(128, 160, 3, stride=1, padding=1), nn.BatchNorm2d(160), nn.ELU(inplace=True),
            )
            self.head = nn.Sequential(
                nn.AdaptiveAvgPool2d((6, 10)), nn.Flatten(),
                nn.Linear(160 * 6 * 10, 512), nn.ELU(inplace=True), nn.Dropout(p=0.18),
                nn.Linear(512, 256), nn.ELU(inplace=True), nn.Dropout(p=0.12),
                nn.Linear(256, 64), nn.ELU(inplace=True),
                nn.Linear(64, 2), nn.Tanh(),
            )

        def forward(self, x):
            return self.head(self.backbone(x))


def apply_clahe_bgr(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    v = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(v)
    return cv2.cvtColor(cv2.merge((h, s, v)), cv2.COLOR_HSV2BGR)


def preprocess(frame_bgr, width, height, use_clahe):
    if use_clahe:
        frame_bgr = apply_clahe_bgr(frame_bgr)
    img = cv2.resize(frame_bgr, (width, height), interpolation=cv2.INTER_AREA)
    img = img.astype(np.float32) / 255.0
    img = (img - 0.5) / 0.5                       # -> [-1, 1]  (matches vision.py)
    img = np.transpose(img, (2, 0, 1))            # HWC -> CHW
    return img[np.newaxis, ...].astype(np.float32)  # NCHW


# Series 3.1+ hybrid head buckets (must match the shared Series 3/4 trainer bins):
# 9 classes, fine near center, coarse at the edges.
_S3_HYBRID_LO = np.array([0, 45, 60, 75, 85, 95, 105, 120, 135], dtype=np.float32)
_S3_HYBRID_HI = np.array([45, 60, 75, 85, 95, 105, 120, 135, 180], dtype=np.float32)


def _series4_current_raw(values):
    """Return the current-horizon 18-vector, or None for a non-Series-4 output."""
    values = np.asarray(values, dtype=np.float32)
    if values.size >= 18 and values.size % 18 == 0:
        return values.reshape(-1, 18)[0]
    return None


def _decode_hybrid18(raw):
    logits = raw[:9]
    offset_raw = raw[9:18]
    cls = int(np.argmax(logits))
    offset = float(1.0 / (1.0 + np.exp(-offset_raw[cls])))
    lo = float(_S3_HYBRID_LO[cls])
    hi = float(_S3_HYBRID_HI[cls])
    return float(np.clip(lo + offset * (hi - lo), 0.0, 180.0))


def decode_output(values):
    """Model output -> (steering_deg 0..180, throttle 0..1), auto-detected:
      * [...,18] -> Series 4: decode horizon 0; steering only, throttle=0.
      * 19 -> Series 3.1+ hybrid: 9 class logits + 9 within-bucket offsets + 1 throttle.
              argmax the logits, sigmoid that bucket's offset, steer = lo + off*(hi-lo).
      * 2  -> Series 3.0 unit controls (steer,throttle in [-1,1]).
      * 1  -> Series 1/2, already in degrees."""
    series4_raw = _series4_current_raw(values)
    if series4_raw is not None:
        return _decode_hybrid18(series4_raw), 0.0
    flat = np.asarray(values, dtype=np.float32).reshape(-1)
    n = flat.size
    k = _S3_HYBRID_LO.size                                   # 9 steering classes
    if n == 2 * k + 1:                                       # 19 -> hybrid head
        logits = flat[0:k]
        offset = 1.0 / (1.0 + np.exp(-flat[k:2 * k]))        # sigmoid -> 0..1 fraction
        cls = int(np.argmax(logits))
        lo = float(_S3_HYBRID_LO[cls]); hi = float(_S3_HYBRID_HI[cls])
        steer = lo + float(offset[cls]) * (hi - lo)          # place inside the picked bucket
        throttle = float(1.0 / (1.0 + np.exp(-flat[2 * k]))) # throttle head (off in training)
        return float(np.clip(steer, 0.0, 180.0)), throttle
    if n >= 2:                                               # 2 -> Series 3.0 unit controls
        u0 = float(np.clip(flat[0], -1.0, 1.0))
        u1 = float(np.clip(flat[1], -1.0, 1.0))
        return 90.0 + 90.0 * u0, (u1 + 1.0) * 0.5
    return float(flat[0]), 0.0                               # 1 -> Series 1/2 degrees


def decode_probs9(values):
    """Current-horizon 9-bucket probabilities; zeros for non-hybrid outputs."""
    series4_raw = _series4_current_raw(values)
    if series4_raw is not None:
        logits = series4_raw[:9]
        z = logits - np.max(logits)
        e = np.exp(z)
        return (e / float(np.sum(e))).astype(np.float32)
    flat = np.asarray(values, dtype=np.float32).reshape(-1)
    k = _S3_HYBRID_LO.size
    if flat.size == 2 * k + 1:                               # hybrid: first k are class logits
        z = flat[0:k] - np.max(flat[0:k])
        e = np.exp(z)
        return (e / float(np.sum(e))).astype(np.float32)
    return np.zeros(k, dtype=np.float32)


class SteeringModel:
    def __init__(self, spec, models_dir=None, use_clahe=False, steer_scale=86.0, force_size=None):
        if cv2 is None:
            raise RuntimeError("opencv-python is required.")
        self.models_dir = models_dir
        self.use_clahe = use_clahe
        self.steer_scale = steer_scale
        self.force_size = force_size
        self.current_version = None
        self.pinned = False          # True = ignore the Pi's per-frame model choice
        self.backend = None          # "onnx" or "torch"
        self.width = self.height = None
        self.history_input_name = None
        self.history_steps = 0
        self.target_history = []
        self.load(spec)

    def reset_temporal_state(self):
        """Start a causal Series 4 sequence from centered target commands."""
        self.target_history = [90.0] * int(self.history_steps)

    def ensure_version(self, spec):
        """Hot-swap the model if the Pi requested a different version."""
        if spec and str(spec) != str(self.current_version):
            try:
                self.load(spec)
            except SystemExit as exc:
                print(f"[jon] model switch to '{spec}' failed: {exc}", flush=True)

    def load(self, spec):
        model_path = resolve_model_path(spec, self.models_dir)
        # CLAHE + output-scale follow the VERSION (mirror the Pi's vision.py), because the
        # Pi only sends a version string. e.g. 2.0/2.0b -> CLAHE on; every other model raw.
        # A raw/unrecognized filename falls back to the startup --clahe/--steer-scale.
        version = _version_from_path(model_path)
        if version is not None:
            self.use_clahe, steer_scale = _preproc_policy_for_version(version)
        else:
            steer_scale = self.steer_scale
        low = model_path.lower()

        if low.endswith(".onnx"):
            if ort is None:
                raise RuntimeError("onnxruntime is required for .onnx models.")
            # Prefer GPU: TensorRT > CUDA > CPU. These only appear if a GPU-capable
            # onnxruntime build is installed (on Jetson: the JetPack-matched
            # onnxruntime-gpu wheel; the plain PyPI 'onnxruntime' is CPU-only).
            available = ort.get_available_providers()
            # CUDA first: fast, predictable GPU startup. (TensorRT EP is faster but
            # rebuilds its engine every start without a cache -> save it for the
            # explicit INT8/TensorRT step later.)
            if "CUDAExecutionProvider" in available:
                # Do not also register TensorRT here. A partially installed TensorRT EP
                # can make ORT reject the complete provider list and silently retry on
                # CPU even when CUDA itself is healthy.
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            elif "TensorrtExecutionProvider" in available:
                providers = ["TensorrtExecutionProvider", "CPUExecutionProvider"]
            else:
                providers = ["CPUExecutionProvider"]
            if providers == ["CPUExecutionProvider"]:
                print("[jon] WARNING: no GPU execution provider available -> running on CPU (slow). "
                      "Install the JetPack-matched onnxruntime-gpu wheel to get CUDA/TensorRT. "
                      f"(available: {available})", flush=True)
            self.session = ort.InferenceSession(model_path, providers=providers)
            inputs = self.session.get_inputs()
            image_input = next((item for item in inputs if len(item.shape) == 4), inputs[0])
            history_input = next(
                (item for item in inputs if item.name == "target_history" or len(item.shape) == 2),
                None,
            )
            self.input_name = image_input.name
            self.history_input_name = history_input.name if history_input is not None else None
            self.history_steps = (
                int(history_input.shape[1])
                if history_input is not None and isinstance(history_input.shape[1], int)
                else (3 if history_input is not None else 0)
            )
            shape = image_input.shape   # [N,3,H,W]
            self.height = shape[2] if isinstance(shape[2], int) else None
            self.width = shape[3] if isinstance(shape[3], int) else None
            self.backend = "onnx"
            providers_used = self.session.get_providers()
        else:  # .pt / .pth (torch)
            if torch is None:
                raise RuntimeError("torch is required for .pt/.pth models.")
            obj = torch.load(model_path, map_location="cpu", weights_only=False)
            if isinstance(obj, dict) and not isinstance(obj, nn.Module):
                sd = obj.get("state_dict", obj)
                try:
                    model = SidewalkPilotV3(); model.load_state_dict(sd)   # S3 (2-out)
                except Exception:
                    model = SteeringAutonomyV2(steer_scale); model.load_state_dict(sd)  # S1/2
            else:
                model = obj  # full nn.Module or TorchScript ScriptModule
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = model.to(self.device).eval()
            # input size by detected arch (or override)
            if isinstance(model, SidewalkPilotV3):
                self.width, self.height = 320, 180
            elif isinstance(model, SteeringAutonomyV2):
                self.width, self.height = 200, 66
            self.backend = "torch"
            self.history_input_name = None
            self.history_steps = 0
            providers_used = self.device

        if self.force_size:
            self.width, self.height = self.force_size
        if not self.width or not self.height:
            raise RuntimeError("Could not determine model input size; pass --width/--height.")
        self.current_version = str(spec)
        self.reset_temporal_state()
        contract = f" history={self.history_steps}" if self.history_steps else ""
        print(f"[jon] model={model_path} (v{self.current_version}) backend={self.backend} "
              f"input={self.width}x{self.height}{contract} clahe={self.use_clahe} "
              f"on={providers_used}", flush=True)

    def infer(self, frame_bgr):
        x = preprocess(frame_bgr, self.width, self.height, self.use_clahe)
        if self.backend == "onnx":
            feeds = {self.input_name: x}
            if self.history_input_name is not None:
                feeds[self.history_input_name] = np.asarray(
                    [self.target_history], dtype=np.float32
                )
            out = self.session.run(None, feeds)[0]
        else:
            with torch.no_grad():
                out = self.model(torch.from_numpy(x).to(self.device)).detach().cpu().numpy()
        steer, throttle = decode_output(out)
        if self.history_steps:
            self.target_history = (self.target_history + [float(steer)])[-self.history_steps:]
        return steer, throttle, decode_probs9(out)


def _recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


_TEMP_CACHE = {"t": 0.0, "cpu": 0.0, "gpu": 0.0}


def _read_tegra_temps():
    """(cpu_c, gpu_c) from the Jetson thermal zones, cached ~2s. 0.0 if unreadable."""
    import glob
    now = time.time()
    if now - _TEMP_CACHE["t"] < 2.0:
        return _TEMP_CACHE["cpu"], _TEMP_CACHE["gpu"]
    cpu = gpu = 0.0
    try:
        for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
            try:
                ztype = open(zone + "/type").read().strip().lower()
                milli = float(open(zone + "/temp").read().strip())
            except Exception:
                continue
            c = milli / 1000.0
            if "cpu" in ztype:
                cpu = max(cpu, c)
            elif "gpu" in ztype:
                gpu = max(gpu, c)
    except Exception:
        pass
    _TEMP_CACHE.update({"t": now, "cpu": cpu, "gpu": gpu})
    return cpu, gpu


def serve(model, host, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    print(f"[jon] listening on {host}:{port} — waiting for the Pi ...", flush=True)
    while True:
        conn, addr = srv.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        model.reset_temporal_state()
        print(f"[jon] connected: {addr}", flush=True)
        frames, t0, ifps, last_frame_ts = 0, time.time(), 0.0, 0.0
        try:
            while True:
                # Frame: [1B version-len][version utf8][4B jpeg-len][jpeg bytes].
                # version-len 0 means "keep current model". The Pi sends its active
                # model choice every frame, so Jon hot-swaps when it changes.
                vhdr = _recv_exact(conn, 1)
                if not vhdr:
                    break
                vlen = vhdr[0]
                if vlen:
                    vbytes = _recv_exact(conn, vlen)
                    if vbytes is None:
                        break
                    if not getattr(model, "pinned", False):
                        model.ensure_version(vbytes.decode("utf-8", "replace"))
                hdr = _recv_exact(conn, 4)
                if not hdr:
                    break
                n = struct.unpack(">I", hdr)[0]
                if n == 0:
                    # status ping (no frame): report temps + current ifps, run no inference
                    model.reset_temporal_state()
                    jcpu, jgpu = _read_tegra_temps()
                    conn.sendall(struct.pack(">15f", 90.0, 0.0, jcpu, jgpu, ifps, 0.0, *([0.0] * 9)))
                    continue
                data = _recv_exact(conn, n)
                if not data:
                    break
                # inference rate (EMA) + Jetson temps, reported back to the Pi dashboard
                now = time.time()
                if last_frame_ts:
                    dt_f = now - last_frame_ts
                    if dt_f > 0.0:
                        ifps = 0.3 * (1.0 / dt_f) + 0.7 * ifps
                last_frame_ts = now
                jcpu, jgpu = _read_tegra_temps()
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)  # BGR
                if frame is None:
                    conn.sendall(struct.pack(">15f", 90.0, 0.0, jcpu, jgpu, ifps, 0.0, *([0.0] * 9)))
                    continue
                t_inf = time.time()
                steering, throttle, probs9 = model.infer(frame)   # preprocess + session.run
                infer_ms = (time.time() - t_inf) * 1000.0
                # reply: steering, throttle, jcpu, jgpu, infer_fps, infer_ms + 9 bucket probs (15x f32)
                conn.sendall(struct.pack(">15f", steering, throttle, jcpu, jgpu, ifps, infer_ms,
                                         *[float(p) for p in probs9]))
                frames += 1
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            conn.close()
            print(f"[jon] disconnected: {addr}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="highest",
                    help="version (3.0b, 2.4 ...), a path to .onnx/.pt/.pth, or 'highest' "
                         "(default). A concrete version PINS it (the Pi's per-frame model "
                         "choice is ignored); 'highest' follows whatever the Pi requests.")
    ap.add_argument("--models-dir", default=None, help="extra dir to search for SidewalkPilot-v*.*")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--clahe", action="store_true",
                    help="FALLBACK CLAHE for unrecognized model filenames. Recognized "
                         "SidewalkPilot-v* models auto-select (2.0/2.0b on, rest off).")
    ap.add_argument("--steer-scale", type=float, default=86.0,
                    help="FALLBACK output_scale_deg for unrecognized S1/2 filenames "
                         "(recognized: S2=85, S1=86 auto).")
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    args = ap.parse_args()

    force = (args.width, args.height) if (args.width and args.height) else None
    model = SteeringModel(args.model, models_dir=args.models_dir, use_clahe=args.clahe,
                          steer_scale=args.steer_scale, force_size=force)

    # An explicit concrete version (or path) PINS the model: ignore the Pi's per-frame
    # choice. 'highest'/'latest' (the default) FOLLOWS whatever the Pi requests.
    model.pinned = str(args.model).strip().lower() not in ("highest", "latest", "newest", "max")
    print(f"[jon] model {'PINNED to v' + str(model.current_version) + ' (ignoring Pi choice)' if model.pinned else 'FOLLOWS the Pi per-frame choice'}.",
          flush=True)

    serve(model, args.host, args.port)


if __name__ == "__main__":
    main()
