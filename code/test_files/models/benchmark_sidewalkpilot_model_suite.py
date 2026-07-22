#!/usr/bin/env python3
"""Run and compare the full SidewalkPilot ONNX model suite across devices."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
BENCHMARK_SCRIPT = SCRIPT_DIR / "benchmark_v41a_devices.py"
DEFAULT_IMAGES = SCRIPT_DIR / "v41a_benchmark_sidewalks"
DEFAULT_MODEL_DIRS = [
    REPO_ROOT / "code" / "ai_models",
]
MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>\d+\.\d+[a-z]?)\.onnx$")


def _version_key(version: str) -> tuple[int, int, str]:
    match = re.fullmatch(r"(\d+)\.(\d+)([a-z]?)", version)
    if match is None:
        raise ValueError(f"Invalid model version: {version}")
    return int(match.group(1)), int(match.group(2)), match.group(3)


def _series(version: str) -> int:
    return int(version.split(".", 1)[0])


def discover_models(model_dirs: list[Path]) -> list[tuple[str, Path]]:
    discovered: dict[str, Path] = {}
    for directory in model_dirs:
        if not directory.is_dir():
            continue
        for path in directory.glob("SidewalkPilot-v*.onnx"):
            match = MODEL_RE.fullmatch(path.name)
            if match is None:
                continue
            version = match.group("version")
            previous = discovered.get(version)
            if previous is not None and previous.resolve() != path.resolve():
                raise SystemExit(
                    f"Duplicate ONNX model v{version}: {previous} and {path}"
                )
            discovered[version] = path.resolve()
    return sorted(discovered.items(), key=lambda item: _version_key(item[0]))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read {path}: {exc}") from exc


def run_suite(args: argparse.Namespace) -> dict[str, Any]:
    model_dirs = [path.expanduser().resolve() for path in args.models_dir]
    models = discover_models(model_dirs)
    if not models:
        raise SystemExit(f"No SidewalkPilot ONNX models found in {model_dirs}")
    if args.require_all and len(models) != 52:
        found_series = {series: 0 for series in range(1, 5)}
        for version, _path in models:
            found_series[_series(version)] += 1
        raise SystemExit(
            "Expected all 52 models (30 Series 1/2 and 22 Series 3/4), found "
            f"{len(models)} with counts {found_series}. Run "
            "export_series12_benchmark_onnx.py first."
        )

    reports: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="sidewalkpilot-model-suite-") as temp:
        temp_dir = Path(temp)
        for index, (version, model_path) in enumerate(models, start=1):
            report_path = temp_dir / f"v{version}.json"
            command = [
                sys.executable,
                str(BENCHMARK_SCRIPT),
                "run",
                "--model",
                str(model_path),
                "--images",
                str(args.images.expanduser().resolve()),
                "--provider",
                args.provider,
                "--label",
                args.label,
                "--warmup",
                str(args.warmup),
                "--runs",
                str(args.runs),
                "--output",
                str(report_path),
            ]
            print(
                f"[{index:02d}/{len(models):02d}] v{version} on "
                f"{args.label or 'this device'}",
                flush=True,
            )
            completed = subprocess.run(
                command,
                check=False,
                text=True,
                stdout=None if args.verbose else subprocess.DEVNULL,
                stderr=None,
            )
            if completed.returncode != 0:
                raise SystemExit(
                    f"Benchmark failed for v{version} with exit code "
                    f"{completed.returncode}"
                )
            report = _load_json(report_path)
            if report["model"].get("version") != version:
                raise SystemExit(
                    f"Report/model mismatch: expected v{version}, got "
                    f"{report['model'].get('version')}"
                )
            reports.append(report)

    suite = {
        "schema_version": 1,
        "benchmark": "SidewalkPilot-full-model-device-suite-v1",
        "timestamp_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "label": args.label or reports[0]["label"],
        "provider": reports[0]["runtime"]["primary_provider"],
        "model_count": len(reports),
        "models": reports,
    }
    args.output.expanduser().resolve().write_text(
        json.dumps(suite, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Saved {len(reports)} model reports to {args.output}")
    return suite


def _reports_by_version(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(report["model"]["version"]): report for report in suite.get("models", [])
    }


def _geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0.0 for value in values):
        return float("nan")
    return math.exp(sum(math.log(value) for value in values) / len(values))


def _format_optional(value: float | None, width: int = 8) -> str:
    return f"{value:{width}.1f}" if value is not None else f"{'n/a':>{width}}"


def compare_suites(args: argparse.Namespace) -> dict[str, Any]:
    baseline = _load_json(args.baseline.expanduser().resolve())
    comparison = _load_json(args.comparison.expanduser().resolve())
    if baseline.get("benchmark") != comparison.get("benchmark"):
        raise SystemExit("Suite files use different benchmark definitions.")

    baseline_models = _reports_by_version(baseline)
    comparison_models = _reports_by_version(comparison)
    versions = sorted(
        set(baseline_models) & set(comparison_models), key=_version_key
    )
    missing = (set(baseline_models) ^ set(comparison_models))
    if missing and not args.allow_missing:
        raise SystemExit(
            f"Device suites do not contain the same models: {sorted(missing)}"
        )

    rows: list[dict[str, Any]] = []
    for version in versions:
        first = baseline_models[version]
        second = comparison_models[version]
        if first["model"]["sha256"] != second["model"]["sha256"]:
            raise SystemExit(f"v{version} model hashes differ between devices")
        if first["fixtures"]["set_sha256"] != second["fixtures"]["set_sha256"]:
            raise SystemExit(f"v{version} fixture hashes differ between devices")
        first_perf = first["performance"]
        second_perf = second["performance"]
        speedup = second_perf["ips"] / first_perf["ips"]
        mean_reduction = 1.0 - (
            second_perf["latency_mean_ms"] / first_perf["latency_mean_ms"]
        )
        rows.append(
            {
                "version": version,
                "series": _series(version),
                "baseline_ips": first_perf["ips"],
                "comparison_ips": second_perf["ips"],
                "speedup_x": speedup,
                "throughput_gain_percent": 100.0 * (speedup - 1.0),
                "baseline_mean_ms": first_perf["latency_mean_ms"],
                "comparison_mean_ms": second_perf["latency_mean_ms"],
                "mean_latency_reduction_percent": 100.0 * mean_reduction,
                "baseline_effective_cpu_cores": first_perf.get(
                    "inference_effective_cpu_cores"
                ),
                "comparison_effective_cpu_cores": second_perf.get(
                    "inference_effective_cpu_cores"
                ),
                "baseline_rss_delta_mib": first["memory"][
                    "warm_process_rss_delta_mib"
                ],
                "comparison_rss_delta_mib": second["memory"][
                    "warm_process_rss_delta_mib"
                ],
                "comparison_cuda_visible_delta_mib": second["memory"].get(
                    "warm_cuda_visible_used_delta_mib"
                ),
                "model_file_mib": first["model"]["size_mib"],
            }
        )

    print(
        f"\nSidewalkPilot model suite: {baseline['label']} -> {comparison['label']}"
    )
    print(
        f"{'Model':>7} {'S':>2} {'Pi IPS':>9} {'Jetson IPS':>11} {'Gain %':>8} "
        f"{'Pi mean':>9} {'Jet mean':>9} {'Lat -%':>8} {'Pi CPU':>7} "
        f"{'Jet CPU':>7} {'File':>7} {'Pi RSS':>8} {'Jet RSS':>8} {'CUDA':>8}"
    )
    for row in rows:
        print(
            f"{('v' + row['version']):>7} {row['series']:2d} "
            f"{row['baseline_ips']:9.2f} {row['comparison_ips']:11.2f} "
            f"{row['throughput_gain_percent']:8.1f} "
            f"{row['baseline_mean_ms']:9.2f} {row['comparison_mean_ms']:9.2f} "
            f"{row['mean_latency_reduction_percent']:8.1f} "
            f"{row['baseline_effective_cpu_cores']:7.2f} "
            f"{row['comparison_effective_cpu_cores']:7.2f} "
            f"{row['model_file_mib']:7.1f} "
            f"{row['baseline_rss_delta_mib']:8.1f} "
            f"{row['comparison_rss_delta_mib']:8.1f} "
            f"{_format_optional(row['comparison_cuda_visible_delta_mib'])}"
        )

    family_specs = [
        ("Series 1/2", {1, 2}),
        ("Series 3/4", {3, 4}),
        ("All models", {1, 2, 3, 4}),
    ]
    summaries: list[dict[str, Any]] = []
    print("\nFamily summaries (each model weighted equally)")
    print(
        f"{'Family':12} {'Models':>6} {'Geo speedup':>12} "
        f"{'Mean gain %':>12} {'Mean latency -%':>16}"
    )
    for name, included_series in family_specs:
        selected = [row for row in rows if row["series"] in included_series]
        speedups = [row["speedup_x"] for row in selected]
        gains = [row["throughput_gain_percent"] for row in selected]
        reductions = [row["mean_latency_reduction_percent"] for row in selected]
        summary = {
            "family": name,
            "model_count": len(selected),
            "geometric_mean_speedup_x": _geometric_mean(speedups),
            "mean_throughput_gain_percent": sum(gains) / len(gains),
            "mean_latency_reduction_percent": sum(reductions) / len(reductions),
        }
        summaries.append(summary)
        print(
            f"{name:12} {summary['model_count']:6d} "
            f"{summary['geometric_mean_speedup_x']:12.3f} "
            f"{summary['mean_throughput_gain_percent']:12.1f} "
            f"{summary['mean_latency_reduction_percent']:16.1f}"
        )

    result = {
        "schema_version": 1,
        "benchmark": "SidewalkPilot-full-model-device-comparison-v1",
        "baseline": baseline["label"],
        "comparison": comparison["label"],
        "rows": rows,
        "family_summaries": summaries,
        "claim_note": (
            "Throughput and latency cover batch-one local ONNX model execution only. "
            "They are not camera-to-servo end-to-end measurements."
        ),
    }
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"\nSaved comparison: {output}")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark and compare all SidewalkPilot ONNX models."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run every discovered model on one device")
    run.add_argument(
        "--models-dir",
        action="append",
        type=Path,
        default=None,
        help=(
            "repeatable; defaults to the canonical code/ai_models directory"
        ),
    )
    run.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    run.add_argument("--provider", choices=("auto", "cpu", "cuda"), default="auto")
    run.add_argument("--label", required=True)
    run.add_argument("--warmup", type=int, default=20)
    run.add_argument("--runs", type=int, default=200)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument(
        "--require-all", action=argparse.BooleanOptionalAction, default=True
    )
    run.add_argument("--verbose", action="store_true")

    compare = subparsers.add_parser(
        "compare", help="compare two device suite JSON files"
    )
    compare.add_argument("baseline", type=Path)
    compare.add_argument("comparison", type=Path)
    compare.add_argument("--allow-missing", action="store_true")
    compare.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        args.models_dir = args.models_dir or DEFAULT_MODEL_DIRS
        args.output = args.output.expanduser().resolve()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        run_suite(args)
    else:
        compare_suites(args)


if __name__ == "__main__":
    main()
