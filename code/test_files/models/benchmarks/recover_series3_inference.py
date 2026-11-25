"""Reconstruct eval-mode Series 3 PyTorch weights from Conv/BN-folded ONNX exports.

These are inference equivalents, not the original trained BN or optimizer states.
"""
import argparse
import hashlib
from pathlib import Path
import sys

import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ai_models_datasets/series_3_and_4"))
from series_3_sidewalkpilot_trainer import SidewalkPilotV3


def recover(path):
    dest = path.with_suffix(".pth")
    if dest.exists():
        raise FileExistsError(dest)
    graph = onnx.load(path).graph
    weights = {w.name:torch.from_numpy(numpy_helper.to_array(w).copy()) for w in graph.initializer}
    model = SidewalkPilotV3().cpu().eval()
    state = model.state_dict()
    used = set()
    convs = [n for n in graph.node if n.op_type == "Conv"]
    if len(convs) != 6:
        raise ValueError("Expected six folded convolutions")
    for index, node in enumerate(convs):
        i = 3*index
        for param, key in zip(("weight","bias"),node.input[1:],strict=True):
            state[f"backbone.{i}.{param}"] = weights[key]
            used.add(key)
        # Identity in eval mode: (x - 0) / sqrt((1 - eps) + eps).
        state[f"backbone.{i+1}.running_var"].fill_(1-model.backbone[i+1].eps)
    for key in state:
        if key.startswith("head."):
            state[key] = weights[key]
            used.add(key)
    if set(weights) != used:
        raise ValueError("Unmapped ONNX weights")
    model.load_state_dict(state,strict=True)
    session = ort.InferenceSession(str(path),providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(20261125)
    max_err = 0.
    with torch.inference_mode():
        for x in [np.zeros((1,3,180,320),np.float32),rng.random((4,3,180,320),dtype=np.float32)]:
            expected = session.run(None,{session.get_inputs()[0].name:x})[0]
            actual = model(torch.from_numpy(x)).numpy()
            np.testing.assert_allclose(actual,expected,rtol=2e-4,atol=1e-4)
            max_err=max(max_err,float(np.abs(actual-expected).max()))
    torch.save(dict(model_state_dict=state, source_onnx_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    provenance="Derived from folded ONNX; eval mode only. Not the original training checkpoint.",
                    tested_max_absolute_error=max_err),dest)
    print(dest.name,max_err,flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files",nargs="+",type=Path)
    torch.set_num_threads(2)
    for path in parser.parse_args().files:
        recover(path)
