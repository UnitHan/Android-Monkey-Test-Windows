"""Build from a private snapshot outside both Vite and Tauri's development watch roots."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
VERSION_FILES = (
    "frontend/package.json", "frontend/package-lock.json", "frontend/src-tauri/tauri.conf.json",
    "frontend/src-tauri/Cargo.toml", "frontend/src-tauri/Cargo.lock", "backend/pyproject.toml",
    "backend/uv.lock", "backend/src/monkey_api/__init__.py", "backend/openapi.json", "frontend/src/api/schema.d.ts",
)


def next_version() -> tuple[str, str]:
    current = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))["version"]
    versions = [current]
    for directory in (DIST / "installers", DIST / "release-work"):
        if directory.exists():
            versions.extend(p.name for p in directory.iterdir() if re.fullmatch(r"\d+\.\d+\.\d+", p.name))
    base = max(versions, key=lambda v: tuple(map(int, v.split("."))))
    major, minor, patch = map(int, base.split("."))
    return base, f"{major}.{minor}.{patch + 1}"


def copy_source(stage: Path, base: str) -> None:
    for name in ("scripts", "backend/src", "backend/scripts", "frontend/src", "frontend/public"):
        shutil.copytree(ROOT / name, stage / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "frontend/src-tauri", stage / "frontend/src-tauri",
                    ignore=shutil.ignore_patterns("target", "runtime", ".tauri", "gen"))
    for name in ("backend/pyproject.toml", "backend/uv.lock", "backend/openapi.json",
                 "frontend/package.json", "frontend/package-lock.json", "frontend/index.html",
                 "frontend/tsconfig.json", "frontend/vite.config.ts"):
        shutil.copy2(ROOT / name, stage / name)
    path = stage / "frontend/package.json"
    package = json.loads(path.read_text(encoding="utf-8"))
    package["version"] = base
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def attach_dependencies(stage: Path) -> None:
    # Junction contains installed dependencies only, never live source or Rust build output.
    link, target = stage / "frontend/node_modules", ROOT / "frontend/node_modules"
    def quote(path: Path) -> str:
        return "'" + str(path).replace("'", "''") + "'"
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                    f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} | Out-Null"],
                   check=True, creationflags=subprocess.CREATE_NO_WINDOW)


def main() -> None:
    if os.name != "nt" or not PYTHON.is_file():
        raise SystemExit("Windows build environment and backend virtual environment required.")
    original = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in VERSION_FILES}
    base, version = next_version()
    stage = DIST / "release-work" / version
    stage.mkdir(parents=True, exist_ok=False)
    copy_source(stage, base)
    attach_dependencies(stage)
    env = dict(os.environ, MONKEY_ISOLATED_BUILD=str(stage.resolve()), MONKEY_BUILD_PYTHON=str(PYTHON),
               MONKEY_RELEASE_OUTPUT=str(DIST), MONKEY_SOURCE_ENV_FILE=str(ROOT / ".env"),
               PYTHONPATH=str(stage / "backend/src"), CARGO_TARGET_DIR=str(DIST / "release-target"),
               CARGO_BUILD_JOBS=os.environ.get("CARGO_BUILD_JOBS", "2"))
    print(f"Isolated installer {version}: {stage}", flush=True)
    print("Live development sources, version files and runtime will not be modified.", flush=True)
    try:
        subprocess.run([str(PYTHON), str(stage / "scripts/release_worker.py")], cwd=stage, env=env, check=True,
                       creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    finally:
        changed = [p for p, digest in original.items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest]
        result = {"version": version, "source_version_files_unchanged": not changed, "changed_files": changed}
        (stage / "source-preservation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
