"""Read aapt2 resource metadata without extracting ZIP entries onto the filesystem."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Resource:
    apk: Path
    value: str
    density: int = 0


def icon_path(badging: str) -> str | None:
    match = re.search(r"^application:.*? icon='([^']+)'", badging, re.MULTILINE)
    return match.group(1) if match else None


def resource_table(output: str, apk: Path) -> dict[str, list[Resource]]:
    table: dict[str, list[Resource]] = {}
    current = ""
    densities = {"ldpi": 120, "mdpi": 160, "hdpi": 240, "xhdpi": 320, "xxhdpi": 480, "xxxhdpi": 640}
    for line in output.splitlines():
        if match := re.search(r"resource (0x[0-9a-f]+) ", line):
            current = match.group(1)
        elif current and (match := re.match(r"\s+\(([^)]*)\) (.+)", line)):
            config, value = match.groups()
            file = re.match(r"\(file\) (\S+)", value)
            if file:
                value = file.group(1)
            if file or re.fullmatch(r"#[0-9a-fA-F]{6,8}|@0x[0-9a-f]+", value):
                density = max((v for k, v in densities.items() if k in config.split("-")), default=0)
                table.setdefault(current, []).append(Resource(apk, value, density))
    return table


def adaptive_layers(xmltree: str) -> dict[str, str]:
    """Only accept Android adaptive-icon background/foreground drawable references."""
    layers: dict[str, str] = {}
    if not re.search(r"E: adaptive-icon\b", xmltree):
        return layers
    current = ""
    for line in xmltree.splitlines():
        if match := re.search(r"E: (\S+)", line):
            current = match.group(1)
        elif current in ("background", "foreground"):
            match = re.search(r":drawable\([^)]*\)=(@0x[0-9a-f]+|#[0-9a-fA-F]+)", line)
            if match:
                layers[current] = match.group(1)
    return layers
