# Hybrid Head Versus Regression

Series 1/2 and v3.0 directly regress steering. Series 3 v3.1 and later use a
nine-class steering distribution plus one local offset per class.

## Contracts

Series 1/2 produce one bounded steering value. The v3.1+ Series 3 head produces
19 values:

```text
9 class logits + 9 class-local offset logits + 1 throttle logit
```

The steering classes are:

```text
0-45 | 45-60 | 60-75 | 75-85 | 85-95 | 95-105 | 105-120 | 120-135 | 135-180
```

At inference, the highest-logit class is selected and its sigmoid-bounded offset
is mapped within that class. The current runtime ignores the throttle output;
motion policy owns throttle and braking.

## Engineering reason

A direct regression loss can favor values near a common central target on an
imbalanced dataset. A hybrid head makes coarse steering-class behavior visible in
the loss and in evaluation while retaining a continuous within-class angle. It
also introduces an argmax class boundary: a small probability change can switch
the selected class. The architecture therefore changes the error surface; it does
not guarantee turn recall or smooth closed-loop steering.

## Evidence

- v3.0/v3.0b use the regression contract; v3.1 and later use the hybrid contract.
- The common evaluator measures the hybrid models with nine-class recall,
  adjacent-class recall, continuous error, and signed bias.
- v3.3 and v3.3b regressed in the July 13 field comparison despite using the
  hybrid head.
- v3.4 became the field-selected model after completing the presented turn and
  shadow cases.

These observations support keeping class-level evaluation. They do not isolate
the head design as the cause of any checkpoint's field result because data,
training settings, and weights also changed across versions.

## Alternatives

| Head | Advantage | Limitation |
|---|---|---|
| Direct regression | Small and simple | Aggregate losses can hide rare-class behavior |
| Pure classification | Direct class supervision | Quantized output unless a continuous stage is added |
| Class plus local offset | Class metrics plus continuous angle | More complex loss/decoder and class-boundary discontinuities |

## Related pages

- [Series 3 Hybrid Head](../../ai-and-models/architecture/series-3-hybrid-head.md)
- [Model Framing and Loss](../../research-and-math/machine-learning/loss-function.md)
- [Offline and Field Comparison](../../model-evaluation/comparisons/offline-vs-field.md)
