"""桌面提醒事项 - 入口。"""
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import config
from app.ui.main_window import MainWindow
from app.ui.theme import render_stylesheet

STYLE_PATH = config.resource_path("app/ui/styles.qss")
ICON_PATH = config.resource_path("assets/icon.ico")


def _install_crash_logger():
    import traceback
    from app import config

    log_path = config.DATA_DIR / "error.log"

    def hook(exc_type, exc, tb):
        with open(log_path, "a", encoding="utf-8") as f:
            traceback.print_exception(exc_type, exc, tb, file=f)
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook


def main():
    _install_crash_logger()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关到托盘也不退出

    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    if STYLE_PATH.exists():
        cfg = config.load()
        template = STYLE_PATH.read_text(encoding="utf-8")
        app.setStyleSheet(render_stylesheet(template, cfg["accent"]))

    win = MainWindow()
    app.aboutToQuit.connect(win._save_state)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
