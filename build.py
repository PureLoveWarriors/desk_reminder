"""打包成单文件 exe：python build.py"""
import PyInstaller.__main__

PyInstaller.__main__.run([
    "main.py",
    "--name=DeskReminder",
    "--onefile",
    "--windowed",                          # 不弹黑框
    "--add-data=app/ui/styles.qss;app/ui", # 打包样式表（Windows 用 ;）
    "--add-data=assets/icon.ico;assets",   # 图标资源（运行时设窗口图标用）
    "--icon=assets/icon.ico",              # 程序 exe 图标（缩小版界面风格，替代默认 Python 图标）
    "--noconfirm",
    "--clean",
])
