"""设置面板 + 倒计时选择弹窗（嵌在主窗口内，避免独立 Popup 黑角）。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF, QEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QSpinBox,
    QWidget,
)
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QPainterPath

from app.config import THEME_PRESETS


class ThemeSwatch(QAbstractButton):
    """一个配色预设的圆形色块预览：上半是顶部栏颜色，下半是主体背景颜色。"""

    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setCheckable(True)
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(theme["name"])

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        circle = QRectF(4, 4, 22, 22)
        path = QPainterPath()
        path.addEllipse(circle)
        p.setClipPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(self.theme["body"])))
        p.drawRect(QRectF(0, 0, self.width(), self.height()))
        p.setBrush(QBrush(QColor(self.theme["top"])))
        p.drawRect(QRectF(0, 0, self.width(), self.height() / 2 + 4))
        p.setClipping(False)
        if self.isChecked():
            pen = QPen(QColor(self.theme["accent"]), 2.4)
        else:
            pen = QPen(QColor(0, 0, 0, 40), 1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(circle)


class _PanelFrame(QFrame):
    """嵌在主窗口里的圆角白底面板，不是独立窗口，不会有黑角。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPanel")
        self.setFixedWidth(220)
        self.hide()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(0, 0, 0, 28), 1))
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.drawRoundedRect(rect, 14, 14)


class SettingsPanel(_PanelFrame):
    opacityChanged = Signal(int)
    themeChanged = Signal(str)          # theme id
    exitBehaviorReset = Signal()

    def __init__(self, opacity: int, theme_id: str, parent=None):
        super().__init__(parent)
        self.setFixedWidth(236)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        title = QLabel("背景透明度")
        title.setObjectName("PopupLabel")
        lay.addWidget(title)

        row = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(20, 100)
        self.slider.setValue(opacity)
        self.slider.valueChanged.connect(self.opacityChanged.emit)
        self.value_lbl = QLabel(f"{opacity}%")
        self.value_lbl.setObjectName("PopupLabel")
        self.value_lbl.setFixedWidth(36)
        self.slider.valueChanged.connect(lambda v: self.value_lbl.setText(f"{v}%"))
        row.addWidget(self.slider)
        row.addWidget(self.value_lbl)
        lay.addLayout(row)

        theme_title = QLabel("配色主题")
        theme_title.setObjectName("PopupLabel")
        lay.addWidget(theme_title)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(8)
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        for t in THEME_PRESETS:
            swatch = ThemeSwatch(t)
            swatch.setChecked(t["id"] == theme_id)
            self._theme_group.addButton(swatch)
            theme_row.addWidget(swatch)
        theme_row.addStretch()
        lay.addLayout(theme_row)
        self._theme_group.buttonClicked.connect(
            lambda btn: self.themeChanged.emit(btn.theme["id"])
        )

        exit_title = QLabel("退出按钮行为")
        exit_title.setObjectName("PopupLabel")
        lay.addWidget(exit_title)
        reset_exit_btn = QPushButton("改回「每次都询问」")
        reset_exit_btn.setObjectName("PopupButton")
        reset_exit_btn.clicked.connect(self.exitBehaviorReset.emit)
        lay.addWidget(reset_exit_btn)

        self.adjustSize()

    def set_theme(self, theme_id: str):
        for btn in self._theme_group.buttons():
            btn.setChecked(btn.theme["id"] == theme_id)

    def show_at(self, global_anchor, host: QWidget):
        """相对主窗口定位并显示。"""
        local = host.mapFromGlobal(global_anchor)
        x = max(8, min(local.x() - self.width() + 28, host.width() - self.width() - 8))
        y = local.y() + 4
        self.move(x, y)
        self.raise_()
        self.show()
        self.setFocus(Qt.PopupFocusReason)


class TimerPopup(_PanelFrame):
    """选择倒计时时长（分钟）。"""

    accepted = Signal(int)   # 分钟；0 表示清除

    def __init__(self, current_minutes: int = 25, parent=None):
        super().__init__(parent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        title = QLabel("倒计时（分钟）")
        title.setObjectName("PopupLabel")
        lay.addWidget(title)

        presets = QHBoxLayout()
        for m in (5, 10, 25):
            b = QPushButton(str(m))
            b.setObjectName("PopupButton")
            b.setFixedHeight(28)
            b.clicked.connect(lambda _=False, mm=m: self._pick(mm))
            presets.addWidget(b)
        lay.addLayout(presets)

        row = QHBoxLayout()
        self.spin = QSpinBox()
        self.spin.setObjectName("PopupSpin")
        self.spin.setRange(1, 600)
        self.spin.setValue(current_minutes or 25)
        row.addWidget(self.spin, 1)
        ok = QPushButton("开始")
        ok.setObjectName("PopupButton")
        ok.clicked.connect(lambda: self._pick(self.spin.value()))
        row.addWidget(ok)
        lay.addLayout(row)

        clear = QPushButton("清除计时")
        clear.setObjectName("PopupButton")
        clear.clicked.connect(lambda: self._pick(0))
        lay.addWidget(clear)

        self.adjustSize()

    def show_at(self, global_anchor, host: QWidget):
        local = host.mapFromGlobal(global_anchor)
        x = max(8, min(local.x(), host.width() - self.width() - 8))
        y = local.y() + 4
        self.move(x, y)
        self.raise_()
        self.show()

    def _pick(self, minutes: int):
        self.accepted.emit(minutes)
        self.hide()


class ExitConfirmPanel(_PanelFrame):
    """点退出按钮时的确认面板：最小化到托盘 / 直接退出，可选记住选择。"""

    decided = Signal(str, bool)   # behavior: "minimize" / "quit", remember

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        title = QLabel("要退出程序吗？")
        title.setObjectName("PopupLabel")
        lay.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(8)
        minimize_btn = QPushButton("最小化到托盘")
        minimize_btn.setObjectName("PopupButton")
        minimize_btn.clicked.connect(lambda: self._pick("minimize"))
        quit_btn = QPushButton("直接退出")
        quit_btn.setObjectName("PopupButton")
        quit_btn.clicked.connect(lambda: self._pick("quit"))
        row.addWidget(minimize_btn)
        row.addWidget(quit_btn)
        lay.addLayout(row)

        self.remember_chk = QCheckBox("记住我的选择，不再询问")
        self.remember_chk.setObjectName("PopupLabel")
        lay.addWidget(self.remember_chk)

        self.adjustSize()

    def _pick(self, behavior: str):
        self.decided.emit(behavior, self.remember_chk.isChecked())
        self.remember_chk.setChecked(False)
        self.hide()

    def show_centered(self, host: QWidget):
        x = (host.width() - self.width()) // 2
        y = (host.height() - self.height()) // 2
        self.move(max(8, x), max(8, y))
        self.raise_()
        self.show()
        self.setFocus(Qt.PopupFocusReason)
