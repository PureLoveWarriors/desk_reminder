"""窗口/外观配置的读写，存到用户目录下的 JSON。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "DeskReminder"


def resource_path(rel: str) -> Path:
    """兼容开发运行和 PyInstaller 打包后的资源路径。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    return base / rel


def _resolve_data_dir() -> Path:
    """默认 ~/.deskreminder；截图/测试可设环境变量 DESK_REMINDER_HOME 指向临时目录。"""
    override = os.environ.get("DESK_REMINDER_HOME", "").strip()
    path = Path(override).expanduser() if override else Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


# 数据统一放在用户目录，打包成 exe 后也能正常写入
DATA_DIR = _resolve_data_dir()
CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "reminder.db"

# 配色预设：id / 名称 / 顶部栏颜色 / 主体背景色 / 强调色（圆圈、高亮、滑块等）
THEME_PRESETS = [
    {"id": "classic", "name": "经典白", "top": "#ffffff", "body": "#fafafa", "accent": "#ff6b6b"},
    {"id": "sunshine", "name": "暖阳黄", "top": "#ffe9a8", "body": "#fffdf6", "accent": "#ff9f1c"},
    {"id": "mint", "name": "薄荷绿", "top": "#c8f4de", "body": "#f5fffa", "accent": "#2ec4b6"},
    {"id": "sky", "name": "天空蓝", "top": "#cde7ff", "body": "#f5faff", "accent": "#4a90e2"},
    {"id": "sakura", "name": "樱花粉", "top": "#ffd6e8", "body": "#fff7fa", "accent": "#ff6b9d"},
]
DEFAULT_THEME_ID = THEME_PRESETS[0]["id"]


def get_theme(theme_id: str) -> dict:
    for t in THEME_PRESETS:
        if t["id"] == theme_id:
            return t
    return THEME_PRESETS[0]


DEFAULTS = {
    "geometry": [200, 200, 320, 380],   # x, y, w, h
    "bg_opacity": 85,                    # 背景透明度 0-100
    "always_on_top": True,
    "accent": "#ff6b6b",                # 圆圈/强调色（跟随主题预设）
    "theme": DEFAULT_THEME_ID,           # 配色预设 id
    "exit_behavior": "ask",              # ask / minimize / quit：点退出按钮的行为
}


def load() -> dict:
    data = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            data.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save(data: dict) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
