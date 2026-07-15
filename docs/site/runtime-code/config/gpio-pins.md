# GPIO Pins

This page documents the GPIO pin assignments and hardware-address constants that the runtime uses to reach the Pi 5's motors, hall sensor, and steering servo. All of these constants live in `code/controller/current/rc_car_app/config.py` and are consumed by `code/controller/current/rc_car_app/hardware.py`, which is the only module that touches the pins directly.

## How it works

Keeping every pin number in one config block means the wiring is described once and imported everywhere else. `hardware.py` imports the pin constants and wraps each output in a `gpiozero` `PWMOutputDevice` (motors) or `DigitalInputDevice` (hall sensor). The steering servo is not a GPIO pin at all: it is driven over I2C through a PCA9685 board, so its "address" is an I2C address plus a channel rather than a BCM pin.

Motor pins are set up as 1 kHz PWM outputs (`PWMOutputDevice(pin, frequency=1000, initial_value=0)`). The Yahboom AT8236 H-bridge takes a forward pin and a backward pin per side; the runtime drives one of the pair to move and holds the other low.

| Constant | Pin (BCM) | Role |
|---|---|---|
| `MOTOR_RIGHT_FWD_PIN` | 19 | Right drive motor forward (PWM) |
| `MOTOR_RIGHT_BWD_PIN` | 20 | Right drive motor backward (PWM) |
| `MOTOR_LEFT_FWD_PIN` | 25 | Left drive motor forward (PWM) |
| `MOTOR_LEFT_BWD_PIN` | 13 | Left drive motor backward (PWM) |
| `HALL_SENSOR_GPIO_PIN` | 24 | Wheel hall sensor input (speed/odometry) |

The steering servo lives on the PCA9685, not a GPIO pin:

| Constant | Value | Role |
|---|---|---|
| `USE_PCA9685_SERVO` | `True` | Use the PCA9685 path instead of a direct-GPIO servo |
| `PCA9685_I2C_ADDRESS` | `0x40` | I2C address of the PCA9685 board |
| `PCA9685_SERVO_CHANNEL` | `0` | PCA9685 output channel the steering servo is on |

Two feature flags in the same block decide whether the hall sensor is wired at all:

- `ENABLE_HALL_SENSOR = True` — when `True`, `hardware.py` builds a `DigitalInputDevice(HALL_SENSOR_GPIO_PIN, pull_up=True)` and attaches the pulse callback on both edges (`when_activated` and `when_deactivated`).

## Why this choice

Pin numbers describe physical wiring, so they belong in config rather than being scattered through the loop. The hall sensor is on GPIO 24 with an internal pull-up, and the runtime counts both signal edges. The motors use forward/backward pins per side because the AT8236 is a dual H-bridge. This also permits independent motor scaling, which remains at `1.0` on both sides unless a controlled balance test supports a change.

## Failure symptom

If a pin is wrong or the device is busy, `hardware.py` retries device init up to four times on `Resource temporarily unavailable`, then raises. On any GPIO init failure the whole `Hardware` object falls back to dummy devices and prints `Error initializing GPIO: ...  Running in simulation mode.` — the car will then "run" with no motor or servo output, which on the dashboard looks like a live controller that never moves the wheels.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
