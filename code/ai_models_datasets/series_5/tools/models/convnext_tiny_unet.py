"""Primary Series 5 encoder/decoder, with an explicit full-FP32 contract."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import torch
from torch import nn
import torch.nn.functional as F
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny

ARCHITECTURE = "convnext_tiny_unet"
ENCODER_CHANNELS = (96, 192, 384, 768)
DECODER_CHANNELS = (256, 128, 64, 32)


def configure_fp32():
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")


def validate_precision(precision):
    if precision != "fp32":
        raise ValueError("ConvNeXt-Tiny U-Net requires explicit fp32; AMP/FP16/BF16 are disabled")


def config(weights):
    if weights not in ("imagenet", "none"):
        raise ValueError("Unknown initialization")
    return dict(architecture=ARCHITECTURE, num_classes=2,
                backbone_weights="ConvNeXt_Tiny_Weights.IMAGENET1K_V1" if weights == "imagenet" else None,
                encoder_channels=list(ENCODER_CHANNELS), decoder_channels=list(DECODER_CHANNELS),
                freeze_backbone_bn_statistics=False,
                precision_policy={"weights": "fp32", "inputs": "fp32", "logits": "fp32",
                                  "autocast": False, "tf32": False,
                                  "deployment": "FP32 reference; no reduced-precision engine built"})


def validate_state(state):
    cfg = state["config"]
    validate_precision(cfg["precision"])
    expected = config(cfg["weights"])
    if any(cfg.get(key) != value for key, value in expected.items()):
        raise ValueError("Checkpoint architecture/precision contract differs")
    if any(t.is_floating_point() and t.dtype != torch.float32 for t in state["model"].values()):
        raise ValueError("Checkpoint contains non-FP32 model tensors")


class ConvNeXtEncoder(nn.Module):
    def __init__(self, weights):
        super().__init__()
        self.features = convnext_tiny(weights=weights).features

    def forward(self, image):
        skips = []
        for index, layer in enumerate(self.features):
            image = layer(image)
            if index in (1, 3, 5, 7):
                skips.append(image)
        return skips


def conv_block(inputs, outputs):
    return nn.Sequential(
        nn.Conv2d(inputs, outputs, 3, padding=1, bias=False),
        nn.GroupNorm(8, outputs), nn.GELU(),
        nn.Conv2d(outputs, outputs, 3, padding=1, bias=False),
        nn.GroupNorm(8, outputs), nn.GELU(),
    )


class SkipBlock(nn.Module):
    def __init__(self, inputs, skip_channels, outputs):
        super().__init__()
        self.skip_projection = nn.Conv2d(skip_channels, outputs, 1)
        self.fusion = conv_block(inputs + outputs, outputs)

    def forward(self, value, skip):
        value = F.interpolate(value, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return self.fusion(torch.cat((value, self.skip_projection(skip)), dim=1))


class UNetDecoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.bottleneck = nn.Conv2d(768, 256, 1)
        self.up16 = SkipBlock(256, 384, 128)
        self.up8 = SkipBlock(128, 192, 64)
        self.up4 = SkipBlock(64, 96, 32)
        self.head = nn.Conv2d(32, 2, 1)

    def forward(self, features, size):
        low, middle, high, deepest = features
        value = self.up16(self.bottleneck(deepest), high)
        value = self.up8(value, middle)
        value = self.up4(value, low)
        return F.interpolate(self.head(value), size=size, mode="bilinear", align_corners=False)


class ConvNeXtTinyUNet(nn.Module):
    def __init__(self, weights="imagenet"):
        super().__init__()
        config(weights)
        pretrained = ConvNeXt_Tiny_Weights.IMAGENET1K_V1 if weights == "imagenet" else None
        self.backbone = ConvNeXtEncoder(pretrained)
        self.classifier = UNetDecoder()
        self.float()

    def forward(self, image):
        if image.ndim != 4 or image.shape[1] != 3 or min(image.shape[-2:]) < 32:
            raise ValueError("Expected NCHW RGB input with height and width at least 32")
        if image.dtype != torch.float32:
            raise ValueError("Input must be FP32, not silently converted")
        if any(p.dtype != torch.float32 for p in self.parameters()):
            raise ValueError("All model parameters must remain FP32")
        # A surrounding mixed-precision context must not change this model's contract.
        with torch.autocast(device_type=image.device.type, enabled=False):
            return {"out": self.classifier(self.backbone(image), image.shape[-2:])}


def make_model(weights="imagenet"):
    configure_fp32()
    return ConvNeXtTinyUNet(weights)
