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
DASHBOARD_PAGE_COUNT = 17
TELEMETRY_STALE_DISPLAY_SEC = 4.0

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
LESS_THAN_GLYPH_INDEX = 8
ALL_GLYPH_INDEX = 57
PLUS_GLYPH_INDEX = 0
MINUS_GLYPH_INDEX = 1
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
    letter_map["+"] = sign_glyphs[PLUS_GLYPH_INDEX]
    letter_map["-"] = sign_glyphs[MINUS_GLYPH_INDEX]
    letter_map["@"] = sign_glyphs[AT_GLYPH_INDEX]
    letter_map["%"] = sign_glyphs[PERCENT_GLYPH_INDEX]
    letter_map["<"] = sign_glyphs[LESS_THAN_GLYPH_INDEX]
    letter_map["ALL"] = sign_glyphs[ALL_GLYPH_INDEX]
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
        row_addr_type: int,
        multiplexing: int,
        limit_refresh_rate_hz: int,
        rgb_sequence: str,
        no_hardware_pulse: bool,
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
        options.row_address_type = row_addr_type
        options.multiplexing = multiplexing
        options.limit_refresh_rate_hz = limit_refresh_rate_hz
        options.led_rgb_sequence = rgb_sequence
        options.disable_hardware_pulsing = no_hardware_pulse
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
        self.transition_axis = "vertical"
        self.transition_start = 0.0
        self.transition_duration_sec = 0.22
        self.latest_payload: Dict[str, object] = {}
        self.render_x_offset_px = 0

    def _set_pixel(self, x: int, y: int, color: Color):
        x += self.render_x_offset_px
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

    def _draw_model_decimal_at(self, row_index: int, col_index: int, color: Color, y_offset_px: int = 0):
        base_x = col_index * CELL_SIZE
        base_y = (row_index * CELL_SIZE) + y_offset_px
        self._set_pixel(base_x + 7, base_y + 4, color)

    def _draw_vertical_bar_at(self, row_index: int, col_index: int, color: Color, y_offset_px: int = 0):
        base_x = col_index * CELL_SIZE
        base_y = (row_index * CELL_SIZE) + y_offset_px
        for row in range(1, 7):
            self._set_pixel(base_x + 3, base_y + row, color)

    def _draw_slash_at(self, row_index: int, col_index: int, color: Color, y_offset_px: int = 0):
        base_x = col_index * CELL_SIZE
        base_y = (row_index * CELL_SIZE) + y_offset_px
        for i in range(6):
            self._set_pixel(base_x + 1 + i, base_y + 6 - i, color)

    def _draw_notification_row(self, row_index: int, cells: Sequence[str], color: Color, y_offset_px: int = 0):
        for col_index, raw_cell in enumerate(list(cells)[:8]):
            cell = str(raw_cell)
            if not cell:
                continue
            if cell == ".":
                self._draw_decimal_point_at(row_index, col_index, color, y_offset_px)
                continue
            if cell == "|":
                self._draw_vertical_bar_at(row_index, col_index, color, y_offset_px)
                continue
            if cell == "/":
                self._draw_slash_at(row_index, col_index, color, y_offset_px)
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

    def _clear_row(self, row_index: int, y_offset_px: int = 0):
        y_origin = (row_index * CELL_SIZE) + y_offset_px
        for y in range(CELL_SIZE):
            for x in range(PANEL_WIDTH):
                self._set_pixel(x, y_origin + y, (0, 0, 0))

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

    def _signed_two_digit_cells(self, value: float) -> List[str]:
        rounded = int(round(float(value)))
        sign = "-" if rounded < 0 else "+"
        magnitude = max(0, min(99, abs(rounded)))
        tens = "" if magnitude < 10 else str(magnitude // 10)
        return [sign, tens, str(magnitude % 10)]

    def _optional_three_digit_cells(self, value: float) -> List[str]:
        rounded = max(0, min(999, int(round(float(value)))))
        hundreds = "" if rounded < 100 else str(rounded // 100)
        tens = "" if rounded < 10 else str((rounded // 10) % 10)
        return [hundreds, tens, str(rounded % 10)]

    def _signed_offset_cells(self, value: float) -> List[str]:
        clamped = max(-0.9999, min(0.9999, float(value)))
        sign = "-" if clamped < 0 else "+"
        scaled = int(round(abs(clamped) * 10000))
        if scaled > 9999:
            scaled = 9999
        digits = f"{scaled:05d}"
        return [sign, f"{digits[0]}.", digits[1], digits[2], digits[3], digits[4], "", ""]

    def _nav_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        raw_nav = payload.get("nav_status", {})
        return raw_nav if isinstance(raw_nav, dict) else {}

    def _node_cells(self, node_id: object) -> List[str]:
        text = str(node_id or "").upper()[:3]
        return list((text + "___")[:3])

    def _digits(self, value: object, width: int) -> List[str]:
        try:
            number = int(round(float(value)))
        except (TypeError, ValueError):
            number = 0
        number = max(0, min((10 ** width) - 1, number))
        return list(f"{number:0{width}d}")

    def _meters_cells(self, value: object, width: int = 4) -> List[str]:
        return self._digits(value, width)

    def _time_cells(self, seconds_value: object) -> List[str]:
        try:
            seconds = max(0, int(round(float(seconds_value))))
        except (TypeError, ValueError):
            seconds = 0
        minutes = min(999, seconds // 60)
        seconds = min(59, seconds % 60)
        return [*list(f"{minutes:03d}"), "m", "", *list(f"{seconds:02d}"), "s"]

    def _latlon_rows(self, label: str, value: object, positive_hemi: str, negative_hemi: str) -> Tuple[List[str], List[str]]:
        try:
            coord = float(value)
        except (TypeError, ValueError):
            coord = 0.0
        hemi = positive_hemi if coord >= 0 else negative_hemi
        abs_coord = abs(coord)
        whole = int(abs_coord)
        frac = int(round((abs_coord - whole) * 10_000_000))
        if frac >= 10_000_000:
            whole += 1
            frac = 0
        label_cells = list((label.upper() + "   ")[:3])
        return (
            [*label_cells, ":", *list(f"{whole:03d}")[-3:], hemi],
            [".", *list(f"{frac:07d}")],
        )

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
        odometer_total_m: float = 0.0,
        y_offset_px: int = 0,
    ):
        speed_digits = self._speed_digits(speed_mph)
        for cell_index, char in enumerate(speed_digits):
            self._draw_glyph(self.digit_map.get(char, self.letter_map[" "]), cell_index, TEXT_CYAN, y_offset_px)

        # Decimal point in bottom-right of R1C1.
        self._set_pixel(7, 7 + y_offset_px, TEXT_CYAN)

        for offset, gear_char in enumerate("PRND", start=4):
            color = GEAR_GREEN_ACTIVE if gear == gear_char else GEAR_RED_DIM
            self._draw_glyph(self.letter_map.get(gear_char, self.letter_map[" "]), offset, color, y_offset_px)

        if left_signal_visible:
            self._draw_glyph_at(self.left_turn_signal, 3, 0, ARROW_YELLOW, y_offset_px)
        if right_signal_visible:
            self._draw_glyph_at(self.right_turn_signal, 3, 7, ARROW_YELLOW, y_offset_px)
        alert_txt = str(dashboard_alert).strip()
        if alert_txt:
            for offset, char in enumerate(alert_txt[:4], start=2):
                self._draw_glyph_at(self.letter_map.get(char, self.letter_map[" "]), 3, offset, ALERT_RED_DIM, y_offset_px)
        else:
            # no WARN/STOP active -> show total odometer (m) in the same 4 cells as WARN/STOP
            odo = max(0, min(9999, int(float(odometer_total_m))))
            for offset, char in enumerate(f"{odo:04d}", start=2):
                self._draw_glyph_at(self.digit_map.get(char, self.letter_map[" "]), 3, offset, TEXT_WHITE, y_offset_px)
        for row_offset, cells in enumerate(list(notification_rows)[:2], start=1):
            self._draw_notification_row(row_offset, cells, NOTIFICATION_WHITE, y_offset_px)

    def _draw_page_two(self, payload: Dict[str, object], y_offset_px: int = 0):
        servo_cells = self._format_three_digits(float(payload.get("servo_deg", 90.0)))
        throttle_cells = self._format_percent_cells(float(payload.get("throttle_percent", 0)))
        brake_cells = self._format_percent_cells(float(payload.get("brake_percent", 0)))
        mode = str(payload.get("drive_mode", "MAN")).upper()[:3]
        nav = self._nav_payload(payload)
        if bool(nav.get("active", False)):
            mode = "NAV"
        if mode == "CC":
            mode = " CC"
        if len(mode) < 3:
            mode = (mode + "   ")[:3]
        self._draw_text_row(0, ["S", "R", "V", "O", ":", *servo_cells], TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["T", "T", "L", "E", ":", *throttle_cells], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["B", "R", "K", "E", ":", *brake_cells], TEXT_ORANGE, y_offset_px)
        self._draw_text_row(3, ["M", "O", "D", "E", ":", mode[0], mode[1], mode[2]], ARROW_YELLOW, y_offset_px)

    def _draw_autonomy_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        # V2H2 autonomy metrics: ICSE (cause code), ADT (dist m), IPKM (interv/km), AUT (avg uptime MM.SS).
        code = (str(payload.get("autonomy_cause_code", "") or "---")[:3].upper() + "   ")[:3]
        adt = max(0, min(9999, int(float(payload.get("autonomy_distance_m", 0)))))
        ipkm = max(0, min(999, round(float(payload.get("autonomy_interv_per_km", 0.0)))))
        aut = max(0, int(float(payload.get("autonomy_avg_uptime_s", 0))))
        mm, ss = min(99, aut // 60), aut % 60
        self._draw_text_row(0, ["I", "C", "S", "E", ":", code[0], code[1], code[2]], TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["A", "D", "T", ":", *list(f"{adt:04d}")], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["I", "P", "K", "M", ":", *list(f"{ipkm:3d}")], ARROW_YELLOW, y_offset_px)
        m1, m2 = f"{mm:02d}"
        s1, s2 = f"{ss:02d}"
        self._draw_text_row(3, ["A", "U", "T", ":", m1, m2, s1, s2], TEXT_ORANGE, y_offset_px)
        self._draw_decimal_point_at(3, 5, TEXT_ORANGE, y_offset_px)           # dot between MM and SS

    def _draw_page_three(self, payload: Dict[str, object], y_offset_px: int = 0):
        # PRUN / PALL / FPS / STS
        photos_run = max(0, min(99999, int(payload.get("photos_run", 0))))
        photos_all = max(0, min(99999, int(payload.get("photos_all", 0))))
        fps_val = max(0.0, min(99.99, float(payload.get("camera_fps", 0.0))))
        fps_int = int(fps_val)
        fps_frac = int(round((fps_val - fps_int) * 100))
        sts = str(payload.get("system_status", ""))[:4].upper()
        sts_colors = {
            "GOOD": TEXT_GREEN,
            "CTRE": TEXT_CYAN,
            "SAVE": ARROW_YELLOW,
            "LINK": ALERT_RED_DIM,
            "ERR":  ALERT_RED_DIM,
        }
        sts_color = sts_colors.get(sts, TEXT_GREEN)
        sts = (sts + "    ")[:4]
        # short labels + 5-digit counts so thousands of photos display correctly
        self._draw_text_row(0, ["P", "R", ":", *self._digits(photos_run, 5)], TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["P", "A", ":", *self._digits(photos_all, 5)], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["F", "P", "S", ":", str(fps_int // 10), f"{fps_int % 10}.", str(fps_frac // 10), str(fps_frac % 10)], TEXT_ORANGE, y_offset_px)
        self._draw_text_row(3, ["S", "T", "S", ":", sts[0], sts[1], sts[2], sts[3]], sts_color, y_offset_px)

    def _draw_lidar_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        # Forward-facing view: car at bottom-centre, forward = up. Two guide rays mark the
        # +/-30 deg forward cone; points colored by range (red near -> blue far).
        car_x = PANEL_WIDTH // 2
        car_y = (PANEL_HEIGHT - 1) + y_offset_px
        scale = 9.0                       # px per metre (forward ~0..3.4 m fills the height)
        for cone_deg in (-30.0, 30.0):    # forward +/-30 deg cone guide rays
            cr = math.radians(cone_deg)
            d = 0.2
            while d <= 3.4:
                gx = int(round(car_x + math.sin(cr) * d * scale))
                gy = int(round(car_y - math.cos(cr) * d * scale))
                self._set_pixel(gx, gy, (0, 130, 200))   # brighter cone rays
                d += 0.15
        raw_points = payload.get("lidar_points", [])
        point_count = max(0, int(payload.get("lidar_point_count", 0)))
        if not raw_points:
            self._draw_text_row(0, ["L", "D", "R", ":", "N", "O", "N", "E"], ALERT_RED_DIM, y_offset_px)
            count_cells = self._format_three_digits(point_count)
            self._draw_text_row(1, ["P", "T", "S", ":", "", *count_cells], TEXT_CYAN, y_offset_px)
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
                x = int(round(car_x + math.sin(angle_rad) * distance_m * scale))
                y = int(round(car_y - math.cos(angle_rad) * distance_m * scale))
                if distance_m < 0.6:
                    color = LIDAR_POINT_RED
                elif distance_m < 1.2:
                    color = LIDAR_POINT_YELLOW
                elif distance_m < 3.0:
                    color = LIDAR_POINT_GREEN
                else:
                    color = LIDAR_POINT_BLUE
                self._set_pixel(x, y, color)
        for dx, dy in ((-1, 0), (0, 0), (1, 0), (0, -1)):
            self._set_pixel(car_x + dx, car_y + dy, LIDAR_CAR)

    def _format_model_cells(self, model_choice: str) -> List[str]:
        model_choice = str(model_choice)
        match = re.search(r"(\d+)\.(\d+)", model_choice)
        if not match:
            return ["0.", "0", ""]
        suffix = "b" if model_choice.strip().lower().endswith("b") else ""
        return [f"{match.group(1)[-1]}.", match.group(2)[0], suffix]

    def _draw_page_four(self, payload: Dict[str, object], y_offset_px: int = 0):
        model_cells = self._format_model_cells(str(payload.get("model_choice", "0.0")))
        pred_cells = self._format_three_digits(float(payload.get("servo_deg", 90.0)))
        confidence_cells = self._format_percent_cells(float(payload.get("camera_confidence_percent", 0)))
        ips = max(0.0, min(99.99, float(payload.get("infer_fps", 0.0))))
        ips_i = int(ips)
        ips_frac = min(99, int(round((ips - ips_i) * 100)))
        ips_cells = [str(ips_i // 10), f"{ips_i % 10}.", str(ips_frac // 10), str(ips_frac % 10)]
        if model_cells[2]:
            row_cells = ["M", "O", "D", "L", ":", "", model_cells[1], model_cells[2]]
            decimal_col = 5
        else:
            row_cells = ["M", "O", "D", "L", ":", "", "", model_cells[1]]
            decimal_col = 6
        self._draw_text_row(0, row_cells, TEXT_CYAN, y_offset_px)
        self._draw_glyph_at(self.digit_map.get(model_cells[0][0], self.letter_map[" "]), 0, decimal_col, TEXT_CYAN, y_offset_px)
        self._draw_model_decimal_at(0, decimal_col, TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["P", "R", "E", "D", ":", *pred_cells], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["C", "O", "N", "F", ":", *confidence_cells], ARROW_YELLOW, y_offset_px)
        self._draw_text_row(3, ["I", "P", "S", ":", *ips_cells], TEXT_ORANGE, y_offset_px)

    def _read_zero_cpu_temp(self) -> float:
        """Zero's own CPU temp (°C), cached ~2s. 0.0 if unreadable."""
        now = time.time()
        if now - getattr(self, "_ztemp_t", 0.0) < 2.0:
            return getattr(self, "_ztemp_c", 0.0)
        c = 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as fh:
                c = float(fh.read().strip()) / 1000.0
        except Exception:
            c = 0.0
        self._ztemp_t = now
        self._ztemp_c = c
        return c

    def _draw_temps_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        # v3h3 temps: RTMP=Pi CPU, JTMP=Jon CPU, GTMP=Jon GPU, ZTMP=Zero CPU
        def tcells(v):
            t = max(0, min(99, int(round(float(v)))))
            return [str(t // 10), str(t % 10), "C"]
        self._draw_text_row(0, ["R", "T", "M", "P", ":", *tcells(payload.get("cpu_temp_c", 0.0))], TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["J", "T", "M", "P", ":", *tcells(payload.get("jon_cpu_temp_c", 0.0))], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["G", "T", "M", "P", ":", *tcells(payload.get("jon_gpu_temp_c", 0.0))], ARROW_YELLOW, y_offset_px)
        self._draw_text_row(3, ["Z", "T", "M", "P", ":", *tcells(self._read_zero_cpu_temp())], TEXT_ORANGE, y_offset_px)

    def _draw_page_six(self, payload: Dict[str, object], y_offset_px: int = 0):
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

    def _draw_gps_odo_sts_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        nav = self._nav_payload(payload)
        fix = bool(nav.get("fix", False))
        fix_cells = ["Y", "E", "S"] if fix else ["", "N", "O"]
        fix_color = TEXT_GREEN if fix else ALERT_RED_DIM
        sats = max(0, int(nav.get("sats", 0) or 0))
        sats_cells = self._digits(sats, 3)
        odo_cells = self._meters_cells(nav.get("odometer_m", 0), 4)
        if sats >= 4:
            sts_cells = ["", "", "3", "D"]
            sts_color = TEXT_GREEN
        elif sats == 3:
            sts_cells = ["", "", "2", "D"]
            sts_color = ARROW_YELLOW
        else:
            sts_cells = ["N", "O", "N", "E"]
            sts_color = ALERT_RED_DIM
        self._draw_text_row(0, ["F", "I", "X", ":", "", *fix_cells], fix_color, y_offset_px)
        self._draw_text_row(1, ["S", "A", "T", "S", ":", *sats_cells], TEXT_CYAN, y_offset_px)
        self._draw_text_row(2, ["O", "D", "O", ":", *odo_cells], ARROW_YELLOW, y_offset_px)
        self._draw_text_row(3, ["S", "S", "T", ":", *sts_cells], sts_color, y_offset_px)

    def _photo_run_stats(self, payload: Dict[str, object]) -> Dict[str, int]:
        raw_stats = payload.get("photo_run_stats", {})
        if not isinstance(raw_stats, dict):
            raw_stats = {}
        stats = {}
        for key in ("left", "center", "right", "throttle_below_50"):
            try:
                stats[key] = max(0, int(raw_stats.get(key, 0)))
            except (TypeError, ValueError):
                stats[key] = 0
        return stats

    def _draw_photo_run_stats_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        stats = self._photo_run_stats(payload)
        self._draw_text_row(0, ["L", "P", ":", *self._digits(stats["left"], 5)], TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["C", "P", ":", *self._digits(stats["center"], 5)], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["R", "P", ":", *self._digits(stats["right"], 5)], TEXT_ORANGE, y_offset_px)
        self._draw_text_row(3, ["<", "5", ":", *self._digits(stats["throttle_below_50"], 5)], ARROW_YELLOW, y_offset_px)

    def _gain_cells(self, formatted: str) -> List[str]:
        """'000.5' -> ['0','0','0.','5'] : the decimal point rides on the digit cell
        before it, so a 4-digit gain + dot fits in 4 cells (matches the TUNE layout)."""
        cells: List[str] = []
        i = 0
        while i < len(formatted):
            ch = formatted[i]
            if ch == ".":
                i += 1
                continue
            if i + 1 < len(formatted) and formatted[i + 1] == ".":
                cells.append(ch + ".")
                i += 2
            else:
                cells.append(ch)
                i += 1
        return cells

    def _signed_dd_d(self, value: float) -> List[str]:
        """Signed value -> 4 cells: sign, tens, ones(with dot), tenths  (e.g. +12.3)."""
        sign = "-" if float(value) < 0 else "+"
        s = f"{min(99.9, abs(float(value))):04.1f}"   # 'dd.d'
        return [sign, s[0], s[1] + ".", s[3]]

    def _d_dd(self, value: float) -> List[str]:
        """Unsigned 0..9.99 -> 3 cells: ones(with dot), tenths, hundredths (e.g. 1.42)."""
        s = f"{min(9.99, max(0.0, float(value))):.2f}"   # 'd.dd'
        return [s[0] + ".", s[2], s[3]]

    def _draw_yaw_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        # v1h4 yaw-PID telemetry.
        #   YAW : +/- dd.d   current yaw rate (deg/s)
        #   SPD :     d.dd   speed (m/s)
        #   COR : +/- dd.d   PID correction (deg)
        #   /III|OOO         input steer | output steer (servo deg)
        yaw = float(payload.get("yaw_rate_dps", 0.0))
        spd_ms = float(payload.get("speed_mph", 0.0)) * 0.44704      # telemetry is mph -> show m/s
        cor = float(payload.get("yaw_pid_correction_deg", 0.0))
        in_cells = self._format_three_digits(float(payload.get("steering_cmd_deg", 90.0)))
        out_cells = self._format_three_digits(float(payload.get("servo_deg", 90.0)))
        self._draw_text_row(0, ["Y", "A", "W", ":", *self._signed_dd_d(yaw)], TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["S", "P", "D", ":", " ", *self._d_dd(spd_ms)], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["C", "O", "R", ":", *self._signed_dd_d(cor)], ARROW_YELLOW, y_offset_px)
        self._draw_text_row(3, ["/", *in_cells, "|", *out_cells], TEXT_ORANGE, y_offset_px)

    def _draw_tuning_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        # TUNE page. D-pad up/down picks the row (white), left/right dec/inc.
        #   DELT : +/- N N     center trim (deg)
        #   kP   :  d d d. d   yaw Kp   (dot after 3rd digit)
        #   kI   :  d d. d d   yaw Ki   (dot after 2nd digit)
        #   kD   :  d. d d d   yaw Kd   (dot after 1st digit)
        delta = float(payload.get("steering_trim_delta_deg", 0.0))
        kp = min(99.99, max(0.0, float(payload.get("yaw_kp", 0.0))))
        ki = min(99.99, max(0.0, float(payload.get("yaw_ki", 0.0))))
        kd = min(9.999, max(0.0, float(payload.get("yaw_kd", 0.0))))
        selected = max(0, min(3, int(payload.get("tune_selected_row", 0))))
        rows = [
            (["D", "E", "L", "T", ":", *self._signed_two_digit_cells(delta)], TEXT_CYAN),
            (["k", "P", ":", " ", *self._gain_cells(f"{kp:05.2f}")], ARROW_YELLOW),
            (["k", "I", ":", " ", *self._gain_cells(f"{ki:05.2f}")], TEXT_GREEN),
            (["k", "D", ":", " ", *self._gain_cells(f"{kd:05.3f}")], TEXT_ORANGE),
        ]
        for panel_row, (cells, color) in enumerate(rows):
            if panel_row == selected:
                color = TEXT_WHITE
            self._draw_text_row(panel_row, cells, color, y_offset_px)

    def _draw_nav_entry_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        nav = self._nav_payload(payload)
        if bool(nav.get("arrived_visible", False)):
            node = self._node_cells(nav.get("arrived_node", nav.get("closest_node", "")))
            self._draw_text_row(0, ["", "", "E", "N", "D", "E", "D", ""], TEXT_GREEN, y_offset_px)
            self._draw_text_row(2, ["A", "R", "R", "I", "V", "E", "D", "@"], TEXT_GREEN, y_offset_px)
            self._draw_text_row(3, ["", "", "", node[0], node[1], node[2], "", ""], TEXT_GREEN, y_offset_px)
            return

        start_cells = self._node_cells(nav.get("start_id", ""))
        end_cells = self._node_cells(nav.get("end_id", ""))
        phase = str(nav.get("entry_phase", "end"))
        confirm_yes = bool(nav.get("confirm_yes", True))
        if bool(nav.get("active", False)):
            confirm_cells = ["C", "A", "N", "C", "E", "L", ":", "X"]
            confirm_color = TEXT_ORANGE if confirm_yes else ALERT_RED_DIM
        elif bool(nav.get("entry_error", False)):
            confirm_cells = ["E", "R", "R", "O", "R", "", "", ""]
            confirm_color = ALERT_RED_DIM
        else:
            confirm_cells = ["S", "T", "A", "R", "T", ":", "X", ""]
            confirm_color = TEXT_ORANGE
        self._draw_text_row(0, list("NAVIGATE"), TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["F", "R", "M", ":", "", *start_cells], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["T", "O", " ", ":", "", *end_cells], ARROW_YELLOW, y_offset_px)
        if phase == "end":
            cursor = max(0, min(2, int(nav.get("entry_cursor", 0) or 0)))
            active_cell = end_cells[cursor]
            if active_cell.isdigit():
                glyph = self.digit_map.get(active_cell, self.letter_map[" "])
            else:
                glyph = self.letter_map.get(active_cell, self.letter_map[" "])
            self._draw_glyph_at(glyph, 2, 5 + cursor, ALERT_RED_DIM, y_offset_px)
        self._draw_text_row(3, confirm_cells, confirm_color, y_offset_px)

    def _draw_gps_status_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        nav = self._nav_payload(payload)
        fix_cells = ["Y", "E", "S"] if bool(nav.get("fix", False)) else ["", "N", "O"]
        sats_cells = self._digits(nav.get("sats", 0), 3)
        cnde = self._node_cells(nav.get("closest_node", ""))
        odo = self._meters_cells(nav.get("odometer_m", 0), 4)
        self._draw_text_row(0, ["F", "I", "X", ":", "", *fix_cells], TEXT_GREEN if bool(nav.get("fix", False)) else ALERT_RED_DIM, y_offset_px)
        self._draw_text_row(1, ["S", "A", "T", "S", ":", *sats_cells], TEXT_CYAN, y_offset_px)
        self._draw_text_row(2, ["C", "N", "D", "E", ":", *cnde], ARROW_YELLOW, y_offset_px)
        self._draw_text_row(3, ["O", "D", "O", ":", *odo], TEXT_GREEN, y_offset_px)

    def _draw_route_nodes_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        nav = self._nav_payload(payload)
        active = bool(nav.get("active", False))
        blank = ["", "", ""]
        operator = str(nav.get("operator", "MNUL")).upper()[:4] if active else "    "
        operator = (operator + "    ")[:4]
        pnde = self._node_cells(nav.get("previous_node", "")) if active else blank
        cnde = self._node_cells(nav.get("closest_node", "")) if active else blank
        nnde = self._node_cells(nav.get("next_node", "")) if active else blank
        self._draw_text_row(0, ["O", "P", "R", ":", *list(operator)], TEXT_CYAN, y_offset_px)
        self._draw_text_row(1, ["P", "N", "D", "E", ":", *pnde], TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["C", "N", "D", "E", ":", *cnde], ARROW_YELLOW, y_offset_px)
        self._draw_text_row(3, ["N", "N", "D", "E", ":", *nnde], TEXT_ORANGE, y_offset_px)

    def _draw_latlon_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        nav = self._nav_payload(payload)
        lat_top, lat_bottom = self._latlon_rows("LAT", nav.get("lat", 0.0), "N", "S")
        lon_top, lon_bottom = self._latlon_rows("LON", nav.get("lon", 0.0), "E", "W")
        self._draw_text_row(0, lat_top, TEXT_GREEN, y_offset_px)
        self._draw_text_row(1, lat_bottom, TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, lon_top, TEXT_CYAN, y_offset_px)
        self._draw_text_row(3, lon_bottom, TEXT_CYAN, y_offset_px)

    def _draw_route_distance_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        nav = self._nav_payload(payload)
        active = bool(nav.get("active", False))
        rdt = nav.get("remaining_distance_m", 0) if active else None
        ndt = nav.get("next_node_distance_m", 0) if active else None
        sdt = nav.get("start_distance_m", 0) if active else None
        tdt = nav.get("total_distance_m", 0) if active else None
        blank = ["", "", "", ""]
        self._draw_text_row(0, ["R", "D", "T", ":", *(self._meters_cells(rdt, 4) if rdt is not None else blank)], TEXT_GREEN, y_offset_px)
        self._draw_text_row(1, ["N", "D", "T", ":", *(self._meters_cells(ndt, 4) if ndt is not None else blank)], TEXT_CYAN, y_offset_px)
        self._draw_text_row(2, ["S", "D", "T", ":", *(self._meters_cells(sdt, 4) if sdt is not None else blank)], ARROW_YELLOW, y_offset_px)
        self._draw_text_row(3, ["T", "D", "T", ":", *(self._meters_cells(tdt, 4) if tdt is not None else blank)], TEXT_ORANGE, y_offset_px)

    def _draw_route_time_page(self, payload: Dict[str, object], y_offset_px: int = 0):
        nav = self._nav_payload(payload)
        active = bool(nav.get("active", False))
        blank = ["", "", "", "", "", "", "", ""]
        self._draw_text_row(0, ["R", "T", "M", ":", "", "", "", ""], TEXT_GREEN, y_offset_px)
        self._draw_text_row(1, self._time_cells(nav.get("remaining_time_s", 0)) if active else blank, TEXT_GREEN, y_offset_px)
        self._draw_text_row(2, ["N", "T", "M", ":", "", "", "", ""], TEXT_CYAN, y_offset_px)
        self._draw_text_row(3, self._time_cells(nav.get("next_node_time_s", 0)) if active else blank, TEXT_CYAN, y_offset_px)

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
            self._draw_page_four(payload, y_offset_px)
            return
        if page == 4:
            self._draw_autonomy_page(payload, y_offset_px)
            return
        if page == 5:
            self._draw_nav_entry_page(payload, y_offset_px)
            return
        if page == 6:
            self._draw_gps_odo_sts_page(payload, y_offset_px)
            return
        if page == 7:
            self._draw_route_nodes_page(payload, y_offset_px)
            return
        if page == 8:
            self._draw_latlon_page(payload, y_offset_px)
            return
        if page == 9:
            self._draw_route_distance_page(payload, y_offset_px)
            return
        if page == 10:
            self._draw_route_time_page(payload, y_offset_px)
            return
        if page == 11:
            self._draw_page_six(payload, y_offset_px)
            return
        if page == 12:
            self._draw_photo_run_stats_page(payload, y_offset_px)
            return
        if page == 13:
            self._draw_tuning_page(payload, y_offset_px)
            return
        if page == 14:
            self._draw_page_three(payload, y_offset_px)   # V3H1 photo counters (PR/PA/FPS/STS)
            return
        if page == 15:
            self._draw_yaw_page(payload, y_offset_px)
            return
        if page == 16:
            self._draw_temps_page(payload, y_offset_px)
            return
        if page == 17:
            self._draw_lidar_page(payload, y_offset_px)   # V7H1 lidar scan (forward +/-30 cone)
            return
        self._draw_page_one(
            float(payload.get("speed_mph", 0.0)),
            str(payload.get("gear", "P"))[:1],
            bool(payload.get("left_signal_visible", False)),
            bool(payload.get("right_signal_visible", False)),
            str(payload.get("dashboard_alert", ""))[:4],
            notification_rows,
            float(self._nav_payload(payload).get("odometer_m", 0.0)),  # same source as the V5 ODO
            y_offset_px,
        )

    def _draw_page_with_offset(
        self,
        page: int,
        payload: Dict[str, object],
        notification_rows: Sequence[Sequence[str]],
        x_offset_px: int = 0,
        y_offset_px: int = 0,
    ):
        previous_x_offset = self.render_x_offset_px
        self.render_x_offset_px = x_offset_px
        try:
            self._draw_page(page, payload, notification_rows, y_offset_px)
        finally:
            self.render_x_offset_px = previous_x_offset

    def render(self, payload: Dict[str, object], notification_rows: Sequence[Sequence[str]]):
        requested_page = max(1, min(DASHBOARD_PAGE_COUNT, int(payload.get("dashboard_page", self.current_page))))
        transition = str(payload.get("dashboard_page_transition", ""))
        if requested_page != self.current_page:
            self.previous_page = self.current_page
            self.current_page = requested_page
            if transition in ("right", "left"):
                self.transition_axis = "horizontal"
                self.transition_direction = 1 if transition == "right" else -1
            else:
                self.transition_axis = "vertical"
                if transition in ("forward", "back"):
                    self.transition_direction = 1 if transition == "forward" else -1
                else:
                    self.transition_direction = 1 if requested_page > self.previous_page else -1
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
            self._draw_page_with_offset(self.current_page, payload, notification_rows, 0, 0)
        else:
            if self.transition_axis == "horizontal":
                shift_px = int(round(progress * PANEL_WIDTH))
                if self.transition_direction > 0:
                    previous_offset = -shift_px
                    current_offset = PANEL_WIDTH - shift_px
                else:
                    previous_offset = shift_px
                    current_offset = -PANEL_WIDTH + shift_px
                self._draw_page_with_offset(self.previous_page, payload, notification_rows, previous_offset, 0)
                self._draw_page_with_offset(self.current_page, payload, notification_rows, current_offset, 0)
            else:
                shift_px = int(round(progress * PANEL_HEIGHT))
                if self.transition_direction > 0:
                    previous_offset = -shift_px
                    current_offset = PANEL_HEIGHT - shift_px
                else:
                    previous_offset = shift_px
                    current_offset = -PANEL_HEIGHT + shift_px
                self._draw_page_with_offset(self.previous_page, payload, notification_rows, 0, previous_offset)
                self._draw_page_with_offset(self.current_page, payload, notification_rows, 0, current_offset)

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


def parse_args():
    parser = argparse.ArgumentParser(description="Zero 2 W dashboard receiver for HUB75 and MAX7219 displays")
    parser.add_argument("--transport", choices=("udp", "serial"), default="udp")
    parser.add_argument("--serial-port", default="/dev/ttyGS0")
    parser.add_argument("--baud-rate", type=int, default=115200)
    parser.add_argument("--udp-host", default="0.0.0.0")
    parser.add_argument("--udp-port", type=int, default=8765)
    parser.add_argument("--led-slowdown-gpio", type=int, default=2)
    parser.add_argument("--led-row-addr-type", type=int, default=0)
    parser.add_argument("--led-multiplexing", type=int, default=0)
    parser.add_argument("--led-panel-type", default="")
    parser.add_argument("--led-brightness", type=int, default=70)
    parser.add_argument("--led-pwm-bits", type=int, default=7)
    parser.add_argument("--led-limit-refresh", type=int, default=120)
    parser.add_argument("--led-rgb-sequence", default="RGB")
    parser.add_argument("--led-no-hardware-pulse", action="store_true")
    parser.add_argument("--idle-exit-sec", type=float, default=0.0)
    return parser.parse_args()


def main():
    args = parse_args()
    renderer = DashboardRenderer(
        slowdown_gpio=args.led_slowdown_gpio,
        panel_type=args.led_panel_type,
        brightness=args.led_brightness,
        pwm_bits=args.led_pwm_bits,
        row_addr_type=args.led_row_addr_type,
        multiplexing=args.led_multiplexing,
        limit_refresh_rate_hz=args.led_limit_refresh,
        rgb_sequence=args.led_rgb_sequence,
        no_hardware_pulse=args.led_no_hardware_pulse,
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
    yaw_rate_dps = 0.0
    yaw_pid_correction_deg = 0.0
    steering_cmd_deg = 90.0
    throttle_percent = 0
    brake_percent = 0
    drive_mode = "MAN"
    lidar_points: List[List[float]] = []
    lidar_point_count = 0
    model_choice = ""
    camera_confidence_percent = 0
    cpu_temp_c = 0.0
    jon_cpu_temp_c = 0.0
    jon_gpu_temp_c = 0.0
    infer_fps = 0.0
    camera_pixels: List[str] = []
    photos_run = 0
    photos_all = 0
    photo_run_stats: Dict[str, int] = {}
    camera_fps = 0.0
    system_status = "GOOD"
    nav_status: Dict[str, object] = {}
    steering_trim_delta_deg = 0.0
    steering_trim_total_deg = 90.0
    steering_center_offset = 0.0
    tune_selected_row = 0
    yaw_kp = 0.0
    yaw_ki = 0.0
    yaw_kd = 0.0
    receiver_start_time = time.monotonic()
    last_packet_time = time.monotonic()
    have_received_payload = False
    telemetry_stale_reported = False
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

    def render_current_state(status_override: str | None = None) -> None:
        notification_rows = update_notification_rows()
        now = time.monotonic()
        if not have_received_payload:
            if now - receiver_start_time >= 3.0:
                notification_rows.insert(0, ["N", "O", "", "L", "I", "N", "K", ""])
                status_override = status_override or "LINK"
        elif now - last_packet_time >= TELEMETRY_STALE_DISPLAY_SEC:
            notification_rows.insert(0, ["S", "T", "A", "L", "E", "", "", ""])
            status_override = status_override or "LINK"
        notification_rows = notification_rows[:2]
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
                "yaw_rate_dps": yaw_rate_dps,
                "yaw_pid_correction_deg": yaw_pid_correction_deg,
                "steering_cmd_deg": steering_cmd_deg,
                "throttle_percent": throttle_percent,
                "brake_percent": brake_percent,
                "drive_mode": drive_mode,
                "lidar_points": lidar_points,
                "lidar_point_count": lidar_point_count,
                "model_choice": model_choice,
                "camera_confidence_percent": camera_confidence_percent,
                "cpu_temp_c": cpu_temp_c,
                "jon_cpu_temp_c": jon_cpu_temp_c,
                "jon_gpu_temp_c": jon_gpu_temp_c,
                "infer_fps": infer_fps,
                "camera_pixels": camera_pixels,
                "photos_run": photos_run,
                "photos_all": photos_all,
                "photo_run_stats": photo_run_stats,
                "camera_fps": camera_fps,
                "system_status": status_override or system_status,
                "nav_status": nav_status,
                "steering_trim_delta_deg": steering_trim_delta_deg,
                "steering_trim_total_deg": steering_trim_total_deg,
                "steering_center_offset": steering_center_offset,
                "tune_selected_row": tune_selected_row,
                "yaw_kp": yaw_kp,
                "yaw_ki": yaw_ki,
                "yaw_kd": yaw_kd,
            },
            notification_rows,
        )

    def handle_idle() -> int | None:
        nonlocal telemetry_stale_reported
        if args.idle_exit_sec > 0.0 and have_received_payload and time.monotonic() - last_packet_time >= args.idle_exit_sec:
            if not telemetry_stale_reported:
                print(
                    "Dashboard telemetry idle; exiting "
                    f"({args.idle_exit_sec:.1f}s without packets)."
                )
                telemetry_stale_reported = True
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
        nonlocal yaw_rate_dps
        nonlocal yaw_pid_correction_deg
        nonlocal steering_cmd_deg
        nonlocal throttle_percent
        nonlocal brake_percent
        nonlocal drive_mode
        nonlocal lidar_points
        nonlocal lidar_point_count
        nonlocal model_choice
        nonlocal camera_confidence_percent
        nonlocal cpu_temp_c
        nonlocal jon_cpu_temp_c
        nonlocal jon_gpu_temp_c
        nonlocal infer_fps
        nonlocal camera_pixels
        nonlocal photos_run
        nonlocal photos_all
        nonlocal photo_run_stats
        nonlocal camera_fps
        nonlocal system_status
        nonlocal nav_status
        nonlocal steering_trim_delta_deg
        nonlocal steering_trim_total_deg
        nonlocal steering_center_offset
        nonlocal tune_selected_row
        nonlocal yaw_kp
        nonlocal yaw_ki
        nonlocal yaw_kd
        nonlocal telemetry_stale_reported

        if payload.get("shutdown"):
            print("Dashboard receiver shutdown requested by controller.")
            return 0

        have_received_payload = True
        telemetry_stale_reported = False
        last_packet_time = time.monotonic()
        latest_speed = float(payload.get("speed_mph", latest_speed))
        latest_gear = str(payload.get("gear", latest_gear))[:1]
        left_signal_visible = bool(payload.get("left_signal_visible", left_signal_visible))
        right_signal_visible = bool(payload.get("right_signal_visible", right_signal_visible))
        dashboard_alert = str(payload.get("dashboard_alert", dashboard_alert))[:4]
        brightness_percent = max(0, min(100, int(payload.get("brightness_percent", brightness_percent))))
        dashboard_page = max(1, min(DASHBOARD_PAGE_COUNT, int(payload.get("dashboard_page", dashboard_page))))
        dashboard_page_transition = str(payload.get("dashboard_page_transition", ""))[:8]
        servo_deg = max(0.0, min(180.0, float(payload.get("servo_deg", servo_deg))))
        yaw_rate_dps = float(payload.get("yaw_rate_dps", yaw_rate_dps))
        yaw_pid_correction_deg = float(payload.get("yaw_pid_correction_deg", yaw_pid_correction_deg))
        steering_cmd_deg = max(0.0, min(180.0, float(payload.get("steering_cmd_deg", steering_cmd_deg))))
        throttle_percent = max(0, min(100, int(payload.get("throttle_percent", throttle_percent))))
        brake_percent = max(0, min(100, int(payload.get("brake_percent", brake_percent))))
        drive_mode = str(payload.get("drive_mode", drive_mode)).upper()[:3]
        model_choice = str(payload.get("model_choice", model_choice))[:4]
        camera_confidence_percent = max(0, min(100, int(payload.get("camera_confidence_percent", camera_confidence_percent))))
        cpu_temp_c = max(0.0, min(99.0, float(payload.get("cpu_temp_c", cpu_temp_c))))
        jon_cpu_temp_c = max(0.0, min(99.0, float(payload.get("jon_cpu_temp_c", jon_cpu_temp_c))))
        jon_gpu_temp_c = max(0.0, min(99.0, float(payload.get("jon_gpu_temp_c", jon_gpu_temp_c))))
        infer_fps = max(0.0, min(99.99, float(payload.get("infer_fps", infer_fps))))
        raw_lidar_points = payload.get("lidar_points", lidar_points)
        if isinstance(raw_lidar_points, list):
            lidar_points = raw_lidar_points[:180]
        lidar_point_count = max(0, int(payload.get("lidar_point_count", len(lidar_points))))
        raw_camera_pixels = payload.get("camera_pixels", camera_pixels)
        if isinstance(raw_camera_pixels, list):
            camera_pixels = [str(row)[: PANEL_WIDTH * 4] for row in raw_camera_pixels[:PANEL_HEIGHT]]
        photos_run = max(0, int(payload.get("photos_run", photos_run)))
        photos_all = max(0, int(payload.get("photos_all", photos_all)))
        raw_photo_run_stats = payload.get("photo_run_stats", photo_run_stats)
        if isinstance(raw_photo_run_stats, dict):
            photo_run_stats = dict(raw_photo_run_stats)
        camera_fps = max(0.0, float(payload.get("camera_fps", camera_fps)))
        system_status = str(payload.get("system_status", system_status))[:4].upper() or "GOOD"
        raw_nav_status = payload.get("nav_status", nav_status)
        if isinstance(raw_nav_status, dict):
            nav_status = dict(raw_nav_status)
        steering_trim_delta_deg = max(
            -180.0,
            min(180.0, float(payload.get("steering_trim_delta_deg", steering_trim_delta_deg))),
        )
        steering_trim_total_deg = max(
            0.0,
            min(180.0, float(payload.get("steering_trim_total_deg", steering_trim_total_deg))),
        )
        steering_center_offset = max(
            -1.0,
            min(1.0, float(payload.get("steering_center_offset", steering_center_offset))),
        )
        tune_selected_row = max(0, min(4, int(payload.get("tune_selected_row", tune_selected_row))))
        yaw_kp = max(0.0, float(payload.get("yaw_kp", yaw_kp)))
        yaw_ki = max(0.0, float(payload.get("yaw_ki", yaw_ki)))
        yaw_kd = max(0.0, float(payload.get("yaw_kd", yaw_kd)))
        renderer.set_brightness(brightness_percent)
        notification = payload.get("dashboard_notification")
        if isinstance(notification, dict):
            raw_cells = notification.get("cells", [])
            if isinstance(raw_cells, list):
                cells = [str(cell)[:2] for cell in raw_cells[:8]]
                if len(cells) < 8:
                    cells.extend([""] * (8 - len(cells)))
                now = time.monotonic()
                prune_expired_notifications(now)
                duration_sec = max(0.1, float(notification.get("duration_sec", 2.0)))
                duplicate_notification = False
                for active_notification in active_notifications:
                    if list(active_notification.get("cells", []))[:8] == cells:
                        active_notification["duration_sec"] = duration_sec
                        active_notification["expires_at"] = now + duration_sec
                        duplicate_notification = True
                        break
                if duplicate_notification:
                    render_current_state()
                    return None
                if len(active_notifications) >= 2:
                    active_notifications.pop(0)
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


if __name__ == "__main__":
    raise SystemExit(main())
