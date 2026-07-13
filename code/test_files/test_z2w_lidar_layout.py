#!/usr/bin/env python3
"""Pixel-level checks for the Zero 2 W LiDAR dashboard layout."""

from __future__ import annotations

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parents[1] / "controller" / "current"
MODULE_PATH = CURRENT_DIR / "z2w_dashboard.py"


def load_dashboard_module():
    rgbmatrix = types.ModuleType("rgbmatrix")
    rgbmatrix.RGBMatrix = object
    rgbmatrix.RGBMatrixOptions = object
    serial = types.ModuleType("serial")
    sys.modules.setdefault("rgbmatrix", rgbmatrix)
    sys.modules.setdefault("serial", serial)

    spec = importlib.util.spec_from_file_location("z2w_dashboard_test_module", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


D = load_dashboard_module()


class PixelCanvas:
    def __init__(self):
        self.pixels = {}

    def SetPixel(self, x, y, red, green, blue):
        self.pixels[(x, y)] = (red, green, blue)


def renderer():
    value = D.DashboardRenderer.__new__(D.DashboardRenderer)
    value.canvas = PixelCanvas()
    value.render_x_offset_px = 0
    value.letter_map = D.build_letter_map()
    return value


class LidarDashboardLayoutTest(unittest.TestCase):
    def test_guides_are_equally_spaced_with_side_padding(self):
        self.assertEqual(D.LIDAR_PREVIEW_GUIDE_X, (6, 23, 40, 57))
        gaps = [right - left for left, right in zip(
            D.LIDAR_PREVIEW_GUIDE_X,
            D.LIDAR_PREVIEW_GUIDE_X[1:],
        )]
        self.assertEqual(gaps, [17, 17, 17])
        self.assertGreater(D.LIDAR_PREVIEW_GUIDE_X[0], 0)
        self.assertLess(D.LIDAR_PREVIEW_GUIDE_X[-1], D.PANEL_WIDTH - 1)

    def test_outer_and_inner_guides_have_equal_intensity(self):
        self.assertEqual(sum(D.LIDAR_OUTER_GUIDE), sum(D.LIDAR_INNER_GUIDE))
        self.assertEqual(max(D.LIDAR_OUTER_GUIDE), max(D.LIDAR_INNER_GUIDE))
        self.assertNotEqual(D.LIDAR_OUTER_GUIDE, D.LIDAR_INNER_GUIDE)

    def test_lane_zone_colors_follow_the_four_rungs(self):
        self.assertEqual(D.lidar_lane_zone_color(2.0), D.LIDAR_POINT_BLUE)
        self.assertEqual(D.lidar_lane_zone_color(1.60), D.LIDAR_POINT_GREEN)
        self.assertEqual(D.lidar_lane_zone_color(1.35), D.LIDAR_POINT_YELLOW)
        self.assertEqual(D.lidar_lane_zone_color(1.20), D.LIDAR_POINT_ORANGE)
        self.assertEqual(D.lidar_lane_zone_color(1.00), D.LIDAR_POINT_RED)

    def test_lane_classification_matches_equal_corridor_thirds(self):
        self.assertEqual(D.lidar_lane_for_coordinates(-0.50, 1.0), "L")
        self.assertEqual(D.lidar_lane_for_coordinates(0.00, 1.0), "C")
        self.assertEqual(D.lidar_lane_for_coordinates(0.50, 1.0), "R")
        self.assertIsNone(D.lidar_lane_for_coordinates(0.80, 1.0))

    def test_lidar_page_uses_full_letter_bitmaps(self):
        value = renderer()
        value._draw_lidar_page({"lidar_points": [[0.0, 2.0]], "lidar_point_count": 1})

        label_bases = {"L": 11, "C": 28, "R": 45}
        for lane, base_x in label_bases.items():
            expected = {
                (base_x + bit, row)
                for row, row_bits in enumerate(value.letter_map[lane])
                for bit in range(8)
                if row_bits & (1 << (7 - bit))
            }
            actual = {
                point for point in expected
                if value.canvas.pixels.get(point) == D.LIDAR_LANE_CLEAR
            }
            self.assertEqual(actual, expected, lane)

    def test_each_lane_label_uses_its_nearest_rung_color(self):
        value = renderer()

        def point(lateral_m, forward_m):
            angle_deg = math.degrees(math.atan2(lateral_m, forward_m))
            return [angle_deg, math.hypot(lateral_m, forward_m)]

        value._draw_lidar_page({
            "lidar_points": [
                point(-0.50, 1.55),
                point(0.00, 1.35),
                point(0.50, 1.20),
            ],
            "lidar_point_count": 3,
        })

        expected_colors = {
            "L": D.LIDAR_POINT_GREEN,
            "C": D.LIDAR_POINT_YELLOW,
            "R": D.LIDAR_POINT_ORANGE,
        }
        label_bases = {"L": 11, "C": 28, "R": 45}
        for lane, base_x in label_bases.items():
            glyph_pixel = next(
                (base_x + bit, row)
                for row, row_bits in enumerate(value.letter_map[lane])
                for bit in range(8)
                if row_bits & (1 << (7 - bit))
            )
            self.assertEqual(value.canvas.pixels[glyph_pixel], expected_colors[lane])

    def test_all_four_guides_span_the_panel(self):
        value = renderer()
        value._draw_lidar_page({"lidar_points": [[0.0, 2.0]], "lidar_point_count": 1})

        for index, guide_x in enumerate(D.LIDAR_PREVIEW_GUIDE_X):
            color = D.LIDAR_OUTER_GUIDE if index in (0, 3) else D.LIDAR_INNER_GUIDE
            self.assertEqual(value.canvas.pixels[(guide_x, 8)], color)
            self.assertEqual(value.canvas.pixels[(guide_x, 30)], color)


if __name__ == "__main__":
    unittest.main()
