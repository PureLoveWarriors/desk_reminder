"""自绘图标按钮：对齐一致、粗细可控，不依赖 Unicode 字形。"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath
from PySide6.QtWidgets import QAbstractButton


class IconButton(QAbstractButton):
    """统一尺寸的自绘图标按钮。kind: pin / pin_top / history / gear / minimize / close / timer / delete / highlight"""

    def __init__(
        self,
        kind: str,
        tooltip: str = "",
        *,
        size: int = 28,
        checkable: bool = False,
        accent: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._kind = kind
        self._hover = False
        self._accent = QColor(accent) if accent else None
        self.setCheckable(checkable)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

    def set_accent(self, color: str):
        self._accent = QColor(color)
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # 背景圆角
        bg = QColor(0, 0, 0, 0)
        if self.isChecked():
            bg = QColor(255, 107, 107, 40)
        elif self._hover:
            if self._kind == "close":
                bg = QColor(255, 95, 87)
            elif self._kind == "delete":
                bg = QColor(255, 107, 107, 36)
            else:
                bg = QColor(0, 0, 0, 20)
        if bg.alpha():
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(bg))
            radius = 4 if self._kind == "pin_top" else 7
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        accent = self._accent or QColor("#ff6b6b")

        # 图标颜色
        if self._kind in ("close", "delete"):
            color = QColor("#ffffff") if (self._kind == "close" and self._hover) else QColor("#ff5f57")
        elif self._kind == "pin":
            color = accent if self.isChecked() else QColor("#555555")
        elif self._kind == "pin_top":
            color = accent if (self.isChecked() or self._hover) else QColor(0, 0, 0, 68)
        elif self._kind == "history":
            color = accent if self.isChecked() else QColor("#4a90e2")
        elif self._kind == "highlight":
            color = accent if self.isChecked() else QColor(0, 0, 0, 90)
        else:
            color = QColor("#555555")

        if self._kind == "pin":
            thick = 2.15 if self.isChecked() else 1.85
            self._draw_pin(p, cx, cy, color, filled=False, stroke=thick)
        elif self._kind == "pin_top":
            self._draw_pin(p, cx, cy, color, filled=True, scale=0.94, needle_stroke=1.35)
        elif self._kind == "history":
            self._draw_history(p, cx, cy, color)
        elif self._kind == "gear":
            self._draw_gear(p, cx, cy, color)
        elif self._kind == "minimize":
            self._draw_minimize(p, cx, cy, color)
        elif self._kind in ("close", "delete"):
            self._draw_close(p, cx, cy, color, thick=(self._kind == "delete"))
        elif self._kind == "timer":
            self._draw_timer(p, cx, cy, color)
        elif self._kind == "highlight":
            self._draw_highlight(p, cx, cy, color, filled=self.isChecked())

    def _pushpin_path(self, cx: float, cy: float) -> QPainterPath:
        """苹果备忘录风格图钉：平顶横条 + 收腰圆鼓身。"""
        path = QPainterPath()
        top_w, top_h = 11.0, 2.8
        top_y = cy - 8.2
        path.addRoundedRect(QRectF(cx - top_w / 2, top_y, top_w, top_h), 1.3, 1.3)

        neck = top_y + top_h + 0.4
        belly = cy + 1.8
        path.moveTo(cx - 3.6, neck)
        path.cubicTo(cx - 5.8, cy - 1.5, cx - 6.0, belly - 1.0, cx - 3.8, belly)
        path.quadTo(cx, belly + 2.0, cx + 3.8, belly)
        path.cubicTo(cx + 6.0, belly - 1.0, cx + 5.8, cy - 1.5, cx + 3.6, neck)
        path.closeSubpath()
        return path

    def _draw_pin(
        self,
        p: QPainter,
        cx: float,
        cy: float,
        color: QColor,
        *,
        filled: bool,
        stroke: float = 1.85,
        scale: float = 1.0,
        needle_stroke: float = 2.0,
    ):
        p.save()
        if scale != 1.0:
            p.translate(cx, cy)
            p.scale(scale, scale)
            p.translate(-cx, -cy)

        body = self._pushpin_path(cx, cy)
        needle_top = cy + 3.8
        needle_bot = cy + 8.8

        if filled:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(color))
            p.drawPath(body)
            p.setPen(QPen(color, needle_stroke, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx, needle_top), QPointF(cx, needle_bot))
        else:
            pen = QPen(color, stroke)
            pen.setJoinStyle(Qt.RoundJoin)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(body)
            p.drawLine(QPointF(cx, needle_top), QPointF(cx, needle_bot))
        p.restore()

    def _draw_history(self, p: QPainter, cx: float, cy: float, color: QColor):
        # 勾选方框：圆角矩形 + 对勾
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(cx - 7, cy - 7, 14, 14), 3, 3)
        p.drawLine(QPointF(cx - 4, cy), QPointF(cx - 1, cy + 3.5))
        p.drawLine(QPointF(cx - 1, cy + 3.5), QPointF(cx + 5, cy - 3.5))

    def _draw_gear(self, p: QPainter, cx: float, cy: float, color: QColor):
        # 简化齿轮：外圆 + 内圆 + 四条短齿
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 5.5, 5.5)
        p.drawEllipse(QPointF(cx, cy), 2.2, 2.2)
        for dx, dy in ((0, -8), (0, 8), (-8, 0), (8, 0)):
            p.drawLine(QPointF(cx + dx * 0.55, cy + dy * 0.55),
                       QPointF(cx + dx, cy + dy))

    def _draw_minimize(self, p: QPainter, cx: float, cy: float, color: QColor):
        pen = QPen(color, 2.2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx - 6, cy), QPointF(cx + 6, cy))

    def _draw_close(self, p: QPainter, cx: float, cy: float, color: QColor, thick: bool = False):
        pen = QPen(color, 2.6 if thick else 2.2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        s = 5.5 if thick else 5.0
        p.drawLine(QPointF(cx - s, cy - s), QPointF(cx + s, cy + s))
        p.drawLine(QPointF(cx + s, cy - s), QPointF(cx - s, cy + s))

    def _draw_timer(self, p: QPainter, cx: float, cy: float, color: QColor):
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy + 1), 6.5, 6.5)
        # 顶部小钮
        p.drawLine(QPointF(cx - 2.5, cy - 6.5), QPointF(cx + 2.5, cy - 6.5))
        # 指针
        p.drawLine(QPointF(cx, cy + 1), QPointF(cx, cy - 2.5))
        p.drawLine(QPointF(cx, cy + 1), QPointF(cx + 3.5, cy + 3))

    def _draw_highlight(self, p: QPainter, cx: float, cy: float, color: QColor, filled: bool):
        # 五角星：标记"正在进行"的任务
        path = QPainterPath()
        outer, inner = 6.5, 2.8
        for i in range(10):
            ang = math.pi / 2 + i * math.pi / 5
            r = outer if i % 2 == 0 else inner
            pt = QPointF(cx + r * math.cos(ang), cy - r * math.sin(ang))
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        path.closeSubpath()
        if filled:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(color))
        else:
            pen = QPen(color, 1.4)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
        p.drawPath(path)
