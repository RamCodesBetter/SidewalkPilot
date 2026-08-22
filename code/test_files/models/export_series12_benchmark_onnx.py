#!/usr/bin/env python3
"""Export Series 1/2 checkpoints to untracked ONNX files for device benchmarks."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import torch
import torch.nn as nn


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODELS_DIR = REPO_ROOT / "code" / "ai_models"
DEFAULT_OUTPUT = MODELS_DIR
SERVER_DIR = REPO_ROOT / "code" / "controller" / "current" / "rc_car_app"
MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>[12]\.\d+b?)\.pth$")

sys.path.insert(0, str(SERVER_DIR))
from jetson_inference_server import SteeringAutonomyV2  # noqa: E402


class FixedAdaptivePool4x8(nn.Module):
    """Exact AdaptiveAvgPool2d((4, 8)) equivalent for a 1x18 feature map."""

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        columns = []
        input_width = 18
        output_width = 8
        for index in range(output_width):
            start = (index * input_width) // output_width
            end = ((index + 1) * input_width + output_width - 1) // output_width
            columns.append(inputs[:, :, :, start:end].mean(dim=3, keepdim=True))
        pooled_row = torch.cat(columns, dim=3)
        return pooled_row.repeat(1, 1, 4, 1)


def _state_dict(checkpoint: object) -> dict[str, torch.Tensor]:
    state = checkpoint
    if isinstance(checkpoint, dict):
        for key in ("model_state_dict", "state_dict", "model"):
            candidate = checkpoint.get(key)
            if isinstance(candidate, dict):
                state = candidate
                break
    if not isinstance(state, dict):
        raise TypeError(f"Unsupported checkpoint object: {type(checkpoint).__name__}")
    return {str(key).removeprefix("module."): value for key, value in state.items()}


def _version_key(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"([12])\.(\d+)(b?)", version)
    if match is None:
        raise ValueError(version)
    return int(match.group(1)), int(match.group(2)), int(bool(match.group(3)))


def export_models(models_dir: Path, output_dir: Path, opset: int) -> None:
    sources: list[tuple[str, Path]] = []
    for path in models_dir.glob("SidewalkPilot-v*.pth"):
        match = MODEL_RE.fullmatch(path.name)
        if match:
            sources.append((match.group("version"), path))
    sources.sort(key=lambda item: _version_key(item[0]))
    if not sources:
        raise SystemExit(f"No Series 1/2 checkpoints found in {models_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    example = torch.linspace(
        -1.0, 1.0, steps=3 * 66 * 200, dtype=torch.float32
    ).reshape(1, 3, 66, 200)
    for index, (version, source) in enumerate(sources, start=1):
        scale = 85.0 if version.startswith("2.") else 86.0
        model = SteeringAutonomyV2(output_scale_deg=scale)
        checkpoint = torch.load(source, map_location="cpu", weights_only=False)
        model.load_state_dict(_state_dict(checkpoint), strict=True)
        model.eval()
        with torch.no_grad():
            expected = model(example)
        model.head[0] = FixedAdaptivePool4x8()
        with torch.no_grad():
            replacement = model(example)
        if not torch.allclose(expected, replacement, atol=1e-6, rtol=1e-6):
            raise RuntimeError(f"Export pooling replacement changed v{version} output")
        destination = output_dir / f"SidewalkPilot-v{version}.onnx"
        torch.onnx.export(
            model,
            example,
            destination,
            input_names=["image"],
            output_names=["steering_deg"],
            dynamic_axes={"image": {0: "batch"}, "steering_deg": {0: "batch"}},
            opset_version=opset,
            do_constant_folding=True,
        )
        try:
            import onnxruntime as ort
        except ImportError:
            ort = None
        if ort is not None:
            session = ort.InferenceSession(
                str(destination), providers=["CPUExecutionProvider"]
            )
            actual = torch.from_numpy(
                session.run(None, {session.get_inputs()[0].name: example.numpy()})[0]
            )
            if not torch.allclose(expected, actual, atol=1e-4, rtol=1e-5):
                raise RuntimeError(f"ONNX output did not match PyTorch for v{version}")
        print(f"[{index:02d}/{len(sources):02d}] exported v{version} -> {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export SidewalkPilot Series 1/2 checkpoints to benchmark-only ONNX."
        )
    )
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()
    export_models(args.models_dir.expanduser(), args.output.expanduser(), args.opset)


if __name__ == "__main__":
    main()
