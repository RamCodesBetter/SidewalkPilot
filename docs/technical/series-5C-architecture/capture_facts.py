"""Capture implementation facts and verify the worked math without training a model."""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import torch
import torchvision

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
CODE = REPO / "code/ai_models_datasets/series_5/tools"
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE.parent))
import workspace
workspace.activate()
import convnext_tiny_unet as architecture
from series_5_b_sidewalkpilot_trainer import conservative_loss
from verify_teaching_examples import verify


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    torch.manual_seed(20261121)
    torch.set_num_threads(2)
    model = architecture.make_model("none").eval()
    cfg = json.loads(workspace.source_path("series_5_c_config.json").read_text())
    trace, hooks = [], []
    names = {f"backbone.features.{i}" for i in range(8)} | {
        "classifier.bottleneck", "classifier.up16", "classifier.up8",
        "classifier.up4", "classifier.head"}
    for name, module in model.named_modules():
        if name in names:
            hooks.append(module.register_forward_hook(
                lambda layer, inputs, result, name=name: trace.append(
                    dict(name=name, shape=list(result.shape), dtype=str(result.dtype)))))
    with torch.inference_mode():
        result = model(torch.zeros(1, 3, cfg["height"], cfg["width"]))["out"]
    for hook in hooks:
        hook.remove()
    assert list(result.shape) == [1, 2, 540, 960]
    assert all(row["dtype"] == "torch.float32" for row in trace)
    parameters = dict(encoder=sum(p.numel() for p in model.backbone.parameters()),
                      decoder=sum(p.numel() for p in model.classifier.parameters()),
                      total=sum(p.numel() for p in model.parameters()))
    assert parameters["total"] == 28855298
    teaching = verify(model)
    # An isolated scalar example: one sidewalk pixel with logit z_1 = 2*w.
    weight = torch.tensor(0.5, dtype=torch.float32, requires_grad=True)
    optimizer = torch.optim.AdamW([weight], lr=0.001, weight_decay=0.0001)
    logits = torch.stack((torch.zeros_like(weight), 2 * weight)).reshape(1, 2, 1, 1)
    loss, _, _ = conservative_loss(logits, torch.ones(1, 1, 1, dtype=torch.long), torch.tensor([True]))
    loss.backward()
    gradient = float(weight.grad)
    expected_gradient = 2 * (1 / (1 + math.exp(-1)) - 1)
    assert abs(gradient - expected_gradient) < 1e-6
    torch.nn.utils.clip_grad_norm_([weight], 1.0)
    optimizer.step()
    expected_weight = 0.5 * (1 - 0.001 * 0.0001) - 0.001 * gradient / (abs(gradient) + 1e-8)
    assert abs(float(weight.detach()) - expected_weight) < 1e-6
    # Verify the two-pixel weighted loss described in the document.
    sample = torch.tensor([[[[0.0, 0.0]], [[math.log(4), math.log(4)]]]], requires_grad=True)
    target = torch.tensor([[[0, 1]]])
    weighted, _, _ = conservative_loss(sample, target, torch.tensor([True]))
    expected_loss = (-2 * math.log(0.2) - math.log(0.8)) / 3
    assert abs(float(weighted.detach()) - expected_loss) < 1e-6
    weighted.backward()
    assert torch.allclose(sample.grad[0, 1, 0], torch.tensor([2 * 0.8 / 3, -0.2 / 3]), atol=1e-6)
    sources = []
    for name in ("convnext_tiny_unet.py", "series_5_c_config.json", "series_5_c_sidewalkpilot_trainer.py",
                 "series_5_a_sidewalkpilot_trainer.py", "series_5_b_sidewalkpilot_trainer.py",
                 "pseudo_mask_filter.py", "pseudo_training_targets.py"):
        path = workspace.source_path(name)
        sources.append(dict(path=str(path.relative_to(REPO)), sha256=digest(path)))
    library = Path(torchvision.__file__).parent / "models/convnext.py"
    facts = dict(captured_at=datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(),
                 scope="Code/shape audit and isolated numerical examples, not trained-model results",
                 torch=str(torch.__version__), torchvision=str(torchvision.__version__), config=cfg,
                 parameters=parameters, trace=trace, output_shape=list(result.shape),
                 teaching=teaching,
                 teaching_audit_sha256=digest(ROOT / "verify_teaching_examples.py"),
                 fp32_weights_mib=parameters["total"] * 4 / 1024**2,
                 toy=dict(probability=1 / (1 + math.exp(-1)), loss=float(loss.detach()),
                          gradient=gradient, updated_weight=float(weight.detach()), weighted_loss=expected_loss),
                 sources=sources, torchvision_convnext_sha256=digest(library))
    (ROOT / "implementation-facts.json").write_text(json.dumps(facts, indent=2) + "\n")
    print(json.dumps(dict(parameters=parameters, output=list(result.shape), toy=facts["toy"]), indent=2))


if __name__ == "__main__":
    main()
