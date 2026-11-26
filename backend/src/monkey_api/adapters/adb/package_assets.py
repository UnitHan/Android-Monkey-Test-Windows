"""Parse installed APK paths and installation identity (captured-device fixtures)."""

import re

from monkey_api.core.icon_errors import IconUnavailable


def apk_paths(output: str) -> list[str]:
    paths = [line.removeprefix("package:").strip() for line in output.splitlines() if line.startswith("package:")]
    if not paths or len(paths) > 64 or any(not p.startswith("/") or not p.endswith(".apk") for p in paths):
        raise IconUnavailable("설치된 앱의 APK 경로를 확인할 수 없습니다.")
    return sorted(set(paths), key=lambda p: (not p.endswith("/base.apk"), p))


def installation_identity(output: str) -> str:
    parts = re.findall(r"^\s*(versionCode=\d+|lastUpdateTime=[^\r\n]+)", output, re.MULTILINE)
    if len(parts) < 2:
        raise IconUnavailable("설치 버전과 업데이트 시각을 확인할 수 없습니다.")
    return "\n".join(parts)
