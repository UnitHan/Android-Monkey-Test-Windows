"""Build the ported AppkiumPerf protocol 1 collector without its desktop/Gradle project.

The original nine Java source files live in device_tools/perf_agent/src.
Requires a JDK and Android SDK; runtime uses the bundled appkium-android.jar.
"""

import argparse
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(android_jar: Path, build_tools: Path, output: Path) -> None:
    java, javac = shutil.which("java"), shutil.which("javac")
    if not java or not javac:
        raise SystemExit("A JDK (java and javac on PATH) is required")
    d8 = build_tools / "lib" / "d8.jar"
    if not android_jar.is_file() or not d8.is_file():
        raise SystemExit("Valid Android SDK android.jar and build-tools/lib/d8.jar are required")
    sources = sorted((ROOT / "device_tools" / "perf_agent" / "src").rglob("*.java"))
    if not sources:
        raise SystemExit("Collector Java sources are missing")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryDirectory(prefix=".perf-build-", dir=ROOT) as temp:
        work = Path(temp)
        classes, dex = work / "classes", work / "dex"
        classes.mkdir()
        dex.mkdir()
        subprocess.run(
            [
                javac,
                "--release",
                "8",
                "-encoding",
                "UTF-8",
                "-classpath",
                str(android_jar),
                "-d",
                str(classes),
                *map(str, sources),
            ],
            check=True,
            creationflags=flags,
        )
        _dex(java, d8, android_jar, classes, dex, flags)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".jar.tmp")
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(dex / "classes.dex", "classes.dex")
        temporary.replace(output)


def _dex(java: str, d8: Path, android_jar: Path, classes: Path, dex: Path, flags: int) -> None:
    class_jar = classes.parent / "agent-classes.jar"
    with zipfile.ZipFile(class_jar, "w") as archive:
        for compiled in sorted(classes.rglob("*.class")):
            archive.write(compiled, compiled.relative_to(classes).as_posix())
    subprocess.run(
        [
            java,
            "-cp",
            str(d8),
            "com.android.tools.r8.D8",
            "--release",
            "--min-api",
            "21",
            "--lib",
            str(android_jar),
            "--output",
            str(dex),
            str(class_jar),
        ],
        check=True,
        creationflags=flags,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android-jar", type=Path, required=True)
    parser.add_argument("--build-tools", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "src/monkey_api/data/appkium-android.jar")
    args = parser.parse_args()
    build(args.android_jar, args.build_tools, args.output)
    print(f"Built {args.output.name} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
