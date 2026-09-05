"""打包成单文件 exe：python build.py"""
import os
import subprocess
import sys
import time

OUTPUT_EXE = os.path.abspath(os.path.join("dist", "DeskReminder.exe"))
_EXE_NAME = "DeskReminder.exe"


def _remove_output_exe():
    """删除旧 exe。成功或不存在返回 True，仍被占用返回 False。"""
    if not os.path.isfile(OUTPUT_EXE):
        return True
    try:
        os.remove(OUTPUT_EXE)
        return True
    except PermissionError:
        return False
    except OSError as exc:
        sys.exit(f"无法删除旧的 {OUTPUT_EXE}: {exc}")


def _kill_packaged_app():
    if sys.platform != "win32":
        return
    print(f"检测到 {_EXE_NAME} 被占用，正在结束相关进程…")
    kwargs = {"capture_output": True, "check": False}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run(["taskkill", "/F", "/IM", _EXE_NAME], **kwargs)


def _ensure_output_writable():
    """Windows 上正在运行的 exe 会被锁定，PyInstaller 无法覆盖。"""
    if _remove_output_exe():
        return

    _kill_packaged_app()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _remove_output_exe():
            return
        time.sleep(0.25)

    sys.exit(
        f"无法覆盖 {OUTPUT_EXE}。\n"
        "请先关闭正在运行的 DeskReminder，然后重新执行: python build.py"
    )


try:
    import PySide6  # noqa: F401
except ImportError:
    sys.exit("未安装 PySide6，无法打包。请先执行: pip install -r requirements.txt")

try:
    import PyInstaller.__main__
except ImportError:
    sys.exit("未安装 PyInstaller，无法打包。请先执行: pip install pyinstaller")

_ensure_output_writable()

PyInstaller.__main__.run([
    "main.py",
    "--name=DeskReminder",
    "--onefile",
    "--windowed",                          # 不弹黑框
    "--add-data=app/ui/styles.qss;app/ui", # 打包样式表（Windows 用 ;）
    "--add-data=assets/icon.ico;assets",   # 图标资源（运行时设窗口图标用）
    "--icon=assets/icon.ico",              # 程序 exe 图标（缩小版界面风格，替代默认 Python 图标）
    "--manifest=assets/app.manifest",      # Per-Monitor V2，避免新电脑缩放后点不到
    "--noconfirm",
    "--clean",
])
