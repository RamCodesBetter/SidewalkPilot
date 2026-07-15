#!/usr/bin/env python3
"""List valid manual takeovers recorded in SidewalkPilot run CSV files.

A valid takeover is an autonomous-to-manual disengagement after a real autonomy
stint (six seconds by default) caused by steering, throttle, brake, or the
autonomy-toggle button. Planned navigation handoffs and destination arrivals
are not takeovers.

Examples:
  python3 code/test_files/data/takeover_log_report.py
  python3 code/test_files/data/takeover_log_report.py ~/logs/log_20260715_*.csv
  python3 code/test_files/data/takeover_log_report.py /nvme/logs --min-segment-seconds 6
  python3 code/test_files/data/takeover_log_report.py ~/logs --show-rejected
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


COL_CLOCK = "Current Time"
COL_ELAPSED = "Time Since Program Started (s)"
COL_AUTO = "Autonomous Mode (On/Off)"
COL_EVENT = "Intervention (Event)"
COL_CAUSE = "Intervention Cause"
COL_SPEED = "Current Speed (MPH)"
COL_STEER = "Steer (Value)"
COL_SERVO = "Steering Servo Deg"
COL_GAS = "Gas (Value)"
COL_BRAKE = "Brake (On/Off)"
COL_AEB = "AEB Enabled (On/Off)"
COL_PAYLOAD = "Dashboard JSON Payload"

REQUIRED_COLUMNS = {COL_ELAPSED, COL_AUTO}
MANUAL_CAUSES = {"steer", "throttle", "brake", "button"}


@dataclass(frozen=True)
class Disengagement:
    path: Path
    row_number: int
    clock: str
    elapsed_s: float
    segment_s: float
    cause: str
    speed_mph: float
    steer: float
    servo_deg: float | None
    gas: float
    brake: bool
    aeb_enabled: bool
    model: str
    valid: bool
    rejection: str = ""


def parse_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_optional_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "on", "yes"}


def normalize_cause(value: object) -> str:
    cause = str(value or "").strip().lower()
    if cause in {"steer", "steering", "str"}:
        return "steer"
    if cause in {"gas", "throttle", "tle"}:
        return "throttle"
    if cause in {"brake", "brk"}:
        return "brake"
    if cause in {"a", "button", "btn", "autonomy_button"}:
        return "button"
    if cause in {"arrival", "arrived", "destination", "arr"}:
        return "arrived"
    if cause in {"navigation", "nav", "operator", "segment"}:
        return "nav"
    return cause or "unknown"


def model_from_row(row: dict[str, str]) -> str:
    raw = row.get(COL_PAYLOAD, "")
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    for key in ("model", "model_version", "model_name"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def classify_disengagement(
    cause: str,
    segment_s: float,
    min_segment_s: float,
    allow_unknown: bool,
) -> tuple[bool, str]:
    if segment_s < min_segment_s:
        return False, f"segment shorter than {min_segment_s:g}s"
    if cause in MANUAL_CAUSES:
        return True, ""
    if cause == "unknown" and allow_unknown:
        return True, ""
    if cause in {"nav", "arrived"}:
        return False, "planned navigation transition"
    return False, f"non-manual or unknown cause: {cause}"


def read_disengagements(
    path: Path,
    min_segment_s: float,
    allow_unknown: bool = False,
) -> list[Disengagement]:
    results: list[Disengagement] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fields
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"missing required column(s): {names}")

        previous_auto = False
        segment_start_s: float | None = None
        for row_number, row in enumerate(reader, start=2):
            elapsed_s = parse_float(row.get(COL_ELAPSED))
            autonomous = parse_bool(row.get(COL_AUTO))

            if autonomous and not previous_auto:
                segment_start_s = elapsed_s

            falling_edge = previous_auto and not autonomous
            event = parse_bool(row.get(COL_EVENT))
            if (falling_edge or event) and segment_start_s is not None:
                cause = normalize_cause(row.get(COL_CAUSE))
                segment_s = max(0.0, elapsed_s - segment_start_s)
                valid, rejection = classify_disengagement(
                    cause,
                    segment_s,
                    min_segment_s,
                    allow_unknown,
                )
                results.append(
                    Disengagement(
                        path=path,
                        row_number=row_number,
                        clock=str(row.get(COL_CLOCK, "")).strip(),
                        elapsed_s=elapsed_s,
                        segment_s=segment_s,
                        cause=cause,
                        speed_mph=parse_float(row.get(COL_SPEED)),
                        steer=parse_float(row.get(COL_STEER)),
                        servo_deg=parse_optional_float(row.get(COL_SERVO)),
                        gas=parse_float(row.get(COL_GAS)),
                        brake=parse_bool(row.get(COL_BRAKE)),
                        aeb_enabled=parse_bool(row.get(COL_AEB)),
                        model=model_from_row(row),
                        valid=valid,
                        rejection=rejection,
                    )
                )
                segment_start_s = None

            previous_auto = autonomous

    return results


def resolve_csv_paths(inputs: Iterable[str]) -> list[Path]:
    patterns = list(inputs) or [str(Path.home() / "logs")]
    resolved: set[Path] = set()
    for raw in patterns:
        expanded = str(Path(raw).expanduser())
        matches = glob.glob(expanded) if glob.has_magic(expanded) else [expanded]
        for match in matches:
            path = Path(match)
            if path.is_dir():
                resolved.update(item.resolve() for item in path.glob("*.csv"))
            elif path.is_file() and path.suffix.lower() == ".csv":
                resolved.add(path.resolve())
    return sorted(resolved)


def format_number(value: float | None, width: int = 0) -> str:
    text = "-" if value is None else f"{value:.2f}"
    return f"{text:>{width}}" if width else text


def print_report(events: list[Disengagement], show_rejected: bool) -> None:
    shown = [event for event in events if event.valid or show_rejected]
    if not shown:
        print("No valid takeovers found.")
        return

    print(
        f"{'VALID':<5} {'FILE':<25} {'RUN(s)':>8} {'AUTO(s)':>8} "
        f"{'CAUSE':<8} {'MPH':>6} {'STEER':>7} {'SERVO':>7} "
        f"{'GAS':>6} {'BRK':>3} {'AEB':>3} {'MODEL':<10} TIME"
    )
    print("-" * 132)
    for event in shown:
        print(
            f"{('yes' if event.valid else 'no'):<5} "
            f"{event.path.name:<25.25} "
            f"{event.elapsed_s:>8.2f} {event.segment_s:>8.2f} "
            f"{event.cause:<8.8} {event.speed_mph:>6.2f} "
            f"{event.steer:>7.2f} {format_number(event.servo_deg, 7)} "
            f"{event.gas:>6.2f} {int(event.brake):>3} "
            f"{int(event.aeb_enabled):>3} {event.model:<10.10} {event.clock}"
        )
        if not event.valid:
            print(f"      rejected at CSV row {event.row_number}: {event.rejection}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show valid manual takeovers from SidewalkPilot run CSV logs."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="CSV file, directory, or glob; defaults to ~/logs",
    )
    parser.add_argument(
        "--min-segment-seconds",
        type=float,
        default=6.0,
        help="minimum autonomous segment duration (default: 6.0)",
    )
    parser.add_argument(
        "--allow-legacy-unknown",
        action="store_true",
        help="count unknown-cause falling edges from older logs as valid",
    )
    parser.add_argument(
        "--show-rejected",
        action="store_true",
        help="also print short segments and planned/non-manual disengagements",
    )
    args = parser.parse_args()

    if args.min_segment_seconds < 0:
        parser.error("--min-segment-seconds must be non-negative")

    paths = resolve_csv_paths(args.paths)
    if not paths:
        parser.error("no CSV logs matched the supplied paths")

    all_events: list[Disengagement] = []
    skipped = 0
    for path in paths:
        try:
            all_events.extend(
                read_disengagements(
                    path,
                    min_segment_s=args.min_segment_seconds,
                    allow_unknown=args.allow_legacy_unknown,
                )
            )
        except (OSError, csv.Error, ValueError) as exc:
            skipped += 1
            print(f"warning: skipped {path}: {exc}")

    print_report(all_events, args.show_rejected)
    valid_count = sum(event.valid for event in all_events)
    rejected_count = len(all_events) - valid_count
    print(
        f"\nScanned {len(paths)} CSV file(s): {valid_count} valid takeover(s), "
        f"{rejected_count} rejected disengagement(s), {skipped} skipped file(s)."
    )


if __name__ == "__main__":
    main()
