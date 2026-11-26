"""Create/refresh backend/.venv with the standard library venv + pip (no uv required).

    python backend/scripts/setup_venv.py          # runtime + dev dependencies
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
VENV = BACKEND / ".venv"
PY = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, check=True, cwd=BACKEND)


def main() -> None:
    if sys.version_info < (3, 12):
        sys.exit(f"Python 3.12+ required, found {sys.version.split()[0]}")
    if not PY.exists():
        venv.EnvBuilder(with_pip=True, upgrade_deps=True).create(VENV)
    elif subprocess.run([str(PY), "-m", "pip", "--version"], capture_output=True).returncode != 0:
        run(str(PY), "-m", "ensurepip", "--upgrade")
    run(str(PY), "-m", "pip", "install", "--upgrade", "pip")
    run(str(PY), "-m", "pip", "install", "-e", ".", "--group", "dev")
    print(f"\nvenv ready: {PY}")


if __name__ == "__main__":
    main()
