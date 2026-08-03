"""主题配色：把 styles.qss 模板里的 @ACCENT@ 等占位符换成当前主题的实际颜色。"""
from __future__ import annotations

from PySide6.QtGui import QColor


def _rgba(hex_color: str, alpha: float) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def render_stylesheet(template: str, accent: str) -> str:
    """用主题强调色渲染样式表模板（不用 str.format，避免和 QSS 的花括号冲突）。"""
    return (
        template
        .replace("@ACCENT_SOFT_BG@", _rgba(accent, 0.15))
        .replace("@ACCENT_HOVER_BG@", _rgba(accent, 0.18))
        .replace("@ACCENT@", accent)
    )
