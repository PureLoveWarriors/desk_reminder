"""Pure geometry helper for Qt-side window resize."""
import unittest

from PySide6.QtCore import QPoint, QRect

from app.ui.main_window import MIN_H, MIN_W, apply_edge_resize, hit_edge


class ApplyEdgeResizeTest(unittest.TestCase):
    def test_right_edge_grows_width(self):
        geo = QRect(100, 100, 320, 380)
        out = apply_edge_resize(geo, QPoint(40, 0), "r", MIN_W, MIN_H)
        self.assertEqual(out, QRect(100, 100, 360, 380))

    def test_bottom_edge_grows_height(self):
        geo = QRect(100, 100, 320, 380)
        out = apply_edge_resize(geo, QPoint(0, 50), "b", MIN_W, MIN_H)
        self.assertEqual(out, QRect(100, 100, 320, 430))

    def test_min_size_clamped(self):
        geo = QRect(100, 100, 320, 380)
        out = apply_edge_resize(geo, QPoint(-400, -400), "br", MIN_W, MIN_H)
        self.assertEqual(out.width(), MIN_W)
        self.assertEqual(out.height(), MIN_H)


class HitEdgeTest(unittest.TestCase):
    """加大后的缩放热区：离边 16px、离角 28px 仍应能抓到。"""

    def test_left_hot_zone_is_wide(self):
        self.assertEqual(hit_edge(16, 120, 320, 380), "l")

    def test_bottom_hot_zone_is_wide(self):
        self.assertEqual(hit_edge(160, 364, 320, 380), "b")

    def test_corner_hot_zone_is_wide(self):
        self.assertEqual(hit_edge(28, 28, 320, 380), "tl")

    def test_interior_is_not_edge(self):
        self.assertIsNone(hit_edge(80, 120, 320, 380))


if __name__ == "__main__":
    unittest.main()
