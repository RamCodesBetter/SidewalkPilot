#!/usr/bin/python3
import datetime
import math
import os
import time
from dataclasses import dataclass, field

# --- SELF-DRIVING BUILD FLAGS ---
ENABLE_HALL_SENSOR = True
ENABLE_WEBCAM_VISION = True
USE_PI_CAMERA = True
PI_CAMERA_NUM = 0
PI_CAMERA_ROTATE_180 = True

AUTONOMOUS_CRUISE_PWM = 1.0
AUTONOMOUS_TURN_PWM = 1.0
AUTONOMOUS_WARN_PWM = 0.8
AUTONOMOUS_LIDAR_OVERRIDE_PWM = 0.5
CAMERA_STEER_GAIN = 0.75
CAMERA_TURN_BLEND = 0.35
MAX_AUTONOMOUS_SPEED_MPH = 3.2
MAX_TARGET_HEADING_DEG = 60.0
PASSABLE_WIDTH_MIN_M = 0.40
LIDAR_FORWARD_ANGLE_MIN_DEG = -75
LIDAR_FORWARD_ANGLE_MAX_DEG = 75
LIDAR_HEADING_WINDOW_DEG = 12
LOW_CAMERA_CONFIDENCE = 0.25
HIGH_CAMERA_CONFIDENCE = 0.60
DRIVEWAY_CUT_MIN_FORWARD_CLEARANCE_M = 1.2
DRIVEWAY_CUT_DETECTION_SECONDS = 0.35
FORWARD_OBSTACLE_STOP_DISTANCE_M = 0.5
PARTIAL_BLOCKAGE_MIN_CLEARANCE_M = 0.8
LIDAR_OVERRIDE_EMERGENCY_STOP_M = 0.35
LIDAR_OVERRIDE_SIDE_CLEARANCE_M = 0.75
LIDAR_OVERRIDE_STEER_DEG = 38.0

# --- GPIO SETUP ---
STEERING_SERVO_PIN = 12
HALL_SENSOR_GPIO_PIN = 24
LIDAR_MOTOR_ENABLE_GPIO_PIN = 18
MOTOR_RIGHT_FWD_PIN = 19
MOTOR_RIGHT_BWD_PIN = 20
MOTOR_LEFT_FWD_PIN = 25
MOTOR_LEFT_BWD_PIN = 13

# --- PCA9685 SERVO SETTINGS ---
USE_PCA9685_SERVO = True
PCA9685_I2C_ADDRESS = 0x40
PCA9685_SERVO_CHANNEL = 0
PCA9685_FREQUENCY_HZ = 50
STEERING_SERVO_MIN_PULSE_US = 1000
STEERING_SERVO_MAX_PULSE_US = 2000
STEERING_SERVO_ACTUATION_RANGE_DEG = 180
STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG = float(
    os.environ.get("RC_CAR_STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG", "48.812")
)
STEERING_SERVO_REFERENCE_RIGHT_LIMIT_DEG = float(
    os.environ.get("RC_CAR_STEERING_SERVO_REFERENCE_RIGHT_LIMIT_DEG", "131.188")
)
STEERING_SERVO_CENTER_OFFSET = float(
    os.environ.get(
        "RC_CAR_STEERING_SERVO_CENTER_OFFSET",
        str(12.0 / (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0)),
    )
)
STEERING_SERVO_CENTER_PRELOAD = 0.0
STEERING_SERVO_CENTER_PRELOAD_WINDOW = 0.0
STEERING_CENTER_SETTLE_OVERSHOOT_DEG = float(os.environ.get("RC_CAR_STEERING_CENTER_SETTLE_OVERSHOOT_DEG", "4.0"))
STEERING_CENTER_SETTLE_LEFT_OVERSHOOT_DEG = float(
    os.environ.get(
        "RC_CAR_STEERING_CENTER_SETTLE_LEFT_OVERSHOOT_DEG",
        os.environ.get("RC_CAR_STEERING_CENTER_SETTLE_OVERSHOOT_DEG", "4.0"),
    )
)
STEERING_CENTER_SETTLE_HIGH_OVERSHOOT_DEG = float(
    os.environ.get(
        "RC_CAR_STEERING_CENTER_SETTLE_HIGH_OVERSHOOT_DEG",
        os.environ.get("RC_CAR_STEERING_CENTER_SETTLE_OVERSHOOT_DEG", "4.0"),
    )
)
STEERING_CENTER_SETTLE_DURATION_SEC = float(os.environ.get("RC_CAR_STEERING_CENTER_SETTLE_DURATION_SEC", "1.0"))
STEERING_CENTER_SETTLE_LOW_RELEASE_TARGET_DEG = float(
    os.environ.get(
        "RC_CAR_STEERING_CENTER_SETTLE_LOW_RELEASE_TARGET_DEG",
        os.environ.get(
            "RC_CAR_STEERING_CENTER_SETTLE_LX_DEG",
            # Ram's rule: settle target = center + trim delta (L = 90 + D), so the
            # left-release overshoot auto-follows the trim. At +13deg trim this
            # is 103 (the well-tuned L103:0.25 +13D). Env vars still override.
            str((STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0) * (1.0 + STEERING_SERVO_CENTER_OFFSET)),
        ),
    )
)
STEERING_CENTER_SETTLE_LOW_RELEASE_DURATION_SEC = float(
    os.environ.get(
        "RC_CAR_STEERING_CENTER_SETTLE_LOW_RELEASE_DURATION_SEC",
        os.environ.get(
            "RC_CAR_STEERING_CENTER_SETTLE_LS_SEC",
            "0.25",
        ),
    )
)
STEERING_CENTER_SETTLE_RELEASE_MIN_DEG = float(os.environ.get("RC_CAR_STEERING_CENTER_SETTLE_RELEASE_MIN_DEG", "12.0"))
# Servo angles within this many degrees of center snap to exactly center.
# Keep small so fine offsets (e.g. 88/89/91/92) are still commandable; the
# input deadzone already handles stick jitter near center.
STEERING_CENTER_SNAP_DEG = float(os.environ.get("RC_CAR_STEERING_CENTER_SNAP_DEG", "0.5"))

# --- Steering settle pushback curve (measured 2026-06-24 via pushback_curve_sim) ---
# On a left release, the settle kicks the servo to poly(released_servo): released
# value clamped to [0, center], output clamped to [center, range]. Quartic fit of
# Ram's calibration (least average offset, ~0.28 deg). Coeffs ascending power:
# c0 + c1*x + c2*x^2 + c3*x^3 + c4*x^4.
STEERING_SETTLE_PUSHBACK_COEFFS = (
    135.03247,
    -0.97102,
    0.0247475,
    -0.000351665,
    0.00000149645,
)
# Skip the settle if the curve asks for less than this much kick past center.
STEERING_CENTER_SETTLE_MIN_KICK_DEG = float(os.environ.get("RC_CAR_STEERING_CENTER_SETTLE_MIN_KICK_DEG", "1.0"))

# --- Live-tunable steering overrides (written by the on-device tuning page) ---
# steering_tune.json IS the persisted defaults: if present it overrides the four
# values above, so an on-device SAVE survives restarts. Delete the file to
# revert to the code defaults above.
import json as _json
STEERING_TUNE_PATH = os.path.join(os.path.dirname(__file__), "steering_tune.json")
try:
    with open(STEERING_TUNE_PATH) as _tune_f:
        _tune = _json.load(_tune_f)
    if isinstance(_tune, dict):
        if "trim_delta_deg" in _tune:
            STEERING_SERVO_CENTER_OFFSET = float(_tune["trim_delta_deg"]) / (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0)
        if "settle_target_deg" in _tune:
            STEERING_CENTER_SETTLE_LOW_RELEASE_TARGET_DEG = float(_tune["settle_target_deg"])
        if "settle_duration_sec" in _tune:
            STEERING_CENTER_SETTLE_LOW_RELEASE_DURATION_SEC = float(_tune["settle_duration_sec"])
        if "settle_trigger_deg" in _tune:
            STEERING_CENTER_SETTLE_RELEASE_MIN_DEG = float(_tune["settle_trigger_deg"])
except FileNotFoundError:
    pass
except Exception as _tune_exc:
    print(f"steering_tune.json ignored ({_tune_exc})")

# Reduce the stronger side below 1.0 if the car pulls while steering is centered.
LEFT_MOTOR_PWM_SCALE = 1.0
RIGHT_MOTOR_PWM_SCALE = 1.0

# --- HUB75 DASHBOARD TELEMETRY ---
ENABLE_HUB75_DASHBOARD_TELEMETRY = True
# Use only the Pi 5 <-> Zero 2 W USB Ethernet gadget for dashboard telemetry.
HUB75_DASHBOARD_TRANSPORT = os.environ.get("RC_CAR_DASHBOARD_TRANSPORT", "udp").strip().lower()
HUB75_DASHBOARD_HOST = os.environ.get("RC_CAR_DASHBOARD_HOST", "192.168.10.2").strip() or "192.168.10.2"
HUB75_DASHBOARD_UDP_PORT = int(os.environ.get("RC_CAR_DASHBOARD_UDP_PORT", "8765"))
HUB75_DASHBOARD_SERIAL_PORT = os.environ.get("RC_CAR_DASHBOARD_SERIAL_PORT", "/dev/ttyACM0")
HUB75_DASHBOARD_BAUD_RATE = 115200
HUB75_DASHBOARD_SEND_INTERVAL_SEC = 0.1
HUB75_DASHBOARD_IDLE_EXIT_SEC = 2.0
HUB75_DASHBOARD_SHUTDOWN_ON_EXIT = os.environ.get("RC_CAR_DASHBOARD_SHUTDOWN_ON_EXIT", "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
DASHBOARD_BRIGHTNESS_PERCENT_DEFAULT = 80
DASHBOARD_BRIGHTNESS_STEP_PERCENT = 10

# --- TURN SIGNAL / DASHBOARD DISPLAY ---
TURN_SIGNAL_BLINK_INTERVAL_SEC = 0.45
HAZARD_BUTTON = 10

# --- MOTOR SETTINGS ---
ACCEL_RATE = 0.5
BRAKE_RATE = 8.0
COASTING_RATE = 0.6
AEB_BRAKE_RATE = 10.0
AEB_ACTIVATION_DELAY_SEC = 1.0

# --- SPEED SETTINGS ---
WHEEL_DIAMETER_CM = 7.0
PULSES_PER_REVOLUTION = 455.0
SPEED_SMOOTHING_ALPHA = 0.2
WHEEL_CIRCUMFERENCE_CM = math.pi * WHEEL_DIAMETER_CM
CM_PER_SEC_TO_MPH = 0.0223694

# --- PID SETTINGS ---
KP = 0.50
KI = 0.08
KD = 0.005

# --- LOGGING ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
LOG_DIR = os.environ.get("RC_CAR_LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
PHOTO_DIR = os.environ.get("RC_CAR_PHOTO_DIR", os.path.join(PROJECT_ROOT, "media/photos"))
os.makedirs(PHOTO_DIR, exist_ok=True)
CSV_FILENAME = os.path.join(LOG_DIR, f"log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
LOG_INTERVAL_SEC = 1.0

CSV_HEADERS = [
    "Current Time",
    "Time Since Program Started (s)",
    "Autonomous Mode (On/Off)",
    "Cruise Control (Active/Inactive)",
    "Shift Up PRND (Event)",
    "Shift Down PRND (Event)",
    "Quit (Event)",
    "Increase CC (Event)",
    "Decrease CC (Event)",
    "Steer (Value)",
    "Brake (On/Off)",
    "Gas (Value)",
    "Maximum Speed Recall (MPH)",
    "Average Speed (MPH)",
    "Current Speed (MPH)",
    "Motor PWM Value",
    "Gear Mode",
    "Cruise Control Target Speed (MPH)",
    "LiDAR Front Distance (m)",
    "LiDAR Left Distance (m)",
    "LiDAR Right Distance (m)",
    "LiDAR Back Distance (m)",
    "LiDAR Determined Direction",
    "Target Heading (deg)",
    "Stop Reason",
    "CPU Usage (%)",
    "Memory Usage (%)",
    "Number of LiDAR Points in Scan",
    "Time Since Last Hall Sensor Pulse (s)",
    "CPU Temp (C)",
    "AEB Enabled (On/Off)",
    "AEB Triggered (On/Off)",
    "PID Output (Cruise Control)",
    "LiDAR Best Heading (deg)",
    "LiDAR Heading Confidence",
    "LiDAR Forward Clearance (m)",
    "Camera Steering Bias",
    "Camera Confidence",
    "Camera Left Edge Found",
    "Camera Right Edge Found",
    "Camera Corridor Width (px)",
    "Driveway Cut Suspected",
    "Steering Servo Deg",
    "Settle Active (0/1)",
    "Settle Source Deg",
    "Settle Target Deg",
    "Dashboard JSON Payload",
]

GEARS = ["P", "R", "N", "D"]
STEERING_AXIS = 0
STEERING_DEADZONE = 0.1
DASHBOARD_PAGE_AXIS = 3
DASHBOARD_PAGE_HORIZONTAL_AXIS = 2
THROTTLE_AXIS = 4
BRAKE_AXIS = 5
SHARED_TRIGGER_AXIS = False
DEBUG_CONTROLLER_INPUTS = False
DASHBOARD_PAGE_COUNT = 14
DASHBOARD_PAGE_AXIS_THRESHOLD = 0.65
DASHBOARD_PAGE_HOLD_SEC = 0.05
DASHBOARD_SCROLL_REPEAT_START_SEC = 0.6
DASHBOARD_SCROLL_REPEAT_INTERVAL_SEC = 0.22
DPAD_SCROLL_REPEAT_START_SEC = 0.6
DPAD_SCROLL_REPEAT_INTERVAL_SEC = 0.22
NAV_LETTER_REPEAT_START_SEC = 0.35
NAV_LETTER_REPEAT_INTERVAL_SEC = 0.08

CRUISE_TOGGLE_BUTTONS = (4,)
SHIFT_DOWN_BUTTON = 6
SHIFT_UP_BUTTON = 7
AUTONOMY_TOGGLE_BUTTON = 0
AEB_TOGGLE_BUTTON = 14
PHOTO_BUTTON = 1
AUTO_PHOTO_BUTTON = 11
AUTO_PHOTO_MIN_INTERVAL_SEC = 2
AUTO_PHOTO_MAX_INTERVAL_SEC = 4
NAV_SELECT_BUTTON = 3
QUIT_BUTTON = 15


def create_state():
    return {
        "steer": 0.0,
        "steering_servo_deg": STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0,
        "steering_trim_delta_deg": STEERING_SERVO_CENTER_OFFSET * (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0),
        # Live-tunable settle params (on-device tuning page). Init from config
        # (which is steering_tune.json-overridden) so behavior is unchanged
        # until you tune on the display.
        "settle_target_deg": float(STEERING_CENTER_SETTLE_LOW_RELEASE_TARGET_DEG),
        "settle_duration_sec": float(STEERING_CENTER_SETTLE_LOW_RELEASE_DURATION_SEC),
        "settle_trigger_deg": float(STEERING_CENTER_SETTLE_RELEASE_MIN_DEG),
        "tune_selected_row": 0,
        "tune_saved_flash_until": 0.0,
        "steering_trim_total_deg": (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0)
        + (STEERING_SERVO_CENTER_OFFSET * (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0)),
        "steering_center_offset": STEERING_SERVO_CENTER_OFFSET,
        "steering_center_settle_until": 0.0,
        "steering_center_settle_deg": STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0,
        "steering_effective_servo_deg": STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0,
        "steering_last_noncenter_servo_deg": STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0,
        "steering_settle_source_deg": STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0,
        "throttle": 0.0,
        "brake": False,
        "brake_force": 0.0,
        "manual_brake_force": 0.0,
        "cc_active": False,
        "cc_target_speed": 0.0,
        "current_motor_pwm": 0.0,
        "gear_mode": "P",
        "direction_arrow": " ",
        "target_heading_deg": 0.0,
        "stop_reason": "",
        "event_shift_up": False,
        "event_shift_down": False,
        "event_quit_pressed": False,
        "event_cc_increase": False,
        "event_cc_decrease": False,
        "lidar_front_dist": 12.0,
        "lidar_left_dist": 12.0,
        "lidar_right_dist": 12.0,
        "lidar_back_dist": 12.0,
        "lidar_stop_threshold_m": FORWARD_OBSTACLE_STOP_DISTANCE_M,
        "lidar_warn_threshold_m": 1.2,
        "lidar_best_heading_deg": 0.0,
        "lidar_heading_confidence": 0.0,
        "lidar_forward_clearance_m": 12.0,
        "lidar_override_active": False,
        "lidar_override_side": "",
        "num_lidar_points": 0,
        "autonomous_mode": False,
        "camera_steering_bias": 0.0,
        "camera_confidence": 0.0,
        "camera_left_edge_found": False,
        "camera_right_edge_found": False,
        "camera_corridor_width_px": 0.0,
        "driveway_cut_suspected": False,
        "turn_signal_mode": "off",
        "turn_signal_left_visible": False,
        "turn_signal_right_visible": False,
        "dashboard_brightness_percent": DASHBOARD_BRIGHTNESS_PERCENT_DEFAULT,
        "dashboard_page": 1,
        "dashboard_page_vertical": 1,
        "dashboard_page_horizontal": 1,
        "dashboard_page_axis_value": 0.0,
        "dashboard_page_horizontal_axis_value": 0.0,
        "dpad_y_value": 0,
        "dashboard_throttle_percent": 0,
        "dashboard_brake_percent": 0,
        "dashboard_payload_json": "",
        "auto_photo_enabled": False,
    }


@dataclass
class Metrics:
    pulse_count: int = 0
    last_pulse_time: float = time.time()
    previous_pulse_count: int = 0
    previous_speed_calculation_time: float = time.time()
    current_raw_mph: float = 0.0
    smoothed_speed_mph: float = 0.0
    max_speed_recall: float = 0.0
    total_distance_cm: float = 0.0
    start_time: float = time.time()
    pid_integral_error: float = 0.0
    pid_previous_error: float = 0.0
    pid_output: float = 0.0
    stop_warning_start_time: float = 0.0
    aeb_enabled: bool = True
    aeb_triggered: bool = False
    last_confident_heading_deg: float = 0.0
    driveway_cut_candidate_since: float = 0.0
    cruise_ignore_throttle_until_release: bool = False
    turn_signal_last_toggle_time: float = time.time()
    turn_signal_blink_on: bool = False
    dashboard_page_axis_direction: int = 0
    dashboard_page_axis_hold_since: float = 0.0
    dashboard_page_axis_latched: bool = False
    dashboard_page_axis_last_repeat_time: float = 0.0
    dashboard_page_horizontal_axis_direction: int = 0
    dashboard_page_horizontal_axis_hold_since: float = 0.0
    dashboard_page_horizontal_axis_latched: bool = False
    dashboard_page_horizontal_axis_last_repeat_time: float = 0.0
    dpad_y_direction: int = 0
    dpad_y_hold_since: float = 0.0
    dpad_y_last_repeat_time: float = 0.0
    dashboard_page_transition: str = ""
    dashboard_cpu_temp_c: float = 0.0
    dashboard_cpu_temp_last_sample_time: float = 0.0
    dashboard_photos_run: int = 0
    dashboard_photos_all: int = 0
    dashboard_photo_run_stats: dict = field(
        default_factory=lambda: {"left": 0, "center": 0, "right": 0, "throttle_below_50": 0}
    )
    dashboard_photo_stats_last_sample_time: float = 0.0
    auto_photo_next_time: float = 0.0
    servo_error_count: int = 0
    servo_error_last_log_time: float = 0.0
    servo_fault_until: float = 0.0
