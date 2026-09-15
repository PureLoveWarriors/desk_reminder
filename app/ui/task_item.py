"""单条任务控件：圆圈打勾 + 可编辑标题 + 倒计时。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF, QRect, QPoint, QTimer, QEvent
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QFocusEvent, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QGraphicsDropShadowEffect,
    QApplication,
    QWidget,
)

from app.ui.icons import IconButton

_GESTURE_LOCK_THRESHOLD = 6
_HORIZONTAL_RATIO = 0.65


class TaskTitleEdit(QLineEdit):
    """任务标题输入框：失焦后强制把长文字的显示滚回最左边。"""

    def focusOutEvent(self, event: QFocusEvent):
        super().focusOutEvent(event)
        QTimer.singleShot(0, self.scroll_to_start)

    def scroll_to_start(self):
        text = self.text()
        if not text:
            return
        self.blockSignals(True)
        self.setText(text)
        self.setCursorPosition(0)
        self.deselect()
        self.blockSignals(False)


class CircleCheck(QAbstractButton):
    """左侧的圆圈，点一下完成。"""

    def __init__(self, accent="#ff6b6b", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)
        self._accent = QColor(accent)

    def set_accent(self, color: str):
        self._accent = QColor(color)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(2, 2, 18, 18)
        if self.isChecked():
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(self._accent))
            p.drawEllipse(rect)
            pen = QPen(QColor("white"), 2)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(7, 11, 10, 14)
            p.drawLine(10, 14, 15, 8)
        else:
            pen = QPen(QColor(0, 0, 0, 90), 2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(rect)


class TaskItemWidget(QFrame):
    toggled = Signal(int, bool)
    titleChanged = Signal(int, str)
    deleteRequested = Signal(int)
    timerRequested = Signal(int)
    highlightToggled = Signal(int, bool)
    pinnedToggled = Signal(int, bool)
    dragStarted = Signal(int)
    dragMoved = Signal(int, QPoint)
    dragEnded = Signal(int)

    def __init__(self, task, accent="#ff6b6b", parent=None):
        super().__init__(parent)
        self.task = task
        self._accent = QColor(accent)
        self._drag_enabled = True
        self._drag_active = False
        self._maybe_dragging = False
        self._press_global: QPoint | None = None
        self._press_in_title = False
        self._gesture_locked: str | None = None
        self._row_rect_global: QRect | None = None
        self._dragging_visual = False
        self._base_height = 40
        self._drag_height = 52

        self.setObjectName("TaskItem")
        self.setMinimumHeight(self._base_height)
        self.setMouseTracking(True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 8, 4)
        lay.setSpacing(6)

        self.pin_top_btn = IconButton(
            "pin_top",
            "取消置顶" if getattr(task, "pinned", False) else "置顶",
            size=26,
            checkable=True,
            accent=accent,
        )
        self.pin_top_btn.setChecked(getattr(task, "pinned", False))
        self.pin_top_btn.toggled.connect(self._on_pin_toggle)
        lay.addWidget(self.pin_top_btn)
        lay.addSpacing(2)

        self.check = CircleCheck(accent)
        self.check.setChecked(task.done)
        self.check.clicked.connect(self._on_toggle)
        lay.addWidget(self.check)

        self.title = TaskTitleEdit(task.title)
        self.title.setFrame(False)
        self.title.setToolTip(task.title)
        self._apply_title_style(task.done)
        self.title.editingFinished.connect(self._on_title_edit)
        self.title.scroll_to_start()
        self.title.installEventFilter(self)
        lay.addWidget(self.title, 1)

        self.timer_label = QLabel("")
        self.timer_label.setObjectName("TimerLabel")
        self.timer_label.setVisible(False)
        lay.addWidget(self.timer_label)

        self.highlight_btn = IconButton(
            "highlight", "标记为进行中", size=24, checkable=True, accent=accent
        )
        self.highlight_btn.setChecked(getattr(task, "highlighted", False))
        self.highlight_btn.toggled.connect(self._on_highlight_toggle)
        lay.addWidget(self.highlight_btn)

        self.timer_btn = IconButton("timer", "设置倒计时", size=24)
        self.timer_btn.clicked.connect(lambda: self.timerRequested.emit(task.id))
        lay.addWidget(self.timer_btn)

        self.del_btn = IconButton("delete", "删除", size=24)
        self.del_btn.clicked.connect(lambda: self.deleteRequested.emit(task.id))
        lay.addWidget(self.del_btn)

        self._action_widgets = (
            self.pin_top_btn, self.check, self.highlight_btn,
            self.timer_btn, self.del_btn,
        )

    def set_drag_enabled(self, enabled: bool):
        self._drag_enabled = enabled
        self.pin_top_btn.setVisible(enabled)
        self.setCursor(Qt.OpenHandCursor if enabled else Qt.ArrowCursor)

    def set_accent(self, color: str):
        self._accent = QColor(color)
        self.check.set_accent(color)
        self.highlight_btn.set_accent(color)
        self.update()

    def _is_action_widget(self, widget: QWidget | None) -> bool:
        while widget and widget is not self:
            if widget in self._action_widgets:
                return True
            widget = widget.parentWidget()
        return False

    def _press_on_title(self, pos: QPoint) -> bool:
        widget = self.childAt(pos)
        while widget and widget is not self:
            if widget is self.title:
                return True
            widget = widget.parentWidget()
        return False

    def _begin_gesture(self, global_pos: QPoint, *, in_title: bool):
        self._press_global = global_pos
        self._press_in_title = in_title
        self._maybe_dragging = True
        self._gesture_locked = None
        top_left = self.mapToGlobal(QPoint(0, 0))
        self._row_rect_global = QRect(top_left, self.size())

    def _reset_gesture(self):
        self._maybe_dragging = False
        self._press_global = None
        self._press_in_title = False
        self._gesture_locked = None
        self._row_rect_global = None

    def _exited_row_vertically(self, global_pos: QPoint) -> bool:
        if self._row_rect_global is None:
            return False
        return global_pos.y() < self._row_rect_global.top() or global_pos.y() > self._row_rect_global.bottom()

    def _try_lock_gesture(self, global_pos: QPoint) -> bool:
        """锁定手势方向。返回 True 表示交给标题文字处理。"""
        if self._gesture_locked == "text":
            return True
        if self._gesture_locked == "reorder":
            return False
        if self._press_global is None:
            return False

        delta = global_pos - self._press_global
        if max(abs(delta.x()), abs(delta.y())) < _GESTURE_LOCK_THRESHOLD:
            return False

        if self._press_in_title and abs(delta.x()) >= abs(delta.y()) * _HORIZONTAL_RATIO:
            self._gesture_locked = "text"
            self._maybe_dragging = False
            return True

        self._gesture_locked = "reorder"
        return False

    def _start_drag(self):
        if self._drag_active:
            return
        self._drag_active = True
        self.title.clearFocus()
        self.grabMouse()
        self._apply_drag_visual(True)
        self.raise_()
        self.dragStarted.emit(self.task.id)

    def _end_drag(self):
        if not self._drag_active:
            return
        self._drag_active = False
        if self.mouseGrabber() is self:
            self.releaseMouse()
        self._apply_drag_visual(False)
        self.dragEnded.emit(self.task.id)
        self._reset_gesture()

    def _apply_drag_visual(self, on: bool):
        self._dragging_visual = on
        if on:
            self.setObjectName("TaskItemDragging")
            self.setMinimumHeight(self._drag_height)
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(22)
            shadow.setOffset(0, 5)
            shadow.setColor(QColor(0, 0, 0, 100))
            self.setGraphicsEffect(shadow)
            self.setCursor(Qt.ClosedHandCursor)
        else:
            self.setObjectName("TaskItem")
            self.setMinimumHeight(self._base_height)
            self.setGraphicsEffect(None)
            self.setCursor(Qt.OpenHandCursor if self._drag_enabled else Qt.ArrowCursor)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _track_drag(self, global_pos: QPoint):
        if not self._maybe_dragging or not (QApplication.mouseButtons() & Qt.LeftButton):
            return
        if self._try_lock_gesture(global_pos):
            return
        if self._gesture_locked == "text":
            return
        if not self._drag_active:
            if not self._exited_row_vertically(global_pos):
                return
            self._start_drag()
        if self._drag_active:
            self.dragMoved.emit(self.task.id, global_pos)

    def eventFilter(self, obj, event):
        if not self._drag_enabled or obj is not self.title:
            return super().eventFilter(obj, event)

        et = event.type()
        if et == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
            self._begin_gesture(event.globalPosition().toPoint(), in_title=True)
        elif et == QEvent.Type.MouseMove:
            if self._gesture_locked == "text":
                return super().eventFilter(obj, event)
            self._track_drag(event.globalPosition().toPoint())
            if self._drag_active or self._gesture_locked == "reorder":
                return True
        elif et == QEvent.Type.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self._drag_active:
                self._end_drag()
                return True
            self._reset_gesture()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent):
        if (
            self._drag_enabled
            and event.button() == Qt.LeftButton
            and not self._is_action_widget(self.childAt(event.position().toPoint()))
            and not self._press_on_title(event.position().toPoint())
        ):
            self._begin_gesture(event.globalPosition().toPoint(), in_title=False)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._maybe_dragging and (event.buttons() & Qt.LeftButton):
            self._track_drag(event.globalPosition().toPoint())
            if self._drag_active:
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._drag_active and event.button() == Qt.LeftButton:
            self._end_drag()
            return
        if self._maybe_dragging and event.button() == Qt.LeftButton:
            self._reset_gesture()
        super().mouseReleaseEvent(event)

    def _on_highlight_toggle(self, checked: bool):
        self.task.highlighted = checked
        self.highlightToggled.emit(self.task.id, checked)
        self.update()

    def _on_pin_toggle(self, checked: bool):
        self.task.pinned = checked
        self.pin_top_btn.setToolTip("取消置顶" if checked else "置顶")
        self.pinnedToggled.emit(self.task.id, checked)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)

        if self._dragging_visual:
            path = QPainterPath()
            path.addRoundedRect(rect, 14, 14)
            fill = QColor(255, 255, 255, 215)
            p.fillPath(path, fill)
            pen = QPen(self._accent, 2)
            p.setPen(pen)
            p.drawPath(path)
            return

        if not getattr(self.task, "highlighted", False):
            return
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        p.setClipPath(path)
        fill = QColor(self._accent)
        fill.setAlpha(26)
        p.fillRect(rect, fill)
        bar_color = QColor(self._accent)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(bar_color))
        p.drawRoundedRect(QRectF(0, 3, 4, rect.height() - 6), 2, 2)

    def _apply_title_style(self, done: bool):
        self.title.setObjectName("TaskTitleDone" if done else "TaskTitle")
        font = self.title.font()
        font.setStrikeOut(done)
        self.title.setFont(font)
        self.title.style().unpolish(self.title)
        self.title.style().polish(self.title)

    def _on_toggle(self):
        done = self.check.isChecked()
        self._apply_title_style(done)
        self.toggled.emit(self.task.id, done)

    def _on_title_edit(self):
        text = self.title.text().strip()
        if text and text != self.task.title:
            self.task.title = text
            self.title.setToolTip(text)
            self.titleChanged.emit(self.task.id, text)
        self.title.scroll_to_start()

    def set_remaining(self, seconds: int | None):
        if seconds is None or seconds <= 0:
            self.timer_label.setVisible(False)
            return
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        text = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        self.timer_label.setText(text)
        self.timer_label.setVisible(True)
