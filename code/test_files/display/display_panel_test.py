#!/usr/bin/env python3
"""
Display panel tester for Raspberry Pi Zero 2 W.

Tests the 64x32 HUB75 RGB matrix using direct BCM GPIO bit-banging.

Run examples:
    python3 code/test_files/display/display_panel_test.py
    python3 code/test_files/display/display_panel_test.py --glyph-set digits
"""

from __future__ import annotations

import argparse
import re
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    from gpiozero import DigitalOutputDevice
except ImportError:
    DigitalOutputDevice = None

try:
    import RPi.GPIO as RPI_GPIO
except Exception:
    RPI_GPIO = None

try:
    from gpiozero.pins.lgpio import LGPIOFactory
except Exception:
    LGPIOFactory = None


Color = Tuple[int, int, int]
Frame = List[List[Color]]
Glyph = List[int]


BASE_DIR = Path(__file__).resolve().parents[2]
CURRENT_DIR = BASE_DIR / "controller" / "current"
BITMAPS_DIR = CURRENT_DIR / "8x8_bitmaps"
GLYPH_FILES: Dict[str, Path] = {
    "digits": BITMAPS_DIR / "digits.h",
    "letters": BITMAPS_DIR / "letters.h",
    "signs": BITMAPS_DIR / "signs.h",
}
GLYPH_LABELS: Dict[str, List[str]] = {
    "digits": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "10"],
    "letters": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["space"] + list("abcdefghijklmnopqrstuvwxyz"),
    "signs": [f"sign_{index:02d}" for index in range(57)],
}


def load_glyphs_from_header(path: Path) -> List[Glyph]:
    text = path.read_text(encoding="utf-8")
    values = [int(match.group(1), 2) for match in re.finditer(r"0b([01]{8})", text)]
    if len(values) % 8 != 0:
        raise ValueError(f"{path} does not contain a whole number of 8-row glyphs")
    return [values[index:index + 8] for index in range(0, len(values), 8)]


class Hub75MatrixTest:
    WIDTH = 64
    HEIGHT = 32
    CELL_SIZE = 8
    GRID_WIDTH = WIDTH // CELL_SIZE
    GRID_HEIGHT = HEIGHT // CELL_SIZE
    GRID_SLOTS = GRID_WIDTH * GRID_HEIGHT

    def __init__(self) -> None:
        if DigitalOutputDevice is None:
            print("Missing dependency: gpiozero")
            print("Install on the Pi with: sudo apt install python3-gpiozero")
            raise SystemExit(1)
        self.pin_r1 = 5
        self.pin_g1 = 6
        self.pin_b1 = 12
        self.pin_r2 = 13
        self.pin_g2 = 16
        self.pin_b2 = 19
        self.pin_a = 20
        self.pin_b = 21
        self.pin_c = 22
        self.pin_d = 23
        self.pin_clk = 25
        self.pin_lat = 26
        self.pin_oe = 27

        self.data_pins = [
            self.pin_r1,
            self.pin_g1,
            self.pin_b1,
            self.pin_r2,
            self.pin_g2,
            self.pin_b2,
        ]
        self.addr_pins = [self.pin_a, self.pin_b, self.pin_c, self.pin_d]
        self.all_pins = self.data_pins + self.addr_pins + [self.pin_clk, self.pin_lat, self.pin_oe]

        self.pin_factory = None
        self.use_rpi_gpio = RPI_GPIO is not None

        if self.use_rpi_gpio:
            RPI_GPIO.setmode(RPI_GPIO.BCM)
            RPI_GPIO.setwarnings(False)
            RPI_GPIO.setup(self.all_pins, RPI_GPIO.OUT, initial=RPI_GPIO.LOW)
            RPI_GPIO.output(self.pin_oe, RPI_GPIO.HIGH)
            self.outputs = {}
            print("HUB75: using RPi.GPIO backend for faster refresh.")
            return

        if LGPIOFactory is not None:
            try:
                self.pin_factory = LGPIOFactory()
                print("HUB75: using lgpio pin factory.")
            except Exception as exc:
                print(f"HUB75: lgpio unavailable, falling back to default gpiozero backend: {exc}")

        self.outputs = {
            pin: self._create_output(pin)
            for pin in self.all_pins
        }
        self.outputs[self.pin_oe].on()

    def cleanup(self) -> None:
        self.blank()
        if self.use_rpi_gpio:
            try:
                RPI_GPIO.cleanup(self.all_pins)
            except Exception:
                pass
            return
        for device in self.outputs.values():
            try:
                device.close()
            except Exception:
                pass

    def blank(self) -> None:
        self._write(self.pin_oe, True)
        for pin in self.data_pins + [self.pin_clk, self.pin_lat]:
            self._write(pin, False)

    def _create_output(self, pin: int) -> DigitalOutputDevice:
        kwargs = {"pin": pin, "initial_value": False}
        if self.pin_factory is not None:
            kwargs["pin_factory"] = self.pin_factory
        return DigitalOutputDevice(**kwargs)

    def _write(self, pin: int, value: bool) -> None:
        if self.use_rpi_gpio:
            RPI_GPIO.output(pin, RPI_GPIO.HIGH if value else RPI_GPIO.LOW)
        else:
            self.outputs[pin].value = bool(value)

    def set_row_address(self, row: int) -> None:
        for bit_index, pin in enumerate(self.addr_pins):
            self._write(pin, bool((row >> bit_index) & 0x01))

    def shift_pixel_pair(self, top: Color, bottom: Color) -> None:
        self._write(self.pin_r1, bool(top[0]))
        self._write(self.pin_g1, bool(top[1]))
        self._write(self.pin_b1, bool(top[2]))
        self._write(self.pin_r2, bool(bottom[0]))
        self._write(self.pin_g2, bool(bottom[1]))
        self._write(self.pin_b2, bool(bottom[2]))
        self._write(self.pin_clk, True)
        self._write(self.pin_clk, False)

    def latch(self) -> None:
        self._write(self.pin_lat, True)
        self._write(self.pin_lat, False)

    def draw_row(self, frame: Frame, row_pair: int, on_time: float) -> None:
        top_row = row_pair
        bottom_row = row_pair + 16

        self._write(self.pin_oe, True)
        self.set_row_address(row_pair)

        for col in range(self.WIDTH):
            self.shift_pixel_pair(frame[top_row][col], frame[bottom_row][col])

        self.latch()
        self._write(self.pin_oe, False)
        time.sleep(on_time)
        self._write(self.pin_oe, True)

    def show_frame(self, frame: Frame, duration: float, row_on_time: float = 0.00025) -> None:
        end_time = time.monotonic() + duration
        while time.monotonic() < end_time:
            for row_pair in range(16):
                self.draw_row(frame, row_pair, row_on_time)

    def solid_frame(self, color: Color) -> Frame:
        return [[color for _ in range(self.WIDTH)] for _ in range(self.HEIGHT)]

    def vertical_bars_frame(self) -> Frame:
        colors: Sequence[Color] = [
            (1, 0, 0),
            (0, 1, 0),
            (0, 0, 1),
            (1, 1, 0),
            (0, 1, 1),
            (1, 0, 1),
            (1, 1, 1),
            (0, 0, 0),
        ]
        bar_width = self.WIDTH // len(colors)
        frame = self.solid_frame((0, 0, 0))
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                frame[y][x] = colors[min(x // bar_width, len(colors) - 1)]
        return frame

    def checker_frame(self, block_size: int = 4) -> Frame:
        frame = self.solid_frame((0, 0, 0))
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if ((x // block_size) + (y // block_size)) % 2 == 0:
                    frame[y][x] = (1, 1, 1)
        return frame

    def crosshair_frame(self) -> Frame:
        frame = self.solid_frame((0, 0, 0))
        mid_x = self.WIDTH // 2
        mid_y = self.HEIGHT // 2
        for x in range(self.WIDTH):
            frame[mid_y][x] = (1, 1, 1)
        for y in range(self.HEIGHT):
            frame[y][mid_x] = (1, 1, 1)
        for x in range(self.WIDTH):
            frame[0][x] = (1, 0, 0)
            frame[self.HEIGHT - 1][x] = (0, 0, 1)
        for y in range(self.HEIGHT):
            frame[y][0] = (0, 1, 0)
            frame[y][self.WIDTH - 1] = (1, 1, 0)
        return frame

    def repeated_glyph_frame(self, glyph: Sequence[int], color: Color) -> Frame:
        frame = self.solid_frame((0, 0, 0))
        for slot_index in range(self.GRID_SLOTS):
            cell_x = (slot_index % self.GRID_WIDTH) * self.CELL_SIZE
            cell_y = (slot_index // self.GRID_WIDTH) * self.CELL_SIZE

            for row in range(8):
                row_bits = glyph[row]
                for bit in range(8):
                    if row_bits & (1 << (7 - bit)):
                        frame[cell_y + row][cell_x + bit] = color
        return frame

    def display_glyph_set(self, set_name: str, seconds_per_page: float = 1.6) -> None:
        path = GLYPH_FILES[set_name]
        glyphs = load_glyphs_from_header(path)
        labels = GLYPH_LABELS.get(set_name, [])
        colors: Dict[str, Color] = {
            "digits": (1, 1, 1),
            "letters": (1, 1, 1),
            "signs": (1, 1, 1),
        }
        color = colors.get(set_name, (1, 1, 1))

        print(f"HUB75: {set_name} from {path}")
        for index, glyph in enumerate(glyphs):
            label = labels[index] if index < len(labels) else f"{set_name}_{index}"
            print(f"  {index:02d}: {label}")
            frame = self.repeated_glyph_frame(glyph, color)
            self.show_frame(frame, seconds_per_page)

    def run_glyph_demo(self, glyph_set: str) -> None:
        if glyph_set not in ("digits", "letters", "signs", "all"):
            return
        sets = ["digits", "letters", "signs"] if glyph_set == "all" else [glyph_set]
        for set_name in sets:
            self.display_glyph_set(set_name)

    def run_demo(self, glyph_set: str) -> None:
        if glyph_set in ("digits", "letters", "signs", "all"):
            self.run_glyph_demo(glyph_set)
            self.blank()
            return

        sequence = [
            ("HUB75: red", self.solid_frame((1, 0, 0)), 1.5),
            ("HUB75: green", self.solid_frame((0, 1, 0)), 1.5),
            ("HUB75: blue", self.solid_frame((0, 0, 1)), 1.5),
            ("HUB75: white", self.solid_frame((1, 1, 1)), 1.5),
            ("HUB75: bars", self.vertical_bars_frame(), 2.0),
            ("HUB75: checker", self.checker_frame(), 2.0),
            ("HUB75: alignment", self.crosshair_frame(), 2.0),
        ]

        for label, frame, seconds in sequence:
            print(label)
            self.show_frame(frame, seconds)

        self.blank()


def install_signal_handlers(cleanups: Iterable) -> None:
    def handler(signum, frame) -> None:  # type: ignore[unused-argument]
        for cleanup in cleanups:
            try:
                cleanup()
            except Exception:
                pass
        raise SystemExit(130)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LED matrix panel tester for Raspberry Pi Zero 2 W")
    parser.add_argument(
        "--glyph-set",
        choices=["digits", "letters", "signs", "all", "none"],
        default="all",
        help="Glyph set to load from code/controller/current for the glyph test",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    cleanups = []

    try:
        hub75 = Hub75MatrixTest()
        cleanups.append(hub75.cleanup)

        install_signal_handlers(cleanups)

        print("Wiring summary")
        print("HUB75 RGB matrix: BCM 5,6,12,13,16,19,20,21,22,23,25,26,27")
        print("Press Ctrl+C to stop.\n")

        hub75.run_demo(args.glyph_set)

        return 0
    finally:
        for cleanup in reversed(cleanups):
            try:
                cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
