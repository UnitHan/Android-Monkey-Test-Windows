"""Exercise a frozen backend with no developer tools on PATH and isolated user data."""

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from monkey_api.adapters.storage.secrets import read_secret
from monkey_api.core.settings import Settings
from monkey_api.services.deployment_settings import snapshot

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "frontend/src-tauri/runtime/monkey-backend/monkey-backend.exe"
PORT = 18765
BASE = f"http://127.0.0.1:{PORT}/api/v1"


def request(path: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        content = response.read()
        return json.loads(content) if "json" in response.headers.get("Content-Type", "") else content


def launch(env: dict, cwd: Path):
    process = subprocess.Popen([str(EXE)], env=env, cwd=cwd, creationflags=0x08000000,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError(process.stderr.read().decode(errors="replace"))
        try:
            health = request("/health")
            return process, health
        except (OSError, urllib.error.URLError):
            time.sleep(.25)
    process.terminate()
    process.wait(timeout=15)
    raise RuntimeError("Frozen backend did not become ready")


def verify_preserved_settings(work: Path, version: str) -> None:
    if not (EXE.parent / "deployment.vault.json").is_file():
        return
    output = Path(os.environ.get("MONKEY_RELEASE_OUTPUT", ROOT / "dist"))
    password = (output / "private-release" / version / "deployment-password.txt").read_text(encoding="utf-8").strip()
    original = snapshot(Settings(_env_file=os.environ.get("MONKEY_SOURCE_ENV_FILE", ROOT / ".env")))
    status = request("/settings/deployment/unlock", "POST", {"password": password})
    assert status["configured"] and status["account"] == "datasvcqa@gmail.com"
    for key, filename in (("client", "play-client.json"), ("oauth", "play-oauth.json"), ("gemini", "gemini.enc.json")):
        restored = json.loads(read_secret(work / "data/credentials" / filename))
        assert restored == original[key], f"Packaged {key} did not preserve the registered setting"
    assert request("/settings/ai")["configured"]
    assert request("/play/auth")["credentials_saved"]
    print("Packaged Google client, OAuth token and Gemini key restored identically in empty user data.")


def main():
    expected_version = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))["version"]
    resources = EXE.parent / "_internal/monkey_api"
    for relative in ("data/appkium-android.jar", "data/app_labels.jar", "adapters/report/report.html.j2"):
        assert (resources / relative).is_file(), f"Missing packaged resource: {relative}"
    forbidden = {".env", "play-oauth.json", "play-client.json", "gemini.enc.json", "deployment-password.txt"}
    assert not any(path.name in forbidden or path.name.startswith("client_secret") for path in EXE.parent.rglob("*"))
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("MONKEY_", "PYTHON", "VIRTUAL_ENV", "ANDROID_"))}
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    with tempfile.TemporaryDirectory(prefix="monkey-runtime-") as directory:
        work = Path(directory)
        env.update(MONKEY_PORT=str(PORT), MONKEY_DATA_DIR=str(work / "data"), MONKEY_EXPORT_DIR=str(work / "exports"))
        process, health = launch(env, work)
        try:
            assert health["status"] == "ok" and "runtime" in health["adb"]["path"]
            assert health["version"] == expected_version
            initial = request("/settings/ai")
            assert Path(initial["config_file"]) == work / "data/credentials/gemini.enc.json"
            assert not initial["configured"]
            verify_preserved_settings(work, expected_version)
            assert len(request("/presets")["items"]) == 6
            saved = request("/settings/ai", "PUT", {"api_key": "synthetic-test-key", "model": "test-model"})
            assert saved["configured"]
            assert "synthetic-test-key" not in (work / "data/credentials/gemini.enc.json").read_text()
            session = request("/sessions", "POST", {"device_serial": "FAKE", "package": "com.example.test", "preset_id": "smoke"})
            assert b"<html" in request(f"/sessions/{session['id']}/report.html")
            assert request(f"/sessions/{session['id']}/report.xlsx").startswith(b"PK")
        finally:
            process.terminate()
            process.wait(timeout=15)
        process, _ = launch(env, work)
        try:
            assert request("/settings/ai")["configured"]
            assert not request("/settings/ai", "DELETE")["configured"]
        finally:
            process.terminate()
            process.wait(timeout=15)
    print(json.dumps({"standalone": True, "version": health["version"], "bundled_adb": True,
                      "encrypted_key_restart": True, "html_xlsx": True}))


if __name__ == "__main__":
    main()
