"""Selected-app extraction with a device/install-specific persistent PNG cache."""

import asyncio
import base64
import hashlib
import tempfile
from pathlib import Path

from monkey_api.adapters.adb.apk_icon import ApkIconRenderer
from monkey_api.adapters.adb.app_labels import read_icon
from monkey_api.adapters.adb.package_assets import apk_paths, installation_identity
from monkey_api.adapters.adb.runner import AdbPort, run_checked
from monkey_api.core.errors import AdbError
from monkey_api.core.icon_errors import IconUnavailable
from monkey_api.core.logging import log
from monkey_api.domain.icon import AppIcon


class IconService:
    def __init__(self, adb: AdbPort, renderer: ApkIconRenderer, root: Path) -> None:
        self.adb, self.renderer, self.root = adb, renderer, root
        self._lock = asyncio.Lock()

    async def get(self, serial: str, package: str) -> AppIcon:
        async with self._lock:
            paths = apk_paths(await run_checked(self.adb, ["shell", "pm", "path", package], serial=serial))
            identity = installation_identity(
                await run_checked(self.adb, ["shell", "dumpsys", "package", package], serial=serial)
            )
            key = hashlib.sha256(f"v2\n{serial}\n{package}\n{identity}\n{paths}".encode()).hexdigest()
            file = self.root / f"{key}.png"
            try:
                cached = file.is_file() and file.stat().st_size <= 256_000
                if cached and not file.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                    cached = False
                data = file.read_bytes() if cached else await self._extract(serial, package, paths, file)
            except OSError:
                raise IconUnavailable("PC의 아이콘 캐시를 읽거나 저장하지 못했습니다.") from None
            log("app", "device app icon loaded", package=package, cached=cached)
            return AppIcon(package=package, data_base64=base64.b64encode(data).decode(), fingerprint=key, cached=cached)

    async def _extract(self, serial: str, package: str, paths: list[str], file: Path) -> bytes:
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.root) as tmp:
            try:
                data = await read_icon(self.adb, serial, package)
            except (AdbError, OSError, ValueError):
                log("app", "device icon renderer unavailable, using APK fallback", package=package)
                data = await self._extract_apks(serial, paths, Path(tmp))
            pending = Path(tmp) / "icon.png"
            pending.write_bytes(data)
            pending.replace(file)
        log("app", "device app icon cached", package=package)
        return data

    async def _extract_apks(self, serial: str, paths: list[str], tmp: Path) -> bytes:
        apks = []
        for index, remote in enumerate(paths):
            apk = Path(tmp) / f"{index}.apk"
            await run_checked(self.adb, ["pull", remote, str(apk)], serial=serial, timeout=90)
            apks.append(apk)
        data = await asyncio.to_thread(self.renderer.render, apks)
        return data
