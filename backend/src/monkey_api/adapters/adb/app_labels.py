"""Read labels resolved by Android PackageManager, including locale and split resources."""

import base64
import json
import re
from importlib import resources
from uuid import uuid4

from monkey_api.adapters.adb.runner import AdbPort, run_checked
from monkey_api.core.errors import AdbError
from monkey_api.core.logging import log
from monkey_api.domain.models import PACKAGE_PATTERN


class DeviceLabels(dict[str, str]):
    launchers: dict[str, tuple[str, ...]] | None = None


def parse_labels(output: str) -> DeviceLabels:
    payload = next((line for line in reversed(output.splitlines()) if line.startswith("{")), "")
    body = json.loads(payload)
    if not isinstance(body, dict) or body.get("version") != 1 or not isinstance(body.get("labels"), dict):
        raise ValueError("unsupported device label response")
    result = DeviceLabels(
        {
            package: name.strip()
            for package, name in body["labels"].items()
            if re.fullmatch(PACKAGE_PATTERN, package) and isinstance(name, str) and 0 < len(name.strip()) <= 512
        }
    )
    if isinstance(body.get("launchers"), dict):
        result.launchers = {
            pkg: tuple(label.strip() for label in values if isinstance(label, str) and 0 < len(label.strip()) <= 512)
            for pkg, values in body["launchers"].items()
            if re.fullmatch(PACKAGE_PATTERN, pkg) and isinstance(values, list)
        }
    return result


async def read_labels(adb: AdbPort, serial: str) -> dict[str, str]:
    return parse_labels(await _read_device(adb, serial))


async def read_icon(adb: AdbPort, serial: str, package: str) -> bytes:
    if not re.fullmatch(PACKAGE_PATTERN, package):
        raise ValueError("invalid icon package")
    output = await _read_device(adb, serial, "icon", package)
    return parse_icon(output, package)


def parse_icon(output: str, package: str) -> bytes:
    payload = next((line for line in reversed(output.splitlines()) if line.startswith("{")), "")
    body = json.loads(payload)
    if (
        not isinstance(body, dict)
        or body.get("version") != 1
        or body.get("package") != package
        or not isinstance(body.get("png"), str)
    ):
        raise ValueError("unsupported icon response")
    if len(body["png"]) > 350_000:
        raise ValueError("oversized icon")
    data = base64.b64decode(body["png"], validate=True)
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 256_000:
        raise ValueError("invalid icon PNG")
    return data


async def _read_device(adb: AdbPort, serial: str, *args: str) -> str:
    helper = resources.files("monkey_api.data").joinpath("app_labels.jar")
    remote = f"/data/local/tmp/monkey-labels-{uuid4().hex}.jar"
    try:
        with resources.as_file(helper) as local:
            await run_checked(adb, ["push", str(local), remote], serial=serial, timeout=15)
        await run_checked(adb, ["shell", "chmod", "444", remote], serial=serial, timeout=5)
        output = await run_checked(
            adb,
            ["shell", f"CLASSPATH={remote}", "app_process", "/system/bin", "AppLabels", *args],
            serial=serial,
            timeout=30,
        )
        return output
    finally:
        try:
            await run_checked(adb, ["shell", "rm", "-f", remote], serial=serial, timeout=5)
        except AdbError as exc:
            log("adb", "temporary label reader cleanup failed", "WARNING", code=exc.code, serial=serial)
