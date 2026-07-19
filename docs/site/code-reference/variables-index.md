# Variables Index

This page lists the constants a reviewer is most likely to search for: pins,
calibration values, thresholds, and defaults. Almost all of them live in
`code/controller/current/rc_car_app/config.py` (runtime) or at the top of the
Series trainers (training). Keeping them here means a reviewer can confirm a wire,
a threshold, or a default without opening the module.

## GPIO pins (`config.py`)

| Constant | Value | Meaning |
|---|---:|---|
| `MOTOR_RIGHT_FWD_PIN` / `MOTOR_RIGHT_BWD_PIN` | `19` / `20` | Right drive motor forward/backward (Yahboom AT8236). |
| `MOTOR_LEFT_FWD_PIN` / `MOTOR_LEFT_BWD_PIN` | `25` / `13` | Left drive motor forward/backward. |
| `HALL_SENSOR_GPIO_PIN` | `24` | Wheel speed hall sensor. |

## Steering servo (`config.py`)

| Constant | Value | Meaning |
|---|---:|---|
| `PCA9685_I2C_ADDRESS` | `0x40` | Servo Controller I2C address. |
| `PCA9685_SERVO_CHANNEL` | `0` | Steering servo channel. |
| `PCA9685_FREQUENCY_HZ` | `50` | Servo PWM frequency. |
| `STEERING_SERVO_MIN_PULSE_US` / `MAX_PULSE_US` | `1000` / `2000` | Pulse-width range. |
| `STEERING_SERVO_ACTUATION_RANGE_DEG` | `180` | Logical range; `0`=left, `90`=center, `180`=right. |
| `STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG` / `_RIGHT_LIMIT_DEG` | `48.812` / `131.188` | Reference steering endpoints used by the physical mapping. |
| `STEERING_SERVO_CENTER_OFFSET` | `17 / 90` by default | +17 degree center trim represented as a normalized offset; persisted tuning can override it. |
| `STEERING_SERVO_CENTER_PRELOAD` / `_WINDOW` | `0.0` / `0.0` | Former preload mechanism, currently disabled. |

`LEFT_MOTOR_PWM_SCALE` and `RIGHT_MOTOR_PWM_SCALE` are both `1.0`, so no motor-balance
correction is active. They can support a controlled test but do not establish the cause of
an observed pull.

## Autonomy and safety thresholds (`config.py`)

| Constant | Value | Meaning |
|---|---:|---|
| `MAX_AUTONOMOUS_SPEED_MPH` | `3.2` | Declared target only; not currently enforced as a final speed governor. |
| `CAMERA_STEER_GAIN` / `CAMERA_TURN_BLEND` | `0.75` / `0.35` | Legacy declarations; current neural steering uses decoded servo degrees directly. |
| `LOW_CAMERA_CONFIDENCE` / `HIGH_CAMERA_CONFIDENCE` | `0.25` / `0.60` | Low gate is active; high threshold is declared but unused. Fresh accepted neural results currently report `1.0`. |
| `LIDAR_GOV_FULL_M` | `1.65` | Full-throttle end of the center-corridor governor. |
| `LIDAR_GOV_STOP_M` | `1.25` | Point where the governor reaches its minimum moving target. |
| `LIDAR_OVERRIDE_EMERGENCY_STOP_M` | `1.05` | Center-corridor emergency-stop boundary. |
| `LIDAR_GOV_MIN_REFERENCE` | `0.60` | Minimum non-stop target on the useful reference throttle scale. |
| `LIDAR_MIN_MOVE_PWM` | `0.55` | Measured physical dead-zone boundary used by reference-throttle mapping. |
| `AEB_ACTIVATION_DELAY_SEC` | `1.0` | Legacy declaration; no current runtime path reads it, so it does not delay AEB. |

## Speed, PID, motor rates (`config.py`)

| Constant | Value | Meaning |
|---|---:|---|
| `WHEEL_DIAMETER_CM` | `7.0` | Wheel diameter for distance/speed. |
| `PULSES_PER_REVOLUTION` | `455.0` | Hall pulses per wheel revolution. |
| `CM_PER_SEC_TO_MPH` | `0.0223694` | Unit conversion. |
| `KP` / `KI` / `KD` | `0.50` / `0.08` / `0.005` | Cruise-control PID gains. |
| `ACCEL_RATE` / `BRAKE_RATE` / `AEB_BRAKE_RATE` | `0.5` / `8.0` / `10.0` | Throttle/brake ramp rates. |

## Dashboard telemetry (`config.py`)

| Constant | Value | Meaning |
|---|---:|---|
| `HUB75_DASHBOARD_TRANSPORT` | `udp` | USB-Ethernet UDP is the default link. |
| `HUB75_DASHBOARD_HOST` | `192.168.10.2` | Zero 2 W address. |
| `HUB75_DASHBOARD_UDP_PORT` | `8765` | Telemetry UDP port. |
| `HUB75_DASHBOARD_SEND_INTERVAL_SEC` | `0.1` | Send cadence. |
| `DASHBOARD_PAGE_COUNT` | `17` | Highest valid internal dashboard page ID; visible pages use sparse IDs. |

## State and metrics factories (`config.py`)

| Symbol | Meaning |
|---|---|
| `create_state()` | Returns the mutable per-run state dict (steer, throttle, gear, LiDAR distances, camera bias, dashboard paging, ~60 keys). |
| `Metrics` (dataclass) | Rolling counters: pulse counts, smoothed speed, PID error, AEB flags, turn-signal timing. |
| `CSV_HEADERS` | The 46-column log schema; must stay aligned with `logging_utils.log_data_to_csv`. |
| `GEARS` | `["P", "R", "N", "D"]`. |

## Training constants (trainers)

| Constant | Value | File |
|---|---:|---|
| `STEERING_MODEL_WIDTH` / `HEIGHT` | `200` / `66` | `vision.py` (runtime inference input). |
| `SERIES_1_STEERING_OUTPUT_SCALE_DEG` | `86.0` | `vision.py`. |
| `SERIES_2_STEERING_OUTPUT_SCALE_DEG` | `85.0` | `vision.py`. |
| Series 1/2 training input | `200x66` | `series_1_and_2/sidewalkpilot_trainer.py`. |
| Series 3/4 training input | `320x180` | Trainers under `series_3_and_4/`. |
| Steering classes | 9 bands: `0-45`, `45-60`, `60-75`, `75-85`, `85-95`, `95-105`, `105-120`, `120-135`, `135-180` | Series 3/4 trainers and evaluator. |

## Related pages

- `code-reference/runtime-modules.md`
- `code-reference/training-modules.md`
- `runtime-code/runtime-loop.md`
