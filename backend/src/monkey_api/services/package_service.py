"""Installed packages with display names (bundled apps.json catalog) and search."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from monkey_api.adapters.adb.device_ops import DeviceOps
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

    def display_name(self, package: str) -> str:
        entry = self.catalog.get(package)
        return entry.name if entry else package.rsplit(".", 1)[-1]

    def matches(self, package: str, query: str) -> bool:
        q = query.casefold()
        entry = self.catalog.get(package)
        haystack = [package, self.display_name(package), *(entry.keywords if entry else ())]
        return any(q in h.casefold() for h in haystack)

    async def list(
        self, serial: str, query: str | None = None, include_system: bool = False, third_party: bool = False
    ) -> list[PackageItem]:
        names = await self.ops.list_packages(serial, third_party=third_party)
        items = [
            PackageItem(name=n, display_name=self.display_name(n))
            for n in names
            if (include_system or not is_system(n)) and (not query or self.matches(n, query))
        ]
        return sorted(items, key=lambda i: (i.name not in self.catalog, i.display_name.casefold()))

    async def version(self, serial: str, package: str) -> PackageVersion:
        return await self.ops.package_version(serial, package)
