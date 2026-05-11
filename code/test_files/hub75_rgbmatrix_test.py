#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from rgbmatrix import RGBMatrix, RGBMatrixOptions

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

Color = Tuple[int, int, int]
Glyph = List[int]

COLOR_MAP: Dict[str, Color] = {
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
}


def load_glyphs_from_header(path: Path) -> List[Glyph]:
    text = path.read_text(encoding="utf-8")
    values = [int(match.group(1), 2) for match in re.finditer(r"0b([01]{8})", text)]
    if len(values) % 8 != 0:
        raise ValueError(f"{path} does not contain a whole number of 8-row glyphs")
    return [values[index:index + 8] for index in range(0, len(values), 8)]


class Hub75GlyphTester:
    WIDTH = 64
    HEIGHT = 32
    CELL = 8
    GRID_W = WIDTH // CELL
    GRID_H = HEIGHT // CELL

    def __init__(
        self,
        slowdown_gpio: int,
        row_addr_type: int,
        multiplexing: int,
        panel_type: str,
        brightness: int,
        pwm_bits: int,
        limit_refresh_rate_hz: int,
        rgb_sequence: str,
        no_hardware_pulse: bool,
    ) -> None:
        options = RGBMatrixOptions()
        options.hardware_mapping = "z2w-custom"
        options.rows = self.HEIGHT
        options.cols = self.WIDTH
        options.chain_length = 1
        options.parallel = 1
        options.gpio_slowdown = slowdown_gpio
        options.row_address_type = row_addr_type
        options.multiplexing = multiplexing
        options.panel_type = panel_type
        options.brightness = brightness
        options.pwm_bits = pwm_bits
        options.limit_refresh_rate_hz = limit_refresh_rate_hz
        options.led_rgb_sequence = rgb_sequence
        options.disable_hardware_pulsing = no_hardware_pulse
        options.drop_privileges = False
        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()

    def clear(self) -> None:
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def repeated_glyph(self, glyph: Sequence[int], color: Color) -> None:
        self.canvas.Clear()
        for cell_y in range(self.GRID_H):
            for cell_x in range(self.GRID_W):
                offset_x = cell_x * self.CELL
                offset_y = cell_y * self.CELL
                for row in range(8):
                    row_bits = glyph[row]
                    for bit in range(8):
                        if row_bits & (1 << (7 - bit)):
                            self.canvas.SetPixel(offset_x + bit, offset_y + row, *color)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def show_set(self, set_name: str, hold_seconds: float, color_name: str) -> None:
        glyphs = load_glyphs_from_header(GLYPH_FILES[set_name])
        labels = GLYPH_LABELS.get(set_name, [])
        color = COLOR_MAP[color_name]
        print(f"HUB75 rgbmatrix: {set_name} color={color_name}")
        for index, glyph in enumerate(glyphs):
            label = labels[index] if index < len(labels) else f"{set_name}_{index}"
            print(f"  {index:02d}: {label}")
            self.repeated_glyph(glyph, color)
            time.sleep(hold_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stable HUB75 glyph tester using rpi-rgb-led-matrix")
    parser.add_argument("--glyph-set", choices=["digits", "letters", "signs", "all"], default="letters")
    parser.add_argument("--hold-seconds", type=float, default=1.2)
    parser.add_argument("--color", choices=sorted(COLOR_MAP.keys()), default="white")
    parser.add_argument("--led-slowdown-gpio", type=int, default=2)
    parser.add_argument("--led-row-addr-type", type=int, default=0)
    parser.add_argument("--led-multiplexing", type=int, default=0)
    parser.add_argument("--led-panel-type", type=str, default="")
    parser.add_argument("--led-brightness", type=int, default=70)
    parser.add_argument("--led-pwm-bits", type=int, default=7)
    parser.add_argument("--led-limit-refresh", type=int, default=120)
    parser.add_argument("--led-rgb-sequence", type=str, default="RGB")
    parser.add_argument("--led-no-hardware-pulse", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sets: Iterable[str] = ["digits", "letters", "signs"] if args.glyph_set == "all" else [args.glyph_set]
    print("HUB75 rgbmatrix startup")
    print(f"  bitmaps: {BITMAPS_DIR}")
    for set_name in sets:
        path = GLYPH_FILES[set_name]
        print(f"  {set_name}: {path} exists={path.exists()}")
    print(
        "  options: "
        f"mapping=z2w-custom rows=32 cols=64 slowdown={args.led_slowdown_gpio} "
        f"row_addr={args.led_row_addr_type} multiplexing={args.led_multiplexing} "
        f"panel_type={args.led_panel_type!r} brightness={args.led_brightness} "
        f"pwm_bits={args.led_pwm_bits} refresh={args.led_limit_refresh} "
        f"rgb={args.led_rgb_sequence} no_hw_pulse={args.led_no_hardware_pulse}"
    )
    tester = Hub75GlyphTester(
        slowdown_gpio=args.led_slowdown_gpio,
        row_addr_type=args.led_row_addr_type,
        multiplexing=args.led_multiplexing,
        panel_type=args.led_panel_type,
        brightness=args.led_brightness,
        pwm_bits=args.led_pwm_bits,
        limit_refresh_rate_hz=args.led_limit_refresh,
        rgb_sequence=args.led_rgb_sequence,
        no_hardware_pulse=args.led_no_hardware_pulse,
    )
    print("  matrix initialized")

    try:
        for set_name in sets:
            tester.show_set(set_name, args.hold_seconds, args.color)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        tester.clear()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
