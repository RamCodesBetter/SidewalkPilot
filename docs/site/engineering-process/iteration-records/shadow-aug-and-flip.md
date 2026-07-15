# Shadow Augmentation and Horizontal Flip

This page records the available Series 3 augmentation mechanisms and the hypothesis behind
the v3.3 experiment. The exact v3.3 launch command and resolved probabilities were not
preserved, so current trainer defaults are not presented as historical run settings.

## Implemented mechanisms

`series_3_sidewalkpilot_trainer.py` contains synthetic shadow, mixed-lighting, diagonal-band,
tree-shadow, edge-shadow, glare, and concrete-texture transforms. Their command-line gates
control whether they are sampled during training. The trainer also supports horizontal flip:

```python
img = cv2.flip(img, 1)
steer = 180.0 - steer
```

Mirroring swaps left and right while preserving steering magnitude. Flipping straight
frames does not add turn coverage, so a turn-focused sampling policy can avoid spending
extra augmentation draws on an already common class.

## Historical hypothesis

The working hypothesis was that a different shadow-augmentation strength and more balanced
left/right turn exposure could reduce shadow-following without losing turns. That is a
plausible experiment, not a proven diagnosis of v3.3's behavior. Current default values show
what the trainer would use today; they do not reconstruct the deleted or unsaved v3.3
command.

## Result

Offline behavior was not enough to promote the experiment. In the July 13 physical
comparison, v3.3 was worse than v3.2 and v3.3b was much worse than v3.2b according to the
operator's bounded qualitative verdict. v3.4 performed best on the normal turns and shadow
cases presented in that session.

This mismatch is the useful result: augmentation choices must pass the car-level test, and
the next comparison should preserve the route, conditions, takeover criteria, and clips.

## Evidence limits

- The v3.3 launch command and resolved augmentation configuration were not preserved.
- The July 13 verdict has no saved route identifier or normalized takeover rate.
- No causal claim is made that one augmentation parameter alone produced the regression.

## Related pages

- `engineering-process/iteration-records/bang-bang-collapse.md`
- `ai-and-models/training-pipeline/augmentation.md`
- `testing/failures/shadow-failures.md`
