# Steering Prediction Framing

SidewalkPilot preserves one physical target convention across model families:

```text
0 degrees = left
90 degrees = center
180 degrees = right
```

## Direct Regression

Series 1/2 and v3.0 predict continuous controls directly. This is simple and compact, but the loss is dominated by common near-straight frames unless sampling and data balance compensate.

## Class Plus Local Regression

Series 3 v3.1+ and Series 4 first classify one of nine steering ranges, then regress a continuous offset inside that range. This is still continuous steering; classification only chooses the local interval.

## Temporal Framing

Series 4 compares:

- PC: previous targets plus image -> current target;
- CF: image -> current and future targets;
- PCF: previous targets plus image -> current and future targets.

Future values are labels used during training, not information supplied during deployment.

See [Series Differences](../../autonomy-stack/camera-steering/series-differences.md) and [Series 4 Temporal Experiments](../../ai-and-models/architecture/series-4-plan.md).
