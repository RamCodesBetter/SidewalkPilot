#!/usr/bin/env python3
"""
Display panel tester for Raspberry Pi Zero 2 W.

Supports:
- 64x32 HUB75 RGB matrix using direct BCM GPIO bit-banging
- 8x32 MAX7219 LED matrix using SPI0 / CE0

Run examples:
    python3 code/test_files/display_panel_test.py --panel both
    python3 code/test_files/display_panel_test.py --panel hub75
    python3 code/test_files/display_panel_test.py --panel max7219
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
    import spidev
except ImportError:
    spidev = None

try:
    from gpiozero.pins.lgpio import LGPIOFactory
except Exception:
    LGPIOFactory = None


Color = Tuple[int, int, int]
Frame = List[List[Color]]
Glyph = List[int]


BASE_DIR = Path(__file__).resolve().parents[1]
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


class Max7219PanelTest:
    REG_NOOP = 0x00
    REG_DIGIT0 = 0x01
    REG_DECODEMODE = 0x09
    REG_INTENSITY = 0x0A
    REG_SCANLIMIT = 0x0B
    REG_SHUTDOWN = 0x0C
    REG_DISPLAYTEST = 0x0F

    def __init__(self, device_count: int = 4, bus: int = 0, device: int = 0) -> None:
        if spidev is None:
            print("Missing dependency: spidev")
            print("Install on the Pi with: sudo apt install python3-spidev")
            raise SystemExit(1)

        self.device_count = device_count
        self.spi = spidev.SpiDev()
        device_path = Path(f"/dev/spidev{bus}.{device}")
        if device_path.exists() and hasattr(self.spi, "open_path"):
            self.spi.open_path(str(device_path))
        else:
            self.spi.open(bus, device)
        self.spi.max_speed_hz = 1_000_000
        self.spi.mode = 0
        self.initialize()

    def cleanup(self) -> None:
        try:
            self.clear()
            self.write_all(self.REG_SHUTDOWN, 0x00)
        finally:
            self.spi.close()

    def write_all(self, register: int, data: int) -> None:
        payload: List[int] = []
        for _ in range(self.device_count):
            payload.extend([register, data])
        self.spi.xfer2(payload)

    def write_row_bytes(self, row_register: int, module_bytes: Sequence[int]) -> None:
        if len(module_bytes) != self.device_count:
            raise ValueError("module_bytes length must match device_count")

        payload: List[int] = []
        for value in reversed(module_bytes):
            payload.extend([row_register, value])
        self.spi.xfer2(payload)

    def initialize(self) -> None:
        self.write_all(self.REG_DISPLAYTEST, 0x00)
        self.write_all(self.REG_DECODEMODE, 0x00)
        self.write_all(self.REG_SCANLIMIT, 0x07)
        self.write_all(self.REG_INTENSITY, 0x03)
        self.write_all(self.REG_SHUTDOWN, 0x01)
        self.clear()

    def clear(self) -> None:
        for row in range(1, 9):
            self.write_all(row, 0x00)

    def set_intensity(self, intensity: int) -> None:
        self.write_all(self.REG_INTENSITY, max(0, min(15, intensity)))

    def display_test_mode(self, enabled: bool, seconds: float) -> None:
        self.write_all(self.REG_DISPLAYTEST, 0x01 if enabled else 0x00)
        time.sleep(seconds)
        self.write_all(self.REG_DISPLAYTEST, 0x00)

    def pattern_rows(self, rows: Sequence[Sequence[int]], seconds: float) -> None:
        if len(rows) != 8:
            raise ValueError("MAX7219 panel requires 8 row definitions")
        end_time = time.monotonic() + seconds
        while time.monotonic() < end_time:
            for row_index, module_bytes in enumerate(rows, start=1):
                self.write_row_bytes(row_index, module_bytes)
            time.sleep(0.02)

    def display_glyph_on_all_modules(self, glyph: Sequence[int], seconds: float) -> None:
        rows = []
        for row_value in glyph:
            rows.append([row_value] * self.device_count)
        self.pattern_rows(rows, seconds)

    def display_glyph_set(self, set_name: str, seconds_per_glyph: float = 0.8) -> None:
        path = GLYPH_FILES[set_name]
        glyphs = load_glyphs_from_header(path)
        labels = GLYPH_LABELS.get(set_name, [])

        print(f"MAX7219: {set_name} from {path}")
        for index, glyph in enumerate(glyphs):
            label = labels[index] if index < len(labels) else f"{set_name}_{index}"
            print(f"  {index:02d}: {label}")
            self.display_glyph_on_all_modules(glyph, seconds_per_glyph)
            self.clear()
            time.sleep(0.12)

    def sweep_columns(self, seconds_per_step: float = 0.08) -> None:
        for x in range(self.device_count * 8):
            rows = []
            for _ in range(8):
                row_modules = [0x00] * self.device_count
                module_index = x // 8
                bit_index = 7 - (x % 8)
                row_modules[module_index] = 1 << bit_index
                rows.append(row_modules)
            self.pattern_rows(rows, seconds_per_step)

    def sweep_rows(self, seconds_per_step: float = 0.12) -> None:
        for y in range(8):
            rows = []
            for row_index in range(8):
                rows.append([0xFF] * self.device_count if row_index == y else [0x00] * self.device_count)
            self.pattern_rows(rows, seconds_per_step)

    def run_demo(self, glyph_set: str) -> None:
        print("MAX7219: display test")
        self.display_test_mode(True, 1.0)

        print("MAX7219: low brightness")
        self.set_intensity(1)
        self.pattern_rows([[0xFF] * self.device_count for _ in range(8)], 1.0)

        print("MAX7219: high brightness")
        self.set_intensity(10)
        self.pattern_rows([[0xFF] * self.device_count for _ in range(8)], 1.0)

        print("MAX7219: checker")
        self.pattern_rows(
            [
                [0xAA] * self.device_count,
                [0x55] * self.device_count,
                [0xAA] * self.device_count,
                [0x55] * self.device_count,
                [0xAA] * self.device_count,
                [0x55] * self.device_count,
                [0xAA] * self.device_count,
                [0x55] * self.device_count,
            ],
            1.5,
        )

        print("MAX7219: column sweep")
        self.sweep_columns()

        print("MAX7219: row sweep")
        self.sweep_rows()

        if glyph_set in ("digits", "letters", "signs", "all"):
            sets = ["digits", "letters", "signs"] if glyph_set == "all" else [glyph_set]
            for set_name in sets:
                self.display_glyph_set(set_name)

        self.clear()


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
        "--panel",
        choices=["hub75", "max7219", "both"],
        default="both",
        help="Select which panel to test",
    )
    parser.add_argument(
        "--max7219-devices",
        type=int,
        default=4,
        help="Number of cascaded 8x8 MAX7219 modules in the 8x32 panel",
    )
    parser.add_argument(
        "--max7219-bus",
        type=int,
        default=0,
        help="SPI bus number for the MAX7219 panel",
    )
    parser.add_argument(
        "--max7219-device",
        type=int,
        default=0,
        help="SPI chip-select/device number for the MAX7219 panel",
    )
    parser.add_argument(
        "--glyph-set",
        choices=["digits", "letters", "signs", "all", "none"],
        default="all",
        help="Glyph set to load from code/controller/current for the MAX7219 test",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    hub75 = None
    max7219 = None
    cleanups = []

    try:
        if args.panel in ("hub75", "both"):
            hub75 = Hub75MatrixTest()
            cleanups.append(hub75.cleanup)

        if args.panel in ("max7219", "both"):
            max7219 = Max7219PanelTest(
                device_count=args.max7219_devices,
                bus=args.max7219_bus,
                device=args.max7219_device,
            )
            cleanups.append(max7219.cleanup)

        install_signal_handlers(cleanups)

        print("Wiring summary")
        print("HUB75 RGB matrix: BCM 5,6,12,13,16,19,20,21,22,23,25,26,27")
        print(
            f"MAX7219 SPI: bus={args.max7219_bus} device={args.max7219_device} "
            "MOSI=GPIO10 SCLK=GPIO11"
        )
        print("Press Ctrl+C to stop.\n")

        if max7219:
            max7219.run_demo(args.glyph_set)

        if hub75:
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
