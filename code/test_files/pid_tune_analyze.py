#!/usr/bin/env python3
"""pid_tune_analyze.py -- turn SidewalkPilot run logs into yaw-PID tuning numbers.

Runs on the Jetson ("Jon"), reading the CSV logs the Pi ships to /nvme/logs. For the
straight-hold samples (moving, commanded ~center) it pulls the yaw rate + PID
correction out of the logged dashboard JSON payload and reports how well the loop
holds straight -- so you tune from DATA instead of by feel.

Per run + aggregate:
  - yaw bias (mean dps)   : steady lean   -> FF slightly off / needs a touch of kI
  - yaw jitter (RMS dps)  : wander off straight (lower = better hold)
  - yaw peak (max |dps|)
  - oscillation (Hz)      : yaw zero-crossing rate -> weaving = kP too high
  - per-speed-bin breakdown: jitter should be ~flat across speed after speed-norm (A)

Usage (on Jon):
  python3 pid_tune_analyze.py
  python3 pid_tune_analyze.py --logs-dir /nvme/logs --output /nvme/logs/pid_tune_report.json
"""
import argparse
import csv
import glob
import json
import math
import os

MPH_TO_MPS = 0.44704
COL_TIME = "Time Since Program Started (s)"
COL_SPEED = "Current Speed (MPH)"
COL_JSON = "Dashboard JSON Payload"
MAX_DT_S = 1.0                       # a gap larger than this breaks a contiguous segment
SPEED_BINS = [(0.3, 0.7), (0.7, 1.1), (1.1, 1.5), (1.5, 9.9)]


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _payload(row):
    raw = row.get(COL_JSON, "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def collect(path, min_speed_mps, band_deg):
    """Straight-hold samples (t, speed_mps, yaw_dps, corr_deg) from one CSV."""
    samples = []
    try:
        with open(path, newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or COL_JSON not in reader.fieldnames:
                return samples
            for row in reader:
                payload = _payload(row)
                if payload is None:
                    continue
                speed = _f(row.get(COL_SPEED)) * MPH_TO_MPS
                cmd = _f(payload.get("steering_cmd_deg", 90.0), 90.0)
                if speed < min_speed_mps or abs(cmd - 90.0) > band_deg:
                    continue                       # only moving, straight-hold samples
                samples.append((
                    _f(row.get(COL_TIME)),
                    speed,
                    _f(payload.get("yaw_rate_dps")),
                    _f(payload.get("yaw_pid_correction_deg")),
                ))
    except Exception as exc:
        print(f"  ! skipped {os.path.basename(path)}: {exc}")
    return samples


def _rms(vals):
    return math.sqrt(sum(v * v for v in vals) / len(vals)) if vals else 0.0


def _zero_cross_hz(samples):
    """Yaw sign-change rate (Hz) within contiguous (dt<=MAX_DT_S) runs; 2 crossings/cycle."""
    crossings = 0
    duration = 0.0
    prev_t = prev_yaw = None
    for t, _speed, yaw, _corr in samples:
        if prev_t is not None and (t - prev_t) <= MAX_DT_S:
            duration += (t - prev_t)
            if prev_yaw is not None and ((prev_yaw < 0) != (yaw < 0)):
                crossings += 1
        prev_t, prev_yaw = t, yaw
    return (crossings / (2.0 * duration)) if duration > 0 else 0.0


def stats(samples):
    if not samples:
        return None
    yaws = [s[2] for s in samples]
    return {
        "samples": len(yaws),
        "yaw_bias_dps": round(sum(yaws) / len(yaws), 2),
        "yaw_rms_dps": round(_rms(yaws), 2),
        "yaw_peak_dps": round(max(abs(y) for y in yaws), 1),
        "osc_hz": round(_zero_cross_hz(samples), 2),
        "corr_rms_deg": round(_rms([s[3] for s in samples]), 2),
    }


def main():
    ap = argparse.ArgumentParser(description="Analyze yaw-PID hold quality from run logs")
    ap.add_argument("--logs-dir", default="/nvme/logs")
    ap.add_argument("--log", default=None,
                    help="analyze ONE log (name or path, .csv optional); overrides the --logs-dir sweep")
    ap.add_argument("--latest-log", action="store_true",
                    help="analyze only the most recently modified log in --logs-dir")
    ap.add_argument("--output", default="/nvme/logs/pid_tune_report.json")
    ap.add_argument("--min-speed", type=float, default=0.3, help="m/s; ignore near-stationary samples")
    ap.add_argument("--straight-band", type=float, default=8.0, help="deg; |cmd-90| within this = straight-hold")
    args = ap.parse_args()

    logs_dir = os.path.expanduser(args.logs_dir)
    if args.log:
        cand = os.path.expanduser(args.log)
        tries = [cand, cand + ".csv", os.path.join(logs_dir, cand), os.path.join(logs_dir, cand + ".csv")]
        match = next((p for p in tries if os.path.isfile(p)), None)
        if not match:
            raise SystemExit(f"Log not found: {args.log} (looked as-is and in {logs_dir})")
        paths = [match]
    elif args.latest_log:
        csvs = glob.glob(os.path.join(logs_dir, "*.csv"))
        if not csvs:
            raise SystemExit(f"No CSV logs in {args.logs_dir}")
        paths = [max(csvs, key=os.path.getmtime)]
        print(f"Latest log: {os.path.basename(paths[0])}")
    else:
        paths = sorted(glob.glob(os.path.join(logs_dir, "*.csv")))
        if not paths:
            raise SystemExit(f"No CSV logs in {args.logs_dir}")

    all_samples, per_file = [], []
    for p in paths:
        s = collect(p, args.min_speed, args.straight_band)
        if s:
            all_samples.extend(s)
            st = stats(s)
            st["file"] = os.path.basename(p)
            per_file.append(st)
    if not all_samples:
        raise SystemExit("No straight-hold samples (need logged dashboard JSON with yaw_rate_dps).")

    overall = stats(all_samples)
    by_speed = {}
    for lo, hi in SPEED_BINS:
        seg = [s for s in all_samples if lo <= s[1] < hi]
        if seg:
            st = stats(seg)
            by_speed[f"{lo:.1f}-{hi:.1f} m/s"] = {
                "yaw_rms_dps": st["yaw_rms_dps"], "osc_hz": st["osc_hz"], "samples": st["samples"]}

    hints = []
    if overall["osc_hz"] >= 1.0 and overall["yaw_rms_dps"] >= 8.0:
        hints.append("Weaving (high oscillation + jitter) -> kP too high; lower it, or add a little kD.")
    if abs(overall["yaw_bias_dps"]) >= 5.0:
        side = "left" if overall["yaw_bias_dps"] > 0 else "right"
        hints.append(f"Steady {side} lean ({overall['yaw_bias_dps']:+} dps) -> FF slightly off or add a small kI.")
    if by_speed:
        rmses = [v["yaw_rms_dps"] for v in by_speed.values()]
        if max(rmses) >= 2.0 * max(0.1, min(rmses)):
            hints.append("Jitter varies strongly with speed -> speed-norm (A) not flat; check REF_SPEED.")
    if overall["yaw_rms_dps"] < 4.0 and overall["osc_hz"] < 1.0:
        hints.append("Holds straight well (low jitter, low oscillation) -- good gains.")
    if not hints:
        hints.append("No strong signal; collect a longer straight-hold run.")

    report = {
        "logs_dir": os.path.abspath(os.path.expanduser(args.logs_dir)),
        "files": len(per_file), "overall": overall, "by_speed": by_speed,
        "per_file": per_file, "hints": hints,
    }
    out = os.path.abspath(os.path.expanduser(args.output))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)

    print(f"Straight-hold analysis over {len(per_file)} log(s), {overall['samples']} samples")
    print(f"  yaw bias   : {overall['yaw_bias_dps']:+.2f} dps   (steady lean)")
    print(f"  yaw jitter : {overall['yaw_rms_dps']:.2f} dps RMS  (lower = holds straighter)")
    print(f"  yaw peak   : {overall['yaw_peak_dps']:.1f} dps")
    print(f"  oscillation: {overall['osc_hz']:.2f} Hz          (high = weaving = kP too high)")
    print(f"  correction : {overall['corr_rms_deg']:.2f} deg RMS")
    if by_speed:
        print("  by speed (jitter should be ~flat across bins after speed-norm):")
        for k, v in by_speed.items():
            print(f"    {k:>12}: RMS {v['yaw_rms_dps']:5.2f} dps, osc {v['osc_hz']:.2f} Hz, n={v['samples']}")
    print("  ---")
    for h in hints:
        print(f"  * {h}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
