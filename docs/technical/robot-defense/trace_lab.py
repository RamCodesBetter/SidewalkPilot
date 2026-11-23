"""Offline CPU exercises: random weights, synthetic pixels, no checkpoint or robot access."""
from pathlib import Path
import sys
import torch

repo = Path(__file__).resolve().parents[3]
models = repo / "code/ai_models_datasets/series_5/tools/models"
sys.path.insert(0, str(models))
from convnext_tiny_unet import make_model
from segmentation_losses import ReviewedFocalLoss


def main():
    torch.manual_seed(4)
    torch.set_num_threads(2)
    model = make_model("none").cpu()
    image = torch.randn(1, 3, 65, 97)
    target = torch.zeros(1, 65, 97, dtype=torch.long)
    target[:, 20:55, 35:68] = 1
    target[:, 30, 40] = 255
    frozen = next(model.backbone.parameters())
    before = frozen.detach().clone()
    model.train()
    model.backbone.requires_grad_(False).eval()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
    with torch.no_grad():
        print("Encoder stages:", [tuple(t.shape) for t in model.backbone(image)])
    head = model.classifier.head
    print("Head parameters:", sum(p.numel() for p in head.parameters()))
    loss_fn = ReviewedFocalLoss()
    for step in (1, 2):
        if step == 2:
            model.backbone.requires_grad_(True).train()
        optimizer.zero_grad(set_to_none=True)
        scores = model(image)["out"]
        scores.retain_grad()
        total, strong, weak = loss_fn(scores, target, torch.tensor([False]), 0.5)
        total.backward()
        print("Step", step, "logits:", tuple(scores.shape), "loss:", total.item(),
              "encoder gradient absent:", frozen.grad is None)
        assert scores.shape == (1, 2, 65, 97)
        assert strong.item() == 0 and torch.allclose(total, 0.5 * weak)
        assert torch.all(scores.grad[0, :, 30, 40] == 0)
        assert (frozen.grad is None) == (step == 1)
        previous_head = head.weight.detach().clone()
        optimizer.step()
        assert not torch.equal(previous_head, head.weight)
        assert torch.equal(before, frozen) == (step == 1)
    print("Verified: ignored output pixel has zero direct gradient; decoder learns in both phases.")


if __name__ == "__main__":
    main()
