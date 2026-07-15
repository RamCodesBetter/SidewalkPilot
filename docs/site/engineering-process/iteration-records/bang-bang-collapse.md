# Bang-Bang Collapse

"Bang-bang" describes steering that spends too much time near the endpoints
instead of producing stable intermediate commands. In SidewalkPilot, this is a
failure pattern to look for, not a proven diagnosis for every weak model.

## Observable symptom

Logical steering uses `0` for full left, `90` for center, and `180` for full
right. A suspicious checkpoint may put unusually large fractions of its
predictions in the hard-left and hard-right classes while leaving the middle
classes nearly empty. On the car, an analogous symptom would be abrupt
left-right corrections instead of smooth tracking.

The evidence surfaces are:

- The predicted-class distribution printed during training;
- The nine-class confusion matrix and per-class recall in the common evaluator;
- Steering telemetry and video from a field run.

These surfaces can establish that endpoint-heavy behavior occurred. They do not,
by themselves, establish why it occurred.

## Historical investigation

Earlier notes proposed strong shadow augmentation and turn rebalancing as causes
of endpoint-heavy predictions. Those are reasonable hypotheses because they
change the image distribution and class exposure, but the project did not run a
controlled ablation that isolated either factor. They must not be reported as
proven root causes.

The current Series 3 trainer uses a nine-class hybrid head: class logits plus a
within-class offset. Its weighted sampler is based on inverse class frequency
raised to `sampler_balance_power` and optional source weighting. Although a
legacy `steering_magnitude_weight()` helper remains in the file, the current
Series 3 sampler does not call it.

## Current conclusion

- Endpoint-heavy predictions are detectable offline through class distributions
  and confusion matrices.
- Field behavior remains the promotion gate because an offline distribution does
  not prove smooth closed-loop control.
- v3.3 and v3.3b were field-tested on July 13, 2026. v3.3 performed worse than
  v3.2, and v3.3b performed much worse than v3.2b, so neither was promoted.
- v3.4 subsequently passed the presented normal-turn and shadow tests and became
  the field-selected baseline.
- No single root cause for the v3.3 regressions has been established.

## Evidence still worth collecting

- Synchronized steering-command telemetry and field video for any future
  endpoint-heavy failure;
- Controlled retrains that change one augmentation or sampling parameter at a
  time;
- Before/after confusion matrices evaluated on the same frozen challenge set.

## Related pages

- [Shadow Augmentation and Flip](shadow-aug-and-flip.md)
- [Turn vs Shadow Tradeoff](turn-vs-shadow-tradeoff.md)
- [Confusion Matrix](../../model-evaluation/offline-evaluation/confusion-matrix.md)
