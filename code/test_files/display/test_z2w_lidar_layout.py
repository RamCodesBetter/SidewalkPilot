#!/usr/bin/env python3
"""Pixel-level checks for the Zero 2 W center-corridor LiDAR page."""

from __future__ import annotations

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parents[2] / "controller" / "current"
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
    def test_removed_photo_countdown_pages_are_outside_page_range(self):
        self.assertEqual(D.DASHBOARD_PAGE_COUNT, 17)
        self.assertFalse(hasattr(D.DashboardRenderer, "_draw_photo_run_stats_page"))
        self.assertFalse(hasattr(D.DashboardRenderer, "_draw_bucket_right_page"))

    def test_preview_keeps_side_padding_but_only_two_center_guides(self):
        self.assertEqual(D.LIDAR_PREVIEW_X, (6, 57))
        self.assertEqual(D.LIDAR_CENTER_GUIDE_X, (23, 40))

        value = renderer()
        value._draw_lidar_page({"lidar_points": [[0.0, 2.0]], "lidar_point_count": 1})
        for guide_x in D.LIDAR_CENTER_GUIDE_X:
            self.assertEqual(value.canvas.pixels[(guide_x, 8)], D.LIDAR_CENTER_GUIDE)
            self.assertEqual(value.canvas.pixels[(guide_x, 30)], D.LIDAR_CENTER_GUIDE)
        self.assertNotEqual(value.canvas.pixels.get((6, 30)), D.LIDAR_CENTER_GUIDE)
        self.assertNotEqual(value.canvas.pixels.get((57, 30)), D.LIDAR_CENTER_GUIDE)

    def test_lane_zone_colors_follow_the_four_rungs(self):
        self.assertEqual(D.lidar_lane_zone_color(2.0), D.LIDAR_POINT_BLUE)
        self.assertEqual(D.lidar_lane_zone_color(1.60), D.LIDAR_POINT_GREEN)
        self.assertEqual(D.lidar_lane_zone_color(1.35), D.LIDAR_POINT_YELLOW)
        self.assertEqual(D.lidar_lane_zone_color(1.20), D.LIDAR_POINT_ORANGE)
        self.assertEqual(D.lidar_lane_zone_color(1.00), D.LIDAR_POINT_RED)

    def test_only_center_coordinates_belong_to_the_safety_corridor(self):
        self.assertEqual(D.lidar_lane_for_coordinates(0.0, 1.0), "C")
        self.assertEqual(D.lidar_lane_for_coordinates(0.20, 1.0), "C")
        self.assertIsNone(D.lidar_lane_for_coordinates(-0.30, 1.0))
        self.assertIsNone(D.lidar_lane_for_coordinates(0.30, 1.0))
        self.assertIsNone(D.lidar_lane_for_coordinates(0.0, -1.0))

    def test_lidar_page_draws_one_full_center_glyph(self):
        value = renderer()
        value._draw_lidar_page({"lidar_points": [[0.0, 2.0]], "lidar_point_count": 1})

        base_x = 28
        expected = {
            (base_x + bit, row)
            for row, row_bits in enumerate(value.letter_map["C"])
            for bit in range(8)
            if row_bits & (1 << (7 - bit))
        }
        actual = {
            point for point in expected
            if value.canvas.pixels.get(point) == D.LIDAR_LANE_CLEAR
        }
        self.assertEqual(actual, expected)

    def test_center_label_uses_nearest_rung_color(self):
        value = renderer()
        value._draw_lidar_page({
            "lidar_points": [[0.0, 1.20]],
            "lidar_point_count": 1,
        })
        base_x = 28
        glyph_pixel = next(
            (base_x + bit, row)
            for row, row_bits in enumerate(value.letter_map["C"])
            for bit in range(8)
            if row_bits & (1 << (7 - bit))
        )
        self.assertEqual(value.canvas.pixels[glyph_pixel], D.LIDAR_POINT_ORANGE)

    def test_side_point_does_not_change_center_label(self):
        value = renderer()
        lateral_m, forward_m = 0.50, 1.0
        value._draw_lidar_page({
            "lidar_points": [[
                math.degrees(math.atan2(lateral_m, forward_m)),
                math.hypot(lateral_m, forward_m),
            ]],
            "lidar_point_count": 1,
        })
        base_x = 28
        glyph_pixel = next(
            (base_x + bit, row)
            for row, row_bits in enumerate(value.letter_map["C"])
            for bit in range(8)
            if row_bits & (1 << (7 - bit))
        )
        self.assertEqual(value.canvas.pixels[glyph_pixel], D.LIDAR_LANE_CLEAR)

    def test_rungs_span_center_corridor_only(self):
        value = renderer()
        value._draw_lidar_page({"lidar_points": [[0.0, 2.0]], "lidar_point_count": 1})
        rung_y = (D.PANEL_HEIGHT - 1) - int(round(1.40 * D.LIDAR_FORWARD_SCALE_PX_PER_M))
        self.assertEqual(value.canvas.pixels[(30, rung_y)], D.LIDAR_POINT_YELLOW)
        self.assertNotEqual(value.canvas.pixels.get((10, rung_y)), D.LIDAR_POINT_YELLOW)
        self.assertNotEqual(value.canvas.pixels.get((50, rung_y)), D.LIDAR_POINT_YELLOW)


if __name__ == "__main__":
    unittest.main()
