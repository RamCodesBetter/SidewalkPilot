# Servo Output

The last stage of the camera-steering pipeline: turning a decoded steering angle into an
actual PCA9685 pulse that moves the front wheels.

## How it works

The model's steering decision arrives as a logical servo angle in the frame **0=left,
90=center, 180=right**. In `apply_autonomous_controls()` (`runtime.py`) that angle is
clamped, stored as `state["steering_servo_deg"]`, and also normalized to `steer` in
`[-1, 1]` and a `target_heading_deg`. In `update_gpio()` the runtime writes the angle to
`hardware.steering_servo.value`. A configurable snap threshold changes logical values less
than `0.5` degrees from center to exactly `90`.

The hardware layer is `PCA9685SteeringServo` in
`code/controller/current/rc_car_app/hardware.py`, driving a servo on the PCA9685 at I2C
`0x40`, channel `0`, `50 Hz`, with a `1000–2000 µs` pulse range over a `180°` actuation
range. The `value` setter does **not** write the logical angle straight to the servo — it
passes through `apply_steering_center_trim_degrees()`, which applies:

- A piecewise-linear logical-to-reference mapping with limits `48.812` and `131.188`, and
- A checked-in center offset of `12/90 = 0.133333...`, adding 12 physical degrees.

The generic near-center preload path is disabled because both its value and window are
`0.0`. With these defaults, logical center `90` produces physical angle `102`.

This is the key design rule made concrete: the model and training labels think in clean
logical steering (0/90/180), and all servo-specific mechanical compensation lives here in
the hardware mapping — never baked into the model output or the CSV labels.

## Why this choice

Isolating trim in the hardware layer keeps the model honest. If center offset were folded
into the model's output, every retrain would inherit one servo's mechanical quirks and the
training labels would no longer mean "point straight." By compensating at
`apply_steering_center_trim_degrees()`, the checkpoint can remain unchanged when the
hardware mapping is recalibrated. Motor scaling and steering trim remain separate controls;
the current configuration leaves both motor scales at `1.0`, and the documentation does not
assign an observed pull to one cause without a controlled test.

## Constants used by this page

- PCA9685: `0x40`, channel `0`, `50 Hz`, pulse `1000–2000 µs`, range `180°` (`config.py`)
- Reference limits `48.812` and `131.188`; center offset `0.133333...`; preload and window
  both `0.0` (`config.py`)
- Center snap threshold `0.5` degrees (`update_gpio()`, `runtime.py`)

## Related pages

- `autonomy-stack/architecture/layered-autonomy.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
