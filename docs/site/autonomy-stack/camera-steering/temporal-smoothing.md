# Temporal Smoothing

Smoothing the per-frame argmax steering class over time to stop the blocky flip-flop the
raw classification head produces.

## How it works

The Series-3 head is a classifier: 9 steering buckets (HL, L, L+, SL, ST, SR, R, R+, HR)
plus per-class offsets and a throttle. Taking the `argmax` bucket each frame is
discontinuous — if two adjacent buckets are nearly tied, the winner can flip frame to
frame even though the scene barely changed, and the steering command jumps in visible
steps. That was seen directly in the v3.1b field test: steering was "blocky," with the
argmax flipping between neighbors.

Temporal smoothing filters the *sequence* of predictions instead of trusting each frame in
isolation. The per-class offset already softens *within* a bucket; smoothing softens the
transitions *between* buckets. The trade-off is latency: too much smoothing lags real
turns, while too little leaves the flip-flop in.

The current runtime uses `STEERING_SMOOTH_ALPHA = 0.45`. The Pi applies this exponential
blend once per newly completed Jetson inference result, not once per 60 Hz controller tick.
If `x_t` is the decoded steering result and `y_(t-1)` is the prior smoothed command, the
new command is `y_t = 0.45*x_t + 0.55*y_(t-1)`. Series 1/2 use a continuous regression
output and do not pass through this Jetson-result smoothing path.

This shipped output filter is separate from Series 4's causal target history. Smoothing
changes the command sent to the car; PC/PCF history changes the information supplied to
the model at its next inference.

## Why it matters

A model that steers in visible steps is uncomfortable to watch and hard to trust, and the
sharp jumps stress the steering linkage (which already has hysteresis,
`steering-hysteresis.md`). More importantly, argmax flips are a symptom, not the disease:
they show up worst exactly where buckets are close together — the mid-turn and
turn-in-shadow cases that are the model's real weakness. Smoothing makes driving look
clean, but the durable fix is more real turn-in-shadow data so the buckets aren't ambiguous
in the first place.

## Related pages

- `ai-and-models/architecture/series-3-hybrid-head.md`
- `autonomy-stack/camera-steering/servo-output.md`
- `model-evaluation/field-evaluation/interruption-clips.md`
