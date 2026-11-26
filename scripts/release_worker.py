"""Release entry point: increment patch version once, freeze backend, build offline NSIS."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from package_backend import BACKEND, PYTHON, ROOT, package_backend
from package_settings import package_settings

FRONTEND = ROOT / "frontend"


def bump_version() -> str:
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    major, minor, patch = map(int, package["version"].split("."))
    version = f"{major}.{minor}.{patch + 1}"
    for path in (FRONTEND / "package.json", FRONTEND / "package-lock.json", FRONTEND / "src-tauri/tauri.conf.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = version
        if "packages" in data:
            data["packages"][""]["version"] = version
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in (BACKEND / "pyproject.toml", FRONTEND / "src-tauri/Cargo.toml"):
        content = path.read_text(encoding="utf-8")
        content = re.sub(r'(?m)^version = "[^"]+"', f'version = "{version}"', content, count=1)
        path.write_text(content, encoding="utf-8")
    for path, name in ((BACKEND / "uv.lock", "monkey-api"), (FRONTEND / "src-tauri/Cargo.lock", "monkey-test")):
        content = path.read_text(encoding="utf-8")
        content = re.sub(rf'(name = "{name}"\nversion = ")[^"]+', rf'\g<1>{version}', content)
        path.write_text(content, encoding="utf-8")
    (BACKEND / "src/monkey_api/__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    return version


def run(args: list[str], cwd: Path, env: dict | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main() -> None:
    if os.environ.get("MONKEY_ISOLATED_BUILD") != str(ROOT.resolve()):
        raise SystemExit("Use npm run installer; release builds require an isolated source snapshot.")
    if os.name != "nt" or not PYTHON.is_file():
        raise SystemExit("Windows build environment required. Run backend setup first.")
    npm = shutil.which("npm.cmd")
    if not npm:
        raise SystemExit("Build PC requires Node.js/npm.")
    version = bump_version()
    print(f"Building installer {version} (patch incremented)", flush=True)
    run([str(PYTHON), "scripts/export_openapi.py"], BACKEND)
    run([npm, "run", "gen:api"], FRONTEND)
    executable = package_backend()
    package_settings(version, executable)
    run([str(PYTHON), "scripts/verify_runtime.py"], ROOT)
    env = dict(os.environ, MONKEY_RELEASE_BUILD=version, VITE_API_ORIGIN="http://127.0.0.1:8765")
    run([npm, "run", "tauri", "--", "build", "--config", "src-tauri/tauri.release.conf.json"], FRONTEND, env)
    finalize_installer(version)


def finalize_installer(version: str) -> None:
    """Copy a completed bundle and write a checksum that supports Korean filenames."""
    bundle = Path(os.environ["CARGO_TARGET_DIR"]) / "release/bundle/nsis"
    installers = list(bundle.glob(f"*_{version}_*.exe"))
    if not installers:
        raise SystemExit("Installer was not produced.")
    output = Path(os.environ["MONKEY_RELEASE_OUTPUT"]) / "installers" / version
    output.mkdir(parents=True, exist_ok=True)
    for source in installers:
        target = output / source.name
        shutil.copy2(source, target)
        with target.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        target.with_suffix(".exe.sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
        print(f"Installer: {target}", flush=True)


if __name__ == "__main__":
    main()
