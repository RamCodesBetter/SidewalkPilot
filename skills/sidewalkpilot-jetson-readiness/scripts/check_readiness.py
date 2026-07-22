#!/usr/bin/env python3
"""Read-only SidewalkPilot readiness checks for a live Jetson host."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(command: list[str], timeout: float = 5.0) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "output": "", "error": str(exc)}
    output = completed.stdout.strip()
    error = completed.stderr.strip()
    return {
        "ok": completed.returncode == 0,
        "output": output,
        "error": error,
        "returncode": completed.returncode,
    }


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip("\x00\n ")
    except OSError:
        return ""


def python_candidates(explicit: str | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        candidates.append(Path(virtual_env) / "bin" / "python")
    candidates.extend((Path.home() / ".venv/bin/python", Path(sys.executable)))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen and candidate.exists():
            seen.add(key)
            unique.append(candidate)
    return unique


def inspect_onnxruntime(candidates: list[Path]) -> dict[str, object]:
    probe = (
        "import json,onnxruntime as ort;"
        "print(json.dumps({'version':ort.__version__,"
        "'providers':ort.get_available_providers()}))"
    )
    attempts: list[dict[str, object]] = []
    for candidate in candidates:
        result = run([str(candidate), "-c", probe], timeout=10.0)
        attempt = {
            "python": str(candidate),
            "ok": result["ok"],
            "error": result.get("error", ""),
        }
        attempts.append(attempt)
        if not result["ok"]:
            continue
        try:
            payload = json.loads(str(result["output"]).splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            attempt["error"] = "ONNX Runtime probe returned invalid JSON"
            continue
        providers = list(payload.get("providers") or [])
        return {
            "ok": True,
            "python": str(candidate),
            "version": payload.get("version"),
            "providers": providers,
            "cuda_available": "CUDAExecutionProvider" in providers,
            "attempts": attempts,
        }
    return {
        "ok": False,
        "python": None,
        "version": None,
        "providers": [],
        "cuda_available": False,
        "attempts": attempts,
    }


def installed_nvidia_skill_roots() -> list[str]:
    candidates = (
        Path.home() / ".codex/skills/jetson-diagnostic/SKILL.md",
        Path.home() / ".claude/skills/jetson-diagnostic/SKILL.md",
        Path.home() / ".agents/skills/jetson-diagnostic/SKILL.md",
        Path.home() / "jetson-device-skills/skills/jetson-diagnostic/SKILL.md",
    )
    return [str(path.parent) for path in candidates if path.is_file()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("SIDEWALKPILOT_ROOT", "/nvme/rc_car_code"))
    parser.add_argument("--model", default=os.environ.get("RC_CAR_STEERING_MODEL", "3.4"))
    parser.add_argument("--python", default=os.environ.get("SIDEWALKPILOT_PYTHON"))
    parser.add_argument("--expected-ip", default="10.42.0.2")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--human", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    model_dir = repo / "code/ai_models"
    server_path = repo / "code/controller/current/rc_car_app/jetson_inference_server.py"
    model_paths = [
        model_dir / f"SidewalkPilot-v{args.model}{extension}"
        for extension in (".onnx", ".pt", ".pth")
    ]
    selected_model = next((path for path in model_paths if path.is_file()), None)

    device_model = read_text(Path("/proc/device-tree/model"))
    l4t_release = read_text(Path("/etc/nv_tegra_release"))
    is_jetson = "jetson" in device_model.lower() or bool(l4t_release)

    ort = inspect_onnxruntime(python_candidates(args.python))
    process = run(["pgrep", "-af", "[j]etson_inference_server.py"])
    sockets = run(["ss", "-ltnp"])
    addresses = run(["ip", "-br", "addr"])
    socket_output = str(sockets.get("output", ""))
    address_output = str(addresses.get("output", ""))
    port_listening = any(
        f":{args.port}" in line and "LISTEN" in line
        for line in socket_output.splitlines()
    )
    expected_ip_present = any(
        token.split("/", 1)[0] == args.expected_ip
        for token in address_output.split()
    )
    nvidia_skill_roots = installed_nvidia_skill_roots()

    deployment_ready = all(
        (
            is_jetson,
            repo.is_dir(),
            server_path.is_file(),
            selected_model is not None,
            bool(ort.get("cuda_available")),
        )
    )
    runtime_healthy = all(
        (deployment_ready, bool(process.get("ok")), port_listening, expected_ip_present)
    )

    payload = {
        "skill": "sidewalkpilot-jetson-readiness",
        "device": {
            "is_jetson": is_jetson,
            "model": device_model or None,
            "l4t_release": l4t_release or None,
        },
        "nvidia_jetson_skills": {
            "diagnostic_roots": nvidia_skill_roots,
            "installed": bool(nvidia_skill_roots),
        },
        "sidewalkpilot": {
            "repo": str(repo),
            "repo_exists": repo.is_dir(),
            "server_path": str(server_path),
            "server_exists": server_path.is_file(),
            "requested_model": str(args.model),
            "model_path": str(selected_model) if selected_model else None,
            "model_exists": selected_model is not None,
        },
        "onnxruntime": ort,
        "runtime": {
            "server_running": bool(process.get("ok")),
            "server_processes": str(process.get("output", "")).splitlines(),
            "port": args.port,
            "port_listening": port_listening,
            "expected_ip": args.expected_ip,
            "expected_ip_present": expected_ip_present,
            "addresses": address_output.splitlines(),
        },
        "deployment_ready": deployment_ready,
        "runtime_healthy": runtime_healthy,
    }
    print(json.dumps(payload, indent=2 if args.human else None, sort_keys=args.human))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
