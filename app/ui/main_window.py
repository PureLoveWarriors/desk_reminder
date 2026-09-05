"""主窗口：无边框、置顶、可拖动/拖边框缩放、半透明圆角背景。"""
from __future__ import annotations

import time

from PySide6.QtCore import (
    Qt,
    QEvent,
    QTimer,
    QPoint,
    QRect,
    QRectF,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QBrush,
    QIcon,
    QPixmap,
    QAction,
    QPainterPath,
    QCursor,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSystemTrayIcon,
    QMenu,
    QApplication,
    QGraphicsOpacityEffect,
    QAbstractButton,
    QAbstractSlider,
    QSpinBox,
)

from app import config
from app.core.db import Database
from app.ui.task_item import TaskItemWidget
from app.ui.settings import SettingsPanel, TimerPopup, ExitConfirmPanel
from app.ui.icons import IconButton
from app.ui.theme import render_stylesheet

RESIZE_MARGIN = 14     # 窗口透明边框宽度（也是主热区，点在这里一定能拉）
EDGE_HIT = 22           # 边的缩放热区，略伸进内容，更好抓
CORNER_HIT = 36         # 四角热区更大，角本来就难点
MIN_W, MIN_H = 240, 260

STYLE_PATH = config.resource_path("app/ui/styles.qss")
STYLE_TEMPLATE = STYLE_PATH.read_text(encoding="utf-8") if STYLE_PATH.exists() else ""

_EDGE_CURSORS = {
    "l": Qt.SizeHorCursor,
    "r": Qt.SizeHorCursor,
    "t": Qt.SizeVerCursor,
    "b": Qt.SizeVerCursor,
    "tl": Qt.SizeFDiagCursor,
    "br": Qt.SizeFDiagCursor,
    "tr": Qt.SizeBDiagCursor,
    "bl": Qt.SizeBDiagCursor,
}


def apply_edge_resize(
    geo: QRect, delta: QPoint, edge: str, min_w: int, min_h: int
) -> QRect:
    """按拖拽边/角计算新窗口矩形，并限制最小宽高。"""
    r = QRect(geo)
    if "l" in edge:
        r.setLeft(r.left() + delta.x())
    if "r" in edge:
        r.setRight(r.right() + delta.x())
    if "t" in edge:
        r.setTop(r.top() + delta.y())
    if "b" in edge:
        r.setBottom(r.bottom() + delta.y())
    if r.width() < min_w:
        if "l" in edge:
            r.setLeft(r.right() - min_w)
        else:
            r.setWidth(min_w)
    if r.height() < min_h:
        if "t" in edge:
            r.setTop(r.bottom() - min_h)
        else:
            r.setHeight(min_h)
    return r


def hit_edge(
    x: int,
    y: int,
    w: int,
    h: int,
    edge_hit: int = EDGE_HIT,
    corner_hit: int = CORNER_HIT,
) -> str | None:
    """判断点是否落在缩放热区。四角优先于边。"""
    if x <= corner_hit and y <= corner_hit:
        return "tl"
    if x >= w - corner_hit and y <= corner_hit:
        return "tr"
    if x <= corner_hit and y >= h - corner_hit:
        return "bl"
    if x >= w - corner_hit and y >= h - corner_hit:
        return "br"
    if x <= edge_hit:
        return "l"
    if x >= w - edge_hit:
        return "r"
    if y <= edge_hit:
        return "t"
    if y >= h - edge_hit:
        return "b"
    return None


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        self.cfg.setdefault("theme", config.DEFAULT_THEME_ID)
        self.cfg["accent"] = config.get_theme(self.cfg["theme"])["accent"]
        self.db = Database()
        self._seed_first_run_samples()

        self.item_widgets: dict[int, TaskItemWidget] = {}
        self.showing_completed = False
        self._anims: list = []          # 保持动画引用，避免被回收
        self._drag_pos: QPoint | None = None
        self._resize_edge: str | None = None
        self._resize_origin: QRect | None = None
        self._resize_anchor: QPoint | None = None
        self._reorder_task_id: int | None = None   # 当前正在被拖拽排序的任务
        self._exit_panel: ExitConfirmPanel | None = None

        self.setWindowTitle(config.APP_NAME)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self._apply_window_flags()

        x, y, w, h = self.cfg["geometry"]
        self.setGeometry(x, y, w, h)
        self.setMinimumSize(MIN_W, MIN_H)

        self._build_ui()
        self._install_resize_filters(self)
        self._setup_tray()
        self._reload_list()

        # 每秒刷新倒计时
        self.tick = QTimer(self)
        self.tick.timeout.connect(self._on_tick)
        self.tick.start(1000)

    # ---------- 窗口标志 ----------
    def _apply_window_flags(self):
        flags = Qt.FramelessWindowHint | Qt.Window
        if self.cfg["always_on_top"]:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def showEvent(self, event):
        super().showEvent(event)
        # 置顶切换会重建 HWND，清掉可能残留的拖拽/缩放状态
        self._resize_edge = None
        self._drag_pos = None

    def _seed_first_run_samples(self):
        """新电脑 / 首次打包运行：空库写入三条样例，只做一次。"""
        if self.cfg.get("samples_seeded"):
            return
        self.db.seed_sample_tasks()
        self.cfg["samples_seeded"] = True
        config.save(self.cfg)

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(RESIZE_MARGIN, RESIZE_MARGIN,
                                RESIZE_MARGIN, RESIZE_MARGIN)
        root.setSpacing(8)

        # 标题栏
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 6, 0)
        bar.setSpacing(4)
        bar.setAlignment(Qt.AlignVCenter)
        self.title_label = QLabel("提醒事项")
        self.title_label.setObjectName("TitleLabel")
        bar.addWidget(self.title_label, 0, Qt.AlignVCenter)
        bar.addStretch()

        self.pin_btn = IconButton("pin", "窗口置顶", checkable=True, accent=self.cfg["accent"])
        self.pin_btn.setChecked(self.cfg["always_on_top"])
        self.pin_btn.toggled.connect(self._on_top_toggle)
        bar.addWidget(self.pin_btn, 0, Qt.AlignVCenter)

        self.completed_btn = IconButton("history", "查看已完成", checkable=True, accent=self.cfg["accent"])
        self.completed_btn.toggled.connect(self._toggle_completed_view)
        bar.addWidget(self.completed_btn, 0, Qt.AlignVCenter)

        self.settings_btn = IconButton("gear", "设置")
        self.settings_btn.clicked.connect(self._open_settings)
        bar.addWidget(self.settings_btn, 0, Qt.AlignVCenter)

        self.min_btn = IconButton("minimize", "最小化到托盘")
        self.min_btn.clicked.connect(self.hide)
        bar.addWidget(self.min_btn, 0, Qt.AlignVCenter)

        self.close_btn = IconButton("close", "退出")
        self.close_btn.clicked.connect(self._on_exit_clicked)
        bar.addWidget(self.close_btn, 0, Qt.AlignVCenter)

        self.title_bar = QWidget()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setLayout(bar)
        self.title_bar.setFixedHeight(42)
        root.addWidget(self.title_bar)

        # 添加输入
        self.add_input = QLineEdit()
        self.add_input.setObjectName("AddInput")
        self.add_input.setPlaceholderText("添加任务，回车确认…")
        self.add_input.returnPressed.connect(self._add_task)
        root.addWidget(self.add_input)

        # 任务列表（滚动）
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_container.setObjectName("TaskList")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.list_container)
        root.addWidget(self.scroll, 1)

        # 设置面板嵌在主窗口内（不是独立 Popup，不会有黑角）
        self.settings_panel = SettingsPanel(self.cfg["bg_opacity"], self.cfg["theme"], self)
        self.settings_panel.opacityChanged.connect(self._on_opacity)
        self.settings_panel.themeChanged.connect(self._apply_theme)
        self.settings_panel.exitBehaviorReset.connect(self._reset_exit_behavior)

    def _setup_tray(self):
        icon = self._make_icon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(config.APP_NAME)
        menu = QMenu()
        show_act = QAction("显示", self)
        show_act.triggered.connect(self._show_from_tray)
        quit_act = QAction("退出", self)
        quit_act.triggered.connect(QApplication.quit)
        menu.addAction(show_act)
        menu.addAction(quit_act)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self._show_from_tray()
            if r == QSystemTrayIcon.Trigger else None
        )
        self.tray.show()

    def _make_icon(self) -> QIcon:
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(self.cfg["accent"])))
        p.setPen(Qt.NoPen)
        p.drawEllipse(8, 8, 48, 48)
        p.end()
        return QIcon(pix)

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ---------- 任务 ----------
    def _reload_list(self):
        for w in self.item_widgets.values():
            w.setParent(None)
            w.deleteLater()
        self.item_widgets.clear()
        for t in self.db.list_tasks(done=self.showing_completed):
            self._add_item_widget(t)

    def _toggle_completed_view(self, on: bool):
        self.showing_completed = on
        self.title_label.setText("已完成" if on else "提醒事项")
        self.add_input.setVisible(not on)
        self._reload_list()

    def _add_item_widget(self, task):
        w = TaskItemWidget(task, self.cfg["accent"])
        w.toggled.connect(self._on_task_toggled)
        w.titleChanged.connect(self.db.set_title)
        w.deleteRequested.connect(self._on_task_delete)
        w.timerRequested.connect(self._on_timer_request)
        w.highlightToggled.connect(self._on_highlight_toggled)
        w.pinToTopRequested.connect(self._on_pin_to_top)
        w.dragStarted.connect(self._on_reorder_started)
        w.dragMoved.connect(self._on_reorder_moved)
        w.dragEnded.connect(self._on_reorder_ended)
        w.set_drag_enabled(not self.showing_completed)
        # 插到 stretch 之前
        self.list_layout.insertWidget(self.list_layout.count() - 1, w)
        self.item_widgets[task.id] = w
        self._install_resize_filters(w)
        # 恢复未走完的倒计时显示
        if task.remind_at > time.time():
            w.set_remaining(int(task.remind_at - time.time()))

    def _add_task(self):
        text = self.add_input.text().strip()
        if not text:
            return
        task = self.db.add_task(text)
        self._add_item_widget(task)
        self.add_input.clear()

    def _on_task_toggled(self, task_id: int, done: bool):
        self.db.set_done(task_id, done)
        w = self.item_widgets.get(task_id)
        if not w:
            return
        # 当前视图与勾选状态不一致时，稍后淡出移除
        # 待办视图里被勾完成、或已完成视图里被取消完成 → 从当前列表消失
        if done != self.showing_completed:
            QTimer.singleShot(700, lambda: self._fade_remove(task_id))

    def _fade_remove(self, task_id: int):
        w = self.item_widgets.get(task_id)
        if not w:
            return
        effect = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(350)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)

        def _done():
            ww = self.item_widgets.pop(task_id, None)
            if ww:
                ww.setParent(None)
                ww.deleteLater()
            if anim in self._anims:
                self._anims.remove(anim)

        anim.finished.connect(_done)
        self._anims.append(anim)
        anim.start()

    def _on_task_delete(self, task_id: int):
        self.db.delete_task(task_id)
        w = self.item_widgets.pop(task_id, None)
        if w:
            w.setParent(None)
            w.deleteLater()

    def _on_highlight_toggled(self, task_id: int, highlighted: bool):
        self.db.set_highlighted(task_id, highlighted)

    def _on_pin_to_top(self, task_id: int):
        if self.showing_completed:
            return
        w = self.item_widgets.get(task_id)
        if not w:
            return
        self.list_layout.removeWidget(w)
        self.list_layout.insertWidget(0, w)
        self._persist_order()

    # ---------- 拖拽排序（仅待办列表） ----------
    def _on_reorder_started(self, task_id: int):
        if self.showing_completed:
            return
        self._reorder_task_id = task_id
        w = self.item_widgets.get(task_id)
        if w:
            w.raise_()

    def _on_reorder_moved(self, task_id: int, global_pos: QPoint):
        if self.showing_completed or self._reorder_task_id != task_id:
            return
        w = self.item_widgets.get(task_id)
        if not w:
            return
        local_y = self.list_container.mapFromGlobal(global_pos).y()
        count = self.list_layout.count() - 1  # 去掉末尾的 stretch
        cur_index = self.list_layout.indexOf(w)
        target_index = count  # 默认：拖到所有任务最后面
        for i in range(count):
            item_w = self.list_layout.itemAt(i).widget()
            if item_w is None or item_w is w:
                continue
            mid = item_w.y() + item_w.height() / 2
            if local_y < mid:
                target_index = i
                break
        if target_index > cur_index:
            target_index -= 1  # 移除自己后，后面的位置要往前补一位
        if target_index != cur_index:
            self.list_layout.removeWidget(w)
            self.list_layout.insertWidget(target_index, w)
        self._autoscroll_for_drag(global_pos)

    def _on_reorder_ended(self, task_id: int):
        if self._reorder_task_id != task_id:
            return
        self._reorder_task_id = None
        self._persist_order()

    def _persist_order(self):
        n = self.list_layout.count() - 1  # 去掉末尾的 stretch
        for idx in range(n):
            item_w = self.list_layout.itemAt(idx).widget()
            if item_w is None:
                continue
            # 待办列表按 sort_order 降序显示，最上面的要给最大的值
            self.db.set_sort_order(item_w.task.id, n - idx)

    def _autoscroll_for_drag(self, global_pos: QPoint):
        viewport = self.scroll.viewport()
        local = viewport.mapFromGlobal(global_pos)
        margin = 24
        bar = self.scroll.verticalScrollBar()
        if local.y() < margin:
            bar.setValue(bar.value() - 12)
        elif local.y() > viewport.height() - margin:
            bar.setValue(bar.value() + 12)

    # ---------- 倒计时 ----------
    def _on_timer_request(self, task_id: int):
        w = self.item_widgets.get(task_id)
        if not w:
            return
        cur_min = int(w.task.duration // 60) if w.task.duration else 25
        if hasattr(self, "_timer_popup") and self._timer_popup:
            self._timer_popup.hide()
            self._timer_popup.deleteLater()
        popup = TimerPopup(cur_min, self)
        popup.accepted.connect(lambda m, tid=task_id: self._set_timer(tid, m))
        self._timer_popup = popup
        anchor = w.timer_btn.mapToGlobal(w.timer_btn.rect().bottomLeft())
        popup.show_at(anchor, self)

    def _set_timer(self, task_id: int, minutes: int):
        w = self.item_widgets.get(task_id)
        if not w:
            return
        if minutes <= 0:
            self.db.set_timer(task_id, 0, 0)
            w.task.duration = 0
            w.task.remind_at = 0
            w.set_remaining(None)
            return
        remind_at = time.time() + minutes * 60
        self.db.set_timer(task_id, minutes * 60, remind_at)
        w.task.duration = minutes * 60
        w.task.remind_at = remind_at
        w.set_remaining(minutes * 60)

    def _on_tick(self):
        now = time.time()
        for task_id, w in list(self.item_widgets.items()):
            if w.task.remind_at and w.task.remind_at > 0:
                remaining = w.task.remind_at - now
                if remaining <= 0:
                    self._fire_reminder(w)
                else:
                    w.set_remaining(int(remaining))

    def _fire_reminder(self, w: TaskItemWidget):
        w.task.remind_at = 0
        w.set_remaining(None)
        self.db.set_timer(w.task.id, w.task.duration, 0)
        self.tray.showMessage(
            "时间到 \u23f0",
            w.task.title,
            self._make_icon(),
            10000,
        )
        QApplication.beep()
        if not self.isVisible():
            self._show_from_tray()

    # ---------- 设置 ----------
    def _open_settings(self):
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
            return
        anchor = self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft())
        self.settings_panel.slider.setValue(self.cfg["bg_opacity"])
        self.settings_panel.set_theme(self.cfg["theme"])
        self.settings_panel.show_at(anchor, self)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        # 点面板外关闭设置（点齿轮按钮本身由 _open_settings 处理）
        if self.settings_panel.isVisible():
            if not self.settings_panel.geometry().contains(pos) and \
                    not self.settings_btn.geometry().contains(
                        self.title_bar.mapFrom(self, pos)):
                self.settings_panel.hide()
        if hasattr(self, "_timer_popup") and self._timer_popup and self._timer_popup.isVisible():
            if not self._timer_popup.geometry().contains(pos):
                self._timer_popup.hide()
        if self._exit_panel and self._exit_panel.isVisible():
            if not self._exit_panel.geometry().contains(pos):
                self._exit_panel.hide()
        if event.button() != Qt.LeftButton:
            return

        # 缩放必须走 Qt 坐标，不能再交给 WM_NCHITTEST：
        # 新电脑常见 125%/150% 缩放时，原生命中会把整窗当成边框，按钮全点不了
        edge = self._edge_at(pos)
        if edge:
            self._begin_resize(edge, event.globalPosition().toPoint())
            return

        if self.title_bar.geometry().contains(pos):
            # 点在按钮上时不拖动窗口
            child = self.childAt(pos)
            if child is None or child is self.title_bar or child is self.title_label:
                self._drag_pos = (event.globalPosition().toPoint()
                                  - self.frameGeometry().topLeft())
            else:
                self._drag_pos = None
        else:
            self._drag_pos = None

    def _on_opacity(self, value: int):
        self.cfg["bg_opacity"] = value
        self.update()

    def _on_top_toggle(self, on: bool):
        if self.cfg["always_on_top"] == on:
            return
        self.cfg["always_on_top"] = on
        # 改窗口标志会重建窗口，先断开信号避免递归
        self.pin_btn.blockSignals(True)
        self._apply_window_flags()
        self.show()
        self.pin_btn.setChecked(on)
        self.pin_btn.blockSignals(False)

    # ---------- 配色主题 ----------
    def _apply_theme(self, theme_id: str):
        theme = config.get_theme(theme_id)
        self.cfg["theme"] = theme_id
        self.cfg["accent"] = theme["accent"]
        self._refresh_theme_visuals()
        config.save(self.cfg)

    def _refresh_theme_visuals(self):
        accent = self.cfg["accent"]
        if STYLE_TEMPLATE:
            app = QApplication.instance()
            app.setStyleSheet(render_stylesheet(STYLE_TEMPLATE, accent))
        self.pin_btn.set_accent(accent)
        self.completed_btn.set_accent(accent)
        for w in self.item_widgets.values():
            w.set_accent(accent)
        self.tray.setIcon(self._make_icon())
        self.update()

    # ---------- 退出行为 ----------
    def _on_exit_clicked(self):
        behavior = self.cfg.get("exit_behavior", "ask")
        if behavior == "minimize":
            self.hide()
        elif behavior == "quit":
            QApplication.quit()
        else:
            self._show_exit_confirm()

    def _show_exit_confirm(self):
        if self._exit_panel is None:
            self._exit_panel = ExitConfirmPanel(self)
            self._exit_panel.decided.connect(self._on_exit_decided)
        self._exit_panel.show_centered(self)

    def _on_exit_decided(self, behavior: str, remember: bool):
        if remember:
            self.cfg["exit_behavior"] = behavior
            config.save(self.cfg)
        if behavior == "minimize":
            self.hide()
        else:
            QApplication.quit()

    def _reset_exit_behavior(self):
        self.cfg["exit_behavior"] = "ask"
        config.save(self.cfg)

    # ---------- 半透明圆角背景 ----------
    def paintEvent(self, _event):
        radius = 18
        theme = config.get_theme(self.cfg.get("theme", config.DEFAULT_THEME_ID))
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(
            RESIZE_MARGIN, RESIZE_MARGIN, -RESIZE_MARGIN, -RESIZE_MARGIN)

        outer_path = QPainterPath()
        outer_path.addRoundedRect(rect, radius, radius)
        p.setClipPath(outer_path)

        alpha = int(255 * self.cfg["bg_opacity"] / 100)
        body_color = QColor(theme["body"])
        body_color.setAlpha(alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(body_color))
        p.drawRect(rect)

        # 顶部工具栏：用主题顶部色，更不透明一点，和正文区分开
        bar_rect = QRectF(rect.left(), rect.top(), rect.width(), self.title_bar.height())
        bar_alpha = min(255, alpha + 45)
        top_color = QColor(theme["top"])
        top_color.setAlpha(bar_alpha)
        p.setBrush(QBrush(top_color))
        p.drawRect(bar_rect)

        # 分隔线
        p.setPen(QColor(0, 0, 0, 22))
        p.drawLine(rect.left(), bar_rect.bottom(), rect.right(), bar_rect.bottom())

    # ---------- 缩放（Qt 自己处理，避免高 DPI 下 WM_NCHITTEST 吞掉点击）----------
    def _edge_at(self, pos: QPoint):
        return hit_edge(pos.x(), pos.y(), self.width(), self.height())

    def _begin_resize(self, edge: str, global_pos: QPoint):
        self._resize_edge = edge
        self._resize_origin = QRect(self.geometry())
        self._resize_anchor = QPoint(global_pos)
        self.grabMouse()

    def _install_resize_filters(self, widget: QWidget):
        widget.installEventFilter(self)
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)
            child.setMouseTracking(True)

    def _widget_allows_resize_grab(self, obj) -> bool:
        """按钮、输入框、设置面板上的点击不抢，避免热区加大后点不到控件。"""
        w = obj if isinstance(obj, QWidget) else None
        while w is not None and w is not self:
            if isinstance(w, (QAbstractButton, QLineEdit, QSpinBox, QAbstractSlider)):
                return False
            if isinstance(w, (SettingsPanel, TimerPopup, ExitConfirmPanel)):
                return False
            w = w.parentWidget()
        return True

    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
            if self._widget_allows_resize_grab(obj):
                pos = self.mapFromGlobal(event.globalPosition().toPoint())
                edge = self._edge_at(pos)
                if edge:
                    self._begin_resize(edge, event.globalPosition().toPoint())
                    return True
        elif et == QEvent.Type.MouseMove and not self._resize_edge and not self._drag_pos:
            if isinstance(obj, QWidget) and (obj is self or self.isAncestorOf(obj)):
                pos = self.mapFromGlobal(event.globalPosition().toPoint())
                if self.rect().contains(pos):
                    edge = self._edge_at(pos)
                    cursor = _EDGE_CURSORS.get(edge, Qt.ArrowCursor)
                    self.setCursor(cursor)
                    if obj is not self and self._widget_allows_resize_grab(obj):
                        if edge:
                            obj.setCursor(cursor)
                        else:
                            obj.unsetCursor()
        return super().eventFilter(obj, event)

    def _update_edge_cursor(self, pos: QPoint):
        edge = self._edge_at(pos)
        self.setCursor(_EDGE_CURSORS.get(edge, Qt.ArrowCursor))

    def mouseMoveEvent(self, event):
        if self._resize_edge and self._resize_origin and self._resize_anchor:
            delta = event.globalPosition().toPoint() - self._resize_anchor
            self.setGeometry(
                apply_edge_resize(
                    self._resize_origin, delta, self._resize_edge, MIN_W, MIN_H
                )
            )
            return
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            return
        self._update_edge_cursor(event.position().toPoint())

    def mouseReleaseEvent(self, _event):
        if self._resize_edge:
            self.releaseMouse()
        self._resize_edge = None
        self._resize_origin = None
        self._resize_anchor = None
        self._drag_pos = None
        self._update_edge_cursor(self.mapFromGlobal(QCursor.pos()))

    def leaveEvent(self, event):
        if not self._resize_edge:
            self.unsetCursor()
        super().leaveEvent(event)

    # ---------- 退出保存 ----------
    def closeEvent(self, event):
        self._save_state()
        super().closeEvent(event)

    def _save_state(self):
        g = self.geometry()
        self.cfg["geometry"] = [g.x(), g.y(), g.width(), g.height()]
        config.save(self.cfg)
