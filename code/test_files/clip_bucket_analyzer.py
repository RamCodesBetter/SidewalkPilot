#!/usr/bin/env python3
"""clip_bucket_analyzer.py -- per-frame steering-bucket readout for a recorded clip.

Runs on Jon (the Jetson). Point it at a video clip (e.g. one of the interruption
clips saved by the Pi) and it replays every frame through the SidewalkPilot model
EXACTLY the way the live inference service does (same preprocess, same bin edges,
same argmax+offset decode), then prints:

  * a per-frame table of the 9 steering-class probabilities (%), the picked bucket,
    the decoded steering angle, and a CLOSE flag when the top-2 buckets are within
    --close of each other (the model was nearly split -- e.g. 0.52 / 0.48);
  * a summary: mean probability per bucket, how many frames landed in each bucket,
    mean/spread of the decoded steering, mean top-1 confidence, and every close-call
    frame index.

There's no ground truth in a raw clip, so the tool can't say a frame is "completely
off" on its own -- it flags AMBIGUOUS frames (CLOSE) and shows you the decoded angle
so you (or I) can eyeball which frames were confidently wrong vs genuinely torn.

Usage on Jon (repo at ~/rc_car_code or /nvme/rc_car_code):
    python3 clip_bucket_analyzer.py --clip ~/interruption_clips/clip_1720300000.mp4
    python3 clip_bucket_analyzer.py --clip clip.mov --model 3.1b --every 1

Defaults to the highest available model (3.1b here) to match the field run.
Deps (already on Jon): numpy, opencv-python, and onnxruntime(-gpu) and/or torch.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

# Reuse the live Jon service's model loader + preprocess + decode so this analyzer
# can never drift from what actually ran on the car.
_HERE = Path(__file__).resolve().parent                       # .../code/test_files
_CTRL = _HERE.parent / "controller" / "current"               # .../code/controller/current
sys.path.insert(0, str(_CTRL))
from rc_car_app import jetson_inference_server as jis          # noqa: E402

try:
    import cv2
except ImportError:
    cv2 = None

# Physical servo mapping — mirrors hardware.logical_to_reference_steering_degrees +
# apply_steering_center_trim_degrees, using config's measured constants. Reproduces the
# DETERMINISTIC part of the runtime pipeline (ref-map + DELT center trim). It does NOT
# include the yaw-PID/D closed-loop correction (needs live IMU yaw, absent from a clip;
# also inactive whenever |cmd-90| > STRAIGHT_BAND ~5deg, i.e. all the turning frames),
# nor the LFF/RFF straight-band feed-forward (only used within +/-5deg of center).
try:
    from rc_car_app import config as _cfg          # noqa: E402
    _REF_L = float(_cfg.STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG)
    _REF_R = float(_cfg.STEERING_SERVO_REFERENCE_RIGHT_LIMIT_DEG)
    _CTR_OFF = float(_cfg.STEERING_SERVO_CENTER_OFFSET)
    _ACT_RANGE = float(_cfg.STEERING_SERVO_ACTUATION_RANGE_DEG)
except Exception:                                  # fallback = measured defaults (2026-07-08)
    _REF_L, _REF_R, _CTR_OFF, _ACT_RANGE = 48.812, 131.188, 9.0 / 90.0, 180.0


def logical_to_physical_deg(logical):
    """Logical steer (0=L,90=C,180=R) -> physical servo command deg (ref-map + DELT trim)."""
    rng = max(1.0, _ACT_RANGE)
    center = rng / 2.0
    lg = max(0.0, min(rng, float(logical)))
    ll = max(0.0, min(center, _REF_L))
    rl = max(center, min(rng, _REF_R))
    if lg <= center:
        ref = center - ((center - lg) / center) * (center - ll)
    else:
        ref = center + ((lg - center) / center) * (rl - center)
    ref += max(-1.0, min(1.0, _CTR_OFF)) * center
    return max(0.0, min(rng, ref))


def _softmax(z):
    z = np.asarray(z, dtype=np.float64)
    z = z - np.max(z)
    e = np.exp(z)
    return e / np.sum(e)


def _raw_forward(model, frame_bgr):
    """Run the live model contract and return its current-horizon raw vector."""
    x = jis.preprocess(frame_bgr, model.width, model.height, model.use_clahe)
    if model.backend == "onnx":
        feeds = {model.input_name: x}
        if model.history_input_name is not None:
            feeds[model.history_input_name] = np.asarray(
                [model.target_history], dtype=np.float32
            )
        out = model.session.run(None, feeds)[0]
    else:
        import torch
        with torch.no_grad():
            out = model.model(torch.from_numpy(x).to(model.device)).detach().cpu().numpy()
    steering, _throttle = jis.decode_output(out)
    if model.history_steps:
        model.target_history = (model.target_history + [float(steering)])[-model.history_steps:]
    series4_raw = jis._series4_current_raw(out)
    if series4_raw is not None:
        return series4_raw
    return np.asarray(out, dtype=np.float32).reshape(-1)


def _bucket_meta():
    """(labels, ranges) for the 9 hybrid buckets. Direction tag: bucket that spans
    90 deg is center (C); lower = left (L), higher = right (R)."""
    lo, hi = jis._S3_HYBRID_LO, jis._S3_HYBRID_HI
    labels, ranges = [], []
    left_n = int(np.sum(hi <= 90.0))          # buckets entirely left of center
    for i in range(lo.size):
        if lo[i] <= 90.0 < hi[i]:
            tag = "C"
        elif hi[i] <= 90.0:
            tag = f"L{left_n - i}"            # outer-left = biggest number
        else:
            tag = f"R{i - left_n}"
        labels.append(tag)
        ranges.append(f"{int(lo[i])}-{int(hi[i])}")
    return labels, ranges


def analyze(clip_path, model_spec, use_clahe, every, max_frames, close_thresh, alpha):
    if cv2 is None:
        raise SystemExit("opencv-python is required (import cv2 failed).")
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        raise SystemExit(f"could not open clip: {clip_path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    model = jis.SteeringModel(model_spec, use_clahe=use_clahe)
    labels, ranges = _bucket_meta()
    k = len(labels)

    print(f"\nclip   : {clip_path}")
    print(f"source : {total} frames @ {src_fps:.1f} fps"
          + (f"  (~{total / src_fps:.1f}s)" if src_fps > 0 else ""))
    print(f"model  : v{model.current_version}  backend={model.backend}  "
          f"input={model.width}x{model.height}  clahe={use_clahe}")
    print(f"every  : {every}   close-call threshold: top1-top2 < {close_thresh:.2f}   "
          f"alpha(EMA smoothing): {alpha:.2f}\n")

    # header: two lines -- degree ranges, then L/C/R tags
    cols = "".join(f"{r:>8}" for r in ranges)
    tags = "".join(f"{t:>8}" for t in labels)
    print(f"{'frame':>6}{'t(s)':>7}  {cols}   {'pick':>6}{'steer':>7}  {'~pick':>6}{'~phys':>8}  flag")
    print(f"{'':>6}{'':>7}  {tags}")
    print(f"  steer = raw MODEL logical (0=L,90=C,180=R).  ~phys = alpha-smoothed -> servo deg via "
          f"ref-map+DELT trim (phys straight ~= {logical_to_physical_deg(90.0):.1f}); excl. yaw-PID/D + LFF/RFF.")
    print("-" * (13 + 8 * k + 38))

    prob_sum = np.zeros(k, dtype=np.float64)
    pick_hist = np.zeros(k, dtype=np.int64)
    steers, top1s = [], []
    ema = None                                # running EMA of the 9 probs (temporal smoothing)
    s_steers, raw_picks, s_picks = [], [], []
    close_frames = []
    n = 0
    idx = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx % every != 0:
            continue
        if max_frames and n >= max_frames:
            break
        flat = _raw_forward(model, frame)
        if flat.size not in (2 * k, 2 * k + 1):
            # not a 3.1+ hybrid head -> bucket view doesn't apply; show decoded only
            steer, thr = jis.decode_output(flat)
            print(f"{idx:>6}{idx / src_fps if src_fps else 0:>7.2f}   "
                  f"(non-hybrid out len={flat.size}) steer={steer:.1f} thr={thr:.2f}")
            steers.append(steer)
            n += 1
            continue

        probs = _softmax(flat[0:k])
        order = np.argsort(probs)[::-1]
        top, second = int(order[0]), int(order[1])
        gap = float(probs[top] - probs[second])
        is_close = gap < close_thresh
        steer, _thr = jis.decode_output(flat)

        # temporal smoothing: EMA the probability vector, then argmax + decode the
        # smoothed-picked bucket using the current frame's within-bucket offset. This is
        # what a per-frame prob-EMA in the runtime would do -- it kills argmax flips.
        ema = probs.copy() if ema is None else (alpha * probs + (1.0 - alpha) * ema)
        s_cls = int(np.argmax(ema))
        s_off = 1.0 / (1.0 + np.exp(-float(flat[k + s_cls])))
        s_steer = float(jis._S3_HYBRID_LO[s_cls]
                        + s_off * (jis._S3_HYBRID_HI[s_cls] - jis._S3_HYBRID_LO[s_cls]))

        prob_sum += probs
        pick_hist[top] += 1
        steers.append(steer)
        top1s.append(float(probs[top]))
        raw_picks.append(top)
        s_picks.append(s_cls)
        s_steers.append(s_steer)
        if is_close:
            close_frames.append((idx, labels[top], labels[second], probs[top], probs[second]))

        cells = "".join(
            (f"{int(round(p * 100)):>6}* " if j == top else f"{int(round(p * 100)):>7} ")
            for j, p in enumerate(probs))
        s_phys = logical_to_physical_deg(s_steer)
        t = idx / src_fps if src_fps else 0.0
        print(f"{idx:>6}{t:>7.2f}  {cells}  {labels[top]:>5}{steer:>7.1f}  "
              f"{labels[s_cls]:>5}{s_phys:>8.1f}  {'CLOSE' if is_close else ''}")
        n += 1

    cap.release()
    if n == 0:
        raise SystemExit("no frames analyzed.")

    print("\n" + "=" * 60)
    print(f"SUMMARY  ({n} frames analyzed)")
    print("=" * 60)
    if steers and prob_sum.any():
        mean_probs = prob_sum / n
        print("\nmean probability per bucket (%):")
        for i in range(k):
            bar = "#" * int(round(mean_probs[i] * 40))
            print(f"  {labels[i]:>4} [{ranges[i]:>7}] {mean_probs[i] * 100:5.1f}  {bar}")
        print("\nframes picked per bucket:")
        for i in range(k):
            if pick_hist[i]:
                print(f"  {labels[i]:>4} [{ranges[i]:>7}] {pick_hist[i]:4d}  "
                      f"({100.0 * pick_hist[i] / n:4.1f}%)")
    sarr = np.asarray(steers, dtype=np.float64)
    print(f"\nsteering (raw)      : mean {sarr.mean():.1f} deg   min {sarr.min():.1f}   "
          f"max {sarr.max():.1f}   std {sarr.std():.1f}")
    if s_steers:
        ss = np.asarray(s_steers, dtype=np.float64)
        switches_raw = sum(1 for a, b in zip(raw_picks, raw_picks[1:]) if a != b)
        switches_s = sum(1 for a, b in zip(s_picks, s_picks[1:]) if a != b)
        print(f"steering (a={alpha:.2f})    : mean {ss.mean():.1f} deg   min {ss.min():.1f}   "
              f"max {ss.max():.1f}   std {ss.std():.1f}   (logical)")
        sp = np.asarray([logical_to_physical_deg(v) for v in s_steers], dtype=np.float64)
        print(f"servo ~phys (a={alpha:.2f})  : mean {sp.mean():.1f} deg   min {sp.min():.1f}   "
              f"max {sp.max():.1f}   std {sp.std():.1f}   (map+DELT, straight~{logical_to_physical_deg(90.0):.1f}, excl yaw-PID/D)")
        print(f"bucket switches     : raw {switches_raw}  ->  smoothed {switches_s}   "
              f"(fewer = calmer wheel)")
    if top1s:
        tarr = np.asarray(top1s, dtype=np.float64)
        conf = 100.0 * np.mean(tarr >= 0.70)
        print(f"top-1 conf: mean {tarr.mean() * 100:.1f}%   "
              f"frames >=70%: {conf:.0f}%   frames close-call: "
              f"{100.0 * len(close_frames) / n:.0f}%")
    if close_frames:
        print(f"\nclose-call frames ({len(close_frames)}) -- model nearly split:")
        for fidx, a, b, pa, pb in close_frames:
            t = fidx / src_fps if src_fps else 0.0
            print(f"  frame {fidx:>5} (t={t:5.2f}s): {a} {pa * 100:.0f}% vs {b} {pb * 100:.0f}%")
    print()


def main():
    ap = argparse.ArgumentParser(description="Per-frame steering-bucket analysis of a recorded clip (runs on Jon).")
    ap.add_argument("--clip", required=True, help="path to the video clip (.mp4/.mov/...)")
    ap.add_argument("--model", default="highest",
                    help="model version (e.g. 3.1b) or path; default 'highest' (matches the field run)")
    ap.add_argument("--clahe", action="store_true", help="apply CLAHE (only if the model was trained with it)")
    ap.add_argument("--every", type=int, default=1, help="analyze every Nth frame (default 1 = all)")
    ap.add_argument("--max-frames", type=int, default=0, help="stop after this many analyzed frames (0 = all)")
    ap.add_argument("--close", type=float, default=0.15,
                    help="close-call threshold: flag when top1-top2 probability < this (default 0.15)")
    ap.add_argument("--alpha", type=float, default=0.45,
                    help="EMA weight of the NEWEST frame's probs for the smoothed ~pick/~steer "
                         "columns (0<alpha<=1; lower = smoother; default 0.45 ~ runtime)")
    args = ap.parse_args()
    analyze(Path(args.clip).expanduser(), args.model, args.clahe,
            max(1, args.every), args.max_frames, args.close, args.alpha)


if __name__ == "__main__":
    main()
