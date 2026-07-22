#!/usr/bin/env python3
"""Benchmark the same SidewalkPilot v4.1a FP32 ONNX model on Pi and Jetson.

Run this file once on each device, then compare the two JSON reports:

    python3 code/test_files/models/benchmark_v41a_devices.py run \
        --label raspberry-pi-5 --provider cpu --output /tmp/rpi5-v4.1a.json

    python3 code/test_files/models/benchmark_v41a_devices.py run \
        --label jetson-orin-nano --provider cuda --output /tmp/jetson-v4.1a.json

    python3 code/test_files/models/benchmark_v41a_devices.py compare \
        /tmp/rpi5-v4.1a.json /tmp/jetson-v4.1a.json

The timed section measures local batch-one ``InferenceSession.run`` calls. It does
not include camera capture, JPEG encoding, Ethernet transfer, preprocessing, or
servo response. Process RSS is useful on both devices, but it may not include all
CUDA allocations on a Jetson. The system-memory delta is reported alongside RSS
because Jetson CPU and GPU share physical LPDDR5 memory.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError as exc:  # pragma: no cover - depends on the target device
    raise SystemExit(
        "onnxruntime is required. Install the CPU build on Raspberry Pi 5 and "
        "the JetPack-matched GPU build on Jetson Orin Nano."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = REPO_ROOT / "code" / "ai_models" / "SidewalkPilot-v4.1a.onnx"
DEFAULT_IMAGES = Path(__file__).resolve().parent / "v41a_benchmark_sidewalks"
MIB = 1024.0 * 1024.0


def _read_text(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip("\x00\n ")
    except OSError:
        return ""


def _device_name() -> str:
    model = _read_text("/proc/device-tree/model")
    if model:
        return model
    return platform.node() or "unknown-device"


def _cpu_name() -> str:
    for line in _read_text("/proc/cpuinfo").splitlines():
        if line.lower().startswith(("model name", "hardware")) and ":" in line:
            return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def _proc_memory_bytes() -> tuple[int, int]:
    values: dict[str, int] = {}
    for line in _read_text("/proc/self/status").splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value, *_units = line.split()
            values[key.rstrip(":")] = int(value) * 1024
    return values.get("VmRSS", 0), values.get("VmHWM", 0)


def _system_memory_bytes() -> tuple[int, int]:
    values: dict[str, int] = {}
    for line in _read_text("/proc/meminfo").splitlines():
        if line.startswith(("MemTotal:", "MemAvailable:")):
            key, value, *_units = line.split()
            values[key.rstrip(":")] = int(value) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    return total, max(0, total - available)


def _memory_snapshot() -> dict[str, float]:
    rss, hwm = _proc_memory_bytes()
    system_total, system_used = _system_memory_bytes()
    return {
        "process_rss_mib": rss / MIB,
        "process_peak_rss_mib": hwm / MIB,
        "system_total_mib": system_total / MIB,
        "system_used_mib": system_used / MIB,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _provider_list(requested: str) -> list[str]:
    available = ort.get_available_providers()
    if requested == "cpu":
        if "CPUExecutionProvider" not in available:
            raise SystemExit(f"CPUExecutionProvider is unavailable: {available}")
        return ["CPUExecutionProvider"]
    if requested == "cuda":
        if "CUDAExecutionProvider" not in available:
            raise SystemExit(
                "CUDAExecutionProvider was requested but is unavailable. Install the "
                "JetPack-matched ONNX Runtime GPU build. Available providers: "
                f"{available}"
            )
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if "CPUExecutionProvider" in available:
        return ["CPUExecutionProvider"]
    raise SystemExit(f"No supported ONNX Runtime provider is available: {available}")


def _fixture_set_hash(records: list[dict[str, Any]], image_dir: Path) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(str(record["file"]).encode("utf-8"))
        digest.update(json.dumps(record["target_history"]).encode("utf-8"))
        with (image_dir / str(record["file"])).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _load_fixture_manifest(image_dir: Path) -> tuple[list[dict[str, Any]], str]:
    manifest_path = image_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"Could not read fixture manifest {manifest_path}: {exc}"
        ) from exc
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise SystemExit(f"Fixture manifest has no image records: {manifest_path}")
    for record in records:
        path = image_dir / str(record.get("file", ""))
        history = record.get("target_history")
        if not path.is_file() or not isinstance(history, list) or len(history) != 3:
            raise SystemExit(f"Invalid fixture record in {manifest_path}: {record}")
    return records, _fixture_set_hash(records, image_dir)


def _fixture_feed(
    record: dict[str, Any], image_dir: Path, image_name: str, history_name: str
) -> dict[str, np.ndarray]:
    path = image_dir / str(record["file"])
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"Could not decode fixture image: {path}")
    if image.shape[:2] != (180, 320):
        image = cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)
    tensor = image.astype(np.float32) / 255.0
    tensor = (tensor - 0.5) / 0.5
    tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...].astype(np.float32)
    history = np.asarray([record["target_history"]], dtype=np.float32)
    return {image_name: tensor, history_name: history}


def _validate_contract(session: "ort.InferenceSession") -> tuple[str, str]:
    inputs = session.get_inputs()
    image = next((item for item in inputs if len(item.shape) == 4), None)
    history = next((item for item in inputs if item.name == "target_history"), None)
    output = session.get_outputs()[0]
    if image is None or list(image.shape[1:]) != [3, 180, 320]:
        details = [(item.name, item.shape) for item in inputs]
        raise SystemExit(f"Unexpected v4.1a image input: {details}")
    if history is None or list(history.shape[1:]) != [3]:
        details = [(item.name, item.shape) for item in inputs]
        raise SystemExit(f"Unexpected v4.1a history input: {details}")
    if list(output.shape[1:]) != [4, 18]:
        raise SystemExit(f"Unexpected v4.1a output: {(output.name, output.shape)}")
    if image.type != "tensor(float)" or history.type != "tensor(float)":
        raise SystemExit(
            f"Expected FP32 inputs, got image={image.type}, history={history.type}"
        )
    return image.name, history.name


def _percentile(values: list[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _delta(after: dict[str, float], before: dict[str, float], key: str) -> float:
    return float(after[key] - before[key])


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    model_path = args.model.expanduser().resolve()
    image_dir = args.images.expanduser().resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model not found: {model_path}")
    if args.warmup < 1 or args.runs < 2:
        raise SystemExit("Use at least 1 warm-up and 2 measured inferences.")

    gc.collect()
    memory_before_load = _memory_snapshot()
    providers = _provider_list(args.provider)
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    load_started = time.perf_counter()
    session = ort.InferenceSession(
        str(model_path), sess_options=options, providers=providers
    )
    load_seconds = time.perf_counter() - load_started
    image_name, history_name = _validate_contract(session)
    providers_used = session.get_providers()
    primary_provider = providers_used[0]
    if args.provider == "cuda" and primary_provider != "CUDAExecutionProvider":
        raise SystemExit(
            f"CUDA was requested but the active provider is {providers_used}"
        )
    memory_after_load = _memory_snapshot()

    records, fixture_hash = _load_fixture_manifest(image_dir)

    output_shape: list[int] | None = None
    for index in range(args.warmup):
        feeds = _fixture_feed(
            records[index % len(records)], image_dir, image_name, history_name
        )
        output = session.run(None, feeds)[0]
        output_shape = list(output.shape)
    memory_after_warmup = _memory_snapshot()

    latencies_ms: list[float] = []
    preprocessing_ms: list[float] = []
    measured_started = time.perf_counter()
    for index in range(args.runs):
        preprocessing_started = time.perf_counter()
        feeds = _fixture_feed(
            records[index % len(records)], image_dir, image_name, history_name
        )
        preprocessing_ms.append((time.perf_counter() - preprocessing_started) * 1000.0)
        started = time.perf_counter()
        output = session.run(None, feeds)[0]
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
    local_pipeline_seconds = time.perf_counter() - measured_started
    inference_seconds = sum(latencies_ms) / 1000.0
    memory_after_runs = _memory_snapshot()

    if output_shape != [1, 4, 18] or list(output.shape) != [1, 4, 18]:
        raise SystemExit(f"Unexpected runtime output shape: {list(output.shape)}")
    if not np.all(np.isfinite(output)):
        raise SystemExit("Model output contains a non-finite value.")

    report: dict[str, Any] = {
        "schema_version": 1,
        "benchmark": "SidewalkPilot-v4.1a-FP32-ONNX-batch1",
        "label": args.label or _device_name(),
        "timestamp_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "device": {
            "board": _device_name(),
            "cpu": _cpu_name(),
            "architecture": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
            "platform": platform.platform(),
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "onnxruntime": ort.__version__,
            "available_providers": ort.get_available_providers(),
            "requested_provider": args.provider,
            "active_providers": providers_used,
            "primary_provider": primary_provider,
        },
        "model": {
            "path": str(model_path),
            "size_mib": model_path.stat().st_size / MIB,
            "sha256": _sha256(model_path),
            "input_dtype": "float32",
            "image_shape": [1, 3, 180, 320],
            "history_shape": [1, 3],
            "output_shape": [1, 4, 18],
            "batch_size": 1,
        },
        "fixtures": {
            "path": str(image_dir),
            "image_count": len(records),
            "set_sha256": fixture_hash,
            "source": "real SidewalkPilot sidewalk frames",
        },
        "performance": {
            "warmup_runs": args.warmup,
            "measured_runs": args.runs,
            "session_load_seconds": load_seconds,
            "inference_seconds": inference_seconds,
            "local_pipeline_seconds": local_pipeline_seconds,
            "ips": args.runs / inference_seconds,
            "local_image_pipeline_ips": args.runs / local_pipeline_seconds,
            "latency_mean_ms": statistics.fmean(latencies_ms),
            "latency_median_ms": statistics.median(latencies_ms),
            "latency_p95_ms": _percentile(latencies_ms, 95.0),
            "latency_p99_ms": _percentile(latencies_ms, 99.0),
            "latency_min_ms": min(latencies_ms),
            "latency_max_ms": max(latencies_ms),
            "preprocessing_mean_ms_excluded_from_ips": statistics.fmean(
                preprocessing_ms
            ),
        },
        "memory": {
            "before_model_load": memory_before_load,
            "after_model_load": memory_after_load,
            "after_warmup": memory_after_warmup,
            "after_measured_runs": memory_after_runs,
            "model_load_process_rss_delta_mib": _delta(
                memory_after_load, memory_before_load, "process_rss_mib"
            ),
            "warm_process_rss_delta_mib": _delta(
                memory_after_warmup, memory_before_load, "process_rss_mib"
            ),
            "warm_system_used_delta_mib": _delta(
                memory_after_warmup, memory_before_load, "system_used_mib"
            ),
            "measurement_note": (
                "Process RSS can exclude CUDA allocations. On Jetson, also inspect the "
                "system-used delta because CPU and GPU share LPDDR5. Run on an "
                "otherwise idle device and repeat before publishing a memory claim."
            ),
        },
    }
    return report


def _print_report(report: dict[str, Any]) -> None:
    perf = report["performance"]
    memory = report["memory"]
    warm = memory["after_warmup"]
    print("\nSidewalkPilot v4.1a FP32 ONNX benchmark")
    print(f"  Device:       {report['label']}")
    print(f"  Board:        {report['device']['board']}")
    print(f"  Provider:     {report['runtime']['primary_provider']}")
    print(f"  Model SHA256: {report['model']['sha256']}")
    print(
        f"  Real images:  {report['fixtures']['image_count']} "
        f"(set {report['fixtures']['set_sha256']})"
    )
    print(
        f"  Runs:         {perf['measured_runs']} "
        f"(+{perf['warmup_runs']} warm-up)"
    )
    print(f"  IPS:          {perf['ips']:.2f}")
    print(
        f"  Local IPS:    {perf['local_image_pipeline_ips']:.2f} "
        "including image prep"
    )
    print(
        "  Latency:      "
        f"mean {perf['latency_mean_ms']:.2f} ms | "
        f"median {perf['latency_median_ms']:.2f} ms | "
        f"p95 {perf['latency_p95_ms']:.2f} ms | "
        f"p99 {perf['latency_p99_ms']:.2f} ms"
    )
    print(f"  Model file:   {report['model']['size_mib']:.2f} MiB")
    print(
        f"  Warm RSS:     {warm['process_rss_mib']:.2f} MiB total process memory"
    )
    print(
        f"  RSS increase: {memory['warm_process_rss_delta_mib']:+.2f} MiB "
        "from pre-load"
    )
    print(
        f"  System delta: {memory['warm_system_used_delta_mib']:+.2f} MiB "
        "from pre-load"
    )


def _load_report(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read benchmark report {path}: {exc}") from exc


def compare_reports(first_path: Path, second_path: Path) -> None:
    first = _load_report(first_path)
    second = _load_report(second_path)
    if first.get("benchmark") != second.get("benchmark"):
        raise SystemExit("Reports use different benchmark definitions.")
    if first["model"]["sha256"] != second["model"]["sha256"]:
        raise SystemExit("Reports used different model files; comparison rejected.")
    if first["model"]["batch_size"] != second["model"]["batch_size"]:
        raise SystemExit("Reports used different batch sizes; comparison rejected.")
    if first["fixtures"]["set_sha256"] != second["fixtures"]["set_sha256"]:
        raise SystemExit(
            "Reports used different sidewalk image sets; comparison rejected."
        )

    a_perf, b_perf = first["performance"], second["performance"]
    speedup = b_perf["ips"] / a_perf["ips"]
    latency_reduction = 100.0 * (
        1.0 - b_perf["latency_median_ms"] / a_perf["latency_median_ms"]
    )

    print("\nSidewalkPilot v4.1a device comparison")
    print(f"  Same model: {first['model']['sha256']}")
    print(
        f"  {'Device':24} {'Provider':24} {'IPS':>9} {'Median ms':>11} "
        f"{'Warm RSS':>11} {'RSS delta':>11}"
    )
    for report in (first, second):
        perf = report["performance"]
        memory = report["memory"]
        print(
            f"  {report['label'][:24]:24} "
            f"{report['runtime']['primary_provider'][:24]:24} "
            f"{perf['ips']:9.2f} {perf['latency_median_ms']:11.2f} "
            f"{memory['after_warmup']['process_rss_mib']:11.2f} "
            f"{memory['warm_process_rss_delta_mib']:11.2f}"
        )
    print(f"\n  Second/first IPS speedup: {speedup:.2f}x")
    print(f"  Median latency reduction: {latency_reduction:.1f}%")
    print(
        "  Memory caution: compare both RSS delta and system delta; Jetson CUDA uses "
        "unified memory that process RSS may not fully attribute."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark SidewalkPilot v4.1a identically on Raspberry Pi 5 and Jetson."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run the local-device benchmark")
    run.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    run.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    run.add_argument("--provider", choices=("auto", "cpu", "cuda"), default="auto")
    run.add_argument("--label", default="")
    run.add_argument("--warmup", type=int, default=20)
    run.add_argument("--runs", type=int, default=200)
    run.add_argument("--output", type=Path)

    compare = subparsers.add_parser("compare", help="compare two saved JSON reports")
    compare.add_argument(
        "first", type=Path, help="baseline report, normally Raspberry Pi 5"
    )
    compare.add_argument("second", type=Path, help="comparison report, normally Jetson")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "compare":
        compare_reports(args.first, args.second)
        return

    report = run_benchmark(args)
    _print_report(report)
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"  JSON report:  {output}")


if __name__ == "__main__":
    main()
