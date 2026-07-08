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
# Autonomous stints shorter than this don't count toward AUT (avg uptime) or IPKM
# (interventions/km) -- a quick tap in/out isn't a real stint. They STILL count toward
# ADT (distance) and ICSE (last cause code).
AUTONOMY_MIN_SEGMENT_S = 6.0
AUTONOMOUS_WARN_PWM = 0.8
AUTONOMOUS_LIDAR_OVERRIDE_PWM = 0.5
CAMERA_STEER_GAIN = 0.75
CAMERA_TURN_BLEND = 0.35
# Temporal smoothing (EMA) for the model steering command. Damps the frame-to-frame
# "blockiness" of the v3.1 hybrid head, whose argmax can flip between steering buckets
# on ambiguous frames: steer = ALPHA*new + (1-ALPHA)*prev.
#   1.0  = off (raw, jittery)   ~0.5 = balanced   lower = smoother but laggier
# Tune in the field: raise it if the car corners late, lower it if still twitchy.
# 0.45 chosen from the 2026-07-03 field log (~8 deg/frame raw jitter) re-tuned at the
# real 30 fps loop rate: ~40% jitter cut, ~0.13 s turn lag -- a middle between max-smooth
# (0.30) and snappy (0.60).
STEERING_SMOOTH_ALPHA = 0.45
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
LIDAR_OVERRIDE_EMERGENCY_STOP_M = 1.05   # hard-stop backstop (raised for earlier reaction)
LIDAR_OVERRIDE_SIDE_CLEARANCE_M = 0.75
LIDAR_OVERRIDE_STEER_DEG = 38.0

# --- LiDAR AVOIDANCE (validated in test_files/lidar_avoidance_sim.py) ---
# Forward cone (+/-) that can BLOCK the path; wider = brakes for more off-center stuff.
LIDAR_FORWARD_CONE_DEG = 30.0        # forward cone that BLOCKS the path (matches the V7H1 cone rays)
LIDAR_NEAR_ANGLE_DEG = 75.0          # full sensed fan; the 30..75 wedges = swerve-clearance only
LIDAR_MIN_CONFIDENCE = 150           # ignore low-confidence points
LIDAR_WARN_M = 1.40                  # forward point closer than this triggers classify/react
LIDAR_GOV_FULL_M = 1.65              # governor full throttle at/above this clearance
LIDAR_GOV_STOP_M = 1.25              # governor throttle 0 at/below this (above the 1.05 emergency)
LIDAR_MIN_MOVE_PWM = 0.55            # car can't move below this -> governor floors "moving" here
LIDAR_AVOID_SIDE_CLEAR_M = 0.40      # a side needs this much room to swerve into
LIDAR_CLUSTER_GAP_DEG = 8.0          # angular gap that splits one object into two (separates legs)
LIDAR_NARROW_MAX_DEG = 15.0          # per-cluster angular cap for a "leg" (person detection)
LIDAR_WALL_MIN_WIDTH_M = 0.65        # PHYSICAL width to count as a wall (mailbox ~0.5m stays swervable)
LIDAR_LEG_GAP_MAX_DEG = 45.0         # two clusters within this apart = a person's two legs
LIDAR_LEG_RANGE_TOL_M = 0.40         # ...and at matching range = same person
LIDAR_SWERVE_MIN_DEG = 20.0          # gentle swerve when the mailbox is far (~WARN)
LIDAR_SWERVE_MAX_DEG = 80.0          # hard swerve when it's close (~GOV_STOP); logical 90 -/+ this
LIDAR_SWERVE_THROTTLE_DROP = 0.30    # sharper swerves shed this much throttle (gentle=full, hardest=CRUISE-drop)

# --- GPIO SETUP ---
STEERING_SERVO_PIN = 12
HALL_SENSOR_GPIO_PIN = 24
# LiDAR is on USB 3.0 now (CP2102, /dev/ttyUSB0) — no GPIO motor-enable pin needed.
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
# Servo angles within this many degrees of center snap to exactly center.
# Keep small so fine offsets (e.g. 88/89/91/92) are still commandable; the
# input deadzone already handles stick jitter near center.
STEERING_CENTER_SNAP_DEG = float(os.environ.get("RC_CAR_STEERING_CENTER_SNAP_DEG", "0.5"))

# --- IMU yaw-rate closed-loop steering (MG24 on /dev/ttyAMA3) ---
# Pure PID (no feed-forward). Default "straight" = hold yaw=0 when commanding ~center
# (turns pass through open-loop). "full" = also track turns. "off" = no IMU.
# Tune the gains right here (edit the numbers): the INTEGRAL discovers the steering
# offset needed to go straight, so push Ki up if it drifts and never centers, push
# Kp up for snappier correction, add a little Kd if it oscillates.
STEERING_YAW_PID_MODE = "straight"
STEERING_YAW_PID_PORT = "/dev/ttyAMA3"
STEERING_YAW_PID_BAUD = 115200
STEERING_YAW_PID_AXIS = 2  # 0=X 1=Y 2=Z (yaw)
# IMU yaw sign so the controller's convention holds: + = LEFT. Measured on the car
# (2026-06-30): driving straight while drifting LEFT read NEGATIVE yaw, i.e. the raw
# gyro is inverted vs the controller's assumption -> flip it. If a future test shows
# the correction still pushes INTO the drift, set this back to +1.0.
STEERING_YAW_PID_YAW_SIGN = -1.0
# Ram-set gains (2026-07-07): stronger P + a small I to hold the line. NOTE: the left
# drift at speed is partly a MOTOR imbalance (thrust differential that scales with
# throttle) the steering servo can't fully cancel -- the real fix is balancing
# LEFT/RIGHT_MOTOR_PWM_SCALE. The small kI is being trialled anyway; the anti-windup
# clamp (STEERING_YAW_PID_MAX_CORRECTION_DEG) bounds its wind-up. Watch for a lurch on
# decel; if it winds up and jerks, drop kI back toward 0.
STEERING_YAW_PID_KP = 0.75
STEERING_YAW_PID_KI = 0.1
STEERING_YAW_PID_KD = 0.05
# Curvature quartic from calibration: curvature(x) [deg/m] vs servo angle x, ascending
# powers c0..c4. Its root (curvature=0) is the open-loop STRAIGHT angle (~109) = the
# feed-forward F; full mode also reads the target curvature off it. From imu_calib.csv.
STEERING_YAW_PID_CURVATURE_COEFFS = (69.59605, -0.242301, -0.0077307, 4.86308e-5, -1.02946e-7)
# Direction-dependent straight-angle feed-forwards. LFF = straight servo angle when
# the last steer was LEFT; RFF = when last steer was RIGHT (picked by _last_side).
# SOFTENED (hand-set) to a gentle +9deg / +8deg off logical center (90): the PID does
# more of the work and the open-loop hand no longer slams the servo ~+20-30deg right.
# Deltas are +9 (left-approach) / +8 (right-approach). ff_calibrate.py measured a much
# harder push (119.5/107.8) at speed; re-run it if you want the measured values back.
STEERING_YAW_PID_LFF_DEG = 99.0   # center 90 + 9
STEERING_YAW_PID_RFF_DEG = 98.0   # center 90 + 8
# A side only counts as "the last steer" once the stick DWELLS there this long.
# Kills flick / spring-back overshoot: on a quick release the stick briefly crosses
# center to the opposite side; without this dwell that transient flips the hysteresis
# F to the wrong value (109<->119 backwards). Real turns dwell well past this.
STEERING_YAW_PID_SIDE_DWELL_SEC = 0.12
# (A) Speed-normalize the correction: the servo->yaw plant gain grows with speed, so a
# fixed kP is too hot fast / sluggish slow. The loop scales the correction by
# REF_SPEED/speed (clamped) so ONE gain holds across speeds. REF = the speed you tune at.
STEERING_YAW_PID_REF_SPEED_MPS = 1.0
# (B) Hard cap on the PID correction (deg off the feed-forward center). Bounds rail-slam
# and, with integral clamping, kills windup so behaviour is repeatable run to run.
STEERING_YAW_PID_MAX_CORRECTION_DEG = 30.0
STEERING_YAW_PID_STRAIGHT_BAND_DEG = 5.0    # |cmd-90| within this -> hold yaw=0; beyond -> passthrough
                                            # (keep small: a wide band makes the loop fight your TURNS,
                                            #  e.g. at servo 70 it tried to cancel the yaw you commanded -> wag)
STEERING_YAW_PID_MIN_SPEED_MPS = 0.05       # below this the loop disengages. 0.05 = the clean handoff
                                            # with the gyro bias auto-zero (which runs below 0.05 m/s);
                                            # going lower would let the loop engage while bias is still
                                            # being learned -> corrupts the zero. Top speed ~1.48 m/s.

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
LOG_DIR = os.environ.get("RC_CAR_LOG_DIR", os.path.expanduser("~/logs"))
os.makedirs(LOG_DIR, exist_ok=True)
PHOTO_DIR = os.environ.get("RC_CAR_PHOTO_DIR", os.path.join(PROJECT_ROOT, "media/photos"))
os.makedirs(PHOTO_DIR, exist_ok=True)
CSV_FILENAME = os.path.join(LOG_DIR, f"log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
LOG_INTERVAL_SEC = 0.1          # log a CSV row every 100 ms

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
    "Intervention (Event)",
    "Intervention Cause",
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
DASHBOARD_PAGE_COUNT = 17
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
# High-rate run capture: when auto-photo is ON it now captures continuously at this
# fps (instead of the old 2-4s random) for dense training-data runs. Each frame is
# labeled with the live logical steering + throttle (appended to a per-run CSV; the
# JSON is built when the run ends).
PHOTO_RUN_CAPTURE_FPS = 10.0

# Jetson ("Jon") remote inference. When JETSON_STEERING_HOST is non-empty the Pi
# does NOT run a steering model: in autonomous mode it sends the camera frame +
# the active model choice to Jon and steers with the (steering, throttle) it gets
# back. Empty host = current behavior (Pi runs its own Series-1/2 model locally).
# If Jon is unreachable the car holds (safe stop), it does not free-run.
# Jon = Jetson Orin Nano, over the wired Pi<->Jetson Ethernet link. Pi eth0 is
# 10.42.0.1 (NetworkManager "shared" mode, connection 'jetson-eth-share'); Jon's
# eth is pinned STATIC to 10.42.0.2 (below the DHCP pool, so it survives reboots).
# Jon keeps internet via gateway 10.42.0.1. Separate from the 192.168.10.x
# Pi5<->Zero2W dashboard USB link.
JETSON_STEERING_HOST = "10.42.0.2"
JETSON_STEERING_PORT = 8770

# Interruption clip recorder (dad+son suggestion #1). While autonomous, keep a rolling
# buffer of the exact JPEGs sent to Jon; the instant the driver takes over
# (autonomous -> manual) a background thread saves the last INTERRUPTION_CLIP_SECONDS
# to INTERRUPTION_CLIP_DIR as clip_<stamp>.mp4 -- the moments right before the takeover.
# At quit every clip is rsync'd to Jon:/nvme/interruption_clips/ for clip_bucket_analyzer.py.
# Records ONLY while autonomous, strictly the seconds BEFORE the takeover (no post-roll).
INTERRUPTION_CLIP_ENABLED = True
INTERRUPTION_CLIP_SECONDS = 2.0
INTERRUPTION_CLIP_DIR = "~/interruption_clips"

NAV_SELECT_BUTTON = 3
QUIT_BUTTON = 15


def create_state():
    return {
        "steer": 0.0,
        "steering_servo_deg": STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0,
        "steering_trim_delta_deg": STEERING_SERVO_CENTER_OFFSET * (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0),
        "tune_selected_row": 0,
        "tune_saved_flash_until": 0.0,
        "steering_trim_total_deg": (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0)
        + (STEERING_SERVO_CENTER_OFFSET * (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0)),
        "steering_center_offset": STEERING_SERVO_CENTER_OFFSET,
        # Live-tunable yaw PID gains (dashboard TUNE page). Start at config values (0).
        "yaw_kp": float(STEERING_YAW_PID_KP),
        "yaw_ki": float(STEERING_YAW_PID_KI),
        "yaw_kd": float(STEERING_YAW_PID_KD),
        "yaw_pid_reset": False,
        "steering_effective_servo_deg": STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0,
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
        "event_intervention": False,
        "intervention_cause": "",
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
    # --- autonomy metrics (V2H2 dashboard page) ---
    # Segments shorter than AUTONOMY_MIN_SEGMENT_S are ignored for AUT + IPKM (a quick
    # tap-in/tap-out isn't a real autonomous stint) but STILL count for ADT + ICSE.
    auto_distance_cm: float = 0.0      # ADT: distance driven while autonomous (ALL segments)
    auto_time_s: float = 0.0           # AUT numerator: summed uptime of COUNTED (>=6s) segments
    auto_intervention_count: int = 0   # IPKM: disengagements from COUNTED (>=6s) segments only
    auto_segments: int = 0             # AUT denominator: number of COUNTED (>=6s) segments
    auto_segment_s: float = 0.0        # duration of the CURRENT autonomous segment (in progress)
    auto_prev_engaged: bool = False    # edge-detect autonomous_mode
    auto_last_cause_code: str = ""     # ICSE: last disengagement cause code (ALL segments)
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
    dpad_x_direction: int = 0
    dpad_x_hold_since: float = 0.0
    dpad_x_last_repeat_time: float = 0.0
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
