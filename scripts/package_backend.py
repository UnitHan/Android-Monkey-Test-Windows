"""Build a self-contained backend and copy an explicit allowlist of Android tools."""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PYTHON = Path(os.environ.get("MONKEY_BUILD_PYTHON", BACKEND / ".venv/Scripts/python.exe"))
RUNTIME = ROOT / "frontend/src-tauri/runtime"
BUILD = ROOT / "dist/installer-build"


def run(args: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def package_backend() -> Path:
    if os.name != "nt":
        raise SystemExit("Build the Windows installer on Windows x64.")
    if not RUNTIME.resolve().is_relative_to(ROOT.resolve()) or RUNTIME.is_symlink():
        raise SystemExit("Runtime output must stay inside the workspace.")
    sdk = Path(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
               or Path.home() / "AppData/Local/Android/Sdk")
    platform = sdk / "platform-tools"
    aapt = sorted((sdk / "build-tools").glob("*/aapt2.exe"),
                  key=lambda p: tuple(int(n) if n.isdigit() else 0 for n in p.parent.name.split(".")))
    if not aapt or not (platform / "adb.exe").is_file():
        raise SystemExit("Build PC requires Android SDK platform-tools and build-tools (ANDROID_HOME).")
    BUILD.mkdir(parents=True, exist_ok=True)
    run([str(PYTHON), "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "monkey-backend",
         "--distpath", str(RUNTIME), "--workpath", str(BUILD / "pyinstaller"), "--specpath", str(BUILD),
         "--paths", str(BACKEND / "src"), "--collect-all", "monkey_api", "--collect-data", "certifi",
         str(BACKEND / "scripts/frozen_entry.py")])
    tools = RUNTIME / "monkey-backend/tools"
    tools.mkdir(parents=True, exist_ok=True)
    for name in ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "libwinpthread-1.dll", "NOTICE.txt", "source.properties"):
        source = platform / name
        if source.is_file():
            shutil.copy2(source, tools / name)
        elif name in ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "NOTICE.txt"):
            raise SystemExit(f"Missing Android runtime file: {name}")
    shutil.copy2(aapt[-1], tools / "aapt2.exe")
    shutil.copy2(aapt[-1].parent / "NOTICE.txt", tools / "aapt2-NOTICE.txt")
    return RUNTIME / "monkey-backend/monkey-backend.exe"


if __name__ == "__main__":
    print(package_backend())
