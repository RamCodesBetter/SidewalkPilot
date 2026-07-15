# Overfitting Risk

Overfitting is when a model fits training examples without learning behavior that transfers to held-out scenes or the car. SidewalkPilot also has a label-prior risk: straight frames are the largest class, so a near-center predictor can obtain a deceptively competitive aggregate error while missing turns. That is why the project reads class-balanced and turn metrics alongside MAE.

## Where the risk comes from

Real sidewalk driving is mostly straight lines with occasional turns, so a naive training set is dominated by near-`90` steering labels. A model that ignores the image and outputs the mean label gets a low average error while being useless at exactly the moments that matter (turns, turns-in-shadow). The documented **key finding** is that this is invisible to MAE:

> MAE alone can reward center-biased predictions on a straight-heavy set. Read it with per-class recall, confusion balance, signed error, and field behavior.

So an "improving" MAE curve can actually mean the model is getting worse at driving.

## The Countermeasures in Code

`code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py` layers several defenses:

- **Dropout in the head.** `SidewalkPilotV3` uses `nn.Dropout(p=0.18)` and `nn.Dropout(p=0.12)` between the fully connected layers; `SteeringAutonomyV2` (Series 1/2) uses `nn.Dropout(p=0.10)`. Dropout is a regularizer; it reduces one route to co-adaptation but does not prevent memorization.
- **Weight decay.** AdamW runs with `weight_decay=1e-4`, an L2 pull that keeps weights small and the function smoother.
- **Train-time augmentation** (see `sim-to-real-gap.md`): camera jitter, contrast/brightness, channel jitter, and shadow/glare/texture transforms change sampled training views. This can reduce reliance on exact pixels, but it does not prevent memorization or guarantee generalization.
- **Balanced sampling.** `make_weighted_sampler` oversamples rare turn buckets and correction frames so the gradient is not swamped by straight frames — this attacks the straight-collapse directly.
- **Turn-weighted loss and penalties.** Turn errors count up to 3x, and an oversteer/saturation penalty discourages the lazy extremes (see `loss-function.md`).
- **Clean validation + best-checkpoint selection.** Validation runs on un-augmented held-out frames (see `validation-split.md`), and the `-best` checkpoint is chosen by validation loss, not training loss.

| Field | Value |
|---|---|
| Dominant risk | straight-collapse (overfitting the near-`90` label prior) |
| Regularizers | dropout `0.10–0.18`, `weight_decay=1e-4`, augmentation, weighted sampler |
| Detection | per-bucket prediction counts + confusion balance, **not** MAE |
| Trainers | `code/ai_models_datasets/series_1_and_2/sidewalkpilot_trainer.py`; `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py` |

## How overfitting is detected in practice

`evaluate()` prints, alongside MAE, the count of predictions in each servo bucket. A center-collapsed model concentrates predictions in `85..95` while targets remain spread across turn buckets. The common evaluator makes that mismatch visible in the nine-class confusion matrix. Final and `b` checkpoints are therefore both retained until offline and field evidence can be compared.

## Worked example

Two models on a validation set that is 80% straight, 20% turns.

```
Model A (straight-collapsed): predicts 90 for everything
  MAE ~ 0.2 * (avg turn magnitude in deg)  -> looks LOW
  turn buckets predicted: 0   -> useless on turns

Model B (balanced): follows the turns, small jitter on straights
  MAE slightly HIGHER (jitter on the 80% straight frames)
  turn buckets predicted: populated -> actually drives
```

Picking by MAE selects Model A. Picking by bucket balance / turn capability selects Model B. SidewalkPilot picks B.

## What can go wrong

- **Trusting MAE / picking the "-best" file blindly.** Early-epoch checkpoints can win on MAE by collapsing to straight. Read the bucket printout and prefer the balanced checkpoint.
- **Too much augmentation.** Overly aggressive shadow/jitter can push the model to *under*-fit turns (it treats real turn cues as noise). The shadow probability was softened in a later retrain precisely because too-hard augmentation killed the left and soft-right buckets.
- **Synthetic data is not field evidence.** Shadow augmentation can broaden training coverage, but promotion still requires real turn-in-shadow testing (see `sim-to-real-gap.md`). v3.4 passed the shadow cases presented in its July 13 field run; that bounded result is not a claim about every possible sidewalk or lighting condition.

## Related pages

- `research-and-math/machine-learning/regression-framing.md`
- `ai-and-models/training-pipeline/overview.md`
- `autonomy-stack/navigation/overview.md`
