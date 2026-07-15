# INT8 Post-Training Quantization

INT8 post-training quantization is a possible future deployment experiment. It is not used by the current SidewalkPilot runtime and no current model claim depends on it.

## Concept

PTQ maps FP32 weights/activations to smaller integer representations after training. Activation ranges are estimated from representative calibration frames. The potential benefit is lower memory traffic and faster compatible kernels; the risk is quantization error in class logits and local offsets.

## Required SidewalkPilot Evaluation

An INT8 model would need to be compared with the exact FP32 source artifact on the same frozen challenge subset. The comparison must include Bal9, turn exact, turn +/-1, straight exact, MAE, median, signed error, and confusion matrices. A physical-car test would still be required.

Calibration should cover real shadow, turn, straight, and exposure cases. Merely producing an engine file is not evidence that the model remains usable.

## Repository Status

The prior TensorRT calibration builder referenced by older notes is not in the current tree. Reintroducing PTQ would be a new implementation/review task, not a command that can be run from the current repository as documented.

See [Quantization Math](../../research-and-math/machine-learning/quantization-math.md) and [TensorRT](tensorrt.md).
