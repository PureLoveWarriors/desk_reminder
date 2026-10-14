"""把 dist/DeskReminder.exe 打成安装包：python build_setup.py

需要本机已安装 Inno Setup 6。程序本体仍由 python build.py 生成。
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(ROOT, "dist", "DeskReminder.exe")
ISS = os.path.join(ROOT, "installer", "desk_reminder.iss")
SETUP = os.path.join(ROOT, "dist", "DeskReminder-Setup.exe")


def find_iscc():
    bases = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        bases.append(os.path.join(local, "Programs"))
    for key in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(key)
        if base:
            bases.append(base)
    for base in bases:
        path = os.path.join(base, "Inno Setup 6", "ISCC.exe")
        if os.path.isfile(path):
            return path
    return shutil.which("ISCC")


def main():
    if not os.path.isfile(EXE):
        sys.exit("找不到 dist/DeskReminder.exe。请先执行: python build.py")
    iscc = find_iscc()
    if not iscc:
        sys.exit("未找到 Inno Setup 6（ISCC.exe）。请先安装 Inno Setup 6。")
    subprocess.check_call([iscc, ISS])
    if not os.path.isfile(SETUP):
        sys.exit(f"编译结束但未生成 {SETUP}")
    print(f"安装包: {SETUP}")


if __name__ == "__main__":
    main()
