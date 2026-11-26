"""Preserve the configured Google login and Gemini key inside an encrypted release vault."""

import os
import secrets
import subprocess
from pathlib import Path

from monkey_api.adapters.storage.deployment_vault import decrypt_bundle, encrypt_bundle
from monkey_api.core.settings import Settings
from monkey_api.services.deployment_settings import snapshot

ROOT = Path(__file__).resolve().parents[1]


def package_settings(version: str, executable: Path) -> None:
    payload = snapshot(Settings(_env_file=os.environ.get("MONKEY_SOURCE_ENV_FILE", ROOT / ".env")))
    password = secrets.token_urlsafe(32)
    envelope = encrypt_bundle(payload, password)
    if decrypt_bundle(envelope, password) != payload:
        raise RuntimeError("Deployment credential verification failed")
    private = Path(os.environ.get("MONKEY_RELEASE_OUTPUT", ROOT / "dist")) / "private-release" / version
    private.mkdir(parents=True, exist_ok=True)
    account = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}"
    subprocess.run(["icacls", str(private), "/inheritance:r", "/grant:r", f"{account}:(OI)(CI)F",
                    "*S-1-5-18:(OI)(CI)F"], check=True, capture_output=True)
    (private / "deployment-password.txt").write_text(password + "\n", encoding="utf-8")
    (executable.parent / "deployment.vault.json").write_text(envelope, encoding="utf-8")
    print("Existing Google client, OAuth login and Gemini key included in encrypted deployment vault.", flush=True)
    print(f"Deployment password file (not included in installer): {private / 'deployment-password.txt'}", flush=True)
