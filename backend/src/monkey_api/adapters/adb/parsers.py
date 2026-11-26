"""Pure parsers for adb command output. Each has fixture-based unit tests."""

from __future__ import annotations

import re

from monkey_api.domain.models import Device

_WIRELESS = re.compile(r"^[\w.\-]+:\d+$|^adb-.*\._adb-tls-connect\._tcp")
_PKG_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
_PSS_TOTAL = re.compile(r"TOTAL PSS:\s*(\d+)")
_TABLE_TOTAL = re.compile(r"^\s*TOTAL\s+(\d+)\b", re.MULTILINE)
_VERSION_CODE = re.compile(r"versionCode=(\d+)")
_VERSION_NAME = re.compile(r"versionName=(\S+)")
_COMPONENT = re.compile(r"\s([A-Za-z][\w.]*)/([\w.$]+)")
_RESUMED_KEYS = ("topResumedActivity", "mResumedActivity", "ResumedActivity", "mFocusedApp", "mCurrentFocus")


def connection_type(serial: str) -> str:
    return "wifi" if _WIRELESS.search(serial) else "usb"


def parse_devices(output: str) -> list[Device]:
    """`adb devices -l`."""
    devices: list[Device] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith(("List of devices", "*")):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        props = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        model = props.get("model")
        devices.append(
            Device(
                serial=serial,
                state=state,
                connection="wifi" if connection_type(serial) == "wifi" else "usb",
                model=model.replace("_", " ") if model else None,
            )
        )
    return devices


def parse_packages(output: str) -> list[str]:
    """`pm list packages` → sorted unique package names."""
    names = {
        line.strip().removeprefix("package:").strip()
        for line in output.splitlines()
        if line.strip().startswith("package:")
    }
    return sorted(n for n in names if _PKG_NAME.match(n))


def parse_meminfo_total_pss_mb(output: str) -> float | None:
    """`dumpsys meminfo <pkg>` → total PSS in MB."""
    if "No process found" in output:
        return None
    m = _PSS_TOTAL.search(output) or _TABLE_TOTAL.search(output)
    if not m:
        return None
    kb = int(m.group(1))
    return round(kb / 1024, 1) if kb > 0 else None


def parse_pidof(output: str) -> int | None:
    """`pidof <pkg>` → first pid."""
    for token in output.split():
        if token.isdigit():
            return int(token)
    return None


def parse_ps_pid(output: str, package: str) -> int | None:
    """`ps -A` → pid of the process whose NAME equals package (main process, not :service)."""
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1] == package and parts[1].isdigit():
            return int(parts[1])
    return None


def parse_top_cpu(output: str, pid: int) -> float | None:
    """`top -b -n 1 -p <pid>` (toybox) → %CPU of pid, using the header to locate the column."""
    header: list[str] | None = None
    for line in output.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "PID":
            header = parts
            continue
        if header and parts[0] == str(pid):
            idx = next((i for i, h in enumerate(header) if "%CPU" in h), None)
            if idx is None:
                return None
            if header[idx].startswith("S["):  # "S[%CPU]" header covers two value columns
                idx += 1
            try:
                return float(parts[idx])
            except (IndexError, ValueError):
                return None
    return None


def parse_package_version(output: str) -> tuple[str | None, str | None]:
    """`dumpsys package <pkg>` → (version_name, version_code)."""
    name = _VERSION_NAME.search(output)
    code = _VERSION_CODE.search(output)
    return (name.group(1) if name else None, code.group(1) if code else None)


def parse_foreground_package(output: str) -> str | None:
    """`dumpsys activity activities` / `dumpsys window` → package of the resumed/focused activity."""
    for key in _RESUMED_KEYS:
        for line in output.splitlines():
            if key in line and (m := _COMPONENT.search(line)):
                return m.group(1)
    return None


def parse_setting_flag(output: str) -> bool | None:
    """`settings get global <key>` → True/False, None if unset."""
    value = output.strip()
    if value in ("1", "true"):
        return True
    if value in ("0", "false"):
        return False
    return None


def parse_launcher_component(output: str, package: str) -> str | None:
    """`cmd package resolve-activity --brief` → validated explicit launcher component."""
    for line in output.splitlines():
        component = line.strip()
        if re.fullmatch(re.escape(package) + r"/[A-Za-z0-9_.$]+", component):
            return component
    return None
