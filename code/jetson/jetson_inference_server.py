#!/usr/bin/env python3
"""
jetson_inference_server.py  —  "Jon" (Jetson Orin Nano) steering inference service.

Runs a SidewalkPilot model (ONNX) on the Jetson and answers steering requests from
the Pi 5 over the network. Generic across Series 1/2/3: it reads the model's input
size straight from the ONNX, so it adapts to 200x66 (S1/2) or 320x180 (S3) without
code changes. Preprocessing MATCHES the Pi runtime (rc_car_app/vision.py) exactly,
so the Jetson produces the same steering the Pi would for a given frame:

    BGR frame  ->  [optional CLAHE]  ->  resize(W,H, INTER_AREA)
               ->  /255  ->  (x-0.5)/0.5   (i.e. range -1..1)
               ->  HWC->CHW  ->  add batch  ->  float32 NCHW

Model output is the steering in LOGICAL servo degrees (0=left, 90=straight,
180=right) — the model's forward already bakes in the 90 + scale*tanh, so we return
it as-is. If the model has a 2nd output it's treated as throttle (0..1) (Series 3);
Series 1/2 (steering only) reply throttle = 0.

Wire protocol (TCP, persistent connection, one round-trip per frame):
    Pi  -> Jon : [4-byte big-endian length N][N bytes JPEG]
    Jon -> Pi  : [8 bytes] = struct '>ff' (steering_deg, throttle)

Run on the Jetson:
    python3 jetson_inference_server.py --model SidewalkPilot-v3.0b.onnx
    # Series 1/2 model (export its .pth to ONNX first), CLAHE-trained models add --clahe
    python3 jetson_inference_server.py --model SidewalkPilot-v2.4b.onnx --clahe

Validate the model alone (no network) on one image:
    python3 jetson_inference_server.py --model X.onnx --test-image some_frame.jpg

NOTE: onnxruntime + opencv-python + numpy must be installed on the Jetson
(onnxruntime-gpu for CUDA). This file is import-light so it only needs them at run.
"""

import argparse
import socket
import struct
import sys
import time

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None
try:
    import onnxruntime as ort
except ImportError:
    ort = None


# --- preprocessing: identical to rc_car_app/vision.py preprocess_steering_frame ---
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
    img = (img - 0.5) / 0.5                       # -> [-1, 1]
    img = np.transpose(img, (2, 0, 1))            # HWC -> CHW
    return img[np.newaxis, ...].astype(np.float32)  # NCHW


class SteeringModel:
    def __init__(self, model_path, use_clahe=False, force_size=None):
        if ort is None or cv2 is None:
            raise RuntimeError("onnxruntime and opencv-python are required on the Jetson.")
        providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider")
                     if p in ort.get_available_providers()] or ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.use_clahe = use_clahe
        shape = self.session.get_inputs()[0].shape   # expect [N,3,H,W]
        # ONNX dims can be strings (dynamic) -> fall back to --width/--height
        h = shape[2] if isinstance(shape[2], int) else (force_size[1] if force_size else None)
        w = shape[3] if isinstance(shape[3], int) else (force_size[0] if force_size else None)
        if not w or not h:
            raise RuntimeError("Model input size is dynamic; pass --width/--height.")
        self.width, self.height = int(w), int(h)
        print(f"[jon] model={model_path} input={self.width}x{self.height} "
              f"clahe={self.use_clahe} providers={self.session.get_providers()}", flush=True)

    def infer(self, frame_bgr):
        x = preprocess(frame_bgr, self.width, self.height, self.use_clahe)
        outs = self.session.run(None, {self.input_name: x})
        flat = np.asarray(outs[0]).reshape(-1)
        steering = float(flat[0])                                  # logical 0..180
        throttle = float(flat[1]) if flat.size > 1 else 0.0        # S3 = throttle, S1/2 = none
        return steering, throttle


def _recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


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
        frames = 0
        t0 = time.time()
        try:
            while True:
                hdr = _recv_exact(conn, 4)
                if not hdr:
                    break
                n = struct.unpack(">I", hdr)[0]
                data = _recv_exact(conn, n)
                if not data:
                    break
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)  # BGR
                if frame is None:
                    conn.sendall(struct.pack(">ff", 90.0, 0.0))   # bad frame -> straight
                    continue
                steering, throttle = model.infer(frame)
                conn.sendall(struct.pack(">ff", steering, throttle))
                frames += 1
                if frames % 100 == 0:
                    fps = frames / max(1e-6, time.time() - t0)
                    print(f"[jon] {frames} frames, {fps:.1f} infer/s, last steer={steering:.1f}", flush=True)
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            conn.close()
            print(f"[jon] disconnected: {addr}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="path to the .onnx model")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--clahe", action="store_true", help="apply CLAHE (only for CLAHE-trained models)")
    ap.add_argument("--width", type=int, default=None, help="override input W if the ONNX is dynamic")
    ap.add_argument("--height", type=int, default=None, help="override input H if the ONNX is dynamic")
    ap.add_argument("--test-image", default=None, help="run inference on ONE local image and exit")
    args = ap.parse_args()

    force = (args.width, args.height) if (args.width and args.height) else None
    model = SteeringModel(args.model, use_clahe=args.clahe, force_size=force)

    if args.test_image:
        frame = cv2.imread(args.test_image)            # BGR
        if frame is None:
            print(f"[jon] could not read {args.test_image}", file=sys.stderr)
            raise SystemExit(1)
        steering, throttle = model.infer(frame)
        print(f"[jon] {args.test_image} -> steering={steering:.2f} deg, throttle={throttle:.3f}")
        return

    serve(model, args.host, args.port)


if __name__ == "__main__":
    main()
