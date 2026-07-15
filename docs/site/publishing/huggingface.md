# Hugging Face - Models & Datasets

This is the **single page** for every SidewalkPilot model and dataset. Full descriptions
(model cards, dataset cards, checkpoints, ONNX exports, images/labels) live on Hugging Face -
they are **not** duplicated in these docs.

Profile: <https://huggingface.co/ram-shreyas-naik-sabavat>

## Models

Every published version is its own HF repo (`SidewalkPilot-v{version}`) with one model artifact, a card, and an artifact manifest. Series 4 artifacts remain local until physical review determines which versions deserve public model repositories.

**Series 1** — [v1.0](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.0) · [v1.0b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.0b) · [v1.1](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.1) · [v1.1b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.1b) · [v1.2](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.2) · [v1.2b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.2b) · [v1.3](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.3) · [v1.3b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.3b) · [v1.4](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.4) · [v1.4b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.4b) · [v1.5](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.5) · [v1.5b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.5b) · [v1.6](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.6) · [v1.6b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.6b) · [v1.7](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.7) · [v1.7b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.7b) · [v1.8](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.8) · [v1.8b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.8b) · [v1.9](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.9) · [v1.9b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v1.9b)

**Series 2** — [v2.0](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.0) · [v2.0b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.0b) · [v2.1](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.1) · [v2.1b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.1b) · [v2.2](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.2) · [v2.2b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.2b) · [v2.3](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.3) · [v2.3b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.3b) · [v2.4](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.4) · [v2.4b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v2.4b)

**Series 3** — [v3.0](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.0) · [v3.0b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.0b) · [v3.1](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.1) · [v3.1b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.1b) · [v3.2](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.2) · [v3.2b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.2b) · [v3.3](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.3) · [v3.3b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.3b) · [v3.4](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.4) · [v3.4b](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.4b)

**Series 4** — all six local artifacts are trained, exported to ONNX, included in the common evaluator, and supported by the Jetson Orin Nano runtime: `4.0p/4.0r` (PC), `4.0f/4.0g` (CF), and `4.0a/4.0c` (PCF). They are not yet field-tested or published as model repositories.

## Datasets

| Repo | Covers | Link |
|---|---|---|
| `SidewalkPilot_v1_and_v2` | Series 1/2 real batches (D0328-D0510) | <https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v1_and_v2> |
| `SidewalkPilot_v3_and_v4` | Shared 81,237-image real dataset for Series 3 and experimental Series 4 | <https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v3_and_v4> |
| `SidewalkPilot_carla` | CARLA synthetic frames | <https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_carla> |
