# Hall Sensor

The wheel hall sensor is the car's speedometer and odometer. It is a `DigitalInputDevice` on GPIO 24 created by `Hardware` in `code/controller/current/rc_car_app/hardware.py`, and its edge callbacks feed the speed/distance math in `runtime.py`. There is no analog readout: speed comes entirely from counting hall pulses over time.

## How it works

When `ENABLE_HALL_SENSOR` is true, `Hardware.__init__` creates `DigitalInputDevice(HALL_SENSOR_GPIO_PIN, pull_up=True)` on GPIO 24 and wires both edges to the runtime's `pulse_detected` callback:

```
self.hall_sensor.when_activated = pulse_callback
self.hall_sensor.when_deactivated = pulse_callback
```

Because both `when_activated` and `when_deactivated` are bound, every transition counts as a pulse. The callback (`pulse_detected` in `runtime.run`) is intentionally small: it only increments a counter and timestamp in gpiozero's callback thread.

```
metrics.pulse_count += 1
metrics.last_pulse_time = time.time()
```

`calculate_speed(state, metrics, dt)` turns those pulses into a speed once every ~0.1 s. It takes the pulses accumulated since the last check, divides by the elapsed time to get pulses/sec, then:

```
revs_per_second = pulses_per_second / PULSES_PER_REVOLUTION
speed_cm_per_sec = revs_per_second * WHEEL_CIRCUMFERENCE_CM
current_raw_mph  = speed_cm_per_sec * CM_PER_SEC_TO_MPH
```

The raw mph is then exponentially smoothed (`SPEED_SMOOTHING_ALPHA`) into `smoothed_speed_mph`, which is what the dashboard, logs, and speed-dependent logic use. When the motor command is essentially zero and raw speed is under 0.2 mph, speed is forced to 0 to avoid jitter at rest. Distance is integrated every loop as `total_distance_cm += (smoothed_speed_mph / CM_PER_SEC_TO_MPH) * dt`, and it also tracks a max-speed recall.

### Constants (from `config.py`)

| Constant | Value | Meaning |
|---|---|---|
| `HALL_SENSOR_GPIO_PIN` | `24` | Input pin (internal pull-up) |
| `ENABLE_HALL_SENSOR` | `True` | Gate; if false, a `DummyDigitalInput` is used |
| `PULSES_PER_REVOLUTION` | `455.0` | Hall edges counted per wheel revolution |
| `WHEEL_DIAMETER_CM` | `7.0` | Drive-wheel diameter |
| `WHEEL_CIRCUMFERENCE_CM` | `π × 7.0` | Distance per revolution |
| `SPEED_SMOOTHING_ALPHA` | `0.2` | EMA weight on the newest raw reading |
| `CM_PER_SEC_TO_MPH` | `0.0223694` | cm/s → mph conversion |

## Why this choice

- Counting edges in a trivial callback and doing the math on a timer keeps the ISR-style path cheap and keeps all the tuning constants (pulses/rev, wheel size, smoothing) in `config.py` where they can be calibrated.
- Using both edges effectively doubles resolution vs. one edge, which matters at the car's low sidewalk speeds.
- Smoothing plus the at-rest zero clamp prevents the dashboard speed from flickering when the car is stopped or crawling.

## Failure symptom

If the hall sensor is disconnected or `ENABLE_HALL_SENSOR` is false, no pulses arrive, `pulse_count` never increments, and `calculate_speed` reports 0 mph and 0 distance even while the motors are clearly driving — the dashboard will show throttle percent but a dead speed readout. Because the sensor is created inside the same `Hardware` init block, a hard init failure also drops the whole controller into all-dummy "simulation mode" (see [Hardware Class](hardware-class.md)).

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
