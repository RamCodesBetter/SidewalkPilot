#!/usr/bin/env python3
"""Benchmark SidewalkPilot FP32 ONNX models identically on Pi and Jetson.

Run this file once on each device, then compare the two JSON reports:

    python3 code/test_files/models/benchmark_v41a_devices.py run \
        --label raspberry-pi-5 --provider cpu --output /tmp/rpi5-v4.1a.json

    python3 code/test_files/models/benchmark_v41a_devices.py run \
        --label jetson-orin-nano --provider cuda --output /tmp/jetson-v4.1a.json

    python3 code/test_files/models/benchmark_v41a_devices.py compare \
        /tmp/rpi5-v4.1a.json /tmp/jetson-v4.1a.json

The default images are a 180-image timing-only mini test dataset sampled from the
separate 81,237-image Series 3/4 training corpus. The timed model section measures
local batch-one ``InferenceSession.run`` calls. It does not include camera capture,
JPEG encoding, Ethernet transfer, or servo response. A second local-pipeline
number includes image decode and preprocessing. Process RSS, system memory, and
CUDA-visible memory are reported separately because Jetson CPU and GPU share
physical LPDDR5 memory and no one counter captures every allocation reliably.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import gc
import hashlib
import json
import math
import os
import platform
import re
import statistics
import threading
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
DEFAULT_IMAGES = Path(__file__).resolve().parent / "mini_test_dataset"
MIB = 1024.0 * 1024.0
MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>\d+\.\d+[a-z]?)\.onnx$")
CLAHE_VERSIONS = {"2.0", "2.0b"}
_CUDART: Any = None
_CUDART_ERROR = ""


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


def _load_cudart() -> Any:
    global _CUDART, _CUDART_ERROR
    if _CUDART is not None or _CUDART_ERROR:
        return _CUDART
    candidates = [
        ctypes.util.find_library("cudart"),
        "libcudart.so",
        "libcudart.so.12",
        "libcudart.so.11.0",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            library = ctypes.CDLL(candidate)
            library.cudaMemGetInfo.argtypes = [
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            library.cudaMemGetInfo.restype = ctypes.c_int
            _CUDART = library
            return _CUDART
        except OSError as exc:
            _CUDART_ERROR = str(exc)
    _CUDART_ERROR = _CUDART_ERROR or "CUDA runtime library was not found"
    return None


def _cuda_memory_snapshot(enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {"available": False, "reason": "CUDA provider not active"}
    library = _load_cudart()
    if library is None:
        return {"available": False, "reason": _CUDART_ERROR}
    free_bytes = ctypes.c_size_t()
    total_bytes = ctypes.c_size_t()
    status = library.cudaMemGetInfo(
        ctypes.byref(free_bytes), ctypes.byref(total_bytes)
    )
    if status != 0:
        return {"available": False, "reason": f"cudaMemGetInfo status {status}"}
    return {
        "available": True,
        "free_mib": free_bytes.value / MIB,
        "total_mib": total_bytes.value / MIB,
        "used_mib": (total_bytes.value - free_bytes.value) / MIB,
    }


def _memory_snapshot(cuda_enabled: bool = False) -> dict[str, Any]:
    rss, hwm = _proc_memory_bytes()
    system_total, system_used = _system_memory_bytes()
    return {
        "process_rss_mib": rss / MIB,
        "process_peak_rss_mib": hwm / MIB,
        "system_total_mib": system_total / MIB,
        "system_used_mib": system_used / MIB,
        "cuda_visible": _cuda_memory_snapshot(cuda_enabled),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _onnx_initializer_stats(path: Path) -> dict[str, Any]:
    try:
        import onnx
    except ImportError:
        return {
            "available": False,
            "reason": "onnx package is not installed; runtime timing is unaffected",
        }
    model = onnx.load(str(path), load_external_data=False)
    bytes_per_element = {
        1: 4,   # FLOAT
        2: 1,   # UINT8
        3: 1,   # INT8
        4: 2,   # UINT16
        5: 2,   # INT16
        6: 4,   # INT32
        7: 8,   # INT64
        9: 1,   # BOOL
        10: 2,  # FLOAT16
        11: 8,  # DOUBLE
        12: 4,  # UINT32
        13: 8,  # UINT64
        16: 2,  # BFLOAT16
    }
    element_count = 0
    storage_bytes = 0
    for initializer in model.graph.initializer:
        elements = math.prod(initializer.dims)
        element_count += elements
        if initializer.raw_data:
            storage_bytes += len(initializer.raw_data)
        else:
            storage_bytes += elements * bytes_per_element.get(initializer.data_type, 0)
    return {
        "available": True,
        "tensor_count": len(model.graph.initializer),
        "element_count": element_count,
        "storage_bytes": storage_bytes,
        "storage_mib": storage_bytes / MIB,
        "note": (
            "ONNX initializer storage is exact for the graph file. It is not the "
            "same as total runtime memory."
        ),
    }


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


def _mini_dataset_hash(records: list[dict[str, Any]], image_dir: Path) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(str(record["file"]).encode("utf-8"))
        digest.update(json.dumps(record["target_history"]).encode("utf-8"))
        with (image_dir / str(record["file"])).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _load_mini_dataset_manifest(
    image_dir: Path,
) -> tuple[list[dict[str, Any]], str]:
    manifest_path = image_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"Could not read mini test dataset manifest {manifest_path}: {exc}"
        ) from exc
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise SystemExit(
            f"Mini test dataset manifest has no image records: {manifest_path}"
        )
    for record in records:
        path = image_dir / str(record.get("file", ""))
        history = record.get("target_history")
        if not path.is_file() or not isinstance(history, list) or len(history) != 3:
            raise SystemExit(
                f"Invalid mini test dataset record in {manifest_path}: {record}"
            )
    return records, _mini_dataset_hash(records, image_dir)


def _mini_dataset_feed(
    record: dict[str, Any],
    image_dir: Path,
    image_name: str,
    width: int,
    height: int,
    history_name: str | None,
    history_steps: int,
    use_clahe: bool,
) -> dict[str, np.ndarray]:
    path = image_dir / str(record["file"])
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"Could not decode mini test dataset image: {path}")
    if use_clahe:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h_channel, s_channel, v_channel = cv2.split(hsv)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        image = cv2.cvtColor(
            cv2.merge((h_channel, s_channel, clahe.apply(v_channel))),
            cv2.COLOR_HSV2BGR,
        )
    if image.shape[:2] != (height, width):
        image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    tensor = image.astype(np.float32) / 255.0
    tensor = (tensor - 0.5) / 0.5
    tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...].astype(np.float32)
    feeds = {image_name: tensor}
    if history_name is not None:
        source_history = [float(value) for value in record["target_history"]]
        history = ([90.0] * history_steps + source_history)[-history_steps:]
        feeds[history_name] = np.asarray([history], dtype=np.float32)
    return feeds


def _validate_contract(session: "ort.InferenceSession") -> dict[str, Any]:
    inputs = session.get_inputs()
    image = next((item for item in inputs if len(item.shape) == 4), None)
    history = next((item for item in inputs if len(item.shape) == 2), None)
    output = session.get_outputs()[0]
    if image is None or image.type != "tensor(float)":
        details = [(item.name, item.shape) for item in inputs]
        raise SystemExit(f"Expected one FP32 NCHW image input: {details}")
    channels, height, width = image.shape[1:]
    if channels != 3 or not isinstance(height, int) or not isinstance(width, int):
        details = [(item.name, item.shape) for item in inputs]
        raise SystemExit(f"Expected a concrete [batch,3,H,W] input: {details}")
    history_steps = 0
    if history is not None:
        if history.type != "tensor(float)" or not isinstance(history.shape[1], int):
            raise SystemExit(
                f"Expected a concrete FP32 history input, got {history.name}: "
                f"{history.shape} {history.type}"
            )
        history_steps = int(history.shape[1])
    if len(inputs) != 1 + int(history is not None):
        details = [(item.name, item.shape) for item in inputs]
        raise SystemExit(f"Unsupported extra model inputs: {details}")
    if output.type != "tensor(float)":
        raise SystemExit(
            f"Expected an FP32 model output, got {output.name}: {output.type}"
        )
    return {
        "image_name": image.name,
        "width": int(width),
        "height": int(height),
        "history_name": history.name if history is not None else None,
        "history_steps": history_steps,
        "output_name": output.name,
        "output_shape": list(output.shape),
    }


def _version_from_path(path: Path) -> str:
    match = MODEL_RE.fullmatch(path.name)
    return match.group("version") if match else path.stem


def _series_from_version(version: str) -> int | None:
    match = re.match(r"^(\d+)\.", version)
    return int(match.group(1)) if match else None


def _jetson_gpu_load_percent() -> float | None:
    candidates = [
        Path("/sys/devices/platform/17000000.gpu/load"),
        Path("/sys/class/devfreq/17000000.gpu/load"),
    ]
    for path in candidates:
        raw = _read_text(path)
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        return value / 10.0 if value > 100.0 else value
    return None


class _GpuLoadSampler:
    def __init__(self, enabled: bool, interval_sec: float = 0.01):
        self.enabled = enabled
        self.interval_sec = interval_sec
        self.values: list[float] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled or _jetson_gpu_load_percent() is None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_sec):
            value = _jetson_gpu_load_percent()
            if value is not None:
                self.values.append(value)

    def finish(self) -> dict[str, float] | None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if not self.values:
            return None
        return {
            "sample_count": len(self.values),
            "mean_percent": statistics.fmean(self.values),
            "p95_percent": _percentile(self.values, 95.0),
            "max_percent": max(self.values),
        }


def _percentile(values: list[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _delta(after: dict[str, float], before: dict[str, float], key: str) -> float:
    return float(after[key] - before[key])


def _cuda_used_delta(
    after: dict[str, Any], before: dict[str, Any]
) -> float | None:
    after_cuda = after.get("cuda_visible", {})
    before_cuda = before.get("cuda_visible", {})
    if not after_cuda.get("available") or not before_cuda.get("available"):
        return None
    return float(after_cuda["used_mib"] - before_cuda["used_mib"])


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    model_path = args.model.expanduser().resolve()
    image_dir = args.images.expanduser().resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model not found: {model_path}")
    if args.warmup < 1 or args.runs < 2:
        raise SystemExit("Use at least 1 warm-up and 2 measured inferences.")

    providers = _provider_list(args.provider)
    cuda_enabled = providers[0] == "CUDAExecutionProvider"
    gc.collect()
    memory_before_load = _memory_snapshot(cuda_enabled)
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    load_started = time.perf_counter()
    session = ort.InferenceSession(
        str(model_path), sess_options=options, providers=providers
    )
    load_seconds = time.perf_counter() - load_started
    contract = _validate_contract(session)
    providers_used = session.get_providers()
    primary_provider = providers_used[0]
    if args.provider == "cuda" and primary_provider != "CUDAExecutionProvider":
        raise SystemExit(
            f"CUDA was requested but the active provider is {providers_used}"
        )
    memory_after_load = _memory_snapshot(cuda_enabled)

    records, mini_dataset_hash = _load_mini_dataset_manifest(image_dir)
    version = _version_from_path(model_path)
    use_clahe = version in CLAHE_VERSIONS

    output_shape: list[int] | None = None
    for index in range(args.warmup):
        feeds = _mini_dataset_feed(
            records[index % len(records)],
            image_dir,
            contract["image_name"],
            contract["width"],
            contract["height"],
            contract["history_name"],
            contract["history_steps"],
            use_clahe,
        )
        output = session.run(None, feeds)[0]
        output_shape = list(output.shape)
    memory_after_warmup = _memory_snapshot(cuda_enabled)

    latencies_ms: list[float] = []
    inference_cpu_seconds = 0.0
    preprocessing_ms: list[float] = []
    gpu_sampler = _GpuLoadSampler(cuda_enabled)
    gpu_sampler.start()
    local_pipeline_cpu_started = time.process_time()
    measured_started = time.perf_counter()
    for index in range(args.runs):
        preprocessing_started = time.perf_counter()
        feeds = _mini_dataset_feed(
            records[index % len(records)],
            image_dir,
            contract["image_name"],
            contract["width"],
            contract["height"],
            contract["history_name"],
            contract["history_steps"],
            use_clahe,
        )
        preprocessing_ms.append((time.perf_counter() - preprocessing_started) * 1000.0)
        cpu_started = time.process_time()
        started = time.perf_counter()
        output = session.run(None, feeds)[0]
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
        inference_cpu_seconds += time.process_time() - cpu_started
    local_pipeline_seconds = time.perf_counter() - measured_started
    local_pipeline_cpu_seconds = time.process_time() - local_pipeline_cpu_started
    gpu_load = gpu_sampler.finish()
    inference_seconds = sum(latencies_ms) / 1000.0
    memory_after_runs = _memory_snapshot(cuda_enabled)

    if output_shape is None or list(output.shape) != output_shape:
        raise SystemExit(f"Output shape changed during the run: {list(output.shape)}")
    if not np.all(np.isfinite(output)):
        raise SystemExit("Model output contains a non-finite value.")
    initializer_stats = _onnx_initializer_stats(model_path)

    report: dict[str, Any] = {
        "schema_version": 2,
        "benchmark": "SidewalkPilot-FP32-ONNX-batch1-v2",
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
            "version": version,
            "series": _series_from_version(version),
            "path": str(model_path),
            "size_mib": model_path.stat().st_size / MIB,
            "sha256": _sha256(model_path),
            "input_dtype": "float32",
            "image_shape": [1, 3, contract["height"], contract["width"]],
            "history_shape": (
                [1, contract["history_steps"]]
                if contract["history_name"] is not None
                else None
            ),
            "output_shape": output_shape,
            "batch_size": 1,
            "preprocessing": (
                "HSV/CLAHE then normalized BGR"
                if use_clahe
                else "normalized BGR"
            ),
            "onnx_initializers": initializer_stats,
        },
        "mini_test_dataset": {
            "path": str(image_dir),
            "image_count": len(records),
            "set_sha256": mini_dataset_hash,
            "source": "real SidewalkPilot sidewalk frames",
            "is_training_dataset": False,
        },
        "performance": {
            "warmup_runs": args.warmup,
            "measured_runs": args.runs,
            "session_load_seconds": load_seconds,
            "inference_seconds": inference_seconds,
            "inference_process_cpu_seconds": inference_cpu_seconds,
            "inference_effective_cpu_cores": inference_cpu_seconds
            / inference_seconds,
            "local_pipeline_seconds": local_pipeline_seconds,
            "local_pipeline_process_cpu_seconds": local_pipeline_cpu_seconds,
            "local_pipeline_effective_cpu_cores": local_pipeline_cpu_seconds
            / local_pipeline_seconds,
            "jetson_gpu_load": gpu_load,
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
            "warm_cuda_visible_used_delta_mib": _cuda_used_delta(
                memory_after_warmup, memory_before_load
            ),
            "measurement_note": (
                "The model file size is exact disk storage. RSS, system-used, and "
                "CUDA-visible deltas are runtime allocation estimates, not "
                "model-weight-only values. "
                "Jetson uses shared LPDDR5, so these counters overlap and must not be "
                "added together. Run on an otherwise idle device and repeat "
                "before publishing a memory claim."
            ),
        },
    }
    return report


def _print_report(report: dict[str, Any]) -> None:
    perf = report["performance"]
    memory = report["memory"]
    warm = memory["after_warmup"]
    print(f"\nSidewalkPilot v{report['model']['version']} FP32 ONNX benchmark")
    print(f"  Device:       {report['label']}")
    print(f"  Board:        {report['device']['board']}")
    print(f"  Provider:     {report['runtime']['primary_provider']}")
    print(f"  Model SHA256: {report['model']['sha256']}")
    print(
        f"  Mini dataset: {report['mini_test_dataset']['image_count']} real images "
        f"(set {report['mini_test_dataset']['set_sha256']})"
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
    print(
        f"  CPU cores:    {perf['inference_effective_cpu_cores']:.2f} effective "
        "cores during model execution"
    )
    gpu_load = perf.get("jetson_gpu_load")
    if gpu_load is not None:
        print(
            f"  GPU load:     mean {gpu_load['mean_percent']:.1f}% | "
            f"p95 {gpu_load['p95_percent']:.1f}% | "
            f"max {gpu_load['max_percent']:.1f}%"
        )
    print(f"  Model file:   {report['model']['size_mib']:.2f} MiB")
    initializers = report["model"].get("onnx_initializers", {})
    if initializers.get("available"):
        print(
            f"  Parameters:   {initializers['element_count']:,} ONNX initializer "
            f"elements ({initializers['storage_mib']:.2f} MiB stored)"
        )
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
    cuda_delta = memory.get("warm_cuda_visible_used_delta_mib")
    if cuda_delta is not None:
        print(
            f"  CUDA delta:   {cuda_delta:+.2f} MiB CUDA-visible shared memory "
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
    if (
        first["mini_test_dataset"]["set_sha256"]
        != second["mini_test_dataset"]["set_sha256"]
    ):
        raise SystemExit(
            "Reports used different sidewalk image sets; comparison rejected."
        )

    a_perf, b_perf = first["performance"], second["performance"]
    speedup = b_perf["ips"] / a_perf["ips"]
    throughput_gain = 100.0 * (speedup - 1.0)
    mean_latency_reduction = 100.0 * (
        1.0 - b_perf["latency_mean_ms"] / a_perf["latency_mean_ms"]
    )
    median_latency_reduction = 100.0 * (
        1.0 - b_perf["latency_median_ms"] / a_perf["latency_median_ms"]
    )

    version = first["model"].get("version", "unknown")
    print(f"\nSidewalkPilot v{version} device comparison")
    print(f"  Same model: {first['model']['sha256']}")
    print(
        f"  {'Device':24} {'Provider':24} {'IPS':>9} {'Median ms':>11} "
        f"{'CPU cores':>10} {'RSS delta':>11}"
    )
    for report in (first, second):
        perf = report["performance"]
        memory = report["memory"]
        print(
            f"  {report['label'][:24]:24} "
            f"{report['runtime']['primary_provider'][:24]:24} "
            f"{perf['ips']:9.2f} {perf['latency_median_ms']:11.2f} "
            f"{perf.get('inference_effective_cpu_cores', float('nan')):10.2f} "
            f"{memory['warm_process_rss_delta_mib']:11.2f}"
        )
    print(f"\n  Second/first IPS speedup: {speedup:.2f}x")
    print(f"  Throughput gain: {throughput_gain:.1f}%")
    print(f"  Mean model-latency reduction: {mean_latency_reduction:.1f}%")
    print(f"  Median model-latency reduction: {median_latency_reduction:.1f}%")
    print(
        "  Memory caution: compare both RSS delta and system delta; Jetson CUDA uses "
        "unified memory that process RSS may not fully attribute."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark SidewalkPilot ONNX models identically on Raspberry Pi 5 "
            "and Jetson."
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
