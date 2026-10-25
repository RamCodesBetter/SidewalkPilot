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
  Output shape and ONNX input metadata select the contract automatically. Production
  requests carry the Raspberry Pi's latest three manual or predicted steering targets;
  the server validates and feeds them to PC/PCF before each inference.

Preprocessing MATCHES rc_car_app/vision.py exactly:
  BGR -> [optional CLAHE] -> resize(W,H, INTER_AREA) -> /255 -> (x-0.5)/0.5
      -> HWC->CHW -> NCHW float32
Input size W,H comes from the ONNX itself, or from the detected arch for torch
(S1/2 = 200x66, S3 = 320x180), or --width/--height.

Wire protocol (TCP, persistent connection, one round-trip per frame):
    Pi  -> Jon : [1-byte 0x80|version length V][V bytes UTF-8 model version]
                 [1-byte history count H][H big-endian float32 steering targets]
                 [4-byte big-endian JPEG length N][N bytes JPEG]
    Jon -> Pi  : 60 bytes = struct '>15f' (steering, throttle, temperatures,
                 inference timing, and 9 current-horizon bucket probabilities)

Run on the Jetson:
    # Dashboard model switching enabled (recommended production command):
    python3 jetson_inference_server.py --model highest

    # Pin one model for a controlled single-model test:
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
_MAX_JPEG_BYTES = 16 * 1024 * 1024


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

# The filename is part of the deployed model contract. Validate it against the
# ONNX graph so an accidentally renamed or incorrectly exported model cannot
# silently drive with the wrong temporal inputs.
_SERIES4_CONTRACTS = {
    "4.0p": (3, 1),
    "4.0r": (3, 1),
    "4.0f": (0, 4),
    "4.0g": (0, 4),
    "4.0a": (3, 4),
    "4.0c": (3, 4),
    "4.1p": (3, 1),
    "4.1r": (3, 1),
    "4.1f": (0, 4),
    "4.1g": (0, 4),
    "4.1a": (3, 4),
    "4.1c": (3, 4),
}


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


def _validate_series4_contract(version, history_steps, output_shape):
    """Reject a Series 4 ONNX graph that does not match its version contract."""
    expected = _SERIES4_CONTRACTS.get(str(version).strip().lower())
    if expected is None:
        return

    expected_history, expected_horizons = expected
    shape = list(output_shape or ())
    actual_horizons = shape[1] if len(shape) == 3 and isinstance(shape[1], int) else None
    output_width = shape[2] if len(shape) == 3 and isinstance(shape[2], int) else None
    if (
        int(history_steps) != expected_history
        or actual_horizons != expected_horizons
        or output_width != 18
    ):
        raise RuntimeError(
            f"Series 4 v{version} contract mismatch: expected history={expected_history}, "
            f"output=[batch,{expected_horizons},18]; got history={history_steps}, "
            f"output={shape}"
        )


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


def _softmax9(logits):
    """Convert nine class logits to stable float32 probabilities."""
    logits = np.asarray(logits, dtype=np.float32)
    shifted = logits - np.max(logits)
    exponentials = np.exp(shifted)
    return (exponentials / np.sum(exponentials)).astype(np.float32)


def _decode_hybrid18(raw):
    logits = raw[:9]
    offset_raw = raw[9:18]
    cls = int(np.argmax(_softmax9(logits)))
    offset = float(1.0 / (1.0 + np.exp(-offset_raw[cls])))
    lo = float(_S3_HYBRID_LO[cls])
    hi = float(_S3_HYBRID_HI[cls])
    return float(np.clip(lo + offset * (hi - lo), 0.0, 180.0))


def decode_output(values):
    """Model output -> (steering_deg 0..180, throttle 0..1), auto-detected:
      * [...,18] -> Series 4: decode horizon 0; steering only, throttle=0.
      * 19 -> Series 3.1+ hybrid: 9 class logits + 9 within-bucket offsets + 1 throttle.
              softmax the logits, argmax the probabilities, sigmoid that bucket's offset,
              steer = lo + off*(hi-lo).
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
        cls = int(np.argmax(_softmax9(logits)))
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
        return _softmax9(series4_raw[:9])
    flat = np.asarray(values, dtype=np.float32).reshape(-1)
    k = _S3_HYBRID_LO.size
    if flat.size == 2 * k + 1:                               # hybrid: first k are class logits
        return _softmax9(flat[0:k])
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

    def set_target_history(self, values):
        """Seed a causal model from steering targets supplied by the controller."""
        if not self.history_steps:
            return
        history = [float(value) for value in values]
        if len(history) != self.history_steps:
            raise ValueError(
                f"expected {self.history_steps} steering-history values, got {len(history)}"
            )
        if not all(np.isfinite(value) and 0.0 <= value <= 180.0 for value in history):
            raise ValueError("steering history must contain finite values in 0..180 degrees")
        self.target_history = history

    def ensure_version(self, spec):
        """Hot-swap the model and report whether the requested version is active."""
        requested = str(spec or "").strip()
        if not requested:
            return True
        if requested == str(self.current_version):
            return True
        previous_state = dict(self.__dict__)
        try:
            self.load(requested)
        except (Exception, SystemExit) as exc:
            self.__dict__.clear()
            self.__dict__.update(previous_state)
            print(f"[jon] model switch to '{requested}' failed: {exc}", flush=True)
            return False
        return requested == str(self.current_version)

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
            _validate_series4_contract(
                version,
                self.history_steps,
                self.session.get_outputs()[0].shape,
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
        self.current_version = str(version or spec)
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
        if not np.isfinite(steer) or not np.isfinite(throttle):
            raise RuntimeError("model produced a non-finite steering/throttle value")
        if not 0.0 <= float(steer) <= 180.0:
            raise RuntimeError(f"model produced steering outside 0..180 degrees: {steer}")
        probabilities = decode_probs9(out)
        if not np.all(np.isfinite(probabilities)):
            raise RuntimeError("model produced non-finite steering probabilities")
        if self.history_steps:
            self.target_history = (self.target_history + [float(steer)])[-self.history_steps:]
        return steer, throttle, probabilities


def _recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _recv_request(conn):
    """Read one legacy or v2 request; return (version, history, JPEG bytes)."""
    vhdr = _recv_exact(conn, 1)
    if not vhdr:
        return None
    extended = bool(vhdr[0] & 0x80)
    vlen = (vhdr[0] & 0x7F) if extended else vhdr[0]
    version = ""
    if vlen:
        vbytes = _recv_exact(conn, vlen)
        if vbytes is None:
            return None
        version = vbytes.decode("utf-8", "replace")

    target_history = None
    if extended:
        hcount_raw = _recv_exact(conn, 1)
        if hcount_raw is None:
            return None
        hcount = hcount_raw[0]
        if hcount:
            hpayload = _recv_exact(conn, hcount * 4)
            if hpayload is None:
                return None
            target_history = struct.unpack(f">{hcount}f", hpayload)

    hdr = _recv_exact(conn, 4)
    if not hdr:
        return None
    size = struct.unpack(">I", hdr)[0]
    if size == 0:
        return version, target_history, b""
    if size > _MAX_JPEG_BYTES:
        raise ValueError(f"JPEG payload exceeds {_MAX_JPEG_BYTES} bytes")
    data = _recv_exact(conn, size)
    if not data:
        return None
    return version, target_history, data


def _activate_requested_model(model, requested_version) -> bool:
    """Return false unless the exact model requested by the Raspberry Pi is active."""
    requested = str(requested_version or "").strip()
    if not requested:
        return True
    if getattr(model, "pinned", False):
        if requested == str(model.current_version):
            return True
        print(
            f"[jon] rejected v{requested}: server is pinned to v{model.current_version}",
            flush=True,
        )
        return False
    return bool(model.ensure_version(requested))


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
        conn.settimeout(2.0)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        model.reset_temporal_state()
        print(f"[jon] connected: {addr}", flush=True)
        frames, ifps, last_frame_ts = 0, 0.0, 0.0
        try:
            while True:
                # v2 sets the high bit on version-len and carries steering history.
                # Legacy packets remain readable for standalone/older clients.
                request = _recv_request(conn)
                if request is None:
                    break
                requested_version, target_history, data = request
                if not _activate_requested_model(model, requested_version):
                    # Close without a reply. The Pi treats the short reply as no result
                    # and holds instead of silently driving the previously loaded model.
                    break
                if not data:
                    # status ping (no frame): report temps + current ifps, run no inference
                    model.reset_temporal_state()
                    jcpu, jgpu = _read_tegra_temps()
                    conn.sendall(struct.pack(">15f", 90.0, 0.0, jcpu, jgpu, ifps, 0.0, *([0.0] * 9)))
                    continue
                # inference rate (EMA) + Jetson temps, reported back to the Pi dashboard
                now = time.perf_counter()
                if last_frame_ts:
                    dt_f = now - last_frame_ts
                    if dt_f > 0.0:
                        ifps = 0.3 * (1.0 / dt_f) + 0.7 * ifps
                last_frame_ts = now
                jcpu, jgpu = _read_tegra_temps()
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)  # BGR
                if frame is None:
                    print("[jon] rejected invalid JPEG frame", flush=True)
                    break
                if target_history is not None:
                    try:
                        model.set_target_history(target_history)
                    except ValueError as exc:
                        print(f"[jon] rejected steering history: {exc}", flush=True)
                        break
                t_inf = time.perf_counter()
                try:
                    steering, throttle, probs9 = model.infer(frame)   # preprocess + session.run
                except Exception as exc:
                    print(f"[jon] inference rejected: {exc}", flush=True)
                    break
                infer_ms = (time.perf_counter() - t_inf) * 1000.0
                # reply: steering, throttle, jcpu, jgpu, infer_fps, infer_ms + 9 bucket probs (15x f32)
                conn.sendall(struct.pack(">15f", steering, throttle, jcpu, jgpu, ifps, infer_ms,
                                         *[float(p) for p in probs9]))
                frames += 1
        except (OSError, ValueError) as exc:
            if isinstance(exc, ValueError):
                print(f"[jon] rejected request: {exc}", flush=True)
        finally:
            conn.close()
            print(f"[jon] disconnected: {addr}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="highest",
                    help="version (3.0b, 2.4 ...), a path to .onnx/.pt/.pth, or 'highest' "
                         "(default). A concrete version PINS it (the Pi's per-frame model "
                         "choice must match); 'highest' follows whatever the Pi requests.")
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

    # An explicit concrete version (or path) pins the model and rejects mismatched Pi
    # requests. 'highest'/'latest' (the default) follows whatever the Pi requests.
    model.pinned = str(args.model).strip().lower() not in ("highest", "latest", "newest", "max")
    print(f"[jon] model {'PINNED to v' + str(model.current_version) + ' (rejecting mismatched Pi choices)' if model.pinned else 'FOLLOWS the Pi per-frame choice'}.",
          flush=True)

    serve(model, args.host, args.port)


if __name__ == "__main__":
    main()
