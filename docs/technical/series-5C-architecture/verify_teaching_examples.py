"""Check the guide's toy arithmetic against PyTorch, without training 5.C."""
import math

import torch
from torch.nn import functional as F


def verify(model):
    normalized_red = (128 / 255 - 0.485) / 0.229
    assert math.isclose(normalized_red, 0.0740646, abs_tol=5e-8)
    q = torch.tensor([0.1, 0.3, 0.5, 0.7], dtype=torch.float64)
    mean, variance = q.mean(), q.var(unbiased=False)
    assert math.isclose(mean.item(), 0.4)
    assert math.isclose(variance.item(), 0.05)
    standardized = (q - mean) / variance.sqrt()
    assert abs(standardized.mean().item()) < 1e-12
    assert math.isclose(standardized.var(unbiased=False).item(), 1)

    x = torch.tensor([0.2, 0.8], dtype=torch.float64)
    matrix = torch.tensor([[1.5, -0.5], [-0.5, 1]], dtype=x.dtype)
    offsets = torch.tensor([0.3, -0.1], dtype=x.dtype)
    assert torch.allclose(matrix @ x + offsets, torch.tensor([0.2, 0.6], dtype=x.dtype))

    patch = torch.tensor([[[[1., 2., 0.], [0., 1., 3.], [2., 0., 1.]]]])
    kernel = torch.tensor([[[[1., 0., -1.], [1., 0., -1.], [1., 0., -1.]]]])
    assert F.conv2d(patch, kernel, torch.tensor([0.5])).item() == -0.5
    head = model.classifier.head
    assert list(head.weight.shape) == [2, 32, 1, 1]
    assert head.bias is not None
    assert sum(p.numel() for p in head.parameters()) == 66
    for block in (model.classifier.up16, model.classifier.up8, model.classifier.up4):
        assert block.skip_projection.bias is not None
        assert block.fusion[0].bias is None and block.fusion[3].bias is None
        assert block.fusion[1].num_groups == 8
        assert block.fusion[1].eps == 1e-5
    assert model.classifier.bottleneck.bias is not None
    layernorms = [m for m in model.backbone.modules() if isinstance(m, torch.nn.LayerNorm)]
    assert layernorms and all(m.eps == 1e-6 for m in layernorms)
    u = torch.tensor([1., 3.], dtype=torch.float64)
    affine = F.layer_norm(u, (2,), torch.tensor([2., .5], dtype=u.dtype),
                         torch.tensor([.1, -.2], dtype=u.dtype), eps=1e-6)
    assert torch.allclose(affine, torch.tensor([-1.9, .3], dtype=u.dtype), atol=2e-6)
    gelu = F.gelu(torch.tensor([-1., 0., 1.], dtype=torch.float64))
    assert torch.allclose(gelu, torch.tensor([-.158655, 0., .841345], dtype=gelu.dtype), atol=5e-7)

    # Reuse the same two-input example for forward, backward, and the SGD illustration.
    params = torch.tensor([1.5, -0.5, 0.3], dtype=torch.float64, requires_grad=True)
    score = params[:2] @ x + params[2]
    logits = torch.stack((torch.zeros_like(score), score))
    probability = logits.softmax(0)[1]
    assert torch.allclose(logits.softmax(0), (logits + 10).softmax(0))
    loss = F.cross_entropy(logits[None], torch.tensor([1]))
    loss.backward()
    expected_grad = (probability.item() - 1) * torch.tensor([.2, .8, 1.], dtype=x.dtype)
    assert torch.allclose(params.grad, expected_grad)
    updated = params.detach() - 0.1 * params.grad
    new_score = updated[:2] @ x + updated[2]
    new_loss = F.softplus(-new_score)
    assert new_loss < loss.detach()
    assert abs(new_score.item() - .275628) < 5e-7
    printed = {
        "0.0740646": normalized_red,
        "0.223607": variance.sqrt().item(),
        "0.549834": probability.item(),
        "0.598139": loss.item(),
        "1.5090033": updated[0].item(),
        "-0.4639867": updated[1].item(),
        "0.3450166": updated[2].item(),
    }
    for literal, value in printed.items():
        places = len(literal.split(".")[1])
        assert abs(float(literal) - value) <= 0.5 * 10 ** -places
    return dict(normalized_red=normalized_red, mean=mean.item(), variance=variance.item(),
                standardized=standardized.tolist(), layernorm_affine=affine.tolist(),
                gelu=gelu.tolist(), neuron_score=score.item(), probability=probability.item(),
                loss=loss.item(), gradients=params.grad.tolist(), sgd_parameters=updated.tolist(),
                updated_score=new_score.item(), updated_loss=new_loss.item(),
                documented_values=printed, class_head_parameters=66)
