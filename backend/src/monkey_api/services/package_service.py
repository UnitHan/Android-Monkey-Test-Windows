"""Installed names come from the device. The bundled catalog is only a search alias index."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from importlib import resources

from monkey_api.adapters.adb.app_labels import read_labels
from monkey_api.adapters.adb.device_ops import DeviceOps
from monkey_api.core.errors import AdbError
from monkey_api.core.logging import log
from monkey_api.domain.app_search import match_rank
from monkey_api.domain.models import PackageItem, PackageVersion

SYSTEM_PREFIXES = (
    "com.google.android",
    "com.android",
    "com.samsung.android",
    "com.sec.android",
    "com.qualcomm",
    "com.mediatek",
    "android",
)
ALWAYS_INCLUDE = frozenset({"com.lguplus.aicallagent"})


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    name: str
    keywords: tuple[str, ...]


def load_catalog() -> dict[str, CatalogEntry]:
    raw = json.loads(resources.files("monkey_api.data").joinpath("apps.json").read_text(encoding="utf-8"))
    return {pkg: CatalogEntry(info.get("app_name", pkg), tuple(info.get("keywords", ()))) for pkg, info in raw.items()}


def is_system(package: str) -> bool:
    return package not in ALWAYS_INCLUDE and package.startswith(SYSTEM_PREFIXES)


class PackageService:
    def __init__(self, ops: DeviceOps, catalog: dict[str, CatalogEntry] | None = None) -> None:
        self.ops = ops
        self.catalog = catalog if catalog is not None else load_catalog()
        self._labels: dict[str, tuple[float, dict[str, str]]] = {}
        self._packages: dict[tuple[str, bool], tuple[float, list[str]]] = {}
        self._lock = asyncio.Lock()

    def matches(self, package: str, name: str, query: str) -> bool:
        return self.rank(package, name, query) is not None

    def rank(self, package: str, name: str, query: str) -> int | None:
        primary = match_rank(name, package, query)
        if primary is not None:
            return primary
        entry = self.catalog.get(package)
        if entry and any(match_rank(alias, "", query) is not None for alias in (entry.name, *entry.keywords)):
            return 7  # Historical names are search aliases, never displayed as the installed app name.
        return None

    async def list(
        self,
        serial: str,
        query: str | None = None,
        include_system: bool = False,
        third_party: bool = False,
        refresh: bool = False,
    ) -> list[PackageItem]:
        names = await self._package_names(serial, third_party, refresh)
        labels = await self._device_labels(serial, refresh)
        launchers = getattr(labels, "launchers", None)
        ranked = []
        for name in names:
            hidden = name not in launchers if launchers is not None else is_system(name)
            if not include_system and hidden:
                continue
            label = labels.get(name, name)
            rank = self.rank(name, label, query or "")
            for launcher_label in (launchers or {}).get(name, ()):
                activity_rank = match_rank(launcher_label, name, query or "")
                if activity_rank is not None:
                    rank = activity_rank if rank is None else min(rank, activity_rank)
            if rank is not None:
                ranked.append((rank, PackageItem(name=name, display_name=label)))
        ranked.sort(
            key=lambda pair: (
                pair[0],
                not query and pair[1].name not in self.catalog,
                pair[1].display_name.casefold(),
                pair[1].name,
            )
        )
        return [item for _, item in ranked]

    async def _package_names(self, serial: str, third_party: bool, refresh: bool) -> list[str]:
        async with self._lock:
            key = (serial, third_party)
            cached = self._packages.get(key)
            if not refresh and cached and time.monotonic() - cached[0] < 30:
                return cached[1]
            names = await self.ops.list_packages(serial, third_party=third_party)
            self._packages[key] = (time.monotonic(), names)
            return names

    async def _device_labels(self, serial: str, refresh: bool) -> dict[str, str]:
        async with self._lock:
            cached = self._labels.get(serial)
            if not refresh and cached and time.monotonic() - cached[0] < 30:
                return cached[1]
            try:
                labels = await read_labels(self.ops.adb, serial)
            except (AdbError, OSError, ValueError) as exc:
                log(
                    "app",
                    "device app names unavailable, using package identifiers",
                    "WARNING",
                    serial=serial,
                    error=type(exc).__name__,
                )
                labels = {}
            self._labels[serial] = (time.monotonic(), labels)
            return labels

    async def version(self, serial: str, package: str) -> PackageVersion:
        return await self.ops.package_version(serial, package)
