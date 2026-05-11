#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import socket
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from rgbmatrix import RGBMatrix, RGBMatrixOptions

try:
    import serial
except ImportError as exc:
    print("Missing dependency: pyserial")
    print("Install on the Pi with: python -m pip install pyserial")
    raise SystemExit(1) from exc

try:
    import spidev
except ImportError:
    spidev = None

Color = Tuple[int, int, int]
Glyph = List[int]

CURRENT_DIR = Path(__file__).resolve().parent
BITMAPS_DIR = CURRENT_DIR / "8x8_bitmaps"
DIGITS_PATH = BITMAPS_DIR / "digits.h"
LETTERS_PATH = BITMAPS_DIR / "letters.h"
SIGNS_PATH = BITMAPS_DIR / "signs.h"

CELL_SIZE = 8
PANEL_WIDTH = 64
PANEL_HEIGHT = 32

DIGIT_BLUE: Color = (0, 0, 255)
GEAR_RED_DIM: Color = (220, 0, 0)
GEAR_GREEN_ACTIVE: Color = (0, 255, 0)
ARROW_YELLOW: Color = (204, 204, 0)
ALERT_RED_DIM: Color = (204, 0, 0)
NOTIFICATION_WHITE: Color = (255, 255, 0)
TEXT_CYAN: Color = (0, 180, 255)
TEXT_GREEN: Color = (0, 255, 0)
TEXT_ORANGE: Color = (255, 120, 0)
TEXT_WHITE: Color = (220, 220, 220)
LIDAR_POINT_GREEN: Color = (0, 255, 70)
LIDAR_POINT_YELLOW: Color = (255, 220, 0)
LIDAR_POINT_RED: Color = (255, 0, 0)
LIDAR_POINT_BLUE: Color = (0, 120, 255)
LIDAR_CAR: Color = (255, 255, 255)
RIGHT_TURN_SIGNAL_INDEX = 28
LEFT_TURN_SIGNAL_INDEX = 29
COLON_GLYPH_INDEX = 17
AT_GLYPH_INDEX = 22
PERCENT_GLYPH_INDEX = 4
MIN_VISIBLE_BRIGHTNESS_PERCENT = 5


def load_glyphs_from_header(path: Path) -> List[Glyph]:
    text = path.read_text(encoding="utf-8")
    values = [int(match.group(1), 2) for match in re.finditer(r"0b([01]{8})", text)]
    if len(values) % 8 != 0:
        raise ValueError(f"{path} does not contain a whole number of 8-row glyphs")
    return [values[index:index + 8] for index in range(0, len(values), 8)]


def build_digit_map() -> Dict[str, Glyph]:
    glyphs = load_glyphs_from_header(DIGITS_PATH)
    labels = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "10"]
    return {label: glyph for label, glyph in zip(labels, glyphs)}


def build_letter_map() -> Dict[str, Glyph]:
    glyphs = load_glyphs_from_header(LETTERS_PATH)
    sign_glyphs = load_glyphs_from_header(SIGNS_PATH)
    labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + [" "] + list("abcdefghijklmnopqrstuvwxyz")
    letter_map: Dict[str, Glyph] = {}
    for label, glyph in zip(labels, glyphs):
        letter_map[label] = glyph
    letter_map[" "] = [0x00] * 8
    letter_map[":"] = sign_glyphs[COLON_GLYPH_INDEX]
    letter_map["@"] = sign_glyphs[AT_GLYPH_INDEX]
    letter_map["%"] = sign_glyphs[PERCENT_GLYPH_INDEX]
    return letter_map


def load_turn_signal_glyphs() -> Tuple[Glyph, Glyph]:
    glyphs = load_glyphs_from_header(SIGNS_PATH)
    return glyphs[LEFT_TURN_SIGNAL_INDEX], glyphs[RIGHT_TURN_SIGNAL_INDEX]


def effective_brightness_percent(requested_percent: int) -> int:
    clamped = max(0, min(100, int(requested_percent)))
    if clamped == 0:
        return 0
    # Low requested values were visually dropping out on the panel. Use a
    # perceptual remap so 50/30/etc. stay visible while keeping 100 at 100.
    remapped = int(round(math.sqrt(clamped / 100.0) * 100.0))
    return max(MIN_VISIBLE_BRIGHTNESS_PERCENT, remapped)


class DashboardRenderer:
    def __init__(
        self,
        slowdown_gpio: int,
        panel_type: str,
        brightness: int,
        pwm_bits: int,
        rgb_sequence: str,
    ):
        options = RGBMatrixOptions()
        options.hardware_mapping = "z2w-custom"
        options.rows = PANEL_HEIGHT
        options.cols = PANEL_WIDTH
        options.chain_length = 1
        options.parallel = 1
        options.gpio_slowdown = slowdown_gpio
        options.panel_type = panel_type
        options.brightness = brightness
        options.pwm_bits = pwm_bits
        options.led_rgb_sequence = rgb_sequence
        options.drop_privileges = False
        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.current_brightness = effective_brightness_percent(brightness)
        self.digit_map = build_digit_map()
        self.letter_map = build_letter_map()
        self.left_turn_signal, self.right_turn_signal = load_turn_signal_glyphs()
        self.current_page = 1
        self.previous_page = 1
        self.transition_direction = 0
        self.transition_start = 0.0
        self.transition_duration_sec = 0.22
        self.latest_payload: Dict[str, object] = {}

    def _set_pixel(self, x: int, y: int, color: Color):
        if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
            self.canvas.SetPixel(x, y, *color)

    def _draw_glyph(self, glyph: Sequence[int], cell_index: int, color: Color, y_offset_px: int = 0):
        base_x = cell_index * CELL_SIZE
        base_y = y_offset_px
        for row in range(8):
            row_bits = glyph[row]
            for bit in range(8):
                if row_bits & (1 << (7 - bit)):
                    self._set_pixel(base_x + bit, base_y + row, color)

    def _draw_glyph_at(
        self,
        glyph: Sequence[int],
        row_index: int,
        col_index: int,
        color: Color,
        y_offset_px: int = 0,
    ):
        base_x = col_index * CELL_SIZE
        base_y = (row_index * CELL_SIZE) + y_offset_px
        for row in range(8):
            row_bits = glyph[row]
            for bit in range(8):
                if row_bits & (1 << (7 - bit)):
                    self._set_pixel(base_x + bit, base_y + row, color)

    def _draw_decimal_point_at(self, row_index: int, col_index: int, color: Color, y_offset_px: int = 0):
        base_x = col_index * CELL_SIZE
        base_y = (row_index * CELL_SIZE) + y_offset_px
        self._set_pixel(base_x + 7, base_y + 7, color)

    def _draw_notification_row(self, row_index: int, cells: Sequence[str], color: Color, y_offset_px: int = 0):
        for col_index, raw_cell in enumerate(list(cells)[:8]):
            cell = str(raw_cell)
            if not cell:
                continue
            if cell == "10":
                self._draw_glyph_at(self.digit_map.get("10", self.letter_map[" "]), row_index, col_index, color, y_offset_px)
                continue
            if len(cell) == 2 and cell[0].isdigit() and cell[1] == ".":
                self._draw_glyph_at(self.digit_map.get(cell[0], self.letter_map[" "]), row_index, col_index, color, y_offset_px)
                self._draw_decimal_point_at(row_index, col_index, color, y_offset_px)
                continue
            if cell.isdigit():
                self._draw_glyph_at(self.digit_map.get(cell, self.letter_map[" "]), row_index, col_index, color, y_offset_px)
                continue
            self._draw_glyph_at(self.letter_map.get(cell, self.letter_map[" "]), row_index, col_index, color, y_offset_px)

    def _speed_digits(self, speed_mph: float) -> str:
        clamped = max(0.0, min(9.99, speed_mph))
        hundredths = int(round(clamped * 100))
        if hundredths > 999:
            hundredths = 999
        ones = hundredths // 100
        tenths = (hundredths // 10) % 10
        hundredths_digit = hundredths % 10
        return f"{ones}{tenths}{hundredths_digit}"

    def _format_three_digits(self, value: float) -> List[str]:
        clamped = max(0, min(999, int(round(float(value)))))
        return [str(clamped // 100), str((clamped // 10) % 10), str(clamped % 10)]

    def _format_percent_cells(self, value: float) -> List[str]:
        clamped = max(0, min(100, int(round(float(value)))))
        if clamped >= 100:
            return ["10", "0", "%"]
        return [str(clamped // 10), str(clamped % 10), "%"]

    def _draw_text_row(self, row_index: int, cells: Sequence[str], color: Color, y_offset_px: int = 0):
        self._draw_notification_row(row_index, cells, color, y_offset_px)

    def _draw_page_one(
        self,
        speed_mph: float,
        gear: str,
        left_signal_visible: bool,
        right_signal_visible: bool,
        dashboard_alert: str,
        notification_rows: Sequence[Sequence[str]],
        y_offset_px: int = 0,
    ):
        speed_digits = self._speed_digits(speed_mph)
        for cell_index, char in enumerate(speed_digits):
            self._draw_glyph(self.digit_map.get(char, self.letter_map[" "]), cell_index, DIGIT_BLUE, y_offset_px)

        # Decimal point in bottom-right of R1C1.
        self._set_pixel(7, 7 + y_offset_px, DIGIT_BLUE)

        for offset, gear_char in enumerate("PRND", start=4):
            color = GEAR_GREEN_ACTIVE if gear == gear_char else GEAR_RED_DIM
            self._draw_glyph(self.letter_map.get(gear_char, self.letter_map[" "]), offset, color, y_offset_px)

        if left_signal_visible:
            self._draw_glyph_at(self.left_turn_signal, 3, 0, ARROW_YELLOW, y_offset_px)
        if right_signal_visible:
            self._draw_glyph_at(self.right_turn_signal, 3, 7, ARROW_YELLOW, y_offset_px)
        for offset, char in enumerate(str(dashboard_alert)[:4], start=2):
            self._draw_glyph_at(self.letter_map.get(char, self.letter_map[" "]), 3, offset, ALERT_RED_DIM, y_offset_px)
        for row_offset, cells in enumerate(list(notification_rows)[:2], start=1):
            self._draw_notification_row(row_offset, cells, NOTIFICATION_WHITE, y_offset_px)

    def _draw_page_two(self, payload: Dict[str, object], y_offset_px: int = 0):
        servo_cells = self._format_three_digits(float(payload.get("servo_deg", 90.0)))
        throttle_cells = self._format_percent_cells(float(payload.get("throttle_percent", 0)))
        brake_cells = self._format_percent_cells(float(payload.get("brake_percent", 0)))
        mode = str(payload.get("drive_mode", "MAN")).upper()[:3]
        if mode == "CC":
            mode = " CC"
        if len(mode) < 3:
            mode = (mode + "   ")[:3]
        self._draw_text_row(0, ["S", "R", "V", "O", ":", *servo_cells], TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["T", "T", "L", "E", ":", *throttle_cells], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["B", "R", "K", "E", ":", *brake_cells], TEXT_ORANGE, y_offset_px)
        self._draw_text_row(3, ["M", "O", "D", "E", ":", mode[0], mode[1], mode[2]], ARROW_YELLOW, y_offset_px)

    def _draw_page_three(self, payload: Dict[str, object], y_offset_px: int = 0):
        center_x = PANEL_WIDTH // 2
        center_y = (PANEL_HEIGHT // 2) + y_offset_px
        scale = 2.5
        for row in range(0, PANEL_HEIGHT, 8):
            self._set_pixel(center_x, row + y_offset_px, (0, 35, 35))
        for col in range(0, PANEL_WIDTH, 8):
            self._set_pixel(col, center_y, (0, 35, 35))
        raw_points = payload.get("lidar_points", [])
        if isinstance(raw_points, list):
            for raw_point in raw_points:
                if not isinstance(raw_point, list) or len(raw_point) < 2:
                    continue
                try:
                    angle_deg = float(raw_point[0])
                    distance_m = max(0.0, min(6.0, float(raw_point[1])))
                except (TypeError, ValueError):
                    continue
                angle_rad = math.radians(angle_deg)
                x = int(round(center_x + math.sin(angle_rad) * distance_m * scale))
                y = int(round(center_y - math.cos(angle_rad) * distance_m * scale))
                if distance_m < 0.6:
                    color = LIDAR_POINT_RED
                elif distance_m < 1.2:
                    color = LIDAR_POINT_YELLOW
                elif distance_m < 3.0:
                    color = LIDAR_POINT_GREEN
                else:
                    color = LIDAR_POINT_BLUE
                self._set_pixel(x, y, color)
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            self._set_pixel(center_x + dx, center_y + dy, LIDAR_CAR)

    def _format_model_cells(self, model_choice: str) -> List[str]:
        match = re.search(r"(\d+)\.(\d+)", str(model_choice))
        if not match:
            return ["0.", "0"]
        return [f"{match.group(1)[-1]}.", match.group(2)[0]]

    def _draw_page_four(self, payload: Dict[str, object], y_offset_px: int = 0):
        model_cells = self._format_model_cells(str(payload.get("model_choice", "0.0")))
        pred_cells = self._format_three_digits(float(payload.get("servo_deg", 90.0)))
        confidence_cells = self._format_percent_cells(float(payload.get("camera_confidence_percent", 0)))
        cpu_temp = max(0, min(99, int(round(float(payload.get("cpu_temp_c", 0.0))))))
        cpu_temp_cells = [str(cpu_temp // 10), str(cpu_temp % 10), "C"]
        self._draw_text_row(0, ["M", "O", "D", "E", "L", ":", "", model_cells[1]], TEXT_CYAN, y_offset_px)
        self._draw_glyph_at(self.digit_map.get(model_cells[0][0], self.letter_map[" "]), 0, 6, TEXT_CYAN, y_offset_px)
        self._set_pixel((6 * CELL_SIZE) + 7, (0 * CELL_SIZE) + 4 + y_offset_px, TEXT_CYAN)
        self._draw_text_row(1, ["P", "R", "E", "D", ":", *pred_cells], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["C", "O", "N", "F", ":", *confidence_cells], ARROW_YELLOW, y_offset_px)
        self._draw_text_row(3, ["C", "T", "M", "P", ":", *cpu_temp_cells], TEXT_ORANGE, y_offset_px)

    def _draw_page_five(self, payload: Dict[str, object], y_offset_px: int = 0):
        rows = payload.get("camera_pixels", [])
        if not isinstance(rows, list) or len(rows) < PANEL_HEIGHT:
            self._draw_text_row(1, ["C", "A", "M", ":", "", "N", "O", ""], TEXT_ORANGE, y_offset_px)
            self._draw_text_row(2, ["F", "R", "A", "M", "E", "", "", ""], TEXT_ORANGE, y_offset_px)
            return
        for y, raw_row in enumerate(rows[:PANEL_HEIGHT]):
            row_text = str(raw_row)
            if len(row_text) < PANEL_WIDTH * 4:
                continue
            for x in range(PANEL_WIDTH):
                pixel_text = row_text[x * 4 : (x + 1) * 4]
                if not re.fullmatch(r"[0-9a-fA-F]{4}", pixel_text):
                    continue
                rgb565 = int(pixel_text, 16)
                r = ((rgb565 >> 11) & 0x1F) << 3
                g = ((rgb565 >> 5) & 0x3F) << 2
                b = (rgb565 & 0x1F) << 3
                # The camera/model/photo pipeline stays OpenCV BGR. The HUB75
                # preview needs red/blue swapped at draw time to look RGB.
                self._set_pixel(x, y + y_offset_px, (b, g, r))

    def _draw_page(
        self,
        page: int,
        payload: Dict[str, object],
        notification_rows: Sequence[Sequence[str]],
        y_offset_px: int = 0,
    ):
        if page == 2:
            self._draw_page_two(payload, y_offset_px)
            return
        if page == 3:
            self._draw_page_three(payload, y_offset_px)
            return
        if page == 4:
            self._draw_page_four(payload, y_offset_px)
            return
        if page == 5:
            self._draw_page_five(payload, y_offset_px)
            return
        self._draw_page_one(
            float(payload.get("speed_mph", 0.0)),
            str(payload.get("gear", "P"))[:1],
            bool(payload.get("left_signal_visible", False)),
            bool(payload.get("right_signal_visible", False)),
            str(payload.get("dashboard_alert", ""))[:4],
            notification_rows,
            y_offset_px,
        )

    def render(self, payload: Dict[str, object], notification_rows: Sequence[Sequence[str]]):
        requested_page = max(1, min(5, int(payload.get("dashboard_page", self.current_page))))
        transition = str(payload.get("dashboard_page_transition", ""))
        if requested_page != self.current_page:
            self.previous_page = self.current_page
            self.current_page = requested_page
            self.transition_direction = 1 if transition == "forward" else -1
            self.transition_start = time.monotonic()
        self.latest_payload = dict(payload)

        self.canvas.Clear()
        progress = 1.0
        if self.transition_direction != 0:
            progress = (time.monotonic() - self.transition_start) / self.transition_duration_sec
            if progress >= 1.0:
                self.transition_direction = 0
                progress = 1.0

        if self.transition_direction == 0:
            self._draw_page(self.current_page, payload, notification_rows, 0)
        else:
            shift_px = int(round(progress * PANEL_HEIGHT))
            if self.transition_direction > 0:
                previous_offset = -shift_px
                current_offset = PANEL_HEIGHT - shift_px
            else:
                previous_offset = shift_px
                current_offset = -PANEL_HEIGHT + shift_px
            self._draw_page(self.previous_page, payload, notification_rows, previous_offset)
            self._draw_page(self.current_page, payload, notification_rows, current_offset)

        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def clear(self):
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def set_brightness(self, brightness_percent: int):
        effective = effective_brightness_percent(brightness_percent)
        if effective == self.current_brightness:
            return
        self.current_brightness = effective
        self.matrix.brightness = effective
        self.canvas.brightness = effective


class Max7219TurnSignalDisplay:
    REG_INTENSITY = 0x0A
    REG_SCANLIMIT = 0x0B
    REG_SHUTDOWN = 0x0C
    REG_DISPLAYTEST = 0x0F
    REG_DECODEMODE = 0x09

    def __init__(self, device_count: int, bus: int, device: int, intensity: int):
        self.available = spidev is not None
        self.device_count = device_count
        self.intensity = max(0, min(15, intensity))
        self.spi = None
        self.left_turn_signal, self.right_turn_signal = load_turn_signal_glyphs()
        if not self.available:
            print("MAX7219 on Zero 2 W disabled: missing dependency 'spidev'.")
            return
        try:
            self.spi = spidev.SpiDev()
            device_path = Path(f"/dev/spidev{bus}.{device}")
            if device_path.exists() and hasattr(self.spi, "open_path"):
                self.spi.open_path(str(device_path))
            else:
                self.spi.open(bus, device)
            self.spi.max_speed_hz = 1_000_000
            self.spi.mode = 0
            self._initialize()
            print(f"MAX7219 on Zero 2 W initialized on SPI{bus}.{device}.")
        except Exception as exc:
            print(f"MAX7219 on Zero 2 W init failed: {exc}")
            self.available = False
            self.spi = None

    def _write_all(self, register: int, value: int):
        if not self.spi:
            return
        payload: List[int] = []
        for _ in range(self.device_count):
            payload.extend([register, value])
        self.spi.xfer2(payload)

    def _write_row_bytes(self, row_register: int, module_bytes: Sequence[int]):
        if not self.spi:
            return
        if len(module_bytes) != self.device_count:
            raise ValueError("module_bytes length must match device_count")
        payload: List[int] = []
        for value in reversed(module_bytes):
            payload.extend([row_register, value])
        self.spi.xfer2(payload)

    def _initialize(self):
        self._write_all(self.REG_DISPLAYTEST, 0x00)
        self._write_all(self.REG_DECODEMODE, 0x00)
        self._write_all(self.REG_SCANLIMIT, 0x07)
        self._write_all(self.REG_INTENSITY, self.intensity)
        self._write_all(self.REG_SHUTDOWN, 0x01)
        self.clear()

    def render(self, left_visible: bool, right_visible: bool):
        if not self.spi:
            return
        for row in range(8):
            module_bytes = [0x00] * self.device_count
            if left_visible:
                module_bytes[self.device_count - 1] = self.left_turn_signal[row]
            if right_visible:
                module_bytes[0] = self.right_turn_signal[row]
            self._write_row_bytes(row + 1, module_bytes)

    def clear(self):
        if not self.spi:
            return
        for row in range(1, 9):
            self._write_all(row, 0x00)

    def set_brightness_percent(self, brightness_percent: int):
        if not self.spi:
            return
        effective = effective_brightness_percent(brightness_percent)
        intensity = max(0, min(15, round((effective / 100.0) * 15.0)))
        if intensity == self.intensity:
            return
        self.intensity = intensity
        self._write_all(self.REG_INTENSITY, self.intensity)

    def cleanup(self):
        try:
            self.clear()
            self._write_all(self.REG_SHUTDOWN, 0x00)
        finally:
            if self.spi:
                self.spi.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Zero 2 W dashboard receiver for HUB75 and MAX7219 displays")
    parser.add_argument("--transport", choices=("udp", "serial"), default="udp")
    parser.add_argument("--serial-port", default="/dev/ttyGS0")
    parser.add_argument("--baud-rate", type=int, default=115200)
    parser.add_argument("--udp-host", default="0.0.0.0")
    parser.add_argument("--udp-port", type=int, default=8765)
    parser.add_argument("--led-slowdown-gpio", type=int, default=4)
    parser.add_argument("--led-panel-type", default="FM6126A")
    parser.add_argument("--led-brightness", type=int, default=80)
    parser.add_argument("--led-pwm-bits", type=int, default=5)
    parser.add_argument("--led-rgb-sequence", default="RGB")
    parser.add_argument("--max7219-bus", type=int, default=0)
    parser.add_argument("--max7219-device", type=int, default=0)
    parser.add_argument("--max7219-devices", type=int, default=4)
    parser.add_argument("--max7219-intensity", type=int, default=10)
    parser.add_argument("--idle-exit-sec", type=float, default=2.0)
    return parser.parse_args()


def main():
    args = parse_args()
    renderer = DashboardRenderer(
        slowdown_gpio=args.led_slowdown_gpio,
        panel_type=args.led_panel_type,
        brightness=args.led_brightness,
        pwm_bits=args.led_pwm_bits,
        rgb_sequence=args.led_rgb_sequence,
    )
    max7219 = Max7219TurnSignalDisplay(
        device_count=args.max7219_devices,
        bus=args.max7219_bus,
        device=args.max7219_device,
        intensity=args.max7219_intensity,
    )

    latest_speed = 0.0
    latest_gear = "P"
    left_signal_visible = False
    right_signal_visible = False
    dashboard_alert = ""
    brightness_percent = args.led_brightness
    dashboard_page = 1
    dashboard_page_transition = ""
    servo_deg = 90.0
    throttle_percent = 0
    brake_percent = 0
    drive_mode = "MAN"
    lidar_points: List[List[float]] = []
    model_choice = ""
    camera_confidence_percent = 0
    cpu_temp_c = 0.0
    camera_pixels: List[str] = []
    last_packet_time = time.monotonic()
    have_received_payload = False
    active_notifications: List[Dict[str, object]] = []

    def prune_expired_notifications(now: float) -> None:
        active_notifications[:] = [
            notification
            for notification in active_notifications
            if now < float(notification.get("expires_at", 0.0))
        ]

    def update_notification_rows() -> List[List[str]]:
        now = time.monotonic()
        prune_expired_notifications(now)
        return [list(notification.get("cells", [""] * 8))[:8] for notification in active_notifications]

    def render_current_state() -> None:
        notification_rows = update_notification_rows()
        renderer.render(
            {
                "speed_mph": latest_speed,
                "gear": latest_gear,
                "left_signal_visible": left_signal_visible,
                "right_signal_visible": right_signal_visible,
                "dashboard_alert": dashboard_alert,
                "dashboard_page": dashboard_page,
                "dashboard_page_transition": dashboard_page_transition,
                "servo_deg": servo_deg,
                "throttle_percent": throttle_percent,
                "brake_percent": brake_percent,
                "drive_mode": drive_mode,
                "lidar_points": lidar_points,
                "model_choice": model_choice,
                "camera_confidence_percent": camera_confidence_percent,
                "cpu_temp_c": cpu_temp_c,
                "camera_pixels": camera_pixels,
            },
            notification_rows,
        )
        max7219.render(left_signal_visible, right_signal_visible)

    def handle_idle() -> int | None:
        if have_received_payload and time.monotonic() - last_packet_time >= args.idle_exit_sec:
            print(
                "Dashboard receiver exiting after telemetry idle timeout "
                f"({args.idle_exit_sec:.1f}s)."
            )
            return 0
        render_current_state()
        return None

    def handle_payload(payload: Dict[str, object]) -> int | None:
        nonlocal have_received_payload
        nonlocal last_packet_time
        nonlocal latest_speed
        nonlocal latest_gear
        nonlocal left_signal_visible
        nonlocal right_signal_visible
        nonlocal dashboard_alert
        nonlocal brightness_percent
        nonlocal dashboard_page
        nonlocal dashboard_page_transition
        nonlocal servo_deg
        nonlocal throttle_percent
        nonlocal brake_percent
        nonlocal drive_mode
        nonlocal lidar_points
        nonlocal model_choice
        nonlocal camera_confidence_percent
        nonlocal cpu_temp_c
        nonlocal camera_pixels

        if payload.get("shutdown"):
            print("Dashboard receiver shutdown requested by controller.")
            return 0

        have_received_payload = True
        last_packet_time = time.monotonic()
        latest_speed = float(payload.get("speed_mph", latest_speed))
        latest_gear = str(payload.get("gear", latest_gear))[:1]
        left_signal_visible = bool(payload.get("left_signal_visible", left_signal_visible))
        right_signal_visible = bool(payload.get("right_signal_visible", right_signal_visible))
        dashboard_alert = str(payload.get("dashboard_alert", dashboard_alert))[:4]
        brightness_percent = max(0, min(100, int(payload.get("brightness_percent", brightness_percent))))
        dashboard_page = max(1, min(5, int(payload.get("dashboard_page", dashboard_page))))
        dashboard_page_transition = str(payload.get("dashboard_page_transition", ""))[:8]
        servo_deg = max(0.0, min(180.0, float(payload.get("servo_deg", servo_deg))))
        throttle_percent = max(0, min(100, int(payload.get("throttle_percent", throttle_percent))))
        brake_percent = max(0, min(100, int(payload.get("brake_percent", brake_percent))))
        drive_mode = str(payload.get("drive_mode", drive_mode)).upper()[:3]
        model_choice = str(payload.get("model_choice", model_choice))[:4]
        camera_confidence_percent = max(0, min(100, int(payload.get("camera_confidence_percent", camera_confidence_percent))))
        cpu_temp_c = max(0.0, min(99.0, float(payload.get("cpu_temp_c", cpu_temp_c))))
        raw_lidar_points = payload.get("lidar_points", lidar_points)
        if isinstance(raw_lidar_points, list):
            lidar_points = raw_lidar_points[:180]
        raw_camera_pixels = payload.get("camera_pixels", camera_pixels)
        if isinstance(raw_camera_pixels, list):
            camera_pixels = [str(row)[: PANEL_WIDTH * 4] for row in raw_camera_pixels[:PANEL_HEIGHT]]
        renderer.set_brightness(brightness_percent)
        max7219.set_brightness_percent(brightness_percent)
        notification = payload.get("dashboard_notification")
        if isinstance(notification, dict):
            raw_cells = notification.get("cells", [])
            if isinstance(raw_cells, list):
                cells = [str(cell)[:2] for cell in raw_cells[:8]]
                if len(cells) < 8:
                    cells.extend([""] * (8 - len(cells)))
                now = time.monotonic()
                prune_expired_notifications(now)
                if len(active_notifications) >= 2:
                    active_notifications.pop(0)
                duration_sec = max(0.1, float(notification.get("duration_sec", 2.0)))
                active_notifications.append(
                    {
                        "cells": cells,
                        "duration_sec": duration_sec,
                        "expires_at": now + duration_sec,
                    }
                )
        render_current_state()
        return None

    try:
        while True:
            if args.transport == "udp":
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        sock.bind((args.udp_host, args.udp_port))
                        sock.settimeout(1.0)
                        print(f"Dashboard receiver listening on UDP {args.udp_host}:{args.udp_port}")
                        while True:
                            try:
                                packet, _ = sock.recvfrom(65535)
                            except socket.timeout:
                                packet = b""
                            if not packet:
                                idle_result = handle_idle()
                                if idle_result is not None:
                                    return idle_result
                                continue
                            try:
                                payload = json.loads(packet.decode("utf-8").strip())
                            except json.JSONDecodeError:
                                continue
                            result = handle_payload(payload)
                            if result is not None:
                                return result
                except Exception as exc:
                    print(f"Dashboard receiver UDP error on {args.udp_host}:{args.udp_port}: {exc}")
                    time.sleep(1.0)
                continue

            try:
                with serial.Serial(args.serial_port, args.baud_rate, timeout=1.0) as ser:
                    print(f"Dashboard receiver listening on {args.serial_port} @ {args.baud_rate}")
                    while True:
                        line = ser.readline()
                        if not line:
                            idle_result = handle_idle()
                            if idle_result is not None:
                                return idle_result
                            continue
                        try:
                            payload = json.loads(line.decode("utf-8").strip())
                        except json.JSONDecodeError:
                            continue
                        result = handle_payload(payload)
                        if result is not None:
                            return result
            except Exception as exc:
                print(f"Dashboard receiver serial error on {args.serial_port}: {exc}")
                time.sleep(1.0)
    except KeyboardInterrupt:
        return 0
    finally:
        renderer.clear()
        max7219.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
