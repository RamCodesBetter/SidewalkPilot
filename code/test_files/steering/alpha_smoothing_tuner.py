#!/usr/bin/env python3
"""alpha_smoothing_tuner.py — pick STEERING_SMOOTH_ALPHA for the runtime steering EMA.

The v3.1 hybrid head produces *blocky* per-frame steering: its argmax flips between
steering buckets on ambiguous frames, so the raw angle jumps by whole buckets
(e.g. 80 -> 120 -> 80). The runtime damps this with an exponential moving average:

    steer_out = alpha * steer_new + (1 - alpha) * steer_prev      (config STEERING_SMOOTH_ALPHA)

alpha is the "trust the new frame" weight:
    alpha = 1.0  -> no smoothing (raw, jittery)
    lower alpha  -> smoother, but LAGS real turns (can understeer a sharp corner)

This tool replays a steering trace through a sweep of alpha and reports two things per
alpha: JITTER (mean frame-to-frame change of the output -> lower = smoother) and LAG
(how many frames / seconds it takes to reach 90% of a real turn). It then recommends the
smoothest alpha that still keeps lag within your budget.

Usage:
  python3 code/test_files/steering/alpha_smoothing_tuner.py
  python3 code/test_files/steering/alpha_smoothing_tuner.py --csv run.csv --col steering
  python3 code/test_files/steering/alpha_smoothing_tuner.py --values 80,120,80,120,150,158,108
  python3 code/test_files/steering/alpha_smoothing_tuner.py --fps 15 --max-lag-s 0.25 --plot /tmp/alpha.png
"""
import argparse
import csv as _csv
import math
import random


def ema(values, alpha):
    """The exact runtime EMA: steer = alpha*new + (1-alpha)*prev."""
    out, prev = [], None
    for v in values:
        prev = v if prev is None else alpha * v + (1.0 - alpha) * prev
        out.append(prev)
    return out


def jitter(seq):
    """Mean absolute frame-to-frame change (deg/frame). Lower = smoother."""
    if len(seq) < 2:
        return 0.0
    return sum(abs(seq[i] - seq[i - 1]) for i in range(1, len(seq))) / (len(seq) - 1)


def step_lag_frames(alpha, reach=0.90):
    """Frames for the EMA to reach `reach` of a sudden step change."""
    if alpha >= 1.0:
        return 0.0
    return math.log(1.0 - reach) / math.log(1.0 - alpha)


def synthetic_trace(n=240, seed=7):
    """A realistic hybrid-style trace: a real steering path (straight -> right -> sharp
    right -> straight) quantized to bucket centers, with ~25% of frames flipped to a
    neighboring bucket to mimic the argmax blockiness."""
    random.seed(seed)
    bins = [(0, 45), (45, 60), (60, 75), (75, 85), (85, 95),
            (95, 105), (105, 120), (120, 135), (135, 180)]
    centers = [(a + b) / 2.0 for a, b in bins]
    out = []
    for i in range(n):
        t = i / n
        if t < 0.30:
            true = 90.0
        elif t < 0.50:
            true = 90.0 + (t - 0.30) / 0.20 * 30.0     # ease into a right turn (~120)
        elif t < 0.70:
            true = 120.0
        elif t < 0.85:
            true = 150.0                               # sharp right
        else:
            true = 95.0                                # back near straight
        k = min(range(9), key=lambda j: abs(centers[j] - true))   # nearest bucket
        if random.random() < 0.25:                                # argmax flip to a neighbor
            k = max(0, min(8, k + random.choice([-2, -1, 1, 2])))
        out.append(centers[k])
    return out


def load_csv(path, col, filter_col=None, filter_val=None):
    """Read numeric `col` from a CSV. If filter_col/filter_val are given, keep only rows
    where that column equals filter_val (e.g. Autonomous Mode == On) — so you tune on the
    frames the MODEL was driving, not manual takeovers."""
    vals, skipped = [], 0
    want = None if filter_val is None else str(filter_val).strip().lower()
    with open(path) as f:
        for row in _csv.DictReader(f):
            if filter_col:
                if str(row.get(filter_col, "")).strip().lower() != want:
                    skipped += 1
                    continue
            try:
                vals.append(float(row[col]))
            except (KeyError, ValueError, TypeError):
                pass
    if not vals:
        raise SystemExit(f"no numeric values in column '{col}' of {path}"
                         + (f" with {filter_col}=={filter_val}" if filter_col else ""))
    if filter_col:
        print(f"[filter] kept {len(vals)} rows where {filter_col}=={filter_val}  (skipped {skipped})")
    return vals


def main():
    ap = argparse.ArgumentParser(description="Tune STEERING_SMOOTH_ALPHA for the steering EMA.")
    ap.add_argument("--csv", help="CSV run log to read a steering column from")
    ap.add_argument("--col", default="steering", help="steering column name in --csv")
    ap.add_argument("--filter-col", help="only use rows where this column == --filter-val "
                                         "(e.g. 'Autonomous Mode (On/Off)')")
    ap.add_argument("--filter-val", help="value to match in --filter-col (e.g. On)")
    ap.add_argument("--values", help="comma-separated steering degrees to replay")
    ap.add_argument("--fps", type=float, default=15.0, help="control-loop frame rate (for lag in seconds)")
    ap.add_argument("--max-lag-s", type=float, default=0.25, help="max acceptable lag to reach 90%% of a turn")
    ap.add_argument("--alphas", default="0.2,0.25,0.3,0.4,0.5,0.6,0.8,1.0")
    ap.add_argument("--plot", help="optional PNG path (raw vs smoothed for a few alphas)")
    a = ap.parse_args()

    if a.values:
        raw = [float(x) for x in a.values.replace(" ", "").split(",") if x]
        src = "--values"
    elif a.csv:
        raw = load_csv(a.csv, a.col, a.filter_col, a.filter_val)
        src = f"{a.csv} [{a.col}]" + (f" where {a.filter_col}=={a.filter_val}" if a.filter_col else "")
    else:
        raw = synthetic_trace()
        src = "built-in synthetic blocky trace"

    raw_j = jitter(raw)
    alphas = [float(x) for x in a.alphas.split(",")]

    print(f"source: {src}   frames={len(raw)}   fps={a.fps:.0f}   lag budget={a.max_lag_s:.2f}s")
    print(f"raw jitter (alpha=1.0, no smoothing): {raw_j:.1f} deg/frame\n")
    print(f"{'alpha':>6} {'jitter':>9} {'jitter_cut':>11} {'lag_90%':>9} {'lag_s':>7}   verdict")
    print("-" * 62)
    for al in sorted(alphas):
        sm = ema(raw, al)
        j = jitter(sm)
        cut = 100.0 * (raw_j - j) / raw_j if raw_j > 0 else 0.0
        lf = step_lag_frames(al)
        ls = lf / a.fps if a.fps > 0 else 0.0
        verdict = "OK" if ls <= a.max_lag_s else "too laggy"
        if al >= 1.0:
            verdict = "raw (off)"
        print(f"{al:>6.2f} {j:>8.1f}° {cut:>10.0f}% {lf:>7.1f}f {ls:>6.2f}s   {verdict}")

    ok = [al for al in sorted(alphas) if step_lag_frames(al) / max(a.fps, 1e-6) <= a.max_lag_s and al < 1.0]
    rec = ok[0] if ok else max(al for al in alphas if al < 1.0)
    print("-" * 62)
    print(f"\nRecommended alpha ~= {rec:.2f}")
    print(f"  = the smoothest alpha that still reaches 90% of a turn within "
          f"{a.max_lag_s:.2f}s at {a.fps:.0f} fps.")
    print(f"  Set in code/controller/current/rc_car_app/config.py:  STEERING_SMOOTH_ALPHA = {rec:.2f}")
    print("  Then tune by feel on the car: corners late -> raise it; still twitchy -> lower it.")

    if a.plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            xs = list(range(len(raw)))
            fig, ax = plt.subplots(figsize=(10, 4), dpi=150)
            ax.plot(xs, raw, color="#cccccc", linewidth=1.0, label="raw (alpha=1.0)")
            for al in (0.6, rec, 0.25):
                ax.plot(xs, ema(raw, al), linewidth=1.8, label=f"alpha={al:.2f}")
            ax.set_xlabel("frame"); ax.set_ylabel("steering (deg)")
            ax.set_title("Steering EMA smoothing vs alpha"); ax.legend(); ax.grid(alpha=0.25)
            fig.tight_layout(); fig.savefig(a.plot); plt.close(fig)
            print(f"\n  plot saved: {a.plot}")
        except Exception as exc:
            print(f"\n  (plot skipped: {exc})")


if __name__ == "__main__":
    main()
