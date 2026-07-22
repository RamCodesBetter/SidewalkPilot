#!/usr/bin/env python3
"""Benchmark SidewalkPilot's real JPEG/TCP inference request path on one device.

The script launches the production inference server on loopback, sends 1280x720 BGR
frames through the production client, and measures JPEG encoding, socket round trip,
server preprocessing/model execution, and total request latency. It excludes camera
capture, the controller loop, PWM scheduling, and physical steering-servo movement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
SERVER = (
    REPO_ROOT
    / "code"
    / "controller"
    / "current"
    / "rc_car_app"
    / "jetson_inference_server.py"
)
CLIENT_DIR = SERVER.parent
DEFAULT_IMAGES = SCRIPT_DIR / "v41a_benchmark_sidewalks"
DEFAULT_MODEL_DIRS = [
    REPO_ROOT / "code" / "ai_models",
]
MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>\d+\.\d+[a-z]?)\.onnx$")

sys.path.insert(0, str(CLIENT_DIR))
from jetson_client import JetsonSteeringClient  # noqa: E402


def _version_key(version: str) -> tuple[int, int, str]:
    match = re.fullmatch(r"(\d+)\.(\d+)([a-z]?)", version)
    if match is None:
        raise ValueError(version)
    return int(match.group(1)), int(match.group(2)), match.group(3)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discover_models(model_dirs: list[Path]) -> dict[str, Path]:
    models: dict[str, Path] = {}
    for directory in model_dirs:
        if not directory.is_dir():
            continue
        for path in directory.glob("SidewalkPilot-v*.onnx"):
            match = MODEL_RE.fullmatch(path.name)
            if match:
                models[match.group("version")] = path.resolve()
    return models


def _fixture_hash(records: list[dict[str, Any]], image_dir: Path) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(str(record["file"]).encode("utf-8"))
        with (image_dir / str(record["file"])).open("rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


def _load_frames(image_dir: Path) -> tuple[list[np.ndarray], str]:
    manifest = json.loads((image_dir / "manifest.json").read_text(encoding="utf-8"))
    records = manifest.get("records", [])
    if not records:
        raise SystemExit(f"No fixture records in {image_dir / 'manifest.json'}")
    frames = []
    for record in records:
        frame = cv2.imread(str(image_dir / str(record["file"])), cv2.IMREAD_COLOR)
        if frame is None:
            raise SystemExit(f"Could not decode fixture {record['file']}")
        frames.append(cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_CUBIC))
    return frames, _fixture_hash(records, image_dir)


def _wait_for_server(port: int, process: subprocess.Popen[Any], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Inference server exited with code {process.returncode}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"Inference server did not listen on 127.0.0.1:{port}")


def _percentile(values: list[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": _percentile(values, 95.0),
        "p99": _percentile(values, 99.0),
        "min": min(values),
        "max": max(values),
    }


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    model_dirs = [path.expanduser().resolve() for path in args.models_dir]
    models = _discover_models(model_dirs)
    released_models_dir = (REPO_ROOT / "code" / "ai_models").resolve()
    extra_model_dirs = [
        directory for directory in model_dirs if directory != released_models_dir
    ]
    if len(extra_model_dirs) > 1:
        raise SystemExit(
            "The production inference server accepts one extra model directory; "
            f"received {extra_model_dirs}"
        )
    if args.versions.strip().lower() == "all":
        versions = sorted(models, key=_version_key)
    else:
        versions = [
            value.strip() for value in args.versions.split(",") if value.strip()
        ]
    missing = [version for version in versions if version not in models]
    if missing:
        raise SystemExit(f"Missing ONNX models: {missing}")
    frames, fixture_hash = _load_frames(args.images.expanduser().resolve())

    with tempfile.NamedTemporaryFile(
        prefix="sidewalkpilot-runtime-server-", suffix=".log", mode="w+"
    ) as server_log:
        command = [
            sys.executable,
            str(SERVER),
            "--model",
            "highest",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ]
        if extra_model_dirs:
            command.extend(["--models-dir", str(extra_model_dirs[0])])
        process = subprocess.Popen(
            command,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        client = JetsonSteeringClient(
            "127.0.0.1",
            port=args.port,
            jpeg_quality=80,
            timeout=args.timeout,
        )
        try:
            _wait_for_server(args.port, process, args.timeout)
            reports = []
            for model_index, version in enumerate(versions, start=1):
                print(
                    f"[{model_index:02d}/{len(versions):02d}] "
                    f"runtime path v{version}"
                )
                history = [90.0, 90.0, 90.0]
                for index in range(args.warmup):
                    result = client.infer(
                        frames[index % len(frames)],
                        model_version=version,
                        target_history=history,
                    )
                    if result is None:
                        raise RuntimeError(f"Warm-up request failed for v{version}")
                    history = (history + [float(result[0])])[-3:]

                encode_ms: list[float] = []
                socket_ms: list[float] = []
                server_ms: list[float] = []
                total_ms: list[float] = []
                for index in range(args.runs):
                    result = client.infer(
                        frames[index % len(frames)],
                        model_version=version,
                        target_history=history,
                    )
                    if result is None:
                        raise RuntimeError(f"Measured request failed for v{version}")
                    history = (history + [float(result[0])])[-3:]
                    encode_ms.append(client.jpeg_encode_ms)
                    socket_ms.append(client.socket_round_trip_ms)
                    server_ms.append(client.infer_ms)
                    total_ms.append(client.inference_request_ms)
                reports.append(
                    {
                        "version": version,
                        "series": int(version.split(".", 1)[0]),
                        "model_path": str(models[version]),
                        "model_sha256": _sha256(models[version]),
                        "model_size_mib": models[version].stat().st_size
                        / (1024.0 * 1024.0),
                        "warmup_runs": args.warmup,
                        "measured_runs": args.runs,
                        "input_bgr_shape": [1, 720, 1280, 3],
                        "jpeg_quality": 80,
                        "jpeg_encode_ms": _stats(encode_ms),
                        "socket_round_trip_ms": _stats(socket_ms),
                        "server_preprocess_and_model_ms": _stats(server_ms),
                        "total_inference_request_ms": _stats(total_ms),
                        "sequential_request_ips": 1000.0 / statistics.fmean(total_ms),
                    }
                )
        except Exception:
            server_log.flush()
            server_log.seek(0)
            print(server_log.read(), file=sys.stderr)
            raise
        finally:
            client.close()
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)

    report = {
        "schema_version": 1,
        "benchmark": "SidewalkPilot-loopback-runtime-inference-path-v1",
        "label": args.label,
        "timestamp_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scope": (
            "1280x720 BGR -> JPEG quality 80 -> loopback TCP -> server JPEG decode -> "
            "model preprocessing -> batch-one inference -> reply. Excludes camera, "
            "controller/PWM scheduling, and physical servo response."
        ),
        "fixture_count": len(frames),
        "fixture_sha256": fixture_hash,
        "model_count": len(reports),
        "models": reports,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Saved runtime-path report: {output}")
    return report


def _load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def compare_reports(args: argparse.Namespace) -> None:
    first = _load_report(args.baseline)
    second = _load_report(args.comparison)
    if first.get("benchmark") != second.get("benchmark"):
        raise SystemExit("Runtime reports use different benchmark definitions")
    first_models = {row["version"]: row for row in first["models"]}
    second_models = {row["version"]: row for row in second["models"]}
    if set(first_models) != set(second_models):
        raise SystemExit("Runtime reports do not contain the same models")
    print(f"\nRuntime inference path: {first['label']} -> {second['label']}")
    print(
        f"{'Model':>7} {'Pi total':>10} {'Jet total':>10} {'Total -%':>9} "
        f"{'Pi server':>10} {'Jet server':>10} {'Server -%':>10}"
    )
    family: dict[str, list[tuple[float, float]]] = {"Series 1/2": [], "Series 3/4": []}
    for version in sorted(first_models, key=_version_key):
        left = first_models[version]
        right = second_models[version]
        if left["model_sha256"] != right["model_sha256"]:
            raise SystemExit(f"v{version} model hashes differ")
        pi_total = left["total_inference_request_ms"]["mean"]
        jet_total = right["total_inference_request_ms"]["mean"]
        pi_server = left["server_preprocess_and_model_ms"]["mean"]
        jet_server = right["server_preprocess_and_model_ms"]["mean"]
        total_reduction = 100.0 * (1.0 - jet_total / pi_total)
        server_reduction = 100.0 * (1.0 - jet_server / pi_server)
        print(
            f"{('v' + version):>7} {pi_total:10.2f} {jet_total:10.2f} "
            f"{total_reduction:9.1f} {pi_server:10.2f} {jet_server:10.2f} "
            f"{server_reduction:10.1f}"
        )
        group = (
            "Series 1/2"
            if int(version.split(".", 1)[0]) <= 2
            else "Series 3/4"
        )
        family[group].append((total_reduction, server_reduction))
    print("\nFamily means (each model weighted equally)")
    for name, values in family.items():
        if not values:
            continue
        print(
            f"  {name}: total request latency "
            f"{statistics.fmean(v[0] for v in values):.1f}% "
            f"lower; server preprocess+model latency "
            f"{statistics.fmean(v[1] for v in values):.1f}% lower"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--models-dir", action="append", type=Path, default=None)
    run.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    run.add_argument("--versions", default="4.1a", help="comma list or 'all'")
    run.add_argument("--warmup", type=int, default=10)
    run.add_argument("--runs", type=int, default=100)
    run.add_argument("--port", type=int, default=18770)
    run.add_argument("--timeout", type=float, default=30.0)
    run.add_argument("--label", required=True)
    run.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("comparison", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        args.models_dir = args.models_dir or DEFAULT_MODEL_DIRS
        run_benchmark(args)
    else:
        compare_reports(args)


if __name__ == "__main__":
    main()
