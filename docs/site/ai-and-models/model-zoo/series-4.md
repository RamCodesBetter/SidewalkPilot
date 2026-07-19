# Series 4 Models

Series 4 keeps the Series 3 image backbone and hybrid steering bins while testing temporal information. All six checkpoints are trained, exported to ONNX, and selectable in the live runtime. None has a physical-car verdict yet, so v3.4 remains the live default.

## Checkpoints

| Pair | Final | Best validation | Contract |
|---|---|---|---|
| PC | `4.0p` | `4.0r` | previous + current |
| CF | `4.0f` | `4.0g` | current + future |
| PCF | `4.0a` | `4.0c` | previous + current + future |

- **PC:** runtime input is the image plus three previous steering targets; output is `[batch,1,18]`.
- **CF:** runtime input is the image; output is `[batch,4,18]`.
- **PCF:** runtime input is the image plus three previous steering targets; output is `[batch,4,18]`.

Every horizon is 18 values: nine class logits and nine class-local offsets. There is no learned throttle. The live runtime decodes horizon 0; later horizons are auxiliary training outputs.

## Common Evaluation

Balanced and exact-class metrics:

| Model | Bal9 | Turn exact | ST exact |
|---|---:|---:|---:|
| **4.0p** | **34.5%** | **32.1%** | 67.7% |
| 4.0r | 32.9% | 27.4% | **77.6%** |
| 4.0f | 25.4% | 23.5% | 62.8% |
| 4.0g | 20.4% | 17.1% | 76.0% |
| 4.0a | 33.5% | 30.9% | 68.1% |
| 4.0c | 32.0% | 29.4% | 75.5% |

Adjacent-class turn tolerance:

| Model | Turn +/-1 |
|---|---:|
| **4.0p** | **65.9%** |
| 4.0r | 62.6% |
| 4.0f | 56.4% |
| 4.0g | 46.4% |
| 4.0a | 65.3% |
| 4.0c | 62.9% |

Numeric steering error in degrees:

| Model | MAE | Median | Signed |
|---|---:|---:|---:|
| **4.0p** | 12.396 | 2.967 | +0.120 |
| 4.0r | 11.636 | 1.846 | -1.136 |
| 4.0f | 15.623 | 6.723 | +1.057 |
| 4.0g | 14.116 | 2.114 | -1.864 |
| 4.0a | 12.379 | 3.115 | +0.290 |
| 4.0c | **11.321** | **1.825** | -0.981 |

The field order below is a test sequence, not a claim of field quality. `4.0p` leads the equal-weight class and turn metrics; `4.0c` leads numeric error. That disagreement is exactly why both should be driven.

## Comparison Baseline

On the same subset, v3.4 scores Bal9 24.2%, turn exact 22.6%, turn +/-1 56.2%, straight exact 64.2%, and MAE 15.083 degrees. The PC and PCF candidates clear the intended offline comparison gate on the balanced and turn metrics. The weaker CF results remain useful negative evidence. No Series 4 model has cleared the field gate.

## Field Order

1. v3.4 baseline
2. `4.0p`
3. `4.0r`
4. `4.0a`
5. `4.0c`
6. v3.4b
7. `4.0f`
8. `4.0g`
9. Optional v3.4 repeat

Use the same route and test normal left/right turns on both sidewalk sides plus the harsh-shadow cases that separated v3.4 from v3.3. Record every takeover and do not infer a winner from one clean section.

See [Series 4 Temporal Experiments](../architecture/series-4-plan.md) for the layer-by-layer design.
