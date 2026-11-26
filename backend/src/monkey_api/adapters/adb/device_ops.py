"""High-level device operations on top of AdbPort. One method = one device capability."""

from __future__ import annotations

from monkey_api.adapters.adb import parsers
from monkey_api.adapters.adb.runner import AdbPort, AdbStream, run_checked
from monkey_api.core.errors import AdbError, DeviceNotFound
from monkey_api.core.logging import log
from monkey_api.domain.models import Device, DeviceInfo, PackageVersion

# Fallbacks for hardened devices (legacy config.PACKAGE_LIST_COMMANDS)
_PACKAGE_LIST_VARIANTS: tuple[tuple[str, ...], ...] = (
    (),
    ("--user", "0"),
    ("--user", "current"),
)
_LAUNCHER = ("-c", "android.intent.category.LAUNCHER", "1")


class DeviceOps:
    def __init__(self, adb: AdbPort) -> None:
        self.adb = adb

    # ---- server / connection ----

    async def version(self) -> str:
        out = await run_checked(self.adb, ["version"], timeout=5)
        return out.splitlines()[0].strip() if out else ""

    async def list_devices(self) -> list[Device]:
        return parsers.parse_devices(await run_checked(self.adb, ["devices", "-l"], timeout=10))

    async def require_device(self, serial: str) -> Device:
        for device in await self.list_devices():
            if device.serial == serial:
                return device
        raise DeviceNotFound(f"device '{serial}' is not connected", serial=serial)

    async def connect(self, host: str, port: int) -> str:
        out = await run_checked(self.adb, ["connect", f"{host}:{port}"], timeout=15)
        if "connected to" not in out.lower():
            raise AdbError(out.strip() or "connect failed", target=f"{host}:{port}")
        return f"{host}:{port}"

    async def pair(self, host: str, port: int, code: str) -> str:
        out = await run_checked(self.adb, ["pair", f"{host}:{port}", code], timeout=20)
        if "successfully paired" not in out.lower():
            raise AdbError(out.strip() or "pair failed", target=f"{host}:{port}")
        return out.strip()

    async def disconnect(self, serial: str) -> None:
        await run_checked(self.adb, ["disconnect", serial], timeout=10)

    async def verify(self, serial: str) -> bool:
        try:
            out = await run_checked(self.adb, ["shell", "echo", "ok"], serial=serial, timeout=10, quiet=True)
        except AdbError:
            return False
        return out.strip() == "ok"

    async def enable_tcpip(self, serial: str, port: int) -> None:
        await run_checked(self.adb, ["tcpip", str(port)], serial=serial, timeout=15)

    async def reboot(self, serial: str) -> None:
        await run_checked(self.adb, ["reboot"], serial=serial, timeout=15)

    async def restart_server(self) -> None:
        await self.adb.run(["kill-server"], timeout=10)
        await run_checked(self.adb, ["start-server"], timeout=20)

    async def reconnect(self, serial: str) -> bool:
        """Recover a lost connection: wireless reconnect, else restart adb server."""
        log("adb", "reconnect attempt", "WARNING", serial=serial)
        if parsers.connection_type(serial) == "wifi":
            host, _, port = serial.rpartition(":")
            await self.adb.run(["disconnect", serial], timeout=10)
            for _ in range(3):
                result = await self.adb.run(["connect", serial], timeout=15)
                if "connected to" in result.stdout.lower() and await self.verify(serial):
                    return True
            log("adb", "wireless reconnect failed", "ERROR", serial=serial, host=host, port=port)
            return False
        await self.restart_server()
        await self.adb.run(["wait-for-device"], serial=serial, timeout=30)
        return await self.verify(serial)

    # ---- device info ----

    async def getprop(self, serial: str, key: str) -> str:
        return (await run_checked(self.adb, ["shell", "getprop", key], serial=serial, quiet=True)).strip()

    async def device_info(self, serial: str) -> DeviceInfo:
        device = await self.require_device(serial)
        model = await self.getprop(serial, "ro.product.model") or await self.getprop(serial, "ro.product.name")
        return DeviceInfo(
            serial=serial,
            connection=device.connection,
            model=model or "unknown",
            android_version=await self.getprop(serial, "ro.build.version.release") or "unknown",
            api_level=await self.getprop(serial, "ro.build.version.sdk") or "unknown",
        )

    # ---- packages ----

    async def list_packages(self, serial: str, third_party: bool = False) -> list[str]:
        last_error: AdbError | None = None
        for variant in _PACKAGE_LIST_VARIANTS:
            args = ["shell", "pm", "list", "packages", *variant, *(["-3"] if third_party else [])]
            try:
                return parsers.parse_packages(await run_checked(self.adb, args, serial=serial, timeout=15))
            except AdbError as exc:
                last_error = exc
                log("adb", "package list variant failed, trying next", "WARNING", variant=list(variant))
        assert last_error is not None
        raise last_error

    async def package_version(self, serial: str, package: str) -> PackageVersion:
        out = await run_checked(self.adb, ["shell", "dumpsys", "package", package], serial=serial)
        name, code = parsers.parse_package_version(out)
        return PackageVersion(package=package, version_name=name, version_code=code)

    # ---- app control ----

    async def force_stop(self, serial: str, package: str) -> None:
        await run_checked(self.adb, ["shell", "am", "force-stop", package], serial=serial)

    async def launch(self, serial: str, package: str) -> None:
        await run_checked(self.adb, ["shell", "monkey", "-p", package, *_LAUNCHER], serial=serial)

    async def pid_of(self, serial: str, package: str) -> int | None:
        result = await self.adb.run(["shell", "pidof", package], serial=serial, timeout=8, quiet=True)
        if result.exit_code == 0 and (pid := parsers.parse_pidof(result.stdout)):
            return pid
        ps = await self.adb.run(["shell", "ps", "-A"], serial=serial, timeout=8, quiet=True)
        return parsers.parse_ps_pid(ps.stdout, package) if ps.exit_code == 0 else None

    async def kill_background(self, serial: str) -> None:
        await self.adb.run(["shell", "am", "kill-all"], serial=serial)

    async def kill(self, serial: str, pid: int) -> None:
        await self.adb.run(["shell", "kill", "-9", str(pid)], serial=serial, timeout=8)

    async def foreground_package(self, serial: str) -> str | None:
        for args in (["shell", "dumpsys", "activity", "activities"], ["shell", "dumpsys", "window"]):
            result = await self.adb.run(args, serial=serial, timeout=8, quiet=True)
            if result.exit_code == 0 and (pkg := parsers.parse_foreground_package(result.stdout)):
                return pkg
        return None

    # ---- metrics ----

    async def memory_mb(self, serial: str, package: str) -> float | None:
        result = await self.adb.run(["shell", "dumpsys", "meminfo", package], serial=serial, quiet=True)
        return parsers.parse_meminfo_total_pss_mb(result.stdout) if result.exit_code == 0 else None

    async def cpu_percent(self, serial: str, pid: int) -> float | None:
        args = ["shell", "top", "-b", "-n", "1", "-p", str(pid)]
        result = await self.adb.run(args, serial=serial, timeout=10, quiet=True)
        return parsers.parse_top_cpu(result.stdout, pid) if result.exit_code == 0 else None

    # ---- network guard ----

    async def global_setting(self, serial: str, key: str) -> bool | None:
        args = ["shell", "settings", "get", "global", key]
        result = await self.adb.run(args, serial=serial, timeout=5, quiet=True)
        return parsers.parse_setting_flag(result.stdout) if result.exit_code == 0 else None

    async def disable_airplane_mode(self, serial: str) -> None:
        await self.adb.run(["shell", "cmd", "connectivity", "airplane-mode", "disable"], serial=serial)

    async def enable_mobile_data(self, serial: str) -> None:
        await self.adb.run(["shell", "svc", "data", "enable"], serial=serial)

    # ---- streams ----

    async def clear_logcat(self, serial: str) -> None:
        await self.adb.run(["logcat", "-c"], serial=serial, timeout=10)

    async def logcat(self, serial: str) -> AdbStream:
        return await self.adb.stream(["logcat", "-v", "threadtime"], serial=serial)

    async def monkey(self, serial: str, args: list[str]) -> AdbStream:
        return await self.adb.stream(args, serial=serial)
