#!/usr/bin/env python3
"""
jetson_inference_server.py  —  "Jon" (Jetson Orin Nano) steering inference service.

Runs a SidewalkPilot model on the Jetson and answers steering requests from the Pi 5
over TCP. Accepts .onnx, .pt (TorchScript), or .pth (state-dict) — and is generic
across Series 1/2/3:

  * Series 1/2 (SteeringAutonomyV2): 1 output, already in DEGREES (90 + scale*tanh).
  * Series 3.0/3.0b (regression):    2 outputs in UNIT controls (steer,throttle in
                                     [-1,1]); decoded steer=90+90*u, throttle=(u+1)/2.
  * Series 3.1+ (hybrid head):       19 outputs = 9 steering-class logits + 9 within-
                                     bucket offsets + 1 throttle; decoded via argmax
                                     bucket + sigmoid(offset) -> degrees.
  The output is auto-decoded by its length (1 -> degrees, 2 -> unit controls,
  19 -> hybrid), so the same code handles every model/format.

Preprocessing MATCHES rc_car_app/vision.py exactly:
  BGR -> [optional CLAHE] -> resize(W,H, INTER_AREA) -> /255 -> (x-0.5)/0.5
      -> HWC->CHW -> NCHW float32
Input size W,H comes from the ONNX itself, or from the detected arch for torch
(S1/2 = 200x66, S3 = 320x180), or --width/--height.

Wire protocol (TCP, persistent connection, one round-trip per frame):
    Pi  -> Jon : [4-byte big-endian length N][N bytes JPEG]
    Jon -> Pi  : 8 bytes = struct '>ff' (steering_deg 0..180, throttle 0..1)

Run on the Jetson:
    python3 jetson_inference_server.py --model SidewalkPilot-v3.0b.onnx
    python3 jetson_inference_server.py --model SidewalkPilot-v2.4b.pth          # S1/2 state-dict
    python3 jetson_inference_server.py --model model.pt                          # TorchScript

Deps on the Jetson: numpy, opencv-python, and onnxruntime(-gpu) and/or torch
(whichever your model format needs).
"""

import argparse
import socket
import struct
import time
from pathlib import Path

import numpy as np

# code/ai_models (released) + series_3 (fresh training output) — searched by version
_CODE_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_MODEL_DIRS = [_CODE_DIR / "ai_models", _CODE_DIR / "ai_models_datasets" / "series_3"]


def _version_key(version):
    """Sort key for a version string like '3.0b' -> (3.0, 1). 'b' alternates rank above
    the plain version of the same number."""
    v = str(version).strip().lower()
    is_b = 1 if v.endswith("b") else 0
    num = v[:-1] if is_b else v
    try:
        return (float(num), is_b)
    except ValueError:
        return (-1.0, is_b)


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


# Series 3.1+ hybrid head buckets (must match series_3 trainer STEER_CLASS_BINS):
# 9 classes, fine near center, coarse at the edges.
_S3_HYBRID_LO = np.array([0, 45, 60, 75, 85, 95, 105, 120, 135], dtype=np.float32)
_S3_HYBRID_HI = np.array([45, 60, 75, 85, 95, 105, 120, 135, 180], dtype=np.float32)


def decode_output(flat):
    """flat = 1-D model output -> (steering_deg 0..180, throttle 0..1), auto-detected
    by length:
      * 19 -> Series 3.1+ hybrid: 9 class logits + 9 within-bucket offsets + 1 throttle.
              argmax the logits, sigmoid that bucket's offset, steer = lo + off*(hi-lo).
      * 2  -> Series 3.0 unit controls (steer,throttle in [-1,1]).
      * 1  -> Series 1/2, already in degrees."""
    flat = np.asarray(flat, dtype=np.float32).reshape(-1)
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
        self.load(spec)

    def ensure_version(self, spec):
        """Hot-swap the model if the Pi requested a different version."""
        if spec and str(spec) != str(self.current_version):
            try:
                self.load(spec)
            except SystemExit as exc:
                print(f"[jon] model switch to '{spec}' failed: {exc}", flush=True)

    def load(self, spec):
        model_path = resolve_model_path(spec, self.models_dir)
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
            preferred = ("CUDAExecutionProvider", "TensorrtExecutionProvider", "CPUExecutionProvider")
            providers = [p for p in preferred if p in available] or ["CPUExecutionProvider"]
            if providers == ["CPUExecutionProvider"]:
                print("[jon] WARNING: no GPU execution provider available -> running on CPU (slow). "
                      "Install the JetPack-matched onnxruntime-gpu wheel to get CUDA/TensorRT. "
                      f"(available: {available})", flush=True)
            self.session = ort.InferenceSession(model_path, providers=providers)
            self.input_name = self.session.get_inputs()[0].name
            shape = self.session.get_inputs()[0].shape   # [N,3,H,W]
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
            providers_used = self.device

        if self.force_size:
            self.width, self.height = self.force_size
        if not self.width or not self.height:
            raise RuntimeError("Could not determine model input size; pass --width/--height.")
        self.current_version = str(spec)
        print(f"[jon] model={model_path} (v{self.current_version}) backend={self.backend} "
              f"input={self.width}x{self.height} clahe={self.use_clahe} on={providers_used}", flush=True)

    def infer(self, frame_bgr):
        x = preprocess(frame_bgr, self.width, self.height, self.use_clahe)
        if self.backend == "onnx":
            out = self.session.run(None, {self.input_name: x})[0]
        else:
            with torch.no_grad():
                out = self.model(torch.from_numpy(x).to(self.device)).detach().cpu().numpy()
        return decode_output(out)


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
        print(f"[jon] connected: {addr}", flush=True)
        frames, t0, ifps, last_frame_ts = 0, time.time(), 0.0, 0.0
        t_wait = t_dec = t_inf = 0.0    # per-100-frame timing: net-wait / jpeg-decode / inference
        try:
            while True:
                loop_t0 = time.time()
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
                    jcpu, jgpu = _read_tegra_temps()
                    conn.sendall(struct.pack(">fffff", 90.0, 0.0, jcpu, jgpu, ifps))
                    continue
                data = _recv_exact(conn, n)
                if not data:
                    break
                wait_done = time.time()   # blocked here = waiting on the Pi (network + Pi send cadence)
                # inference rate (EMA) + Jetson temps, reported back to the Pi dashboard
                now = wait_done
                if last_frame_ts:
                    dt_f = now - last_frame_ts
                    if dt_f > 0.0:
                        ifps = 0.3 * (1.0 / dt_f) + 0.7 * ifps
                last_frame_ts = now
                jcpu, jgpu = _read_tegra_temps()
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)  # BGR
                if frame is None:
                    conn.sendall(struct.pack(">fffff", 90.0, 0.0, jcpu, jgpu, ifps))
                    continue
                dec_done = time.time()
                steering, throttle = model.infer(frame)   # preprocess + session.run
                inf_done = time.time()
                # reply: steering, throttle, jon_cpu_temp_c, jon_gpu_temp_c, infer_fps
                conn.sendall(struct.pack(">fffff", steering, throttle, jcpu, jgpu, ifps))
                t_wait += wait_done - loop_t0
                t_dec += dec_done - wait_done
                t_inf += inf_done - dec_done
                frames += 1
                if frames % 100 == 0:
                    # avg ms/frame over the last 100: wait(net)=Pi/network bound, infer=model-compute bound.
                    # If infer dominates -> FP16 helps a lot; if wait(net) dominates -> fix JPEG/TCP, not the model.
                    print(f"[jon] {frames} frames, {ifps:.1f} infer/s, cpu={jcpu:.0f}C gpu={jgpu:.0f}C "
                          f"steer={steering:.1f} | avg ms/frame: wait(net)={t_wait*10:.1f} "
                          f"decode={t_dec*10:.1f} infer={t_inf*10:.1f}", flush=True)
                    t_wait = t_dec = t_inf = 0.0
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
    ap.add_argument("--clahe", action="store_true", help="apply CLAHE (only for CLAHE-trained models)")
    ap.add_argument("--steer-scale", type=float, default=86.0, help="output_scale_deg for S1/2 .pth (S1=86)")
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
