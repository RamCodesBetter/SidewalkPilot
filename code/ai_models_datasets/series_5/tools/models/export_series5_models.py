#!/usr/bin/env python3
"""Export a named Series 5 checkpoint and verify ONNX logits against PyTorch."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import onnx
import onnxruntime as ort
import torch


from label_grounded_sam2 import sha256
from series_5_sidewalkpilot_trainer import load_checkpoint, MEAN, STD


class Logits(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, image):
        return self.model(image)["out"]


def export(checkpoint, output, name):
    from series_5_sidewalkpilot_trainer import ConvNeXtRecipe
    families = {"SidewalkPilot-v5." + suffix: ConvNeXtRecipe
                for suffix in ("C", "Cb", "Cs", "E", "Eb", "Es")}
    families.update({"SidewalkPilot-v5.A": None, "SidewalkPilot-v5.B": None})
    model, state = load_checkpoint(checkpoint, model_definition=families[name])
    if name.split("-v")[1].rstrip("bs") != state["config"]["model_name"]:
        raise ValueError("Artifact name disagrees with checkpoint model_name")
    model = Logits(model.eval())
    width, height = state["config"]["width"], state["config"]["height"]
    sample = torch.randn(1, 3, height, width, generator=torch.Generator().manual_seed(20261121))
    output.mkdir(parents=True, exist_ok=True)
    target = output / (name + ".onnx")
    with torch.inference_mode():
        expected = model(sample).numpy()
        torch.onnx.export(model, sample, str(target), input_names=["image"],
                          output_names=["logits"], opset_version=17, dynamo=False)
    onnx.checker.check_model(str(target))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(target), sess_options=options, providers=["CPUExecutionProvider"])
    actual = session.run(None, {"image": sample.numpy()})[0]
    np.testing.assert_allclose(actual, expected, rtol=1e-3, atol=1e-4)
    pth = output / (name + ".pth")
    shutil.copy2(checkpoint, pth)
    report = dict(source_checkpoint=str(checkpoint), source_sha256=sha256(checkpoint),
                  checkpoint_format=state["schema"], epoch=state["epoch"],
                  input_shape=list(sample.shape), input="RGB float32, ImageNet normalized",
                  mean=MEAN, std=STD, output="logits [N, 2, H, W]; class 1 = sidewalk",
                  onnx_opset=17, max_absolute_error=float(np.abs(actual - expected).max()),
                  files={p.name:sha256(p) for p in (pth, target)})
    (output / (name + "-export.json")).write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    torch.set_num_threads(2)
    export(args.checkpoint, args.output, args.name)
