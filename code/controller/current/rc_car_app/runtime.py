#!/usr/bin/python3
import datetime
import json
import os
import random
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
    AUTONOMOUS_LIDAR_OVERRIDE_PWM,
    AUTONOMOUS_TURN_PWM,
    AUTO_PHOTO_BUTTON,
    AUTO_PHOTO_MAX_INTERVAL_SEC,
    AUTO_PHOTO_MIN_INTERVAL_SEC,
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
    LIDAR_OVERRIDE_EMERGENCY_STOP_M,
    LIDAR_OVERRIDE_SIDE_CLEARANCE_M,
    LIDAR_OVERRIDE_STEER_DEG,
    MAX_TARGET_HEADING_DEG,
    PHOTO_BUTTON,
    PHOTO_DIR,
    PULSES_PER_REVOLUTION,
    SPEED_SMOOTHING_ALPHA,
    STEERING_AXIS,
    STEERING_CENTER_SETTLE_LOW_RELEASE_DURATION_SEC,
    STEERING_CENTER_SETTLE_LOW_RELEASE_TARGET_DEG,
    STEERING_CENTER_SETTLE_RELEASE_MIN_DEG,
    STEERING_SERVO_ACTUATION_RANGE_DEG,
    STEERING_SERVO_CENTER_OFFSET,
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
from .vision import DEFAULT_STEERING_MODEL_CHOICE, STEERING_MODEL_CHOICES, WebcamVisionProcessor

shutdown_flag = threading.Event()
current_photo_run_dir: Path | None = None
photo_status: str = "GOOD"
DASHBOARD_PHOTO_STATS_INTERVAL_SEC = 5.0


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
                with self.sender_lock:
                    sent = self.sender.send(*args, **kwargs)
                    payload_json = self.sender.last_payload_json
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
        f"  Button {AUTO_PHOTO_BUTTON} (Menu): toggle auto photo "
        f"({AUTO_PHOTO_MIN_INTERVAL_SEC}-{AUTO_PHOTO_MAX_INTERVAL_SEC}s random interval)"
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
    if raw_value < -0.95:
        return 0.0
    if raw_value <= 1.0:
        return max(0.0, min(1.0, (raw_value + 1.0) / 2.0))
    return max(0.0, min(1.0, raw_value))


def split_shared_trigger_axis(raw_value):
    throttle = max(0.0, raw_value)
    brake_force = max(0.0, -raw_value)
    return throttle, brake_force


def clamp_servo_degrees(value: float) -> float:
    return max(0.0, min(float(STEERING_SERVO_ACTUATION_RANGE_DEG), float(value)))


def steering_degrees_to_normalized(servo_degrees: float) -> float:
    center_degrees = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    if center_degrees <= 0.0:
        return 0.0
    return max(-1.0, min(1.0, (float(servo_degrees) - center_degrees) / center_degrees))


def apply_steering_deadzone(raw_value: float) -> float:
    clamped = max(-1.0, min(1.0, float(raw_value)))
    deadzone = max(0.0, min(0.95, float(STEERING_DEADZONE)))
    magnitude = abs(clamped)
    if magnitude <= deadzone:
        return 0.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    return scaled if clamped > 0.0 else -scaled


def joystick_steer_to_servo_degrees(normalized_value: float) -> float:
    clamped = max(-1.0, min(1.0, float(normalized_value)))
    return ((clamped + 1.0) / 2.0) * float(STEERING_SERVO_ACTUATION_RANGE_DEG)


def center_steering(state):
    state["steer"] = 0.0
    state["steering_servo_deg"] = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    state["steering_center_settle_until"] = 0.0


def start_manual_steering_center_settle(state, previous_servo_degrees: float) -> None:
    center_degrees = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    previous_delta = float(previous_servo_degrees) - center_degrees
    if previous_delta >= -float(STEERING_CENTER_SETTLE_RELEASE_MIN_DEG):
        return
    settle_target_degrees = float(STEERING_CENTER_SETTLE_LOW_RELEASE_TARGET_DEG)
    settle_duration_sec = float(STEERING_CENTER_SETTLE_LOW_RELEASE_DURATION_SEC)
    if settle_duration_sec <= 0.0:
        state["steering_center_settle_until"] = 0.0
        return
    state["steering_center_settle_deg"] = clamp_servo_degrees(settle_target_degrees)
    state["steering_center_settle_until"] = time.time() + settle_duration_sec


def get_dashboard_drive_mode(state) -> str:
    if state.get("lidar_override_active"):
        return "LDR"
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


def pick_lidar_override_side(state, lidar_scan) -> str | None:
    left_clear = float(state.get("lidar_left_dist", 0.0)) >= LIDAR_OVERRIDE_SIDE_CLEARANCE_M
    right_clear = float(state.get("lidar_right_dist", 0.0)) >= LIDAR_OVERRIDE_SIDE_CLEARANCE_M
    if not left_clear and not right_clear:
        return None

    warn_distance = float(state.get("lidar_warn_threshold_m", OBSTACLE_WARN_THRESHOLD_M))
    left_obstacle_score = 0.0
    right_obstacle_score = 0.0
    for point in lidar_scan or []:
        if (
            not getattr(point, "is_valid", False)
            or getattr(point, "distance_mm", 0) <= 0
            or getattr(point, "confidence", 0) < 150
        ):
            continue
        angle = float(getattr(point, "angle_deg", 0.0))
        if angle > 180.0:
            angle -= 360.0
        if angle < -75.0 or angle > 75.0:
            continue
        distance_m = float(getattr(point, "distance_mm", 0.0)) / 1000.0
        if distance_m > warn_distance:
            continue
        score = max(0.0, warn_distance - distance_m) + 0.05
        if angle < -5.0:
            left_obstacle_score += score
        elif angle > 5.0:
            right_obstacle_score += score
        else:
            left_obstacle_score += score * 0.5
            right_obstacle_score += score * 0.5

    if left_obstacle_score > right_obstacle_score * 1.15:
        return "right" if right_clear else None
    if right_obstacle_score > left_obstacle_score * 1.15:
        return "left" if left_clear else None
    if right_clear and not left_clear:
        return "right"
    if left_clear and not right_clear:
        return "left"
    return "right" if float(state.get("lidar_right_dist", 0.0)) >= float(state.get("lidar_left_dist", 0.0)) else "left"


DASHBOARD_PAGE_COORDS = {
    1: (1, 1),
    2: (1, 2),
    3: (2, 1),
    4: (2, 2),
    5: (3, 1),
    6: (3, 2),
    7: (4, 1),
    8: (4, 2),
    9: (5, 1),
    10: (5, 2),
    11: (6, 1),
    12: (2, 3),
    13: (6, 2),
    14: (6, 3),
}
DASHBOARD_COORD_PAGES = {coords: page for page, coords in DASHBOARD_PAGE_COORDS.items()}
DASHBOARD_VERTICAL_PAGE_COUNT = 6
STEERING_TRIM_DASHBOARD_PAGE = 13
LIDAR_DASHBOARD_PAGE = 14
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
        active_model_choice = cycle_steering_model(webcam_vision, active_model_choice, 1 if direction == 1 else -1)
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


def cancel_navigation_route(state, metrics, navigation, reason: str) -> None:
    if not navigation.active:
        return
    navigation.active = False
    navigation.reset_entry()
    cancel_autonomous_mode(state, metrics, reason)


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


def cancel_autonomous_mode(state, metrics, reason: str, center: bool = True):
    if reason:
        print(reason)
    state["autonomous_mode"] = False
    state["throttle"] = 0.0
    state["brake"] = False
    state["brake_force"] = 0.0
    state["manual_brake_force"] = 0.0
    state["current_motor_pwm"] = 0.0
    state["dashboard_throttle_percent"] = 0
    state["dashboard_brake_percent"] = 0
    if center:
        center_steering(state)
    metrics.driveway_cut_candidate_since = 0.0
    metrics.pid_integral_error = 0.0
    metrics.pid_previous_error = 0.0
    metrics.pid_output = 0.0


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
    if stop_reason in ("blocked_path", "driveway_cut"):
        return "STOP"
    if stop_reason == "recovering_warn":
        return "WARN"
    return ""


def get_system_status(state, model_frame_is_stale: bool = False) -> str:
    return photo_status


def count_photos_run() -> int:
    if current_photo_run_dir is None or not current_photo_run_dir.exists():
        return 0
    return sum(1 for f in current_photo_run_dir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png"))


def photo_run_stats() -> dict[str, int]:
    stats = {"left": 0, "center": 0, "right": 0, "throttle_below_50": 0}
    if current_photo_run_dir is None or not current_photo_run_dir.exists():
        return stats
    label_path = current_photo_run_dir / f"{current_photo_run_dir.name}.json"
    if not label_path.exists():
        return stats
    try:
        labels = json.loads(label_path.read_text())
    except Exception as exc:
        print(f"Failed to read photo run stats {label_path}: {exc}")
        return stats
    if not isinstance(labels, dict):
        return stats
    for label in labels.values():
        if not isinstance(label, dict):
            continue
        try:
            steering = float(label.get("steering"))
        except (TypeError, ValueError):
            steering = None
        if steering is not None:
            if steering < 85.0:
                stats["left"] += 1
            elif steering > 95.0:
                stats["right"] += 1
            else:
                stats["center"] += 1
        try:
            throttle = float(label.get("throttle"))
        except (TypeError, ValueError):
            throttle = None
        if throttle is not None and throttle < 0.50:
            stats["throttle_below_50"] += 1
    return stats


def count_photos_all() -> int:
    base = Path(PHOTO_DIR)
    if not base.exists():
        return 0
    return sum(1 for f in base.rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png"))


def update_dashboard_photo_stats(metrics, now: float | None = None, force: bool = False) -> None:
    current_time = time.time() if now is None else now
    if not force and current_time - metrics.dashboard_photo_stats_last_sample_time < DASHBOARD_PHOTO_STATS_INTERVAL_SEC:
        return
    metrics.dashboard_photos_run = count_photos_run()
    metrics.dashboard_photos_all = count_photos_all()
    metrics.dashboard_photo_run_stats = photo_run_stats()
    metrics.dashboard_photo_stats_last_sample_time = current_time


def is_stop_brake_condition(state) -> bool:
    if state.get("lidar_override_active"):
        return False
    return (
        state["direction_arrow"] in ("STOP_WARNING", "BLOCKED")
        or float(state.get("lidar_front_dist", MAX_LIDAR_RANGE_M))
        < float(state.get("lidar_stop_threshold_m", FORWARD_OBSTACLE_STOP_DISTANCE_M))
        or state.get("stop_reason") in ("blocked_path", "aeb_stop")
    )


def get_cpu_temp():
    try:
        result = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True, check=True)
        temp_str = result.stdout.strip()
        return float(temp_str.split("=")[1].split("'")[0])
    except Exception:
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
    if state is None:
        return 0.0
    try:
        motor_pwm = float(state.get("current_motor_pwm", state.get("throttle", 0.0)))
    except (TypeError, ValueError):
        motor_pwm = 0.0
    return max(0.0, min(1.0, motor_pwm))


def save_photo_run_label(run_dir: Path, photo_name: str, servo_degrees: float, throttle: float) -> None:
    label_path = run_dir / f"{run_dir.name}.json"
    try:
        if label_path.exists():
            labels = json.loads(label_path.read_text())
            if not isinstance(labels, dict):
                labels = {}
        else:
            labels = {}
        labels[photo_name] = {
            "steering": int(round(clamp_servo_degrees(servo_degrees))),
            "throttle": round(max(0.0, min(1.0, float(throttle))), 4),
        }
        label_path.write_text(json.dumps(labels, indent=2) + "\n")
    except Exception as exc:
        print(f"Failed to save photo steering/throttle label {label_path}: {exc}")


def take_photo(webcam_vision=None, state=None):
    global current_photo_run_dir, photo_status
    if current_photo_run_dir is None:
        current_photo_run_dir = create_photo_run_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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
        success, message = webcam_vision.save_current_frame(filename)
        if success:
            servo_degrees = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
            if state is not None:
                servo_degrees = float(state.get("steering_servo_deg", servo_degrees))
            save_photo_run_label(current_photo_run_dir, photo_name, servo_degrees, current_forward_throttle_label(state))
            photo_status = "SAVE"
            print(f"Photo captured from live Pi camera stream: {message}")
            return True
        photo_status = "ERR"
        print(f"Pi camera stream photo capture unavailable: {message}")
    else:
        photo_status = "ERR"
        print("Pi camera stream photo capture unavailable: no active camera stream")
    return False


def random_auto_photo_delay_sec() -> int:
    min_interval = int(AUTO_PHOTO_MIN_INTERVAL_SEC)
    max_interval = int(AUTO_PHOTO_MAX_INTERVAL_SEC)
    if max_interval < min_interval:
        min_interval, max_interval = max_interval, min_interval
    return random.randint(min_interval, max_interval)


def schedule_next_auto_photo(metrics, now: float | None = None) -> int:
    delay_sec = random_auto_photo_delay_sec()
    metrics.auto_photo_next_time = (time.time() if now is None else now) + delay_sec
    return delay_sec


def toggle_auto_photo(state, metrics, dashboard_sender=None):
    state["auto_photo_enabled"] = not bool(state.get("auto_photo_enabled", False))
    if state["auto_photo_enabled"]:
        delay_sec = schedule_next_auto_photo(metrics)
        print(f"Auto photo ENABLED. First capture in {delay_sec}s.")
    else:
        metrics.auto_photo_next_time = 0.0
        print("Auto photo DISABLED.")
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
    take_photo(webcam_vision, state)
    delay_sec = schedule_next_auto_photo(metrics, now)
    print(f"Next auto photo in {delay_sec}s.")


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


def apply_autonomous_controls(state, metrics, hardware, webcam_vision, lidar_scan):
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
    if webcam_vision:
        camera_analysis, last_frame_time = webcam_vision.get_analysis()
        model_frame_is_stale = time.time() - last_frame_time > 0.75
        if model_frame_is_stale:
            camera_analysis["heading_bias"] = 0.0
            camera_analysis["confidence"] = 0.0
            camera_analysis["left_edge_found"] = False
            camera_analysis["right_edge_found"] = False
            camera_analysis["corridor_width_px"] = 0.0
            camera_analysis["method"] = "stale_model_frame"

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

    lidar_front_dist = float(state.get("lidar_front_dist", MAX_LIDAR_RANGE_M))
    if state["direction_arrow"] == "BLOCKED" or lidar_front_dist < LIDAR_OVERRIDE_EMERGENCY_STOP_M:
        apply_hard_stop_state(state, "blocked_path")
        return 0.0, True

    if state["direction_arrow"] in ("STOP_WARNING", "WARN_WARNING") or lidar_front_dist < state["lidar_warn_threshold_m"]:
        override_side = pick_lidar_override_side(state, lidar_scan)
        if override_side is None:
            apply_hard_stop_state(state, "blocked_path")
            return 0.0, True
        steer_sign = 1.0 if override_side == "right" else -1.0
        lidar_steer_deg = (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0) + (steer_sign * LIDAR_OVERRIDE_STEER_DEG)
        state["steering_servo_deg"] = clamp_servo_degrees(lidar_steer_deg)
        state["steer"] = steering_degrees_to_normalized(state["steering_servo_deg"])
        state["target_heading_deg"] = state["steer"] * MAX_TARGET_HEADING_DEG
        state["lidar_override_active"] = True
        state["lidar_override_side"] = override_side
        state["stop_reason"] = "lidar_override"
        return AUTONOMOUS_LIDAR_OVERRIDE_PWM, False

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

    if abs(target_heading_deg) > 15.0:
        return AUTONOMOUS_TURN_PWM, False
    return AUTONOMOUS_CRUISE_PWM, False


def update_gpio(state, metrics, hardware, webcam_vision, lidar_scan, dt, dashboard_sender=None):
    current_time = time.time()
    desired_pwm_from_input = 0.0
    effective_brake_from_input = state["brake"]
    effective_brake_force = max(0.0, min(1.0, float(state.get("brake_force", 0.0))))

    if state["autonomous_mode"]:
        desired_pwm_from_input, effective_brake_from_input = apply_autonomous_controls(
            state, metrics, hardware, webcam_vision, lidar_scan
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

    servo_degrees = clamp_servo_degrees(
        state.get("steering_servo_deg", float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0)
    )
    center_degrees = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    if abs(servo_degrees - center_degrees) < (float(STEERING_SERVO_ACTUATION_RANGE_DEG) * 0.015):
        servo_degrees = center_degrees
    if (
        not state["autonomous_mode"]
        and servo_degrees == center_degrees
        and current_time < float(state.get("steering_center_settle_until", 0.0))
    ):
        servo_degrees = clamp_servo_degrees(state.get("steering_center_settle_deg", center_degrees))
    elif current_time >= float(state.get("steering_center_settle_until", 0.0)):
        state["steering_center_settle_until"] = 0.0
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

    state["dashboard_throttle_percent"] = int(round(pwm_val * 100.0)) if not effective_brake else 0
    state["dashboard_brake_percent"] = int(round(max(0.0, min(1.0, effective_brake_force)) * 100.0)) if effective_brake else 0

    calculate_speed(state, metrics, dt)


def run(model_choice=None):
    global photo_status
    print("RC Car Controller Starting...")
    active_model_choice = model_choice or DEFAULT_STEERING_MODEL_CHOICE
    state = create_state()
    metrics = Metrics()
    csv_file = None
    lidar_parser = None
    webcam_vision = None
    dashboard_sender = None
    gps_reader = None
    navigation = NavigationManager()
    latest_nav = navigation.update({"fix": False, "sats": 0}, 0.0, 0.0)
    navigation_operator_last = ""

    def pulse_detected():
        metrics.pulse_count += 1
        metrics.last_pulse_time = time.time()

    hardware = Hardware(pulse_detected)

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("!!! WARNING: No joystick detected. Please connect a controller. !!!")
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

    webcam_vision = WebcamVisionProcessor(model_choice=active_model_choice)
    if not webcam_vision.start():
        webcam_vision = None

    csv_file, csv_writer = init_csv_logger(CSV_FILENAME, CSV_HEADERS)
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
            dt = current_loop_time - last_update_time
            last_update_time = current_loop_time

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
                            previous_servo_degrees = float(
                                state.get(
                                    "steering_servo_deg",
                                    float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0,
                                )
                            )
                            scaled_steer_val = apply_steering_deadzone(raw_steer_val)
                            if scaled_steer_val == 0.0:
                                was_steering = abs(float(state.get("steer", 0.0))) > 0.0
                                settle_source_degrees = float(
                                    state.get("steering_last_noncenter_servo_deg", previous_servo_degrees)
                                )
                                state["steer"] = 0.0
                                state["steering_servo_deg"] = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
                                if was_steering:
                                    start_manual_steering_center_settle(state, settle_source_degrees)
                            else:
                                state["steer"] = scaled_steer_val
                                state["steering_servo_deg"] = joystick_steer_to_servo_degrees(state["steer"])
                                state["steering_last_noncenter_servo_deg"] = state["steering_servo_deg"]
                                state["steering_center_settle_until"] = 0.0
                    elif SHARED_TRIGGER_AXIS and event.axis == THROTTLE_AXIS:
                        state["throttle"], state["brake_force"] = split_shared_trigger_axis(event.value)
                        state["manual_brake_force"] = state["brake_force"]
                        state["brake"] = state["brake_force"] > 0.1
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and state["throttle"] > 0.05
                        ):
                            cancel_navigation_route(state, metrics, navigation, "Navigation cancelled by gas pedal.")
                        if state["throttle"] > 0.05 and state["autonomous_mode"]:
                            cancel_autonomous_mode(state, metrics, "Autonomous driving cancelled by gas pedal.")
                        handle_manual_throttle_override(state, metrics, dashboard_sender)
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and state["brake"]
                        ):
                            cancel_navigation_route(state, metrics, navigation, "Navigation cancelled by brake.")
                        if state["brake"] and state["autonomous_mode"]:
                            cancel_autonomous_mode(state, metrics, "Autonomous driving cancelled by brake.")
                    elif event.axis == THROTTLE_AXIS:
                        state["throttle"] = normalize_trigger_axis(event.value)
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and state["throttle"] > 0.05
                        ):
                            cancel_navigation_route(state, metrics, navigation, "Navigation cancelled by gas pedal.")
                        if state["throttle"] > 0.05 and state["autonomous_mode"]:
                            cancel_autonomous_mode(state, metrics, "Autonomous driving cancelled by gas pedal.")
                        handle_manual_throttle_override(state, metrics, dashboard_sender)
                    elif not SHARED_TRIGGER_AXIS and event.axis == BRAKE_AXIS:
                        state["brake_force"] = normalize_trigger_axis(event.value)
                        state["manual_brake_force"] = state["brake_force"]
                        state["brake"] = state["brake_force"] > 0.1
                        if (
                            navigation_manual_input_should_cancel(navigation, latest_nav, navigation_operator_last)
                            and state["brake"]
                        ):
                            cancel_navigation_route(state, metrics, navigation, "Navigation cancelled by brake.")
                        if state["brake"] and state["autonomous_mode"]:
                            cancel_autonomous_mode(state, metrics, "Autonomous driving cancelled by brake.")
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
                        current_index = GEARS.index(state["gear_mode"])
                        state["gear_mode"] = GEARS[max(current_index - 1, 0)]
                        state["event_shift_down"] = True
                        state["brake"] = False
                        state["brake_force"] = 0.0
                        state["manual_brake_force"] = 0.0
                        cancel_cruise_control(state, metrics, dashboard_sender)
                    elif event.button == SHIFT_UP_BUTTON:
                        current_index = GEARS.index(state["gear_mode"])
                        state["gear_mode"] = GEARS[min(current_index + 1, len(GEARS) - 1)]
                        state["event_shift_up"] = True
                        state["brake"] = False
                        state["brake_force"] = 0.0
                        state["manual_brake_force"] = 0.0
                        cancel_cruise_control(state, metrics, dashboard_sender)
                    elif event.button == AUTONOMY_TOGGLE_BUTTON:
                        if not state["autonomous_mode"] and webcam_vision is None:
                            print("Autonomous Driving not enabled: steering autonomy model is unavailable.")
                            continue
                        state["autonomous_mode"] = not state["autonomous_mode"]
                        if state["autonomous_mode"]:
                            print("Autonomous Driving ENABLED.")
                            state["gear_mode"] = "D"
                            cancel_cruise_control(state, metrics, dashboard_sender)
                            state["brake"] = False
                            state["brake_force"] = 0.0
                            state["manual_brake_force"] = 0.0
                            metrics.driveway_cut_candidate_since = 0.0
                        else:
                            print("Autonomous Driving DISABLED.")
                            state["throttle"] = 0.0
                            center_steering(state)
                            state["current_motor_pwm"] = 0.0
                            state["brake_force"] = 0.0
                            state["manual_brake_force"] = 0.0
                            metrics.driveway_cut_candidate_since = 0.0
                    elif event.button == AEB_TOGGLE_BUTTON:
                        metrics.aeb_enabled = not metrics.aeb_enabled
                        print(f"Automatic Emergency Braking (AEB): {'ENABLED' if metrics.aeb_enabled else 'DISABLED'}")
                        queue_aeb_toggle_notification(dashboard_sender, metrics.aeb_enabled)
                    elif event.button == PHOTO_BUTTON:
                        take_photo(webcam_vision, state)
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
                                state["autonomous_mode"] = True
                                state["gear_mode"] = "D"
                                cancel_cruise_control(state, metrics, dashboard_sender)
                                print("Navigation route started: model/autonomous segment.")
                            elif operator == "AUTO":
                                cancel_autonomous_mode(state, metrics, "Navigation route requested AI segment, but camera model is unavailable.")
                            elif operator == "MNUL":
                                cancel_autonomous_mode(state, metrics, "Navigation route started: human/manual segment.")
                    elif event.button == QUIT_BUTTON:
                        state["event_quit_pressed"] = True
                        shutdown_flag.set()
                elif event.type == pygame.JOYHATMOTION:
                    hat_x, hat_y = event.value
                    if hat_x:
                        current_dashboard_page = int(state.get("dashboard_page", 1))
                        if current_dashboard_page == STEERING_TRIM_DASHBOARD_PAGE:
                            adjust_steering_center_trim(state, hardware, int(hat_x))
                        elif current_dashboard_page == 5 and not navigation.active:
                            navigation.move_cursor(int(hat_x))
                        elif hat_x == -1:
                            toggle_turn_signal(state, metrics, "left")
                        elif hat_x == 1:
                            toggle_turn_signal(state, metrics, "right")
                    state["dpad_y_value"] = int(hat_y)
                    if hat_y:
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

            latest_scan = []
            if lidar_parser:
                try:
                    latest_scan = lidar_parser.get_latest_scan()
                except Exception as exc:
                    print(f"LiDAR latest scan unavailable; ignoring LiDAR this loop: {exc}")
                    latest_scan = []
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
                state["direction_arrow"] = " "
                state["lidar_front_dist"] = MAX_LIDAR_RANGE_M
                state["lidar_left_dist"] = MAX_LIDAR_RANGE_M
                state["lidar_right_dist"] = MAX_LIDAR_RANGE_M
                state["lidar_back_dist"] = MAX_LIDAR_RANGE_M
                state["lidar_stop_threshold_m"] = FORWARD_OBSTACLE_STOP_DISTANCE_M
                state["lidar_warn_threshold_m"] = OBSTACLE_WARN_THRESHOLD_M
                state["num_lidar_points"] = 0

            update_gpio(state, metrics, hardware, webcam_vision, latest_scan, dt, dashboard_sender)
            update_turn_signal_blink(state, metrics)
            update_dashboard_page_selection(state, metrics)
            if current_loop_time - metrics.dashboard_cpu_temp_last_sample_time >= 1.0:
                metrics.dashboard_cpu_temp_c = get_cpu_temp()
                metrics.dashboard_cpu_temp_last_sample_time = current_loop_time
            update_dashboard_photo_stats(metrics, current_loop_time)
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
                        state["autonomous_mode"] = True
                        state["gear_mode"] = "D"
                        cancel_cruise_control(state, metrics, dashboard_sender)
                        print("Navigation operator: AI/model segment.")
                    elif nav_operator == "AUTO":
                        cancel_autonomous_mode(state, metrics, "Navigation operator requested AI, but camera model is unavailable.")
                    elif nav_operator == "MNUL":
                        cancel_autonomous_mode(state, metrics, "Navigation operator: human/manual segment.")
                    navigation_operator_last = nav_operator
            camera_pixels = []
            if state["dashboard_page"] == 11 and webcam_vision is not None:
                camera_pixels = webcam_vision.get_dashboard_camera_pixels()
            lidar_dashboard_points = []
            if state["dashboard_page"] == LIDAR_DASHBOARD_PAGE:
                lidar_dashboard_points = format_lidar_dashboard_points(latest_scan)
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
                    model_choice=active_model_choice,
                    camera_confidence_percent=int(round(max(0.0, min(1.0, state["camera_confidence"])) * 100.0)),
                    cpu_temp_c=metrics.dashboard_cpu_temp_c,
                    camera_pixels=camera_pixels,
                    photos_run=metrics.dashboard_photos_run,
                    photos_all=metrics.dashboard_photos_all,
                    photo_run_stats=metrics.dashboard_photo_run_stats,
                    camera_fps=webcam_vision.camera_fps if webcam_vision is not None else 0.0,
                    system_status=get_system_status(state),
                    nav_status=latest_nav,
                    steering_trim_delta_deg=state["steering_trim_delta_deg"],
                    steering_trim_total_deg=state["steering_trim_total_deg"],
                    steering_center_offset=state["steering_center_offset"],
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

            clock.tick(60)

    except KeyboardInterrupt:
        state["event_quit_pressed"] = True
    finally:
        shutdown_flag.set()
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
        if webcam_vision:
            webcam_vision.stop()
        if dashboard_sender:
            if HUB75_DASHBOARD_SHUTDOWN_ON_EXIT and not dashboard_shutdown_sent:
                dashboard_sender.send_shutdown()
            dashboard_sender.close()
        hardware.cleanup()
        if csv_file:
            csv_file.close()
        cleanup_photo_run_dir()
        pygame.quit()
