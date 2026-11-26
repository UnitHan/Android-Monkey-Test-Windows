"""Rebuild the tiny, auditable device label reader with a JDK and Android SDK."""

import argparse
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--android-jar", required=True, type=Path)
    parser.add_argument("--build-tools", required=True, type=Path)
    args = parser.parse_args()
    java = shutil.which("java")
    javac = shutil.which("javac")
    if not java or not javac:
        raise SystemExit("A JDK (java and javac on PATH) is required")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp)
        subprocess.run(
            [
                javac,
                "--release",
                "8",
                "-classpath",
                str(args.android_jar),
                "-d",
                str(out),
                str(ROOT / "device_tools" / "AppLabels.java"),
            ],
            check=True,
            creationflags=flags,
        )
        subprocess.run(
            [
                java,
                "-cp",
                str(args.build_tools / "lib" / "d8.jar"),
                "com.android.tools.r8.D8",
                "--lib",
                str(args.android_jar),
                "--min-api",
                "26",
                "--output",
                str(out),
                str(out / "AppLabels.class"),
            ],
            check=True,
            creationflags=flags,
        )
        target = ROOT / "src" / "monkey_api" / "data" / "app_labels.jar"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo("classes.dex", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (out / "classes.dex").read_bytes())
        print(f"Built {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
