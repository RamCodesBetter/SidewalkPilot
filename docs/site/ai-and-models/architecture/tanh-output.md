# Tanh Regression Output

Tanh regression is the output design used by Series 1/2 and the v3.0 regression contract. It is not the v3.1+ or Series 4 steering decoder.

For direct steering regression:

```text
unit = tanh(raw)
steering = 90 + scale * unit
```

Tanh bounds the result and gives a simple continuous command, but on a straight-heavy dataset an average-error loss can favor predictions near 90 degrees. That failure mode motivated the later class-plus-offset head.

Series 3 v3.1+ and Series 4 use unbounded class logits plus sigmoid-bounded local offsets. Throttle handling is separate and Series 4 does not learn throttle.

See [Regression Framing](../../research-and-math/machine-learning/regression-framing.md) and [Series 3 Hybrid Head](series-3-hybrid-head.md).
