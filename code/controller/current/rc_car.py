#!/usr/bin/python3
"""RC car controller entrypoint.

Model selection remains on the dashboard. Production inference runs on the Jetson
Orin Nano; ``--local-inference`` is a temporary Raspberry Pi CPU comparison mode.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path


LOCAL_INFERENCE_HOST = "127.0.0.1"
LOCAL_SERVER_START_TIMEOUT_SEC = 15.0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-inference",
        action="store_true",
        help=(
            "temporarily run the existing ONNX inference service on this Raspberry "
            "Pi's CPU instead of using the Jetson Orin Nano"
        ),
    )
    return parser


def _ensure_port_available(host: str, port: int) -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))
    except OSError as exc:
        raise RuntimeError(
            f"Local inference cannot start because {host}:{port} is already in use."
        ) from exc
    finally:
        probe.close()


def _wait_for_local_server(
    process: subprocess.Popen[bytes], host: str, port: int
) -> None:
    deadline = time.monotonic() + LOCAL_SERVER_START_TIMEOUT_SEC
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"Local inference server exited during startup with code {return_code}."
            )
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(
        f"Local inference server did not listen on {host}:{port} within "
        f"{LOCAL_SERVER_START_TIMEOUT_SEC:.0f} seconds."
    )


def _start_local_server(port: int) -> subprocess.Popen[bytes]:
    _ensure_port_available(LOCAL_INFERENCE_HOST, port)
    server_path = (
        Path(__file__).resolve().parent
        / "rc_car_app"
        / "jetson_inference_server.py"
    )
    process = subprocess.Popen(
        [
            sys.executable,
            str(server_path),
            "--model",
            "highest",
            "--host",
            LOCAL_INFERENCE_HOST,
            "--port",
            str(port),
        ]
    )
    try:
        _wait_for_local_server(process, LOCAL_INFERENCE_HOST, port)
    except Exception:
        _stop_local_server(process)
        raise
    return process


def _stop_local_server(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)

    from rc_car_app.config import JETSON_STEERING_PORT
    from rc_car_app.runtime import run

    local_server = None
    try:
        if args.local_inference:
            local_server = _start_local_server(JETSON_STEERING_PORT)
        run(
            inference_host=(LOCAL_INFERENCE_HOST if args.local_inference else None),
            local_inference=args.local_inference,
        )
    finally:
        _stop_local_server(local_server)


if __name__ == "__main__":
    main()
