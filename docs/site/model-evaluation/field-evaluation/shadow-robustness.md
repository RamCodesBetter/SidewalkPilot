# Shadow Robustness

Shadow robustness means maintaining the intended sidewalk path when hard sunlight/shadow boundaries cross the camera image without treating those boundaries as sidewalk edges.

## July 13, 2026 Comparison

The same field session compared four Series 3 checkpoints on shadow cases and normal left/right turns.

| Rank | Model | Operator field verdict |
|---:|---|---|
| 1 | **3.4** | Completed every shadow case presented during the run; strongest overall |
| 2 | 3.4b | Slightly worse than regular 3.4 |
| 3 | 3.3 | Major regression; worse than 3.2 |
| 4 | 3.3b | Severe regression; much worse than 3.2b |

The comparison promotes `SidewalkPilot-v3.4.onnx` as the runtime default. It does not prove universal shadow handling: route, exact time, weather, video, and manual-takeover count were not recorded in the chat report and must not be invented after the run.

## Interpretation

The v3.3 trainer used a more aggressive shadow regime that produced unstable, bang-bang behavior. The v3.4 adjustments softened the problematic tree-shadow path and restored useful field behavior. This is evidence that augmentation realism and probability matter more than simply maximizing augmentation strength.

Offline MAE remains secondary. A straight-heavy validation set can reward center collapse even when field turns are poor. Use the model report for reproducible metrics, but use this fixed field comparison to decide which checkpoint drives the car.

## Required Retest Record

For the next comparison, save:

- date and local time;
- route/side of road and direction of travel;
- sun position, weather, and surface condition;
- model version and regular/b checkpoint type;
- every manual takeover and reason;
- a video or interruption clip for every failure; and
- whether left turn, right turn, diagonal shadow, tree shadow, and bright-to-dark transition passed.

Retest after changing the dataset, augmentation, preprocessing, temporal smoothing, steering trim, camera position, or model architecture.
