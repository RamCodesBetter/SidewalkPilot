# Motors

The car uses JGB37-520 DC drive motors rated for 12 V and 550 RPM. They are driven by a
Yahboom AT8236 Motor Controller, which the Raspberry Pi 5 controls with PWM on four GPIO
pins. Steering is separate (a servo on the PCA9685); these motors only provide thrust.

## Parts (Amazon)

- [Yahboom AT8236 Motor Controller](https://www.amazon.com/Yahboom-Controller-AT8236-H-Bridge-Raspberry/dp/B0BVW7PBYW/ref=sr_1_1?dib=eyJ2IjoiMSJ9.uPNafB0Kecl7MEifvky-Os4jq9LSVLKfYZ7ng7QQyCusNhtxa5eWjFZ0gjil7eLqQtz6A-GbYKyZXwdw432rlWBHtOqQWKJaU9NIKS05CPcQ9cay-cspsfSoXnukBXOGOoMaqYK5hOnGgK2L1PYDXVb9lNHt7H6HH1stR_3gc1O4vMcXviPEp4CKCcOh8c2F_DAkKhYTZGDTjyLmKcLu__rs3sfnahMZBBAGsrQoyvHIROsZDXMkPHNpqFdAV74yTVv22c8zVqZE3uDRF7uhoXd5wNsgoVEj5WDY3Y9kkkk.cDRzL8BTvFn8RCop3P581cf5S1qfAQCxjEKbVSsehe0&dib_tag=se&keywords=Yahboom%2BDual%2BMotor%2BDrive%2BController%2BBoard%2BModule%2BAT8236%2BDual%2BH-Bridge%2BDC%2BStepper%2Bfor%2BArduino%2BRaspberry%2BPi%2BSTM32%2B(Motor%2BDrive%2BModule%2B%2BPower%2BCable)&nsdOptOutParam=true&qid=1779578440&sr=8-1&th=1) — $12.99

## Motor specification

| Specification | Value |
|---|---|
| Model | JGB37-520 |
| Type | DC geared motor |
| Rated voltage | 12 V DC |
| Rated speed | 550 RPM |

## Wiring

Left and right sides each have a forward and a backward PWM channel (from `config.py`):

| Channel | GPIO pin |
|---|---|
| Right forward | `19` |
| Right backward | `20` |
| Left forward | `25` |
| Left backward | `13` |

Each channel is a `PWMOutputDevice` at **1 kHz** (`hardware.py`). To drive forward,
the forward pins get a PWM duty and the backward pins stay at 0; reverse swaps them.

## How it works

- The control loop computes a motor PWM value (0..1) from throttle, cruise/PID, or autonomy,
  clamped by acceleration/brake rates, and writes it to the AT8236 Motor Controller through the four GPIO
  channels.
- Per-side scaling constants `LEFT_MOTOR_PWM_SCALE` and `RIGHT_MOTOR_PWM_SCALE` (both `1.0`
  currently) can trim a measured drive-force mismatch. A pull can also come from steering
  alignment, linkage load, tires, surface, or payload, so motor scaling should change only
  after a restrained/straight-line test isolates motor thrust as the cause.
- Partial braking ramps PWM toward zero using the configured brake rates. A full brake
  force (including an AEB emergency stop) bypasses that ramp, forces motor PWM to zero,
  and drives both AT8236 Motor Controller inputs high on each side for active brake mode.

## Why this choice

- The AT8236 Motor Controller is sized for this chassis and exposes simple
  PWM/direction control that maps cleanly onto four GPIO pins.
- Keeping optional left/right motor scaling separate from steering calibration makes the two
  effects measurable instead of hiding one inside the other.

## Verify before a run

- Bench test: the hall sensor (`code/test_files/sensors/hall_sensor_test.py`) confirms wheel
  rotation and feeds the speed estimate.
- A car that pulls with logical steering centered is a symptom, not a diagnosis. Compare
  physical wheel alignment, free-wheel behavior, loaded motor speed/current, tire condition,
  surface, and payload before changing either PWM scale or steering trim.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
