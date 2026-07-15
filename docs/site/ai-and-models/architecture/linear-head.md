# Linear Heads

Most Series 3/4 parameters are in the dense image encoder after the convolutional feature map is pooled to `160x6x10` (9,600 values).

## Series 3

The dense path is:

```text
9600 -> 512 -> 256 -> 64 -> output
```

v3.0 ends in two regression outputs. v3.1+ ends in 19 values: nine logits, nine offsets, and throttle.

## Series 4

Series 4 first produces a 256-value image feature. CF maps it to 64 features and uses four `64 -> 18` horizon heads. PC/PCF encode three history targets through `3 -> 32 -> 64`, concatenate history with image features, fuse `320 -> 128 -> 64`, then use one or four 18-value heads.

The history/fusion branch accounts for most of the difference between the approximately 22.15 MB CF file and approximately 22.28-22.29 MB PC/PCF files.

See [CNN](cnn.md) and [Series 4 Temporal Experiments](series-4-plan.md).
