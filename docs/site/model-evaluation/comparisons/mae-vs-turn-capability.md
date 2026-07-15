# MAE vs Turn Capability

Mean absolute error measures degree error per frame. It does not know which frames are operationally important.

## The Imbalance

The common challenge set contains 4,741 straight targets and 2,211 turn targets. A center-biased model can be close on the majority while failing the smaller set of steering events that keep the car on the sidewalk.

## Concrete Examples

| Comparison | Lower MAE | Stronger turn evidence | Field result |
|---|---|---|---|
| v3.4 vs v3.4b | v3.4b: 13.985 | v3.4: turn exact 22.6%, +/-1 56.2% | v3.4 won |
| `4.0p` vs `4.0r` | `4.0r`: 11.636 | `4.0p`: Bal9 34.5%, turn exact 32.1% | pending |
| `4.0a` vs `4.0c` | `4.0c`: 11.321 | `4.0a`: Bal9 33.5%, turn exact 30.9% | pending |

The best-validation partners often have lower MAE and higher ST recall. The final checkpoints often retain more turn behavior. That is a testable pattern, not a rule that final is always better.

## Selection Rule

Use MAE after class balance and turn capability have passed. Then verify the closed-loop car. The project does not reject numeric error; it refuses to let the straight majority hide missing turns.

See [Bal9](../offline-evaluation/bal9.md) and [Model Selection Rubric](model-selection-rubric.md).
