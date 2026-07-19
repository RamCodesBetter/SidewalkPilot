---
name: sidewalkpilot-jetson-readiness
description: Audit a live Jetson Orin Nano for SidewalkPilot steering-inference readiness and runtime health. Use when checking the SidewalkPilot model files, ONNX Runtime CUDA provider, private Ethernet address, inference server process, TCP port 8770, or when diagnosing why the Raspberry Pi 5 cannot receive Jetson predictions.
---

# SidewalkPilot Jetson Readiness

Use this project skill on the Jetson Orin Nano host. Keep the workflow read-only unless the
user separately approves a repair.

## Workflow

1. Run NVIDIA's installed `jetson-diagnostic` snapshot first:

   ```bash
   bash ~/.codex/skills/jetson-diagnostic/scripts/snapshot.sh \
     --human --tegra-secs 3 --top-procs 10
   ```

   If that path is unavailable, try `~/.claude/skills/jetson-diagnostic/` or the original
   `~/jetson-device-skills/skills/jetson-diagnostic/` clone. Do not replace missing Jetson
   fields with generic workstation values.

2. Run the SidewalkPilot-specific check:

   ```bash
   python3 {baseDir}/scripts/check_readiness.py \
     --repo /nvme/rc_car_code --model 3.4 --human
   ```

3. Report these results explicitly:

   - detected Jetson model;
   - requested SidewalkPilot model path;
   - ONNX Runtime version and active providers;
   - whether `CUDAExecutionProvider` is available;
   - whether `jetson_inference_server.py` is running;
   - whether TCP port `8770` is listening;
   - whether the private Ethernet address `10.42.0.2` is assigned;
   - `deployment_ready` and `runtime_healthy` from the script.

4. If memory is the problem, hand off to NVIDIA's `jetson-memory-audit`. Use
   `jetson-package` before recommending a replacement ONNX Runtime wheel. Do not use the
   LLM-serving, LLM-benchmark, speculative-decoding, or LLM memory-tuning skills for the
   SidewalkPilot steering CNN.

## Safety Rules

- Never start autonomous driving, move steering, or write motor outputs from this skill.
- Never install packages, change `nvpmodel`, disable services, alter networking, or enable
  headless mode without explicit approval.
- A missing process or listener means the runtime is inactive; it does not prove the model
  or device is broken.
- A CPU-only ONNX Runtime provider is a deployment failure for the selected live Series 3/4
  path, even if a one-frame test technically runs.
- Preserve NVIDIA's skills as a separate clone so `git pull` can update them. This skill
  complements rather than copies NVIDIA's catalog.

NVIDIA source: https://github.com/NVIDIA-AI-IOT/jetson-device-skills
