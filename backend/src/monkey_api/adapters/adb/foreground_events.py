"""Parse ActivityManager/WindowManager resume events (brief logcat format)."""

import re

_RESUME = re.compile(
    r"\b(?:wm_set_resumed_activity|wm_resume_activity|am_resume_activity)\s*\(\s*\d+\):\s*\[([^\]]+)\]"
)
_COMPONENT = re.compile(r"([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/[A-Za-z0-9_.$]+")


def resumed_package(line: str) -> str | None:
    event = _RESUME.search(line)
    if event:
        for field in event.group(1).split(","):
            if component := _COMPONENT.fullmatch(field.strip()):
                return component.group(1)
    return None
