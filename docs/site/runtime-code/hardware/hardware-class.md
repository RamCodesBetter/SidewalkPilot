# Hardware Integration

The `Hardware` class in `code/controller/current/rc_car_app/hardware.py` is the single hardware abstraction layer for the Raspberry Pi 5 controller. It owns every physical actuator and sensor the runtime touches directly on the Raspberry Pi 5: the steering servo through the PCA9685 Servo Controller, the four PWM control channels for the JGB37-520 DC motors (12 V, 550 RPM) through the Yahboom AT8236 Motor Controller, and the wheel hall sensor. The main loop in `runtime.py` never talks to GPIO or I2C directly — it reads and writes attributes on a single `Hardware` instance, which keeps model changes, safety logic, and dashboard code from silently changing pin behavior.

## How it works

`Hardware.__init__(pulse_callback)` builds every device once at startup. It first assigns dummy stand-ins (`DummyServo`, `DummyPWM`, `DummyDigitalInput`) to every attribute, then attempts to bring up the real devices in order:

- Steering servo: if `USE_PCA9685_SERVO` is true, a `PCA9685SteeringServo` wrapper is created for the PCA9685 Servo Controller at I2C address `0x40`, channel 0.
- JGB37-520 drive motors: four `PWMOutputDevice` control channels are opened at 1000 Hz on the AT8236 Motor Controller pins: right forward/backward on GPIO 19/20 and left forward/backward on GPIO 25/13.
- Hall sensor: if enabled, a pull-up `DigitalInputDevice` on GPIO 24 sends both signal edges to the runtime pulse callback.

The exposed interface is deliberately attribute-based. The runtime writes `hardware.steering_servo.value`, `hardware.motor_left_fwd.value`, and so on, and reads hall pulses through the callback. It also exposes `hardware.gpio_initialized` (set true only after every device came up) and `hardware.cleanup()`.

Device creation is retry-guarded. `_init_device(label, pin, factory)` calls the factory up to four times, sleeping 0.25 s between attempts, but only retries on transient `errno.EAGAIN` / "Resource temporarily unavailable" errors — a real wiring/config fault fails fast with a labeled `RuntimeError` naming the device and pin.

## Why this choice

- One abstraction means the whole hardware surface can be swapped for dummies. If any device fails to initialize, the `except` block in `__init__` prints `Error initializing GPIO: ...; Running in simulation mode.`, runs `cleanup()`, and re-assigns all-dummy devices. The rest of the runtime keeps running (useful for bench work off the car, and so a single bad sensor does not crash the whole controller).
- The dummy classes share the same `.value` / `.close()` shape as the real devices, so runtime code never needs to branch on whether hardware is present.
- Keeping every write behind this class enforces the project rule that hardware compensation (steering center trim, per-side motor PWM scaling) lives in the mapping/hardware layer, not in model labels or the control loop.

## Constants and interface

| Field | Value |
|---|---|
| Owning file | `code/controller/current/rc_car_app/hardware.py` |
| Public devices | `steering_servo`, `motor_left_fwd`, `motor_left_bwd`, `motor_right_fwd`, `motor_right_bwd`, `hall_sensor` |
| Init flag | `gpio_initialized` (true only after all devices came up) |
| Retry policy | `_init_device`: 4 attempts, 0.25 s apart, only on `EAGAIN` / "Resource temporarily unavailable" |
| Fallback | On any init error: print, `cleanup()`, then all-dummy devices ("simulation mode") |
| Config gates | `USE_PCA9685_SERVO`, `ENABLE_HALL_SENSOR` in `config.py` |

## Failure symptom

If wiring or I2C is bad at boot, the console prints `Error initializing GPIO: <reason>. Running in simulation mode.` The car then reads/writes dummy devices: steering will not move, motors stay at 0, and the hall sensor never fires, so the dashboard shows 0 speed even while the throttle is applied. The reason string names which device and pin failed.

## Motor and Cleanup Rules

Positive normalized PWM drives the forward pin pair; negative PWM selects reverse. Braking and gear logic are resolved before these writes. Left/right scale factors belong here rather than in model labels, and both are neutral unless a controlled balance test supports a change.

`cleanup()` sets owned outputs to zero and closes GPIO/PCA9685 devices. Initialization failure also invokes cleanup before installing dummy devices. Dummy mode is useful for software work, but it must be treated as "no physical control," not a healthy-car state.

## Related pages

- [Runtime Loop](../runtime-loop.md)
- [Runtime Configuration](../config/servo-settings.md)
- [Bench Tests](../../testing/bench-tests/overview.md)
