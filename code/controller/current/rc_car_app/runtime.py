#!/usr/bin/python3
import datetime
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import pygame

from .config import (
    ACCEL_RATE,
    AEB_BRAKE_RATE,
    AUTONOMOUS_CRUISE_PWM,
    AUTONOMY_MIN_SEGMENT_S,
    AUTO_PHOTO_BUTTON,
    PHOTO_RUN_CAPTURE_FPS,
    JETSON_STEERING_HOST,
    JETSON_STEERING_PORT,
    JETSON_RESULT_MAX_AGE_SEC,
    JETSON_RESULT_MAX_FRAME_LAG,
    CONTROL_LOOP_HZ,
    CONTROL_LOOP_STALL_WARN_SEC,
    INTERRUPTION_CLIP_ENABLED,
    INTERRUPTION_CLIP_SECONDS,
    INTERRUPTION_CLIP_DIR,
    STEERING_SMOOTH_ALPHA,
    BRAKE_RATE,
    CM_PER_SEC_TO_MPH,
    COASTING_RATE,
    CSV_FILENAME,
    CSV_HEADERS,
    DEBUG_CONTROLLER_INPUTS,
    DASHBOARD_PAGE_AXIS,
    DASHBOARD_PAGE_AXIS_THRESHOLD,
    DASHBOARD_PAGE_COUNT,
    DASHBOARD_PAGE_HORIZONTAL_AXIS,
    DASHBOARD_PAGE_HOLD_SEC,
    DASHBOARD_SCROLL_REPEAT_INTERVAL_SEC,
    DASHBOARD_SCROLL_REPEAT_START_SEC,
    DPAD_SCROLL_REPEAT_INTERVAL_SEC,
    DPAD_SCROLL_REPEAT_START_SEC,
    DASHBOARD_BRIGHTNESS_STEP_PERCENT,
    HAZARD_BUTTON,
    FORWARD_OBSTACLE_STOP_DISTANCE_M,
    GEARS,
    KD,
    KI,
    KP,
    LEFT_MOTOR_PWM_SCALE,
    LOW_CAMERA_CONFIDENCE,
    LOG_INTERVAL_SEC,
    MAX_TARGET_HEADING_DEG,
    PHOTO_BUTTON,
    PHOTO_DIR,
    PULSES_PER_REVOLUTION,
    SPEED_SMOOTHING_ALPHA,
    STEERING_AXIS,
    STEERING_CENTER_SNAP_DEG,
    STEERING_SERVO_ACTUATION_RANGE_DEG,
    STEERING_SERVO_CENTER_OFFSET,
    STEERING_YAW_PID_MODE,
    STEERING_YAW_PID_PORT,
    STEERING_YAW_PID_BAUD,
    STEERING_YAW_PID_AXIS,
    STEERING_YAW_PID_YAW_SIGN,
    STEERING_YAW_PID_KP,
    STEERING_YAW_PID_KI,
    STEERING_YAW_PID_KD,
    STEERING_YAW_PID_CURVATURE_COEFFS,
    STEERING_YAW_PID_LFF_DEG,
    STEERING_YAW_PID_RFF_DEG,
    STEERING_YAW_PID_SIDE_DWELL_SEC,
    STEERING_YAW_PID_REF_SPEED_MPS,
    STEERING_YAW_PID_MAX_CORRECTION_DEG,
    STEERING_YAW_PID_STRAIGHT_BAND_DEG,
    STEERING_YAW_PID_MIN_SPEED_MPS,
    THROTTLE_AXIS,
    TURN_SIGNAL_BLINK_INTERVAL_SEC,
    ENABLE_HUB75_DASHBOARD_TELEMETRY,
    HUB75_DASHBOARD_BAUD_RATE,
    HUB75_DASHBOARD_HOST,
    DASHBOARD_BRIGHTNESS_PERCENT_DEFAULT,
    HUB75_DASHBOARD_SEND_INTERVAL_SEC,
    HUB75_DASHBOARD_SERIAL_PORT,
    HUB75_DASHBOARD_TRANSPORT,
    HUB75_DASHBOARD_UDP_PORT,
    WHEEL_CIRCUMFERENCE_CM,
    create_state,
    Metrics,
    BRAKE_AXIS,
    CRUISE_TOGGLE_BUTTONS,
    SHIFT_DOWN_BUTTON,
    SHIFT_UP_BUTTON,
    AUTONOMY_TOGGLE_BUTTON,
    AEB_TOGGLE_BUTTON,
    NAV_SELECT_BUTTON,
    NAV_LETTER_REPEAT_INTERVAL_SEC,
    NAV_LETTER_REPEAT_START_SEC,
    QUIT_BUTTON,
    RIGHT_MOTOR_PWM_SCALE,
    SHARED_TRIGGER_AXIS,
    STEERING_DEADZONE,
    HUB75_DASHBOARD_IDLE_EXIT_SEC,
    HUB75_DASHBOARD_SHUTDOWN_ON_EXIT,
    absolute_throttle_to_reference,
    reference_throttle_to_absolute,
)
from .hardware import Hardware
from .lidar import (
    BAUD_RATE,
    MAX_LIDAR_RANGE_M,
    OBSTACLE_STOP_THRESHOLD_M,
    OBSTACLE_WARN_THRESHOLD_M,
    SERIAL_PORT,
    LidarParser,
    determine_turn_direction,
)
from .logging_utils import init_csv_logger, log_data_to_csv
from .hub75_dashboard import Hub75DashboardSender
from .navigation import GpsReader, NavigationManager
from .yaw_pid import ImuReader, YawController
from .jetson_client import AsyncJetsonSteeringClient
from .influx_logger import InfluxLogger
from .interruption_recorder import InterruptionClipRecorder
from . import lidar_avoidance
from .vision import DEFAULT_STEERING_MODEL_CHOICE, STEERING_MODEL_CHOICES, WebcamVisionProcessor

shutdown_flag = threading.Event()
current_photo_run_dir: Path | None = None
photo_status: str = "GOOD"
MANUAL_THROTTLE_DEADZONE = 0.05
NAVIGATION_UPDATE_INTERVAL_SEC = 0.10
DASHBOARD_CAMERA_UPDATE_INTERVAL_SEC = 0.10
DASHBOARD_LIDAR_UPDATE_INTERVAL_SEC = 0.10


class AsyncDashboardSender:
    def __init__(self, sender: Hub75DashboardSender):
        self.sender = sender
        self.lock = threading.Lock()
        self.sender_lock = threading.Lock()
        self.latest_args = None
        self.latest_kwargs = None
        self.last_payload_json = ""
        self.last_send_ok = False
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def send(self, *args, **kwargs):
        with self.lock:
            self.latest_args = args
            self.latest_kwargs = dict(kwargs)
            return self.last_send_ok

    def queue_notification(self, cells: list[str], duration_sec: float = 2.0):
        with self.sender_lock:
            self.sender.queue_notification(cells, duration_sec=duration_sec)

    def get_last_payload_json(self) -> str:
        with self.lock:
            return self.last_payload_json

    def send_shutdown(self):
        with self.sender_lock:
            self.sender.send_shutdown()
        self.running = False
        self.thread.join(timeout=1.0)
        with self.sender_lock:
            self.sender.send_shutdown()

    def close(self):
        self.running = False
        self.thread.join(timeout=1.0)
        with self.sender_lock:
            self.sender.close()

    def _run(self):
        while self.running:
            with self.lock:
                args = self.latest_args
                kwargs = dict(self.latest_kwargs or {})
            if args is None:
                sent = False
            else:
                try:
                    with self.sender_lock:
                        sent = self.sender.send(*args, **kwargs)
                        payload_json = self.sender.last_payload_json
                except Exception as exc:
                    print(f"Dashboard sender worker error ignored: {exc}", flush=True)
                    sent = False
                    payload_json = ""
            with self.lock:
                if args is not None:
                    self.last_send_ok = bool(sent)
                    if sent:
                        self.last_payload_json = payload_json
            time.sleep(max(0.01, HUB75_DASHBOARD_SEND_INTERVAL_SEC * 0.25))


def print_controls():
    print("Controls:")
    print(
        f"  Left stick X (axis {STEERING_AXIS}): steering, "
        f"scaled deadzone {STEERING_DEADZONE:.2f}"
    )
    print(f"  Right trigger (axis {THROTTLE_AXIS}): throttle")
    print(f"  Left trigger (axis {BRAKE_AXIS}): brake")
    if SHARED_TRIGGER_AXIS:
        print("  Trigger mode: shared axis")
    print(f"  Button {AUTONOMY_TOGGLE_BUTTON} (A): toggle autonomous driving")
    print(f"  Button {PHOTO_BUTTON} (B): take photo")
    print(
        f"  Button {AUTO_PHOTO_BUTTON} (Menu): toggle run capture "
        f"(continuous {PHOTO_RUN_CAPTURE_FPS:.0f} fps; builds <run>.json on stop)"
    )
    print(f"  Button {NAV_SELECT_BUTTON} (X): navigation page/start/stop")
    print(f"  Buttons {CRUISE_TOGGLE_BUTTONS} (Y): cruise control toggle")
    print(f"  Button {SHIFT_DOWN_BUTTON} (LB): shift down PRND")
    print(f"  Button {SHIFT_UP_BUTTON} (RB): shift up PRND")
    print(f"  Button {HAZARD_BUTTON} (View): hazard lights")
    print(f"  Button {AEB_TOGGLE_BUTTON} (RSB): toggle AEB")
    print(f"  Button {QUIT_BUTTON} (Share): quit")
    print("  D-pad left/right: left/right indicator; move nav cursor on NAVIGATE page; trim on v6h2")
    print("  D-pad up/down: edit nav entry, cycle model, adjust cruise/brightness")
    print(
        f"  D-pad hold: repeat starts after {DPAD_SCROLL_REPEAT_START_SEC:.1f}s; "
        f"nav letters repeat after {NAV_LETTER_REPEAT_START_SEC:.2f}s"
    )
    print(
        f"  Right stick Y (axis {DASHBOARD_PAGE_AXIS}): threshold {DASHBOARD_PAGE_AXIS_THRESHOLD:.2f}, "
        f"move up/down pages after {DASHBOARD_PAGE_HOLD_SEC:.1f}s, repeat after {DASHBOARD_SCROLL_REPEAT_START_SEC:.1f}s"
    )
    print(
        f"  Right stick X (axis {DASHBOARD_PAGE_HORIZONTAL_AXIS}): threshold {DASHBOARD_PAGE_AXIS_THRESHOLD:.2f}, "
        f"move left/right page columns after {DASHBOARD_PAGE_HOLD_SEC:.1f}s, repeat after {DASHBOARD_SCROLL_REPEAT_START_SEC:.1f}s"
    )


def normalize_trigger_axis(raw_value):
    raw = float(raw_value)
    if not math.isfinite(raw):
        return 0.0
    if raw < -0.95:
        return 0.0
    if raw <= 1.0:
        return max(0.0, min(1.0, (raw + 1.0) / 2.0))
    return max(0.0, min(1.0, raw))


def split_shared_trigger_axis(raw_value):
    raw = float(raw_value)
    if not math.isfinite(raw):
        return 0.0, 0.0
    throttle = reference_throttle_to_absolute(
        max(0.0, raw)
    ) if raw > MANUAL_THROTTLE_DEADZONE else 0.0
    brake_force = max(0.0, -raw)
    return throttle, brake_force


def manual_throttle_pwm(raw_value) -> float:
    """Map the useful trigger range to physical PWM while keeping zero truly off."""
    reference = normalize_trigger_axis(raw_value)
    if reference <= MANUAL_THROTTLE_DEADZONE:
        return 0.0
    return reference_throttle_to_absolute(reference)


def clamp_servo_degrees(value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        return float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    return max(0.0, min(float(STEERING_SERVO_ACTUATION_RANGE_DEG), numeric))


def steering_degrees_to_normalized(servo_degrees: float) -> float:
    center_degrees = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    if center_degrees <= 0.0:
        return 0.0
    numeric = float(servo_degrees)
    if not math.isfinite(numeric):
        return 0.0
    return max(-1.0, min(1.0, (numeric - center_degrees) / center_degrees))


def apply_steering_deadzone(raw_value: float) -> float:
    numeric = float(raw_value)
    if not math.isfinite(numeric):
        return 0.0
    clamped = max(-1.0, min(1.0, numeric))
    deadzone = max(0.0, min(0.95, float(STEERING_DEADZONE)))
    magnitude = abs(clamped)
    if magnitude <= deadzone:
        return 0.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    return scaled if clamped > 0.0 else -scaled


def joystick_steer_to_servo_degrees(normalized_value: float) -> float:
    numeric = float(normalized_value)
    if not math.isfinite(numeric):
        numeric = 0.0
    clamped = max(-1.0, min(1.0, numeric))
    return ((clamped + 1.0) / 2.0) * float(STEERING_SERVO_ACTUATION_RANGE_DEG)


def center_steering(state):
    state["steer"] = 0.0
    state["steering_servo_deg"] = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0


def reset_model_steering_state(state) -> None:
    """Start model smoothing from the steering target physically active right now."""
    current = clamp_servo_degrees(
        state.get("steering_servo_deg", float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0)
    )
    state["steer_smoothed_deg"] = current
    state["_jon_result_sequence"] = 0
    state["_jon_submitted_frame_sequence"] = 0


def model_is_series_3(model_choice) -> bool:
    """A Series 3 model choice looks like '3.x'."""
    return str(model_choice).strip().startswith("3")


def get_dashboard_drive_mode(state) -> str:
    if state["autonomous_mode"]:
        return "ATO"
    if state["cc_active"]:
        return "CC"
    return "MAN"


def get_speed_scaled_lidar_thresholds(speed_mph: float) -> tuple[float, float, float]:
    multiplier = 1.75 if float(speed_mph) > 3.0 else 1.0
    return (
        OBSTACLE_STOP_THRESHOLD_M * multiplier,
        OBSTACLE_WARN_THRESHOLD_M * multiplier,
        FORWARD_OBSTACLE_STOP_DISTANCE_M * multiplier,
    )


def format_lidar_dashboard_points(lidar_scan, max_points: int = 180) -> list[list[float]]:
    if not lidar_scan:
        return []
    valid_points = [
        point
        for point in lidar_scan
        if getattr(point, "is_valid", False)
        and getattr(point, "distance_mm", 0) > 0
        and getattr(point, "confidence", 0) > 0
    ]
    if not valid_points:
        return []
    stride = max(1, len(valid_points) // max_points)
    return [
        [
            round(float(getattr(point, "angle_deg", 0.0)), 1),
            round(float(getattr(point, "distance_mm", 0.0)) / 1000.0, 2),
        ]
        for point in valid_points[::stride][:max_points]
    ]


def cycle_steering_model(webcam_vision, current_choice: str, direction: int) -> str:
    choices = tuple(STEERING_MODEL_CHOICES.keys())
    if not choices:
        return current_choice
    try:
        current_index = choices.index(str(current_choice))
    except ValueError:
        current_index = 0
    next_choice = choices[(current_index + direction) % len(choices)]
    if webcam_vision is None:
        print(f"Steering model selection -> {next_choice} (will apply when vision is available).")
        return next_choice
    if webcam_vision.set_model_choice(next_choice):
        return next_choice
    return current_choice


# page number -> (vertical, horizontal) grid position. Page NUMBERS keep their draw
# function + gates; only their grid position is set here to match the target layout.
DASHBOARD_PAGE_COORDS = {
    1: (1, 1),    # V1H1 main (speed/PRND/CC/AEB/dir)
    2: (1, 2),    # V1H2 SRVO/TTLE/BRKE/MODE
    13: (1, 3),   # V1H3 tune DELT/kP/kI/kD
    15: (1, 4),   # V1H4 yaw
    3: (2, 1),    # V2H1 model MODL/PRED/CONF/IPS
    4: (2, 2),    # V2H2 autonomy ICSE/ADT/IPKM/AUT
    16: (2, 3),   # V2H3 temps RTMP/JTMP/GTMP/ZTMP
    14: (3, 1),   # V3H1 photo counters PR/PA/FPS/STS (_draw_page_three)
    5: (4, 1),    # V4H1 nav entry NAVIGATE
    7: (4, 2),    # V4H2 route nodes OPR/PNDE/CNDE/NNDE
    9: (4, 3),    # V4H3 route distance RDT/NDT/SDT/TDT
    10: (4, 4),   # V4H4 route time RTM/NTM
    6: (5, 1),    # V5H1 gps FIX/SATS/ODO/SST
    8: (5, 2),    # V5H2 latlon LAT/LON
    11: (6, 1),   # V6H1 camera/lidar feed
    17: (6, 2),   # V6H2 lidar scan view (forward +/-30 cone)
}
DASHBOARD_COORD_PAGES = {coords: page for page, coords in DASHBOARD_PAGE_COORDS.items()}
DASHBOARD_VERTICAL_PAGE_COUNT = 6
STEERING_TRIM_DASHBOARD_PAGE = 13   # v1h3
LIDAR_DASHBOARD_PAGE = 17           # v6h2 lidar scan view
YAW_DASHBOARD_PAGE = 15             # v1h4 — yaw-PID telemetry
STEERING_TRIM_STEP_DEG = 1.0


def dashboard_page_to_coords(page: int) -> tuple[int, int]:
    page = max(1, min(DASHBOARD_PAGE_COUNT, int(page)))
    return DASHBOARD_PAGE_COORDS.get(page, (1, 1))


def dashboard_coords_to_page(vertical_page: int, horizontal_page: int) -> int:
    vertical_page = max(1, min(DASHBOARD_VERTICAL_PAGE_COUNT, int(vertical_page)))
    horizontal_page = max(1, int(horizontal_page))
    return DASHBOARD_COORD_PAGES.get((vertical_page, horizontal_page), DASHBOARD_COORD_PAGES[(vertical_page, 1)])


def set_dashboard_page(state, page: int) -> None:
    page = max(1, min(DASHBOARD_PAGE_COUNT, int(page)))
    vertical_page, horizontal_page = dashboard_page_to_coords(page)
    state["dashboard_page"] = page
    state["dashboard_page_vertical"] = vertical_page
    state["dashboard_page_horizontal"] = horizontal_page


def steering_center_degrees() -> float:
    return float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0


def sync_steering_trim_state(state, center_offset: float) -> None:
    center_degrees = steering_center_degrees()
    clamped_offset = max(-1.0, min(1.0, float(center_offset)))
    delta_degrees = clamped_offset * center_degrees
    state["steering_center_offset"] = clamped_offset
    state["steering_trim_delta_deg"] = delta_degrees
    state["steering_trim_total_deg"] = center_degrees + delta_degrees


def adjust_steering_center_trim(state, hardware, direction: int) -> None:
    center_degrees = steering_center_degrees()
    current_delta = float(
        state.get(
            "steering_trim_delta_deg",
            STEERING_SERVO_CENTER_OFFSET * center_degrees,
        )
    )
    next_delta = max(-center_degrees, min(center_degrees, current_delta + (int(direction) * STEERING_TRIM_STEP_DEG)))
    next_offset = next_delta / center_degrees if center_degrees else 0.0
    sync_steering_trim_state(state, next_offset)
    servo = getattr(hardware, "steering_servo", None)
    if hasattr(servo, "set_center_offset"):
        try:
            servo.set_center_offset(next_offset)
        except Exception as exc:
            print(f"Steering trim update failed: {exc}")
            return
    print(
        "Steering trim -> "
        f"delta {state['steering_trim_delta_deg']:+.1f} deg, "
        f"total {state['steering_trim_total_deg']:.1f} deg, "
        f"STEERING_SERVO_CENTER_OFFSET={state['steering_center_offset']:+.4f}"
    )


# --- On-device steering tuning page (dashboard page 13 / v1h3) ---------------
# Rows the d-pad up/down cycles through; left/right adjusts the selected one.
# TUNE page rows: trim + the live yaw-PID gains. D-pad up/down picks the row,
# left/right dec/inc. No SAVE -- gains are tuned live in memory.
TUNE_ROWS = ("DELT", "KP", "KI", "KD")


def cycle_tuning_row(state, hat_y: int) -> None:
    # D-pad up (hat_y=+1) moves to the previous row; down moves to the next.
    row = int(state.get("tune_selected_row", 0))
    state["tune_selected_row"] = max(0, min(len(TUNE_ROWS) - 1, row - int(hat_y)))


def adjust_tuning_value(state, hardware, direction: int) -> None:
    row = int(state.get("tune_selected_row", 0))
    step = int(direction)
    if row == 0:    # DELT — center trim +/-1 deg, applied to the servo immediately.
        adjust_steering_center_trim(state, hardware, step)
    elif row == 1:  # KP +/-0.01
        state["yaw_kp"] = max(0.0, round(float(state.get("yaw_kp", 0.0)) + step * 0.01, 3))
        state["yaw_pid_reset"] = True
        print(f"yaw Kp -> {state['yaw_kp']:.2f}")
    elif row == 2:  # KI +/-0.01
        state["yaw_ki"] = max(0.0, round(float(state.get("yaw_ki", 0.0)) + step * 0.01, 3))
        state["yaw_pid_reset"] = True
        print(f"yaw Ki -> {state['yaw_ki']:.2f}")
    elif row == 3:  # KD +/-0.01
        state["yaw_kd"] = max(0.0, round(float(state.get("yaw_kd", 0.0)) + step * 0.01, 3))
        state["yaw_pid_reset"] = True
        print(f"yaw Kd -> {state['yaw_kd']:.2f}")


def dashboard_axis_direction(axis_value: float) -> int:
    if axis_value >= DASHBOARD_PAGE_AXIS_THRESHOLD:
        return 1
    elif axis_value <= -DASHBOARD_PAGE_AXIS_THRESHOLD:
        return -1
    return 0


def dashboard_axis_turn_ready(
    axis_value: float,
    metrics,
    direction_attr: str,
    hold_since_attr: str,
    latched_attr: str,
    last_repeat_attr: str,
) -> int:
    direction = dashboard_axis_direction(axis_value)
    if direction == 0:
        setattr(metrics, direction_attr, 0)
        setattr(metrics, hold_since_attr, 0.0)
        setattr(metrics, latched_attr, False)
        setattr(metrics, last_repeat_attr, 0.0)
        return 0

    now = time.monotonic()
    if direction != getattr(metrics, direction_attr):
        setattr(metrics, direction_attr, direction)
        setattr(metrics, hold_since_attr, now)
        setattr(metrics, latched_attr, False)
        setattr(metrics, last_repeat_attr, 0.0)
        return 0

    held_sec = now - getattr(metrics, hold_since_attr)

    if not getattr(metrics, latched_attr):
        if held_sec < DASHBOARD_PAGE_HOLD_SEC:
            return 0
        setattr(metrics, latched_attr, True)
        setattr(metrics, last_repeat_attr, now)
        return direction

    if held_sec < DASHBOARD_SCROLL_REPEAT_START_SEC:
        return 0

    last_repeat_time = float(getattr(metrics, last_repeat_attr))
    if now - last_repeat_time >= DASHBOARD_SCROLL_REPEAT_INTERVAL_SEC:
        setattr(metrics, last_repeat_attr, now)
        return direction
    return 0


# Hold-to-repeat for the TUNE page left/right adjust. Start matches the d-pad
# default; interval is a touch slower so values step up gently while held.
TUNE_ADJUST_REPEAT_START_SEC = 0.6
TUNE_ADJUST_REPEAT_INTERVAL_SEC = 0.0667      # ~15 adjustments/second while held


def dpad_x_repeat_direction(state, metrics, repeat_start_sec: float, repeat_interval_sec: float) -> int:
    direction = int(state.get("dpad_x_value", 0))
    if direction == 0:
        metrics.dpad_x_direction = 0
        metrics.dpad_x_hold_since = 0.0
        metrics.dpad_x_last_repeat_time = 0.0
        return 0

    now = time.monotonic()
    if direction != metrics.dpad_x_direction:
        metrics.dpad_x_direction = direction
        metrics.dpad_x_hold_since = now
        metrics.dpad_x_last_repeat_time = now
        return 0

    if now - metrics.dpad_x_hold_since < repeat_start_sec:
        return 0
    if now - metrics.dpad_x_last_repeat_time < repeat_interval_sec:
        return 0

    metrics.dpad_x_last_repeat_time = now
    return direction


def dpad_y_repeat_direction(state, metrics, repeat_start_sec: float, repeat_interval_sec: float) -> int:
    direction = int(state.get("dpad_y_value", 0))
    if direction == 0:
        metrics.dpad_y_direction = 0
        metrics.dpad_y_hold_since = 0.0
        metrics.dpad_y_last_repeat_time = 0.0
        return 0

    now = time.monotonic()
    if direction != metrics.dpad_y_direction:
        metrics.dpad_y_direction = direction
        metrics.dpad_y_hold_since = now
        metrics.dpad_y_last_repeat_time = now
        return 0

    if now - metrics.dpad_y_hold_since < repeat_start_sec:
        return 0
    if now - metrics.dpad_y_last_repeat_time < repeat_interval_sec:
        return 0

    metrics.dpad_y_last_repeat_time = now
    return direction


def handle_dpad_y_action(
    direction: int,
    state,
    metrics,
    navigation,
    webcam_vision,
    active_model_choice: str,
    dashboard_sender,
    repeated: bool = False,
) -> str:
    current_page = int(state.get("dashboard_page", 1))
    if current_page == 5:
        if navigation.active:
            return active_model_choice
        navigation.adjust_current(-1 if direction == 1 else 1)
    elif current_page == 3:
        previous_choice = active_model_choice
        active_model_choice = cycle_steering_model(
            webcam_vision,
            active_model_choice,
            1 if direction == 1 else -1,
        )
        if active_model_choice != previous_choice:
            if state["autonomous_mode"]:
                cancel_autonomous_mode(
                    state,
                    metrics,
                    "Autonomous driving cancelled by model change.",
                    cause="model",
                )
            reset_model_steering_state(state)
    elif direction == 1 and state["cc_active"]:
        state["cc_target_speed"] = round(state["cc_target_speed"] + 0.1, 1)
        state["event_cc_increase"] = True
        queue_cc_adjust_notification(dashboard_sender, state["cc_target_speed"])
    elif direction == -1 and state["cc_active"]:
        state["cc_target_speed"] = round(max(0.0, state["cc_target_speed"] - 0.1), 1)
        state["event_cc_decrease"] = True
        queue_cc_adjust_notification(dashboard_sender, state["cc_target_speed"])
    elif direction == 1:
        adjust_dashboard_brightness(state, dashboard_sender, DASHBOARD_BRIGHTNESS_STEP_PERCENT)
    elif direction == -1:
        adjust_dashboard_brightness(state, dashboard_sender, -DASHBOARD_BRIGHTNESS_STEP_PERCENT)
    return active_model_choice


def cancel_navigation_route(
    state,
    metrics,
    navigation,
    reason: str,
    preserve_manual_brake: bool = False,
    preserve_manual_throttle: bool = False,
) -> None:
    if not navigation.active:
        return
    navigation.active = False
    navigation.reset_entry()
    cancel_autonomous_mode(
        state,
        metrics,
        reason,
        preserve_manual_brake=preserve_manual_brake,
        preserve_manual_throttle=preserve_manual_throttle,
    )


def shift_gear(state, metrics, direction: int, navigation=None, dashboard_sender=None) -> None:
    """Apply one PRND step as a manual takeover without releasing a held brake."""
    if navigation is not None and navigation.active:
        cancel_navigation_route(
            state,
            metrics,
            navigation,
            "Navigation cancelled by gear shift.",
            preserve_manual_brake=True,
        )
    elif state["autonomous_mode"]:
        cancel_autonomous_mode(
            state,
            metrics,
            "Autonomous driving cancelled by gear shift.",
            preserve_manual_brake=True,
        )
    current_index = GEARS.index(state["gear_mode"])
    next_index = max(0, min(len(GEARS) - 1, current_index + int(direction)))
    state["gear_mode"] = GEARS[next_index]
    state["event_shift_up"] = direction > 0
    state["event_shift_down"] = direction < 0
    cancel_cruise_control(state, metrics, dashboard_sender)


def navigation_manual_input_should_cancel(navigation, latest_nav, last_operator: str = "") -> bool:
    if not navigation.active:
        return False
    operator = ""
    if isinstance(latest_nav, dict) and latest_nav.get("active"):
        operator = str(latest_nav.get("operator", "")).upper()
    if not operator:
        operator = str(last_operator or "").upper()
    return operator == "AUTO"


def update_dashboard_page_selection(state, metrics) -> None:
    vertical_direction = dashboard_axis_turn_ready(
        float(state.get("dashboard_page_axis_value", 0.0)),
        metrics,
        "dashboard_page_axis_direction",
        "dashboard_page_axis_hold_since",
        "dashboard_page_axis_latched",
        "dashboard_page_axis_last_repeat_time",
    )
    if vertical_direction:
        current_page = max(1, min(DASHBOARD_PAGE_COUNT, int(state.get("dashboard_page", 1))))
        vertical_page, horizontal_page = dashboard_page_to_coords(current_page)
        next_vertical_page = ((vertical_page - 1 + vertical_direction) % DASHBOARD_VERTICAL_PAGE_COUNT) + 1
        next_page = dashboard_coords_to_page(next_vertical_page, horizontal_page)
        set_dashboard_page(state, next_page)
        metrics.dashboard_page_transition = "forward" if vertical_direction > 0 else "back"
        return

    horizontal_direction = dashboard_axis_turn_ready(
        float(state.get("dashboard_page_horizontal_axis_value", 0.0)),
        metrics,
        "dashboard_page_horizontal_axis_direction",
        "dashboard_page_horizontal_axis_hold_since",
        "dashboard_page_horizontal_axis_latched",
        "dashboard_page_horizontal_axis_last_repeat_time",
    )
    if horizontal_direction:
        current_page = max(1, min(DASHBOARD_PAGE_COUNT, int(state.get("dashboard_page", 1))))
        vertical_page, horizontal_page = dashboard_page_to_coords(current_page)
        horizontal_pages = sorted(
            coord_horizontal
            for coord_vertical, coord_horizontal in DASHBOARD_COORD_PAGES
            if coord_vertical == vertical_page
        )
        if len(horizontal_pages) <= 1:
            set_dashboard_page(state, current_page)
            return
        current_index = horizontal_pages.index(horizontal_page)
        next_index = max(0, min(len(horizontal_pages) - 1, current_index + horizontal_direction))
        next_horizontal_page = horizontal_pages[next_index]
        next_page = dashboard_coords_to_page(vertical_page, next_horizontal_page)
        set_dashboard_page(state, next_page)
        metrics.dashboard_page_transition = "right" if horizontal_direction > 0 else "left"


def apply_hard_stop_state(state, reason: str):
    state["target_heading_deg"] = 0.0
    center_steering(state)
    state["throttle"] = 0.0
    state["brake"] = True
    state["brake_force"] = 1.0
    state["stop_reason"] = reason


def write_hardware_hard_stop(hardware) -> None:
    """Command AT8236 brake mode immediately without waiting for service shutdown."""
    outputs = (
        hardware.motor_left_fwd,
        hardware.motor_left_bwd,
        hardware.motor_right_fwd,
        hardware.motor_right_bwd,
    )
    errors = []
    for value in (0.0, 1.0):
        for output in outputs:
            try:
                output.value = value
            except Exception as exc:
                errors.append(exc)
    if errors:
        print(
            f"Immediate motor hard-brake write had {len(errors)} failed output(s): "
            f"{errors[-1]}",
            flush=True,
        )


def _disengagement_cause(reason: str) -> str:
    """Map a cancel reason string to a short cause word for the intervention log."""
    r = (reason or "").lower()
    if "steer" in r:
        return "steer"
    if "gas" in r or "throttle" in r:
        return "throttle"
    if "brake" in r:
        return "brake"
    if "arrived" in r or "destination" in r:
        return "arrived"
    if "nav" in r or "operator" in r or "segment" in r:
        return "nav"
    return "other"


_CAUSE_CODES = {
    "steer": "STR", "throttle": "TLE", "brake": "BRK", "a": "BTN",
    "nav": "NAV", "arrived": "ARR", "lidar": "EMR", "emergency": "EMR", "holding": "HLD",
}


def _cause_code(cause_word: str) -> str:
    """3-letter dashboard code (V2H2 ICSE) for an intervention cause word."""
    return _CAUSE_CODES.get((cause_word or "").strip().lower(), "OTH")


def cancel_autonomous_mode(
    state,
    metrics,
    reason: str,
    center: bool = True,
    cause: str = "",
    preserve_manual_brake: bool = False,
    preserve_manual_throttle: bool = False,
):
    was_autonomous = state["autonomous_mode"]
    retained_brake_force = 0.0
    if preserve_manual_brake:
        retained_brake_force = max(
            0.0,
            min(
                1.0,
                float(
                    state.get(
                        "manual_brake_force",
                        state.get("brake_force", 0.0),
                    )
                ),
            ),
        )
    retained_throttle = 0.0
    retained_motor_pwm = 0.0
    if preserve_manual_throttle:
        requested_throttle = float(state.get("throttle", 0.0))
        current_motor_pwm = float(state.get("current_motor_pwm", 0.0))
        if math.isfinite(requested_throttle):
            retained_throttle = max(0.0, min(1.0, requested_throttle))
        if math.isfinite(current_motor_pwm):
            retained_motor_pwm = max(-1.0, min(1.0, current_motor_pwm))
    if reason:
        print(reason)
    if was_autonomous:                       # only a real disengagement counts as an intervention
        state["event_intervention"] = True
        state["intervention_cause"] = (cause or _disengagement_cause(reason))[:12]
    state["autonomous_mode"] = False
    state["throttle"] = retained_throttle
    state["brake"] = retained_brake_force > 0.1
    state["brake_force"] = retained_brake_force
    state["manual_brake_force"] = retained_brake_force
    state["current_motor_pwm"] = retained_motor_pwm
    state["dashboard_throttle_percent"] = 0
    state["dashboard_brake_percent"] = 0
    if center:
        center_steering(state)
    metrics.driveway_cut_candidate_since = 0.0
    metrics.pid_integral_error = 0.0
    metrics.pid_previous_error = 0.0
    metrics.pid_output = 0.0
    reset_model_steering_state(state)


def engage_autonomous_mode(state, metrics, dashboard_sender=None, jetson_client=None) -> bool:
    """Safely begin a fresh model sequence from the current manual steering target."""
    if float(state.get("manual_brake_force", 0.0)) > 0.1:
        print("Autonomous Driving not enabled: release the brake first.")
        return False
    if jetson_client is not None:
        jetson_client.begin_autonomous_sequence(state["steering_servo_deg"])
    reset_model_steering_state(state)
    state["autonomous_mode"] = True
    state["gear_mode"] = "D"
    cancel_cruise_control(state, metrics, dashboard_sender)
    state["brake"] = False
    state["brake_force"] = 0.0
    state["manual_brake_force"] = 0.0
    metrics.driveway_cut_candidate_since = 0.0
    return True


def move_toward(current: float, target: float, rate: float, dt: float) -> float:
    step = max(0.0, rate) * max(0.0, dt)
    if current < target:
        return min(current + step, target)
    if current > target:
        return max(current - step, target)
    return target


def print_controller_telemetry(event):
    if event.type == pygame.JOYAXISMOTION:
        print(f"[controller] axis {event.axis} -> {event.value:.3f}")
    elif event.type == pygame.JOYBUTTONDOWN:
        print(f"[controller] button {event.button} down")
    elif event.type == pygame.JOYBUTTONUP:
        print(f"[controller] button {event.button} up")
    elif event.type == pygame.JOYHATMOTION:
        print(f"[controller] hat -> {event.value}")


def try_toggle_cruise_control(state, metrics, dashboard_sender=None):
    if state["gear_mode"] != "D":
        print(f"Cruise Control not enabled: gear must be D, current gear is {state['gear_mode']}.")
        return
    if state["brake"]:
        print("Cruise Control not enabled: brake is active.")
        return
    if metrics.smoothed_speed_mph <= 0.1:
        print("Cruise Control not enabled: speed is too low or hall sensor is not reporting.")
        return

    state["cc_active"] = not state["cc_active"]
    if state["cc_active"]:
        state["cc_target_speed"] = metrics.smoothed_speed_mph
        metrics.cruise_ignore_throttle_until_release = state["throttle"] > 0.05
        print(f"Cruise Control ENABLED at {state['cc_target_speed']:.2f} mph.")
        queue_cc_enabled_notification(dashboard_sender, state["cc_target_speed"])
    else:
        metrics.cruise_ignore_throttle_until_release = False
        print("Cruise Control DISABLED.")
        queue_cc_disabled_notification(dashboard_sender)

    metrics.pid_integral_error = 0.0
    metrics.pid_previous_error = 0.0
    metrics.pid_output = 0.0


def format_cc_speed_cells(speed_mph: float) -> list[str]:
    clamped = max(0.0, min(9.9, float(speed_mph)))
    tenths = int(round(clamped * 10.0))
    if tenths > 99:
        tenths = 99
    return [f"{tenths // 10}.", str(tenths % 10)]


def queue_dashboard_notification(dashboard_sender, cells: list[str], duration_sec: float = 2.0):
    if dashboard_sender is None:
        return
    dashboard_sender.queue_notification(cells, duration_sec=duration_sec)


def queue_cc_enabled_notification(dashboard_sender, target_speed_mph: float):
    speed_cells = format_cc_speed_cells(target_speed_mph)
    queue_dashboard_notification(dashboard_sender, ["C", "C", ":", "O", "N", "@", speed_cells[0], speed_cells[1]])


def queue_cc_adjust_notification(dashboard_sender, target_speed_mph: float):
    speed_cells = format_cc_speed_cells(target_speed_mph)
    queue_dashboard_notification(dashboard_sender, ["C", "C", ":", "", "", "", speed_cells[0], speed_cells[1]])


def queue_cc_disabled_notification(dashboard_sender):
    queue_dashboard_notification(dashboard_sender, ["C", "C", ":", "", "", "O", "F", "F"])


def queue_aeb_toggle_notification(dashboard_sender, enabled: bool):
    if enabled:
        queue_dashboard_notification(dashboard_sender, ["A", "E", "B", ":", "", "", "O", "N"])
    else:
        queue_dashboard_notification(dashboard_sender, ["A", "E", "B", ":", "", "O", "F", "F"])


def queue_auto_photo_notification(dashboard_sender, enabled: bool):
    if enabled:
        queue_dashboard_notification(dashboard_sender, ["A", "T", "C", "P", ":", "", "O", "N"])
    else:
        queue_dashboard_notification(dashboard_sender, ["A", "T", "C", "P", ":", "O", "F", "F"])


def format_brightness_cells(brightness_percent: int) -> list[str]:
    clamped = max(0, min(100, int(brightness_percent)))
    if clamped >= 100:
        return ["10", "0", "%"]
    return [str(clamped // 10), str(clamped % 10), "%"]


def queue_glow_notification(dashboard_sender, brightness_percent: int):
    glow_cells = format_brightness_cells(brightness_percent)
    queue_dashboard_notification(dashboard_sender, ["G", "L", "O", "W", ":", glow_cells[0], glow_cells[1], glow_cells[2]])


def adjust_dashboard_brightness(state, dashboard_sender, delta_percent: int):
    current = int(state.get("dashboard_brightness_percent", DASHBOARD_BRIGHTNESS_PERCENT_DEFAULT))
    updated = max(0, min(100, current + int(delta_percent)))
    state["dashboard_brightness_percent"] = updated
    print(f"Dashboard brightness -> {updated}%")
    queue_glow_notification(dashboard_sender, updated)


def cancel_cruise_control(state, metrics, dashboard_sender=None, reason: str | None = None):
    if not state["cc_active"]:
        return
    state["cc_active"] = False
    metrics.cruise_ignore_throttle_until_release = False
    metrics.pid_integral_error = 0.0
    metrics.pid_previous_error = 0.0
    metrics.pid_output = 0.0
    if reason:
        print(reason)
    queue_cc_disabled_notification(dashboard_sender)


def handle_manual_throttle_override(state, metrics, dashboard_sender=None):
    if not state["cc_active"]:
        return
    if metrics.cruise_ignore_throttle_until_release:
        if state["throttle"] <= 0.05:
            metrics.cruise_ignore_throttle_until_release = False
        return
    if state["throttle"] > 0.05:
        cancel_cruise_control(state, metrics, dashboard_sender, "Cruise Control cancelled by throttle input.")


def set_turn_signal_mode(state, metrics, mode: str):
    previous_mode = state["turn_signal_mode"]
    state["turn_signal_mode"] = mode
    metrics.turn_signal_blink_on = mode != "off"
    metrics.turn_signal_last_toggle_time = time.time()
    if previous_mode != mode:
        print(f"Turn signal mode -> {mode}")
    update_turn_signal_outputs(state, metrics)


def toggle_turn_signal(state, metrics, mode: str):
    if state["turn_signal_mode"] == mode:
        set_turn_signal_mode(state, metrics, "off")
    else:
        set_turn_signal_mode(state, metrics, mode)


def update_turn_signal_outputs(state, metrics):
    mode = state["turn_signal_mode"]
    blink_on = metrics.turn_signal_blink_on and mode != "off"
    previous_left = state["turn_signal_left_visible"]
    previous_right = state["turn_signal_right_visible"]
    state["turn_signal_left_visible"] = blink_on and mode in ("left", "hazard")
    state["turn_signal_right_visible"] = blink_on and mode in ("right", "hazard")
    if (
        previous_left != state["turn_signal_left_visible"]
        or previous_right != state["turn_signal_right_visible"]
    ):
        print(
            "Turn signal visible -> "
            f"L={state['turn_signal_left_visible']} "
            f"R={state['turn_signal_right_visible']}"
        )


def update_turn_signal_blink(state, metrics):
    if state["turn_signal_mode"] == "off":
        state["turn_signal_left_visible"] = False
        state["turn_signal_right_visible"] = False
        return
    current_time = time.time()
    if current_time - metrics.turn_signal_last_toggle_time >= TURN_SIGNAL_BLINK_INTERVAL_SEC:
        metrics.turn_signal_blink_on = not metrics.turn_signal_blink_on
        metrics.turn_signal_last_toggle_time = current_time
    update_turn_signal_outputs(state, metrics)


def get_dashboard_alert(state) -> str:
    if state["direction_arrow"] == "STOP_WARNING":
        return "STOP"
    if state["direction_arrow"] == "BLOCKED":
        return "STOP"
    if state["direction_arrow"] == "WARN_WARNING":
        return "WARN"
    stop_reason = state["stop_reason"]
    if stop_reason in ("blocked_path", "driveway_cut", "lidar_unavailable"):
        return "STOP"
    if stop_reason == "recovering_warn":
        return "WARN"
    return ""


def get_system_status(state, model_frame_is_stale: bool = False) -> str:
    return photo_status


def count_photos_all() -> int:
    base = Path(PHOTO_DIR)
    if not base.exists():
        return 0
    return sum(1 for f in base.rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png"))


def is_stop_brake_condition(state) -> bool:
    return bool(state.get("lidar_emergency_stop", False))


def get_cpu_temp():
    """Read the kernel thermal sensor directly; never fork from the control loop."""
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
        value = float(raw)
        return value / 1000.0 if value > 1000.0 else value
    except (OSError, ValueError):
        return 0.0


def create_photo_run_dir() -> Path:
    base_dir = Path(PHOTO_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)
    day_prefix = datetime.datetime.now().strftime("%Y_%m_%d")
    existing_indices = []
    for child in base_dir.iterdir():
        if not child.is_dir():
            continue
        prefix = f"{day_prefix}_run_"
        if not child.name.startswith(prefix):
            continue
        suffix = child.name[len(prefix) :]
        if suffix.isdigit():
            existing_indices.append(int(suffix))
    next_index = (max(existing_indices) + 1) if existing_indices else 1
    run_dir = base_dir / f"{day_prefix}_run_{next_index}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def cleanup_photo_run_dir() -> None:
    global current_photo_run_dir
    if current_photo_run_dir is None or not current_photo_run_dir.exists():
        return
    has_files = any(child.is_file() for child in current_photo_run_dir.iterdir())
    if not has_files:
        current_photo_run_dir.rmdir()
        print(f"Removed empty photo run folder: {current_photo_run_dir}")
    current_photo_run_dir = None


def current_forward_throttle_label(state) -> float:
    """Return absolute physical PWM for training labels (55% remains 0.55)."""
    if state is None:
        return 0.0
    try:
        motor_pwm = float(state.get("current_motor_pwm", state.get("throttle", 0.0)))
    except (TypeError, ValueError):
        motor_pwm = 0.0
    return max(0.0, min(1.0, motor_pwm))


def append_photo_run_row(run_dir: Path, photo_name: str, servo_degrees: float, throttle: float) -> None:
    """Append ONE line to the per-run label CSV (O(1), crash-safe) and bump the live
    stats. The trainer's JSON is built from this CSV by finalize_photo_run()."""
    steering = int(round(clamp_servo_degrees(servo_degrees)))
    thr = round(max(0.0, min(1.0, float(throttle))), 4)
    csv_path = run_dir / f"{run_dir.name}_labels.csv"
    try:
        new = not csv_path.exists()
        with open(csv_path, "a") as f:
            if new:
                f.write("photo,steering,throttle\n")
            f.write(f"{photo_name},{steering},{thr}\n")
    except Exception as exc:
        print(f"Failed to append photo label row {csv_path}: {exc}")
        return
def finalize_photo_run(run_dir: Path | None) -> None:
    """Build the trainer's <run>.json from the appended <run>_labels.csv. Called when
    a capture run ends (toggle off / shutdown) so the heavy JSON write happens once."""
    if run_dir is None:
        return
    csv_path = run_dir / f"{run_dir.name}_labels.csv"
    if not csv_path.exists():
        return
    labels: dict[str, dict] = {}
    try:
        for line in csv_path.read_text().splitlines()[1:]:   # skip header
            parts = line.split(",")
            if len(parts) < 3:
                continue
            try:
                labels[parts[0]] = {"steering": int(float(parts[1])), "throttle": float(parts[2])}
            except ValueError:
                continue
        (run_dir / f"{run_dir.name}.json").write_text(json.dumps(labels, indent=2) + "\n")
        print(f"Finalized photo run: {len(labels)} labels -> {run_dir.name}.json")
    except Exception as exc:
        print(f"Failed to finalize photo run {run_dir}: {exc}")


def take_photo(webcam_vision=None, state=None, metrics=None, quiet=False):
    global current_photo_run_dir, photo_status
    if current_photo_run_dir is None:
        current_photo_run_dir = create_photo_run_dir()
    # microsecond stamp -> unique + ordered + ms-precise at 30fps (no suffix churn)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    photo_name = f"photo_{timestamp}.jpg"
    photo_path = current_photo_run_dir / photo_name
    suffix = 1
    while photo_path.exists():
        photo_name = f"photo_{timestamp}_{suffix}.jpg"
        photo_path = current_photo_run_dir / photo_name
        suffix += 1
    filename = str(photo_path)
    if webcam_vision:
        photo_status = "CTRE"
        # async: fast frame-copy + enqueue; the slow JPEG write is off the loop.
        queued = webcam_vision.queue_frame_save(filename)
        if queued:
            servo_degrees = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
            if state is not None:
                servo_degrees = float(state.get("steering_servo_deg", servo_degrees))
            append_photo_run_row(current_photo_run_dir, photo_name, servo_degrees, current_forward_throttle_label(state))
            if metrics is not None:
                metrics.dashboard_photos_run += 1
                metrics.dashboard_photos_all += 1
            photo_status = "SAVE"
            if not quiet:
                print(f"Photo queued from live Pi camera stream: {photo_name}")
            return True
        photo_status = "ERR"
        print(
            "Pi camera stream photo capture unavailable: "
            "no frame was available or the save queue was full."
        )
    else:
        photo_status = "ERR"
        print("Pi camera stream photo capture unavailable: no active camera stream")
    return False


def schedule_next_auto_photo(metrics, now: float | None = None) -> float:
    # Continuous high-rate capture: next frame one capture-period away.
    delay_sec = 1.0 / max(1.0, float(PHOTO_RUN_CAPTURE_FPS))
    metrics.auto_photo_next_time = (time.time() if now is None else now) + delay_sec
    return delay_sec


def toggle_auto_photo(state, metrics, dashboard_sender=None):
    state["auto_photo_enabled"] = not bool(state.get("auto_photo_enabled", False))
    if state["auto_photo_enabled"]:
        schedule_next_auto_photo(metrics)
        print(f"Run capture ENABLED at {PHOTO_RUN_CAPTURE_FPS:.0f} fps (continuous).")
    else:
        metrics.auto_photo_next_time = 0.0
        finalize_photo_run(current_photo_run_dir)   # build the JSON from the CSV
        print("Run capture DISABLED.")
    queue_auto_photo_notification(dashboard_sender, state["auto_photo_enabled"])


def update_auto_photo(state, metrics, webcam_vision, dashboard_sender=None):
    if not state.get("auto_photo_enabled"):
        return
    now = time.time()
    if metrics.auto_photo_next_time <= 0.0:
        schedule_next_auto_photo(metrics, now)
        return
    if now < metrics.auto_photo_next_time:
        return
    # Don't capture while the car is stopped: stationary frames are near-
    # duplicates that bias the dataset and waste the image budget without
    # teaching steering. Require BOTH ~0 speed AND ~0 throttle so a flaky hall
    # sensor (speed stuck at 0) can't silently kill capture while you're
    # actually driving. Defer (no reschedule) -> resumes the moment you move.
    if (float(getattr(metrics, "smoothed_speed_mph", 0.0)) < 0.1
            and float(state.get("throttle", 0.0)) < 0.05):
        return
    take_photo(webcam_vision, state, metrics, quiet=True)   # quiet: no per-frame spam at 10 fps
    schedule_next_auto_photo(metrics, now)


def write_steering_servo_safely(state, metrics, hardware, servo_degrees: float) -> bool:
    try:
        if getattr(hardware.steering_servo, "value", None) != servo_degrees:
            hardware.steering_servo.value = servo_degrees
        if metrics.servo_fault_until:
            metrics.servo_fault_until = 0.0
            print("Steering servo write recovered.")
        return True
    except OSError as exc:
        metrics.servo_error_count += 1
        metrics.servo_fault_until = time.time() + 0.5
        now = time.time()
        if now - metrics.servo_error_last_log_time >= 2.0:
            print(f"Steering servo I2C write failed; braking until it recovers: {exc}")
            metrics.servo_error_last_log_time = now
        state["stop_reason"] = "servo_i2c_fault"
        return False
    except Exception as exc:
        metrics.servo_error_count += 1
        metrics.servo_fault_until = time.time() + 0.5
        now = time.time()
        if now - metrics.servo_error_last_log_time >= 2.0:
            print(f"Steering servo write failed; braking until it recovers: {exc}")
            metrics.servo_error_last_log_time = now
        state["stop_reason"] = "servo_fault"
        return False


def calculate_speed(state, metrics, dt):
    current_time = time.time()
    time_since_last_raw_speed_calc = current_time - metrics.previous_speed_calculation_time

    if time_since_last_raw_speed_calc >= 0.1:
        pulses_in_interval = metrics.pulse_count - metrics.previous_pulse_count
        if pulses_in_interval > 0:
            pulses_per_second = pulses_in_interval / time_since_last_raw_speed_calc
            revs_per_second = pulses_per_second / PULSES_PER_REVOLUTION
            speed_cm_per_sec = revs_per_second * WHEEL_CIRCUMFERENCE_CM
            metrics.current_raw_mph = speed_cm_per_sec * CM_PER_SEC_TO_MPH
        else:
            metrics.current_raw_mph = 0.0
        metrics.previous_pulse_count = metrics.pulse_count
        metrics.previous_speed_calculation_time = current_time

    if abs(state["current_motor_pwm"]) < 0.01 and metrics.current_raw_mph < 0.2:
        metrics.smoothed_speed_mph = 0.0
    elif metrics.smoothed_speed_mph == 0.0:
        metrics.smoothed_speed_mph = metrics.current_raw_mph
    else:
        metrics.smoothed_speed_mph = (
            SPEED_SMOOTHING_ALPHA * metrics.current_raw_mph
            + (1.0 - SPEED_SMOOTHING_ALPHA) * metrics.smoothed_speed_mph
        )

    if metrics.smoothed_speed_mph > metrics.max_speed_recall:
        metrics.max_speed_recall = metrics.smoothed_speed_mph

    metrics.total_distance_cm += (metrics.smoothed_speed_mph / CM_PER_SEC_TO_MPH) * dt

    # --- autonomy metrics (V2H2), edge-detected off autonomous_mode ---
    # A stint under AUTONOMY_MIN_SEGMENT_S (6s) is a tap in/out, not a real segment:
    # it's excluded from AUT (avg uptime) + IPKM (interventions), but still counts for
    # ADT (distance, accumulated below) and ICSE (last cause code, set on every disengage).
    engaged = bool(state["autonomous_mode"])
    if engaged and not metrics.auto_prev_engaged:          # engage -> start a segment timer
        metrics.auto_segment_s = 0.0
    elif metrics.auto_prev_engaged and not engaged:        # disengage
        code = _cause_code(state.get("intervention_cause", ""))
        metrics.auto_last_cause_code = code                # ICSE: every disengage
        if metrics.auto_segment_s >= AUTONOMY_MIN_SEGMENT_S:   # only real stints count for AUT/IPKM
            metrics.auto_time_s += metrics.auto_segment_s
            metrics.auto_segments += 1
            if code != "ARR":                              # arrivals aren't interventions
                metrics.auto_intervention_count += 1
        metrics.auto_segment_s = 0.0
    if engaged:
        metrics.auto_segment_s += dt
        metrics.auto_distance_cm += (metrics.smoothed_speed_mph / CM_PER_SEC_TO_MPH) * dt  # ADT: all segments
    metrics.auto_prev_engaged = engaged


def _run_number_today():
    """Nth car launch today (1,2,3...), persisted in ~/.sidewalkpilot_runcount.json.
    Resets when the date rolls over. Shown on the z2w V1H1 page as R###."""
    path = os.path.expanduser("~/.sidewalkpilot_runcount.json")
    today = time.strftime("%Y%m%d")
    data = {}
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        pass
    n = int(data.get("count", 0)) + 1 if data.get("date") == today else 1
    try:
        with open(path, "w") as f:
            json.dump({"date": today, "count": n}, f)
    except Exception:
        pass
    return n


def _tf(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ti(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _drive_telemetry(state, metrics, jetson_client):
    """Flatten the driving state into (influx_fields, influx_tags). Defensive -- missing
    keys drop out, never raises. The 9 bucket probs come from Jon's last reply."""
    g = state.get
    fields = {
        "servo_deg": _tf(g("steering_servo_deg")),
        "steer_norm": _tf(g("steer")),
        "steer_smoothed_deg": _tf(g("steer_smoothed_deg")),
        "target_heading_deg": _tf(g("target_heading_deg")),
        "camera_bias": _tf(g("camera_steering_bias")),
        "camera_confidence": _tf(g("camera_confidence")),
        "motor_pwm": _tf(g("current_motor_pwm")),
        "throttle": _tf(g("throttle")),
        "brake_force": _tf(g("brake_force")),
        "lidar_front_m": _tf(g("lidar_front_dist")),
        "lidar_left_m": _tf(g("lidar_left_dist")),
        "lidar_right_m": _tf(g("lidar_right_dist")),
        "lidar_back_m": _tf(g("lidar_back_dist")),
        "lidar_clearance_m": _tf(g("lidar_forward_clearance_m")),
        "num_lidar_points": _ti(g("num_lidar_points")),
        "override_active": bool(g("lidar_override_active", False)),
        "autonomous": bool(g("autonomous_mode", False)),
        "speed_mph": _tf(getattr(metrics, "smoothed_speed_mph", None)),
        "jon_cpu_c": _tf(g("jon_cpu_temp_c")),
        "jon_gpu_c": _tf(g("jon_gpu_temp_c")),
        "infer_ms": _tf(g("infer_ms")),
        "infer_ips": _tf(g("infer_fps")),
    }
    if g("stop_reason"):
        fields["stop_reason"] = str(g("stop_reason"))
    probs = getattr(jetson_client, "bucket_probs", None) if jetson_client is not None else None
    if probs and len(probs) == 9:
        for i, p in enumerate(probs):
            fields[f"p{i}"] = float(p)
    fields = {k: v for k, v in fields.items() if v is not None}
    tags = {"gear": str(g("gear_mode", "?")), "mode": "auto" if g("autonomous_mode") else "manual"}
    return fields, tags


def apply_autonomous_controls(state, metrics, hardware, webcam_vision, lidar_scan,
                              jetson_client=None, active_model_choice=None,
                              lidar_policy=None):
    # Apply an already-computed emergency decision before waiting on camera/Jetson work.
    # The same policy object is reused below so one control loop cannot interpret two scans.
    av = lidar_policy or lidar_avoidance.evaluate(
        lidar_scan,
        enabled=metrics.aeb_enabled,
        scan_fresh=bool(state.get("lidar_scan_fresh", True)),
    )
    state["lidar_forward_clearance_m"] = av["front_m"]
    state["lidar_lane_occupancy"] = av["lane_occupancy"]
    state["lidar_emergency_lane_occupancy"] = av["emergency_lane_occupancy"]
    state["lidar_lane_action"] = av["lane_action"]
    if av["code"]:
        metrics.auto_last_cause_code = av["code"]
    if av["stop"]:
        apply_hard_stop_state(state, av["reason"])
        return 0.0, True

    camera_analysis = {
        "heading_bias": 0.0,
        "confidence": 0.0,
        "left_edge_found": False,
        "right_edge_found": False,
        "corridor_width_px": 0.0,
        "driveway_cut_hint": False,
        "method": "none",
    }
    model_frame_is_stale = True

    # The Raspberry Pi 5 sends the live frame and active model choice through a
    # latest-frame worker. Network, JPEG, and inference waits stay off the control
    # loop. If the Jetson result is missing, mismatched, or stale, autonomy stops.
    if jetson_client is not None:
        frame_sample = None
        if webcam_vision is not None and hasattr(webcam_vision, "grab_latest_frame_sample"):
            frame_sample = webcam_vision.grab_latest_frame_sample(
                after_sequence=int(state.get("_jon_submitted_frame_sequence", 0))
            )
        elif webcam_vision is not None:
            frame = webcam_vision.grab_latest_frame()
            if frame is not None:
                frame_sample = (int(state.get("_jon_submitted_frame_sequence", 0)) + 1, frame)
        if frame_sample is not None:
            if len(frame_sample) == 3:
                frame_sequence, frame_captured_at, frame = frame_sample
            else:
                frame_sequence, frame = frame_sample
                frame_captured_at = time.monotonic()
            jetson_client.submit(
                frame,
                model_version=active_model_choice,
                source_frame_sequence=frame_sequence,
                captured_at=frame_captured_at,
            )
            state["_jon_submitted_frame_sequence"] = int(frame_sequence)
        jon_sample = jetson_client.get_latest_sample(
            model_version=active_model_choice,
            max_age_sec=JETSON_RESULT_MAX_AGE_SEC,
        )
        if jon_sample is not None:
            source_frame_sequence = int(jon_sample.get("source_frame_sequence", 0))
            latest_frame_sequence = int(state.get("_jon_submitted_frame_sequence", 0))
            frame_lag = max(0, latest_frame_sequence - source_frame_sequence)
            if source_frame_sequence and frame_lag > JETSON_RESULT_MAX_FRAME_LAG:
                jon_sample = None
        if jon_sample is not None:
            jon_result = jon_sample["result"]
            jon_steer_deg, _jon_throttle = jon_result
            # Temporal smoothing (EMA): the v3.1 hybrid head can flip steering buckets
            # frame-to-frame (blocky output). Blend with the previous command to damp it.
            # Apply the EMA once per completed inference, not once per control tick.
            jon_sequence = int(jon_sample["sequence"])
            if jon_sequence != int(state.get("_jon_result_sequence", 0)):
                _prev_steer = state.get("steer_smoothed_deg")
                if _prev_steer is not None and 0.0 < STEERING_SMOOTH_ALPHA < 1.0:
                    jon_steer_deg = (STEERING_SMOOTH_ALPHA * jon_steer_deg
                                     + (1.0 - STEERING_SMOOTH_ALPHA) * _prev_steer)
                state["steer_smoothed_deg"] = jon_steer_deg
                state["_jon_result_sequence"] = jon_sequence
            else:
                jon_steer_deg = float(state.get("steer_smoothed_deg", jon_steer_deg))
            # Jon reports its CPU/GPU temps + inference rate back with each frame
            state["jon_cpu_temp_c"] = float(getattr(jetson_client, "jon_cpu_temp_c", 0.0))
            state["jon_gpu_temp_c"] = float(getattr(jetson_client, "jon_gpu_temp_c", 0.0))
            state["infer_fps"] = float(getattr(jetson_client, "infer_fps", 0.0))
            state["infer_ms"] = float(getattr(jetson_client, "infer_ms", 0.0))
            state["capture_to_result_ms"] = float(
                jon_sample.get("capture_to_result_ms", 0.0)
            )
            state["model_frame_lag"] = frame_lag
            # perf on the Pi cmdline (Jon is headless): IPS vs FPS + Jon session.run ms, throttled ~2s.
            # If infer_ms is small but IPS<FPS -> Pi-loop/JPEG bound, not the model.
            _perf_now = time.time()
            if _perf_now >= state.get("_perf_next", 0.0):
                state["_perf_next"] = _perf_now + 2.0
                _cam_fps = webcam_vision.camera_fps if webcam_vision is not None else 0.0
                _latency = jetson_client.get_latency_summary()
                print(
                    f"[perf] control={state.get('control_loop_hz', 0.0):.1f}Hz  "
                    f"camera={_cam_fps:.1f}FPS  IPS={state['infer_fps']:.1f}  "
                    f"infer={state['infer_ms']:.1f}ms  "
                    f"capture-result={state['capture_to_result_ms']:.1f}ms  "
                    f"lag={state['model_frame_lag']}f",
                    flush=True,
                )
                if _latency["sample_count"]:
                    _request = _latency["inference_request_ms"]
                    _capture = _latency["capture_to_result_ms"]
                    _socket = _latency["socket_round_trip_ms"]
                    _deadline_ms = 1000.0 / float(CONTROL_LOOP_HZ)
                    if _latency["sample_count"] < CONTROL_LOOP_HZ:
                        _deadline_status = "WARMUP"
                    else:
                        _deadline_status = (
                            "PASS" if _request["p95"] <= _deadline_ms else "FAIL"
                        )
                    print(
                        f"[latency:{_latency['sample_count']}] "
                        f"request p50/p95/p99={_request['p50']:.1f}/"
                        f"{_request['p95']:.1f}/{_request['p99']:.1f}ms  "
                        f"socket+server={_socket['p50']:.1f}/{_socket['p95']:.1f}/"
                        f"{_socket['p99']:.1f}ms  "
                        f"capture-result={_capture['p50']:.1f}/{_capture['p95']:.1f}/"
                        f"{_capture['p99']:.1f}ms  "
                        f"{CONTROL_LOOP_HZ}Hz-p95={_deadline_status}",
                        flush=True,
                    )
            camera_analysis = {
                "heading_bias": max(-1.0, min(1.0, (jon_steer_deg - 90.0) / 90.0)),
                "confidence": 1.0,
                "left_edge_found": False,
                "right_edge_found": False,
                "corridor_width_px": 0.0,
                "driveway_cut_hint": False,
                "steering_angle_deg": jon_steer_deg,
                "method": f"jetson:{active_model_choice}",
            }
            model_frame_is_stale = False
        else:
            model_frame_is_stale = True
            camera_analysis["confidence"] = 0.0
            camera_analysis["method"] = "jetson_unreachable"
    else:
        camera_analysis["method"] = "jetson_unavailable"

    state["camera_steering_bias"] = camera_analysis["heading_bias"]
    state["camera_confidence"] = camera_analysis["confidence"]
    state["camera_left_edge_found"] = camera_analysis["left_edge_found"]
    state["camera_right_edge_found"] = camera_analysis["right_edge_found"]
    state["camera_corridor_width_px"] = camera_analysis["corridor_width_px"]
    state["stop_reason"] = ""
    state["lidar_override_active"] = False
    state["lidar_override_side"] = ""

    state["lidar_best_heading_deg"] = 0.0
    state["lidar_heading_confidence"] = 0.0
    state["lidar_forward_clearance_m"] = state["lidar_front_dist"]

    # LiDAR never commands steering. It can only cap throttle or request an emergency
    # stop in the center corridor, and the complete policy follows the AEB toggle.
    # debug (throttled ~1s, autonomous only): shows WHY the car does/doesn't roll --
    # forward clearance, avoidance code/stop, governed throttle, model confidence + source.
    _adbg_now = time.time()
    if _adbg_now >= state.get("_autodbg_next", 0.0):
        state["_autodbg_next"] = _adbg_now + 1.0
        print(f"[auto-dbg] fwd={av['front_m']:.2f}m code={av['code'] or 'CLEAR'} "
              f"stop={av['stop']} gov_thr={av['throttle']:.2f} "
              f"lanes={av['emergency_lane_occupancy'] or '-'} action={av['lane_action']} "
              f"conf={camera_analysis['confidence']:.2f} method={camera_analysis['method']}", flush=True)
    lidar_governed_throttle = av["throttle"]

    camera_confidence = camera_analysis["confidence"]
    if webcam_vision is None or model_frame_is_stale or camera_confidence < LOW_CAMERA_CONFIDENCE:
        state["driveway_cut_suspected"] = False
        apply_hard_stop_state(
            state,
            "model_unavailable" if webcam_vision is None else "model_low_confidence",
        )
        return 0.0, True

    servo_degrees = clamp_servo_degrees(camera_analysis.get("steering_angle_deg", STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0))
    normalized_steer = steering_degrees_to_normalized(servo_degrees)
    target_heading_deg = normalized_steer * MAX_TARGET_HEADING_DEG
    metrics.last_confident_heading_deg = target_heading_deg
    target_heading_deg = max(-MAX_TARGET_HEADING_DEG, min(MAX_TARGET_HEADING_DEG, target_heading_deg))

    state["steering_servo_deg"] = servo_degrees
    state["target_heading_deg"] = target_heading_deg
    state["steer"] = normalized_steer

    # Throttle is set by the LiDAR governor (forward clearance), not a fixed cruise/turn PWM.
    return lidar_governed_throttle, False


def update_gpio(state, metrics, hardware, webcam_vision, lidar_scan, dt, dashboard_sender=None,
                yaw_controller=None, imu_reader=None, jetson_client=None, active_model_choice=None):
    current_time = time.time()
    desired_pwm_from_input = 0.0
    manual_brake_force = max(
        0.0,
        min(1.0, float(state.get("manual_brake_force", 0.0))),
    )
    effective_brake_from_input = manual_brake_force > 0.1
    effective_brake_force = manual_brake_force
    lidar_policy = lidar_avoidance.evaluate(
        lidar_scan,
        enabled=metrics.aeb_enabled,
        scan_fresh=bool(state.get("lidar_scan_fresh", True)),
    )
    state["lidar_lane_occupancy"] = lidar_policy["lane_occupancy"]
    state["lidar_emergency_lane_occupancy"] = lidar_policy["emergency_lane_occupancy"]
    state["lidar_lane_action"] = lidar_policy["lane_action"]
    state["lidar_throttle_cap"] = lidar_policy["throttle"]
    state["lidar_emergency_stop"] = lidar_policy["stop"]

    if state["autonomous_mode"]:
        desired_pwm_from_input, effective_brake_from_input = apply_autonomous_controls(
            state, metrics, hardware, webcam_vision, lidar_scan,
            jetson_client=jetson_client, active_model_choice=active_model_choice,
            lidar_policy=lidar_policy,
        )
        desired_pwm_from_input = max(0.0, min(AUTONOMOUS_CRUISE_PWM, desired_pwm_from_input))
        state["throttle"] = desired_pwm_from_input
        state["brake"] = effective_brake_from_input
        state["brake_force"] = 1.0 if effective_brake_from_input else 0.0
        effective_brake_force = state["brake_force"]
        cancel_cruise_control(state, metrics, dashboard_sender)
        metrics.pid_integral_error = 0.0
        metrics.pid_previous_error = 0.0
        metrics.pid_output = 0.0
    else:
        state["camera_steering_bias"] = 0.0
        state["camera_confidence"] = 0.0
        state["camera_left_edge_found"] = False
        state["camera_right_edge_found"] = False
        state["camera_corridor_width_px"] = 0.0
        state["target_heading_deg"] = 0.0
        state["lidar_best_heading_deg"] = 0.0
        state["lidar_heading_confidence"] = 0.0
        state["lidar_forward_clearance_m"] = state["lidar_front_dist"]
        state["driveway_cut_suspected"] = False
        state["stop_reason"] = ""
        state["lidar_override_active"] = False
        state["lidar_override_side"] = ""

        if state["gear_mode"] == "P":
            desired_pwm_from_input = 0.0
            effective_brake_from_input = True
            effective_brake_force = 1.0
            state["current_motor_pwm"] = 0.0
            metrics.pid_integral_error = 0.0
            metrics.pid_previous_error = 0.0
            metrics.pid_output = 0.0
        elif state["gear_mode"] == "N":
            desired_pwm_from_input = 0.0
            effective_brake_from_input = False
            effective_brake_force = 0.0
            state["current_motor_pwm"] = 0.0
            metrics.pid_integral_error = 0.0
            metrics.pid_previous_error = 0.0
            metrics.pid_output = 0.0
        elif state["gear_mode"] == "R":
            desired_pwm_from_input = -state["throttle"] if not effective_brake_from_input else 0.0
            metrics.pid_integral_error = 0.0
            metrics.pid_previous_error = 0.0
            metrics.pid_output = 0.0
        elif state["gear_mode"] == "D":
            if effective_brake_from_input:
                desired_pwm_from_input = 0.0
                cancel_cruise_control(state, metrics, dashboard_sender)
            elif state["cc_active"]:
                error = state["cc_target_speed"] - metrics.smoothed_speed_mph
                p_term = KP * error
                metrics.pid_integral_error += error * dt
                metrics.pid_integral_error = max(-10.0, min(10.0, metrics.pid_integral_error))
                i_term = KI * metrics.pid_integral_error
                d_term = KD * ((error - metrics.pid_previous_error) / dt) if dt > 0 else 0.0
                metrics.pid_previous_error = error
                metrics.pid_output = p_term + i_term + d_term
                desired_pwm_from_input = max(0.0, min(1.0, metrics.pid_output))
            else:
                desired_pwm_from_input = state["throttle"]
                metrics.pid_integral_error = 0.0
                metrics.pid_previous_error = 0.0
                metrics.pid_output = 0.0
            if metrics.aeb_enabled:
                desired_pwm_from_input = min(
                    desired_pwm_from_input,
                    float(lidar_policy["throttle"]),
                )

    servo_degrees = clamp_servo_degrees(
        state.get("steering_servo_deg", float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0)
    )
    center_degrees = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    if abs(servo_degrees - center_degrees) < float(STEERING_CENTER_SNAP_DEG):
        servo_degrees = center_degrees

    # --- IMU yaw-rate closed loop (mode "off" = no-op passthrough = baseline) ---
    # The open-loop pushback/settle kick has been removed; the IMU loop now owns
    # drift correction. When engaged it REPLACES the open-loop value above, feeding
    # the raw model/joystick command into the PID. Disengaged (off / not moving /
    # lidar override) it leaves the open-loop servo_degrees untouched.
    if yaw_controller is not None and yaw_controller.mode != "off":
        # apply the live-tuned gains (dashboard TUNE page) and reset on any change
        yaw_controller.kp = float(state.get("yaw_kp", 0.0))
        yaw_controller.ki = float(state.get("yaw_ki", 0.0))
        yaw_controller.kd = float(state.get("yaw_kd", 0.0))
        if state.get("yaw_pid_reset"):
            yaw_controller.reset()
            state["yaw_pid_reset"] = False
        raw_command = clamp_servo_degrees(
            state.get("steering_servo_deg", float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0)
        )
        imu_fresh = imu_reader is not None and imu_reader.is_fresh()
        speed_mps = float(getattr(metrics, "smoothed_speed_mph", 0.0)) * 0.44704  # mph -> m/s
        if imu_reader is not None and speed_mps < 0.05:
            imu_reader.note_stationary()   # stopped -> true yaw is 0, learn out the residual bias
        measured_yaw = imu_reader.get_yaw() if imu_fresh else 0.0
        # No IMU correction in REVERSE -- yaw-rate feedback inverts driving backward,
        # so just keep plain open-loop steering (+17D trim) there.
        allow = (
            imu_fresh
            and not state.get("lidar_override_active", False)
            and state.get("gear_mode") != "R"
        )
        pid_servo = yaw_controller.compute(raw_command, measured_yaw, speed_mps, dt, allow=allow)
        if yaw_controller.engaged:
            servo_degrees = clamp_servo_degrees(pid_servo)
        state["yaw_rate_dps"] = measured_yaw
        state["yaw_pid_engaged"] = yaw_controller.engaged
        state["yaw_pid_target_yaw_dps"] = yaw_controller.last_target_yaw
        state["yaw_pid_correction_deg"] = yaw_controller.last_correction

    state["steering_effective_servo_deg"] = servo_degrees
    servo_write_ok = write_steering_servo_safely(state, metrics, hardware, servo_degrees)

    effective_brake = effective_brake_from_input
    desired_pwm_final = desired_pwm_from_input
    current_brake_rate = BRAKE_RATE
    servo_fault_active = not servo_write_ok or time.time() < metrics.servo_fault_until

    aeb_stop_active = metrics.aeb_enabled and state["gear_mode"] != "R" and is_stop_brake_condition(state)
    if aeb_stop_active:
        metrics.stop_warning_start_time = current_time
        effective_brake = True
        effective_brake_force = 1.0
        desired_pwm_final = 0.0
        current_brake_rate = AEB_BRAKE_RATE
        metrics.aeb_triggered = True
        state["throttle"] = 0.0
        if not state["stop_reason"]:
            state["stop_reason"] = "aeb_stop"
        cancel_cruise_control(state, metrics, dashboard_sender)
    else:
        metrics.stop_warning_start_time = 0.0
        metrics.aeb_triggered = False

    if state["gear_mode"] == "R":
        effective_brake_force = max(0.0, min(1.0, float(state.get("manual_brake_force", 0.0))))
        effective_brake = effective_brake_force > 0.1
        desired_pwm_final = desired_pwm_from_input
        current_brake_rate = BRAKE_RATE 

    if servo_fault_active:
        effective_brake = True
        effective_brake_force = 1.0
        desired_pwm_final = 0.0
        current_brake_rate = AEB_BRAKE_RATE

    state["brake"] = effective_brake
    state["brake_force"] = effective_brake_force if effective_brake else 0.0

    full_hard_brake = effective_brake and effective_brake_force >= 0.95
    if full_hard_brake:
        state["current_motor_pwm"] = 0.0
    else:
        if effective_brake:
            rate_of_change = COASTING_RATE + ((current_brake_rate - COASTING_RATE) * effective_brake_force)
        elif abs(desired_pwm_final) > abs(state["current_motor_pwm"]):
            rate_of_change = ACCEL_RATE
        else:
            rate_of_change = COASTING_RATE
        state["current_motor_pwm"] = move_toward(
            state["current_motor_pwm"],
            desired_pwm_final,
            rate_of_change,
            dt,
        )

    pwm_val = max(0.0, min(1.0, abs(state["current_motor_pwm"])))
    left_pwm = max(0.0, min(1.0, pwm_val * LEFT_MOTOR_PWM_SCALE))
    right_pwm = max(0.0, min(1.0, pwm_val * RIGHT_MOTOR_PWM_SCALE))
    hardware.motor_left_fwd.value = 0
    hardware.motor_left_bwd.value = 0
    hardware.motor_right_fwd.value = 0
    hardware.motor_right_bwd.value = 0

    if full_hard_brake:
        # AT8236 brake mode: IN1=1 and IN2=1 clamps both motor outputs low.
        hardware.motor_left_fwd.value = 1.0
        hardware.motor_left_bwd.value = 1.0
        hardware.motor_right_fwd.value = 1.0
        hardware.motor_right_bwd.value = 1.0
    elif state["current_motor_pwm"] > 0.001:
        hardware.motor_right_fwd.value = right_pwm
        hardware.motor_left_bwd.value = left_pwm
    elif state["current_motor_pwm"] < -0.001:
        hardware.motor_right_bwd.value = right_pwm
        hardware.motor_left_fwd.value = left_pwm

    state["dashboard_throttle_percent"] = (
        int(round(absolute_throttle_to_reference(pwm_val) * 100.0))
        if not effective_brake else 0
    )
    state["dashboard_brake_percent"] = int(round(max(0.0, min(1.0, effective_brake_force)) * 100.0)) if effective_brake else 0

    calculate_speed(state, metrics, dt)


def _ship_logs_to_jon(host=None):
    """On exit, rsync the run CSV logs to Jon (/nvme/logs) and delete the ones that
    transferred (rsync --remove-source-files). Fails safe: keeps logs locally if Jon
    is unreachable or there's no passwordless SSH key. Never raises because shutdown
    must not depend on it."""
    configured_host = JETSON_STEERING_HOST if host is None else host
    host = (configured_host or "").strip()
    if not host:
        return
    logs_dir = os.path.dirname(CSV_FILENAME)
    try:
        csvs = sorted(os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.endswith(".csv"))
    except OSError:
        return
    if not csvs:
        return
    try:
        subprocess.run(
            ["rsync", "-a", "--remove-source-files",
             "-e", "ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new",
             *csvs, f"ram@{host}:/nvme/logs/"],
            timeout=30, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        print(f"Shipped {len(csvs)} run log(s) to Jon:/nvme/logs and cleared them locally.")
    except Exception as exc:
        print(f"Log ship to Jon skipped (kept locally): {exc}")


def run(model_choice=None, inference_host=None):
    global photo_status
    shutdown_flag.clear()
    print("RC Car Controller Starting...")
    active_model_choice = str(model_choice or DEFAULT_STEERING_MODEL_CHOICE).strip()
    if active_model_choice not in STEERING_MODEL_CHOICES:
        valid = ", ".join(STEERING_MODEL_CHOICES)
        raise ValueError(
            f"Unknown steering model '{active_model_choice}'. Valid choices: {valid}"
        )
    configured_inference_host = (
        JETSON_STEERING_HOST if inference_host is None else inference_host
    )
    jetson_host = (configured_inference_host or "").strip()
    if not jetson_host:
        raise ValueError(
            "JETSON_STEERING_HOST is required because steering inference is "
            "Jetson Orin Nano-only."
        )
    state = create_state()
    metrics = Metrics()
    csv_file = None
    lidar_parser = None
    webcam_vision = None
    jetson_client = None
    clip_recorder = None
    dashboard_sender = None
    gps_reader = None
    navigation = NavigationManager()
    latest_nav = navigation.update({"fix": False, "sats": 0}, 0.0, 0.0)
    navigation_operator_last = ""
    last_navigation_update = 0.0
    last_dashboard_camera_update = 0.0
    cached_dashboard_camera_pixels = []
    last_dashboard_lidar_update = 0.0
    cached_dashboard_lidar_points = []

    def pulse_detected():
        metrics.pulse_count += 1
        metrics.last_pulse_time = time.time()

    hardware = Hardware(pulse_detected)

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("!!! WARNING: No joystick detected. Please connect a controller. !!!")
        hardware.cleanup()
        pygame.quit()
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Initialized joystick: {joystick.get_name()}")
    print_controls()
    if DEBUG_CONTROLLER_INPUTS:
        print(
            f"Controller axis debug enabled. steer={STEERING_AXIS}, throttle={THROTTLE_AXIS}, brake={BRAKE_AXIS}"
        )

    lidar_parser = LidarParser(SERIAL_PORT, BAUD_RATE)
    lidar_parser.start()
    print("LiDAR reader running in background; runtime will keep retrying if disconnected.")

    gps_reader = GpsReader()
    gps_reader.start()

    # IMU yaw-rate closed-loop steering (MG24 on the GPIO UART). Only opens the
    # serial port when armed; mode "off" leaves steering exactly open-loop.
    yaw_controller = YawController(
        mode=STEERING_YAW_PID_MODE,
        kp=STEERING_YAW_PID_KP, ki=STEERING_YAW_PID_KI, kd=STEERING_YAW_PID_KD,
        curvature_coeffs=STEERING_YAW_PID_CURVATURE_COEFFS,
        lff_deg=STEERING_YAW_PID_LFF_DEG,
        rff_deg=STEERING_YAW_PID_RFF_DEG,
        side_dwell_sec=STEERING_YAW_PID_SIDE_DWELL_SEC,
        ref_speed_mps=STEERING_YAW_PID_REF_SPEED_MPS,
        max_correction_deg=STEERING_YAW_PID_MAX_CORRECTION_DEG,
        straight_band_deg=STEERING_YAW_PID_STRAIGHT_BAND_DEG,
        min_speed_mps=STEERING_YAW_PID_MIN_SPEED_MPS,
        center_deg=float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0,
        actuation_range_deg=float(STEERING_SERVO_ACTUATION_RANGE_DEG),
    )
    imu_reader = None
    if STEERING_YAW_PID_MODE != "off":
        imu_reader = ImuReader(STEERING_YAW_PID_PORT, STEERING_YAW_PID_BAUD,
                               axis=STEERING_YAW_PID_AXIS, sign=STEERING_YAW_PID_YAW_SIGN)
        if imu_reader.start():
            print(f"Yaw-rate PID steering ENABLED (mode={STEERING_YAW_PID_MODE}, "
                  f"LFF={yaw_controller.lff:.1f}/RFF={yaw_controller.rff:.1f}deg) on {STEERING_YAW_PID_PORT}.")
        else:
            print("Yaw-rate PID: IMU failed to start; falling back to OPEN-LOOP steering.")
            yaw_controller.mode = "off"
            imu_reader = None
    else:
        print("Yaw-rate PID steering OFF (open-loop). Set STEERING_YAW_PID_MODE=straight|full to enable.")

    jetson_client = AsyncJetsonSteeringClient(
        jetson_host,
        JETSON_STEERING_PORT,
        history_result_max_age_sec=JETSON_RESULT_MAX_AGE_SEC,
    )
    print(
        "Autonomy inference on Jetson Orin Nano at "
        f"{jetson_host}:{JETSON_STEERING_PORT}. The Raspberry Pi 5 captures "
        "frames and applies fresh returned steering values."
    )

    # Interruption clip recorder: rolling buffer of the exact JPEGs sent to Jon; on every
    # autonomous->manual takeover it saves the 2s-before as a clip (background thread), and
    # ships them to Jon at quit. Only meaningful when Jon is the inference source.
    clip_recorder = InterruptionClipRecorder(
        clip_seconds=INTERRUPTION_CLIP_SECONDS, out_dir=INTERRUPTION_CLIP_DIR,
        enabled=INTERRUPTION_CLIP_ENABLED)

    # Telemetry -> local InfluxDB (non-blocking; disabled if ~/.influxdb.json absent).
    # One run_id per car launch; browse at http://raspberrypi.local:8086.
    drive_run_id = time.strftime("%Y%m%d_%H%M%S")
    dashboard_run_number = _run_number_today()   # R### shown on z2w V1H1
    influx = InfluxLogger(drive_run_id, base_tags={"model": str(active_model_choice), "device": "rpi5"})

    webcam_vision = WebcamVisionProcessor(model_choice=active_model_choice)
    if not webcam_vision.start():
        webcam_vision = None

    csv_file, csv_writer = init_csv_logger(CSV_FILENAME, CSV_HEADERS)
    # The all-time photo count can be expensive with a large dataset. Scan once before
    # entering the real-time loop; successful captures increment this cached value.
    metrics.dashboard_photos_all = count_photos_all()
    if ENABLE_HUB75_DASHBOARD_TELEMETRY:
        dashboard_sender = AsyncDashboardSender(Hub75DashboardSender(
            transport=HUB75_DASHBOARD_TRANSPORT,
            baud_rate=HUB75_DASHBOARD_BAUD_RATE,
            send_interval_sec=HUB75_DASHBOARD_SEND_INTERVAL_SEC,
            serial_port=HUB75_DASHBOARD_SERIAL_PORT,
            udp_host=HUB75_DASHBOARD_HOST,
            udp_port=HUB75_DASHBOARD_UDP_PORT,
        ))
        if HUB75_DASHBOARD_TRANSPORT == "udp":
            print(
                "Hub75 dashboard telemetry transport: UDP "
                f"({HUB75_DASHBOARD_HOST}:{HUB75_DASHBOARD_UDP_PORT})."
            )
            for dashboard_host in [part.strip() for part in HUB75_DASHBOARD_HOST.split(",") if part.strip()]:
                try:
                    resolved = socket.gethostbyname(dashboard_host)
                    print(f"Hub75 dashboard host {dashboard_host} resolves to {resolved}.")
                except OSError as exc:
                    print(f"Hub75 dashboard host '{dashboard_host}' not yet resolvable: {exc}")
        else:
            print(
                "Hub75 dashboard telemetry transport: serial "
                f"({HUB75_DASHBOARD_SERIAL_PORT} @ {HUB75_DASHBOARD_BAUD_RATE})."
            )
        if HUB75_DASHBOARD_SHUTDOWN_ON_EXIT:
            print(
                "Hub75 dashboard linked shutdown enabled "
                f"(idle exit {HUB75_DASHBOARD_IDLE_EXIT_SEC:.1f}s)."
            )
        else:
            print("Hub75 dashboard linked shutdown disabled; receiver stays alive after controller exit.")
    clock = pygame.time.Clock()
    last_update_time = time.time()
    last_log_time = time.time()

    try:
        while not shutdown_flag.is_set():
            current_loop_time = time.time()
            loop_rate_started = state.get("_loop_rate_started")
            if loop_rate_started is None:
                state["_loop_rate_started"] = current_loop_time
                state["_loop_rate_count"] = 0
            else:
                state["_loop_rate_count"] = int(state.get("_loop_rate_count", 0)) + 1
                loop_rate_elapsed = current_loop_time - float(loop_rate_started)
                if loop_rate_elapsed >= 1.0:
                    state["control_loop_hz"] = (
                        float(state["_loop_rate_count"]) / loop_rate_elapsed
                    )
                    state["_loop_rate_started"] = current_loop_time
                    state["_loop_rate_count"] = 0
            try:
                controller_attached = bool(joystick.get_attached())
            except (AttributeError, pygame.error):
                controller_attached = pygame.joystick.get_count() > 0
            if not controller_attached:
                print("Controller disconnected; stopping the car and exiting.", flush=True)
                apply_hard_stop_state(state, "controller_disconnected")
                write_hardware_hard_stop(hardware)
                shutdown_flag.set()
                continue
            dt = current_loop_time - last_update_time
            last_update_time = current_loop_time
            if (
                dt >= CONTROL_LOOP_STALL_WARN_SEC
                and current_loop_time >= state.get("_loop_stall_next_log", 0.0)
            ):
                state["_loop_stall_next_log"] = current_loop_time + 1.0
                print(
                    f"[loop-stall] control loop paused {dt * 1000.0:.0f}ms "
                    f"(auto={int(bool(state['autonomous_mode']))})",
                    flush=True,
                )

            for event in pygame.event.get():
                if DEBUG_CONTROLLER_INPUTS and event.type in (
                    pygame.JOYAXISMOTION,
                    pygame.JOYBUTTONDOWN,
                    pygame.JOYBUTTONUP,
                    pygame.JOYHATMOTION,
                ):
                    print_controller_telemetry(event)

                if event.type == pygame.QUIT:
                    state["event_quit_pressed"] = True
                    shutdown_flag.set()
                elif event.type == pygame.JOYAXISMOTION:
                    if event.axis == STEERING_AXIS:
                        raw_steer_val = event.value
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and abs(raw_steer_val) > STEERING_DEADZONE
                        ):
                            cancel_navigation_route(state, metrics, navigation, "Navigation cancelled by steering input.")
                        if state["autonomous_mode"] and abs(raw_steer_val) > STEERING_DEADZONE:
                            cancel_autonomous_mode(
                                state,
                                metrics,
                                "Autonomous driving cancelled by steering input.",
                                center=False,
                            )
                        if not state["autonomous_mode"]:
                            scaled_steer_val = apply_steering_deadzone(raw_steer_val)
                            center_servo_deg = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
                            if scaled_steer_val == 0.0:
                                state["steer"] = 0.0
                                state["steering_servo_deg"] = center_servo_deg
                            else:
                                state["steer"] = scaled_steer_val
                                state["steering_servo_deg"] = joystick_steer_to_servo_degrees(state["steer"])
                    elif SHARED_TRIGGER_AXIS and event.axis == THROTTLE_AXIS:
                        state["throttle"], state["brake_force"] = split_shared_trigger_axis(event.value)
                        state["manual_brake_force"] = state["brake_force"]
                        state["brake"] = state["brake_force"] > 0.1
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and state["throttle"] > 0.05
                        ):
                            cancel_navigation_route(
                                state,
                                metrics,
                                navigation,
                                "Navigation cancelled by gas pedal.",
                                preserve_manual_throttle=True,
                            )
                        if state["throttle"] > 0.05 and state["autonomous_mode"]:
                            cancel_autonomous_mode(
                                state,
                                metrics,
                                "Autonomous driving cancelled by gas pedal.",
                                preserve_manual_throttle=True,
                            )
                        handle_manual_throttle_override(state, metrics, dashboard_sender)
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and state["brake"]
                        ):
                            cancel_navigation_route(
                                state,
                                metrics,
                                navigation,
                                "Navigation cancelled by brake.",
                                preserve_manual_brake=True,
                            )
                        if state["brake"] and state["autonomous_mode"]:
                            cancel_autonomous_mode(
                                state,
                                metrics,
                                "Autonomous driving cancelled by brake.",
                                preserve_manual_brake=True,
                            )
                    elif event.axis == THROTTLE_AXIS:
                        state["throttle"] = manual_throttle_pwm(event.value)
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and state["throttle"] > 0.05
                        ):
                            cancel_navigation_route(
                                state,
                                metrics,
                                navigation,
                                "Navigation cancelled by gas pedal.",
                                preserve_manual_throttle=True,
                            )
                        if state["throttle"] > 0.05 and state["autonomous_mode"]:
                            cancel_autonomous_mode(
                                state,
                                metrics,
                                "Autonomous driving cancelled by gas pedal.",
                                preserve_manual_throttle=True,
                            )
                        handle_manual_throttle_override(state, metrics, dashboard_sender)
                    elif not SHARED_TRIGGER_AXIS and event.axis == BRAKE_AXIS:
                        state["brake_force"] = normalize_trigger_axis(event.value)
                        state["manual_brake_force"] = state["brake_force"]
                        state["brake"] = state["brake_force"] > 0.1
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and state["brake"]
                        ):
                            cancel_navigation_route(
                                state,
                                metrics,
                                navigation,
                                "Navigation cancelled by brake.",
                                preserve_manual_brake=True,
                            )
                        if state["brake"] and state["autonomous_mode"]:
                            cancel_autonomous_mode(
                                state,
                                metrics,
                                "Autonomous driving cancelled by brake.",
                                preserve_manual_brake=True,
                            )
                    elif event.axis == DASHBOARD_PAGE_AXIS:
                        state["dashboard_page_axis_value"] = event.value
                    elif event.axis == DASHBOARD_PAGE_HORIZONTAL_AXIS:
                        state["dashboard_page_horizontal_axis_value"] = event.value
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button in CRUISE_TOGGLE_BUTTONS:
                        try_toggle_cruise_control(state, metrics, dashboard_sender)
                    elif event.button == HAZARD_BUTTON:
                        toggle_turn_signal(state, metrics, "hazard")
                    elif event.button == SHIFT_DOWN_BUTTON:
                        shift_gear(
                            state,
                            metrics,
                            -1,
                            navigation=navigation,
                            dashboard_sender=dashboard_sender,
                        )
                    elif event.button == SHIFT_UP_BUTTON:
                        shift_gear(
                            state,
                            metrics,
                            1,
                            navigation=navigation,
                            dashboard_sender=dashboard_sender,
                        )
                    elif event.button == AUTONOMY_TOGGLE_BUTTON:
                        if not state["autonomous_mode"] and webcam_vision is None:
                            print("Autonomous Driving not enabled: steering autonomy model is unavailable.")
                            continue
                        if not state["autonomous_mode"]:
                            if engage_autonomous_mode(
                                state,
                                metrics,
                                dashboard_sender,
                                jetson_client,
                            ):
                                print("Autonomous Driving ENABLED.")
                        else:
                            cancel_autonomous_mode(
                                state,
                                metrics,
                                "Autonomous Driving DISABLED.",
                                cause="a",
                            )
                    elif event.button == AEB_TOGGLE_BUTTON:
                        metrics.aeb_enabled = not metrics.aeb_enabled
                        print(f"Automatic Emergency Braking (AEB): {'ENABLED' if metrics.aeb_enabled else 'DISABLED'}")
                        queue_aeb_toggle_notification(dashboard_sender, metrics.aeb_enabled)
                    elif event.button == PHOTO_BUTTON:
                        take_photo(webcam_vision, state, metrics)
                    elif event.button == AUTO_PHOTO_BUTTON:
                        toggle_auto_photo(state, metrics, dashboard_sender)
                    elif event.button == NAV_SELECT_BUTTON:
                        if int(state.get("dashboard_page", 1)) != 5:
                            set_dashboard_page(state, 5)
                            metrics.dashboard_page_transition = "back"
                            continue
                        if navigation.active:
                            cancel_navigation_route(state, metrics, navigation, "Navigation cancelled by user.")
                            print("Navigation cancelled.")
                        else:
                            operator = navigation.advance()
                            if operator:
                                navigation_operator_last = str(operator).upper()
                            if operator == "AUTO" and webcam_vision is not None:
                                if engage_autonomous_mode(
                                    state,
                                    metrics,
                                    dashboard_sender,
                                    jetson_client,
                                ):
                                    print("Navigation route started: model/autonomous segment.")
                                else:
                                    navigation.active = False
                            elif operator == "AUTO":
                                cancel_autonomous_mode(state, metrics, "Navigation route requested AI segment, but camera model is unavailable.")
                            elif operator == "MNUL":
                                cancel_autonomous_mode(state, metrics, "Navigation route started: human/manual segment.")
                    elif event.button == QUIT_BUTTON:
                        state["event_quit_pressed"] = True
                        shutdown_flag.set()
                elif event.type == pygame.JOYHATMOTION:
                    hat_x, hat_y = event.value
                    current_dashboard_page = int(state.get("dashboard_page", 1))
                    on_tuning_page = current_dashboard_page == STEERING_TRIM_DASHBOARD_PAGE
                    # Track hat_x on the tuning page so hold-to-repeat can keep
                    # adjusting the selected value; clear it elsewhere/on release.
                    state["dpad_x_value"] = int(hat_x) if on_tuning_page else 0
                    if hat_x:
                        if on_tuning_page:
                            adjust_tuning_value(state, hardware, int(hat_x))
                        elif current_dashboard_page == 5 and not navigation.active:
                            navigation.move_cursor(int(hat_x))
                        elif hat_x == -1:
                            toggle_turn_signal(state, metrics, "left")
                        elif hat_x == 1:
                            toggle_turn_signal(state, metrics, "right")
                    if on_tuning_page and hat_y:
                        # Up/down selects the tuning row; no model cycling here.
                        cycle_tuning_row(state, int(hat_y))
                    state["dpad_y_value"] = 0 if on_tuning_page else int(hat_y)
                    if hat_y and not on_tuning_page:
                        active_model_choice = handle_dpad_y_action(
                            int(hat_y),
                            state,
                            metrics,
                            navigation,
                            webcam_vision,
                            active_model_choice,
                            dashboard_sender,
                            repeated=False,
                        )

            if shutdown_flag.is_set():
                apply_hard_stop_state(state, "operator_quit")
                write_hardware_hard_stop(hardware)
                continue

            # Hold d-pad left/right on the TUNE page -> keep adjusting the value.
            if int(state.get("dashboard_page", 1)) == STEERING_TRIM_DASHBOARD_PAGE:
                tune_x_repeat = dpad_x_repeat_direction(
                    state, metrics, TUNE_ADJUST_REPEAT_START_SEC, TUNE_ADJUST_REPEAT_INTERVAL_SEC
                )
                if tune_x_repeat:
                    adjust_tuning_value(state, hardware, tune_x_repeat)
            else:
                state["dpad_x_value"] = 0

            nav_letter_repeat = (
                int(state.get("dashboard_page", 1)) == 5
                and not navigation.active
            )
            dpad_repeat_direction = dpad_y_repeat_direction(
                state,
                metrics,
                NAV_LETTER_REPEAT_START_SEC if nav_letter_repeat else DPAD_SCROLL_REPEAT_START_SEC,
                NAV_LETTER_REPEAT_INTERVAL_SEC if nav_letter_repeat else DPAD_SCROLL_REPEAT_INTERVAL_SEC,
            )
            if dpad_repeat_direction:
                active_model_choice = handle_dpad_y_action(
                    dpad_repeat_direction,
                    state,
                    metrics,
                    navigation,
                    webcam_vision,
                    active_model_choice,
                    dashboard_sender,
                    repeated=True,
                )

            update_auto_photo(state, metrics, webcam_vision, dashboard_sender)

            if jetson_client is not None and not state["autonomous_mode"]:
                # Series 4 PC/PCF starts from the operator's actual last three
                # steering targets instead of an artificial centered history.
                jetson_client.observe_manual_steering(state["steering_servo_deg"])

            latest_scan = []
            if lidar_parser:
                try:
                    if hasattr(lidar_parser, "get_latest_scan_state"):
                        latest_scan, state["lidar_scan_fresh"] = (
                            lidar_parser.get_latest_scan_state()
                        )
                    else:
                        latest_scan = lidar_parser.get_latest_scan()
                        state["lidar_scan_fresh"] = lidar_parser.is_scan_fresh()
                except Exception as exc:
                    print(f"LiDAR latest scan unavailable; ignoring LiDAR this loop: {exc}")
                    latest_scan = []
                    state["lidar_scan_fresh"] = False
                obstacle_stop_threshold_m, obstacle_warn_threshold_m, hard_stop_threshold_m = (
                    get_speed_scaled_lidar_thresholds(metrics.smoothed_speed_mph)
                )
                direction, min_front, min_left, min_right, min_back = determine_turn_direction(
                    latest_scan,
                    front_clear_threshold_m=0.8,
                    side_clear_threshold_m=0.8,
                    reverse_clear_threshold_m=0.5,
                    critical_front_stop_threshold_m=0.3,
                    obstacle_stop_threshold_m=obstacle_stop_threshold_m,
                    obstacle_warn_threshold_m=obstacle_warn_threshold_m,
                )
                state["direction_arrow"] = direction
                state["lidar_front_dist"] = min_front
                state["lidar_left_dist"] = min_left
                state["lidar_right_dist"] = min_right
                state["lidar_back_dist"] = min_back
                state["lidar_stop_threshold_m"] = hard_stop_threshold_m
                state["lidar_warn_threshold_m"] = obstacle_warn_threshold_m
                state["num_lidar_points"] = len(latest_scan)
            else:
                state["lidar_scan_fresh"] = False
                state["direction_arrow"] = " "
                state["lidar_front_dist"] = MAX_LIDAR_RANGE_M
                state["lidar_left_dist"] = MAX_LIDAR_RANGE_M
                state["lidar_right_dist"] = MAX_LIDAR_RANGE_M
                state["lidar_back_dist"] = MAX_LIDAR_RANGE_M
                state["lidar_stop_threshold_m"] = FORWARD_OBSTACLE_STOP_DISTANCE_M
                state["lidar_warn_threshold_m"] = OBSTACLE_WARN_THRESHOLD_M
                state["num_lidar_points"] = 0

            update_gpio(state, metrics, hardware, webcam_vision, latest_scan, dt, dashboard_sender,
                        yaw_controller=yaw_controller, imu_reader=imu_reader,
                        jetson_client=jetson_client, active_model_choice=active_model_choice)
            # buffer the exact frame just sent to Jon; saves a clip on the takeover edge
            if clip_recorder is not None:
                clip_recorder.update(bool(state["autonomous_mode"]),
                                     getattr(jetson_client, "last_jpeg", None))
            if influx.enabled:
                _tel_fields, _tel_tags = _drive_telemetry(state, metrics, jetson_client)
                influx.log(_tel_fields, tags=_tel_tags)
            update_turn_signal_blink(state, metrics)
            update_dashboard_page_selection(state, metrics)
            if current_loop_time - metrics.dashboard_cpu_temp_last_sample_time >= 1.0:
                metrics.dashboard_cpu_temp_c = get_cpu_temp()
                metrics.dashboard_cpu_temp_last_sample_time = current_loop_time
                # The asynchronous client refreshes these fields in its worker. Reading
                # cached values here cannot wait on a powered-off or unreachable Jon.
                if jetson_client is not None and not state["autonomous_mode"]:
                    state["jon_cpu_temp_c"] = jetson_client.jon_cpu_temp_c
                    state["jon_gpu_temp_c"] = jetson_client.jon_gpu_temp_c
                    state["infer_fps"] = jetson_client.infer_fps
            if current_loop_time - last_navigation_update >= NAVIGATION_UPDATE_INTERVAL_SEC:
                last_navigation_update = current_loop_time
                gps_state = gps_reader.get_state() if gps_reader is not None else {"fix": False, "sats": 0}
                latest_nav = navigation.update(
                    gps_state,
                    metrics.total_distance_cm / 100.0,
                    metrics.smoothed_speed_mph * 0.44704,
                )
                navigation.set_start_from_gps(latest_nav.get("nearest_node", ""))
                if not latest_nav.get("active"):
                    if navigation_operator_last == "AUTO" and latest_nav.get("arrived_visible"):
                        cancel_autonomous_mode(state, metrics, "Navigation arrived at destination.")
                    navigation_operator_last = ""
                else:
                    nav_operator = str(latest_nav.get("operator", "MNUL")).upper()
                    if nav_operator != navigation_operator_last:
                        if nav_operator == "AUTO" and webcam_vision is not None:
                            if engage_autonomous_mode(
                                state,
                                metrics,
                                dashboard_sender,
                                jetson_client,
                            ):
                                print("Navigation operator: AI/model segment.")
                            else:
                                navigation.active = False
                        elif nav_operator == "AUTO":
                            cancel_autonomous_mode(state, metrics, "Navigation operator requested AI, but camera model is unavailable.")
                        elif nav_operator == "MNUL":
                            cancel_autonomous_mode(state, metrics, "Navigation operator: human/manual segment.")
                        navigation_operator_last = nav_operator
            # Motion-based page swap: tune on v1h3 (TUNE) while stopped, show v1h4
            # (YAW telemetry) while driving. Only toggles between these two pages,
            # so it never yanks you off any other page.
            speed_now_mph = float(getattr(metrics, "smoothed_speed_mph", 0.0))
            current_page_now = int(state.get("dashboard_page", 1))
            if speed_now_mph > 0.01 and current_page_now == STEERING_TRIM_DASHBOARD_PAGE:
                set_dashboard_page(state, YAW_DASHBOARD_PAGE)               # v1h3 -> v1h4
                metrics.dashboard_page_transition = "right"
            elif speed_now_mph <= 0.0 and current_page_now == YAW_DASHBOARD_PAGE:
                set_dashboard_page(state, STEERING_TRIM_DASHBOARD_PAGE)     # v1h4 -> v1h3
                metrics.dashboard_page_transition = "left"

            camera_pixels = []
            if state["dashboard_page"] == 11 and webcam_vision is not None:
                if current_loop_time - last_dashboard_camera_update >= DASHBOARD_CAMERA_UPDATE_INTERVAL_SEC:
                    last_dashboard_camera_update = current_loop_time
                    cached_dashboard_camera_pixels = webcam_vision.get_dashboard_camera_pixels()
                camera_pixels = cached_dashboard_camera_pixels
            else:
                cached_dashboard_camera_pixels = []
            lidar_dashboard_points = []
            if state["dashboard_page"] == LIDAR_DASHBOARD_PAGE:
                if current_loop_time - last_dashboard_lidar_update >= DASHBOARD_LIDAR_UPDATE_INTERVAL_SEC:
                    last_dashboard_lidar_update = current_loop_time
                    cached_dashboard_lidar_points = format_lidar_dashboard_points(latest_scan)
                lidar_dashboard_points = cached_dashboard_lidar_points
            else:
                cached_dashboard_lidar_points = []
            if dashboard_sender is not None:
                dashboard_sent = dashboard_sender.send(
                    metrics.smoothed_speed_mph,
                    state["gear_mode"],
                    state["turn_signal_left_visible"],
                    state["turn_signal_right_visible"],
                    get_dashboard_alert(state),
                    state["dashboard_brightness_percent"],
                    dashboard_page=state["dashboard_page"],
                    dashboard_page_transition=metrics.dashboard_page_transition,
                    servo_deg=state.get("steering_effective_servo_deg", state["steering_servo_deg"]),
                    throttle_percent=state["dashboard_throttle_percent"],
                    brake_percent=state["dashboard_brake_percent"],
                    drive_mode=get_dashboard_drive_mode(state),
                    lidar_points=lidar_dashboard_points,
                    lidar_point_count=state["num_lidar_points"],
                    lidar_lane_occupancy=state.get("lidar_lane_occupancy", ""),
                    lidar_emergency_lane_occupancy=state.get("lidar_emergency_lane_occupancy", ""),
                    lidar_lane_action=state.get("lidar_lane_action", "normal"),
                    model_choice=active_model_choice,
                    camera_confidence_percent=int(round(max(0.0, min(1.0, state["camera_confidence"])) * 100.0)),
                    cpu_temp_c=metrics.dashboard_cpu_temp_c,
                    jon_cpu_temp_c=state.get("jon_cpu_temp_c", 0.0),
                    jon_gpu_temp_c=state.get("jon_gpu_temp_c", 0.0),
                    infer_fps=state.get("infer_fps", 0.0),
                    camera_pixels=camera_pixels,
                    photos_run=metrics.dashboard_photos_run,
                    photos_all=metrics.dashboard_photos_all,
                    camera_fps=webcam_vision.camera_fps if webcam_vision is not None else 0.0,
                    system_status=get_system_status(state),
                    nav_status=latest_nav,
                    steering_trim_delta_deg=state["steering_trim_delta_deg"],
                    steering_trim_total_deg=state["steering_trim_total_deg"],
                    steering_center_offset=state["steering_center_offset"],
                    tune_selected_row=state.get("tune_selected_row", 0),
                    yaw_kp=state.get("yaw_kp", 0.0),
                    yaw_ki=state.get("yaw_ki", 0.0),
                    yaw_kd=state.get("yaw_kd", 0.0),
                    yaw_rate_dps=state.get("yaw_rate_dps", 0.0),
                    yaw_pid_correction_deg=state.get("yaw_pid_correction_deg", 0.0),
                    yaw_pid_engaged=state.get("yaw_pid_engaged", False),
                    steering_cmd_deg=state.get("steering_servo_deg", 90.0),
                    autonomy_cause_code=metrics.auto_last_cause_code,
                    autonomy_distance_m=metrics.auto_distance_cm / 100.0,
                    autonomy_interv_per_km=(metrics.auto_intervention_count /
                        max(0.001, metrics.auto_distance_cm / 100.0 / 1000.0)),
                    autonomy_avg_uptime_s=metrics.auto_time_s / max(1, metrics.auto_segments),
                    run_number=dashboard_run_number,
                )
                if dashboard_sent:
                    metrics.dashboard_page_transition = ""
                    if photo_status in ("SAVE", "ERR"):
                        photo_status = "GOOD"

            if current_loop_time - last_log_time >= LOG_INTERVAL_SEC:
                if dashboard_sender is not None:
                    state["dashboard_payload_json"] = dashboard_sender.get_last_payload_json()
                log_data_to_csv(
                    csv_file,
                    csv_writer,
                    state,
                    metrics,
                    psutil.cpu_percent(interval=None),
                    psutil.virtual_memory().percent,
                    metrics.dashboard_cpu_temp_c,
                )
                last_log_time = current_loop_time

            clock.tick(CONTROL_LOOP_HZ)

    except KeyboardInterrupt:
        state["event_quit_pressed"] = True
    finally:
        shutdown_flag.set()
        apply_hard_stop_state(state, state.get("stop_reason") or "runtime_shutdown")
        write_hardware_hard_stop(hardware)
        if dashboard_sender is not None:
            state["dashboard_payload_json"] = dashboard_sender.get_last_payload_json()
        if state["event_quit_pressed"] and csv_writer:
            log_data_to_csv(
                csv_file,
                csv_writer,
                state,
                metrics,
                psutil.cpu_percent(interval=None),
                psutil.virtual_memory().percent,
                get_cpu_temp(),
            )
        dashboard_shutdown_sent = False
        if dashboard_sender and HUB75_DASHBOARD_SHUTDOWN_ON_EXIT:
            dashboard_sender.send_shutdown()
            dashboard_shutdown_sent = True
        if lidar_parser:
            lidar_parser.stop()
        if gps_reader:
            gps_reader.stop()
        if imu_reader:
            imu_reader.stop()
        finalize_photo_run(current_photo_run_dir)   # build <run>.json from the CSV on exit
        if webcam_vision:
            webcam_vision.stop()
        if jetson_client:
            jetson_client.close()
        if dashboard_sender:
            if HUB75_DASHBOARD_SHUTDOWN_ON_EXIT and not dashboard_shutdown_sent:
                dashboard_sender.send_shutdown()
            dashboard_sender.close()
        hardware.cleanup()
        if csv_file:
            csv_file.close()
        _ship_logs_to_jon(jetson_host)
        if clip_recorder is not None:
            clip_recorder.ship_to_jon(jetson_host)
        influx.close()               # drain remaining telemetry to InfluxDB
        cleanup_photo_run_dir()
        pygame.quit()
