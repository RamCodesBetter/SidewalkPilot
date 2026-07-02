#!/usr/bin/env python3
"""autonomy_metrics.py -- compute SidewalkPilot autonomy metrics from runtime CSV logs.

Reads the runtime CSV run logs (default ~/logs/*.csv) and computes, from the columns
that actually exist ("Time Since Program Started (s)", "Autonomous Mode (On/Off)",
"Current Speed (MPH)"):

  - autonomous_distance_km            : speed x dt integrated while Autonomous Mode == 1
  - interventions_per_km              : count of autonomous->manual (1->0) takeovers / auto km
  - avg_uninterrupted_autonomous_min  : mean duration of continuous autonomous stretches

Success rate is NOT in the CSV (there is no segment/route-completion field), so it is
tallied by hand: pass --segments-completed and --segments-attempted and it is merged in.

Writes a JSON summary (default /nvme/logs/autonomy_metrics.json on the Jetson "Jon").
Intended flow: sync ~/logs from the Pi to Jon, then run this on Jon.

Usage:
  python3 autonomy_metrics.py
  python3 autonomy_metrics.py --logs-dir ~/logs --output /nvme/logs/autonomy_metrics.json \
      --segments-completed 76 --segments-attempted 77
"""
import argparse
import csv
import datetime
import glob
import json
import os

MPH_TO_KM = 1.609344
COL_TIME = "Time Since Program Started (s)"
COL_AUTO = "Autonomous Mode (On/Off)"
COL_SPEED = "Current Speed (MPH)"
MAX_DT_S = 5.0   # cap between-row gaps so a paused/reconnecting log can't inflate totals


def _f(row, key, default=0.0):
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def analyze_file(path):
    """Per-file metrics, or None if the file is unreadable / has no Autonomous column."""
    auto_km = total_km = auto_time_s = 0.0
    interventions = 0
    stretches = []           # duration (s) of each continuous autonomous run
    cur_stretch = 0.0
    prev_t = None
    prev_auto = 0
    rows = 0
    try:
        with open(path, newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or COL_AUTO not in reader.fieldnames:
                return None
            for row in reader:
                rows += 1
                t = _f(row, COL_TIME)
                auto = 1 if str(row.get(COL_AUTO, "0")).strip() in ("1", "1.0", "True", "true") else 0
                speed = _f(row, COL_SPEED)
                if prev_t is not None:
                    dt = t - prev_t
                    if dt < 0.0 or dt > MAX_DT_S:
                        dt = 0.0
                    dist_km = speed * (dt / 3600.0) * MPH_TO_KM
                    total_km += dist_km
                    if auto:
                        auto_km += dist_km
                        auto_time_s += dt
                        cur_stretch += dt
                if prev_auto == 1 and auto == 0:          # autonomous -> manual = a takeover
                    interventions += 1
                    if cur_stretch > 0.0:
                        stretches.append(cur_stretch)
                    cur_stretch = 0.0
                prev_t = t
                prev_auto = auto
            if cur_stretch > 0.0:                          # stretch still open at EOF (not a takeover)
                stretches.append(cur_stretch)
    except Exception as exc:
        print(f"  ! skipped {os.path.basename(path)}: {exc}")
        return None
    if rows == 0:
        return None
    return {
        "file": os.path.basename(path),
        "rows": rows,
        "autonomous_distance_km": auto_km,
        "total_distance_km": total_km,
        "interventions": interventions,
        "autonomous_segments": len(stretches),
        "autonomous_time_s": auto_time_s,
        "_stretches_s": stretches,
    }


def main():
    ap = argparse.ArgumentParser(description="Compute SidewalkPilot autonomy metrics from CSV logs")
    ap.add_argument("--logs-dir", default=os.path.expanduser("~/logs"),
                    help="directory of *.csv run logs (default: ~/logs)")
    ap.add_argument("--output", default="/nvme/logs/autonomy_metrics.json",
                    help="where to write the JSON summary (default: /nvme/logs/autonomy_metrics.json)")
    ap.add_argument("--segments-completed", type=int, default=None,
                    help="segments completed (hand-tallied; enables success rate)")
    ap.add_argument("--segments-attempted", type=int, default=None,
                    help="segments attempted (hand-tallied; enables success rate)")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(os.path.expanduser(args.logs_dir), "*.csv")))
    if not paths:
        raise SystemExit(f"No CSV logs found in {args.logs_dir}")

    per_file = [m for m in (analyze_file(p) for p in paths) if m]
    if not per_file:
        raise SystemExit("No readable logs with an 'Autonomous Mode (On/Off)' column.")

    auto_km = sum(m["autonomous_distance_km"] for m in per_file)
    total_km = sum(m["total_distance_km"] for m in per_file)
    interventions = sum(m["interventions"] for m in per_file)
    auto_time_s = sum(m["autonomous_time_s"] for m in per_file)
    all_stretches = [s for m in per_file for s in m["_stretches_s"]]
    n_seg = len(all_stretches)

    interv_per_km = (interventions / auto_km) if auto_km > 0 else None
    avg_stretch_min = (sum(all_stretches) / n_seg / 60.0) if n_seg else 0.0

    success_rate = None
    if args.segments_completed is not None and args.segments_attempted:
        success_rate = 100.0 * args.segments_completed / args.segments_attempted

    result = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "logs_dir": os.path.abspath(os.path.expanduser(args.logs_dir)),
        "files_analyzed": len(per_file),
        "autonomous_distance_km": round(auto_km, 3),
        "total_distance_km": round(total_km, 3),
        "interventions": interventions,
        "interventions_per_km": round(interv_per_km, 3) if interv_per_km is not None else None,
        "autonomous_segments": n_seg,
        "avg_uninterrupted_autonomous_min": round(avg_stretch_min, 2),
        "total_autonomous_min": round(auto_time_s / 60.0, 2),
        "success_rate_pct": round(success_rate, 1) if success_rate is not None else None,
        "segments_completed": args.segments_completed,
        "segments_attempted": args.segments_attempted,
        "per_file": [{k: (round(v, 3) if isinstance(v, float) else v)
                      for k, v in m.items() if k != "_stretches_s"} for m in per_file],
    }

    out = os.path.abspath(os.path.expanduser(args.output))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"Analyzed {len(per_file)} log(s) from {os.path.expanduser(args.logs_dir)}")
    print(f"  Autonomous distance : {auto_km:.2f} km  (of {total_km:.2f} km total driven)")
    line = f"  Interventions       : {interventions}"
    if interv_per_km is not None:
        line += f"  ({interv_per_km:.2f}/km)"
    print(line)
    print(f"  Autonomous segments : {n_seg}, avg uninterrupted {avg_stretch_min:.1f} min")
    print(f"  Total autonomous    : {auto_time_s / 60.0:.1f} min")
    if success_rate is not None:
        print(f"  Success rate        : {success_rate:.1f}%  ({args.segments_completed}/{args.segments_attempted})")
    else:
        print("  Success rate        : pass --segments-completed/--segments-attempted to include")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
