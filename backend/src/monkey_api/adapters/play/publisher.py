"""Read-only releases.list endpoint; no edit creation, commit, or third-party store fallback."""

from collections.abc import Awaitable, Callable
from typing import Annotated
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, ValidationError

from monkey_api.core.logging import log
from monkey_api.core.play_errors import (
    PlayAuthError,
    PlayError,
    PlayForbidden,
    PlayNotFound,
    PlayRateLimited,
    PlayTimeout,
)
from monkey_api.domain.play import PlayRelease

BASE_URL = "https://androidpublisher.googleapis.com/androidpublisher/v3"
_ERRORS = {
    401: (PlayAuthError, "Google Play 인증이 만료되었거나 유효하지 않습니다. 계정을 다시 연결해 주세요."),
    403: (PlayForbidden, "앱 조회 권한과 Google Play Android Developer API 활성화 여부를 확인해 주세요."),
    404: (PlayNotFound, "Google Play에서 앱 또는 배포 트랙을 찾을 수 없습니다."),
    429: (PlayRateLimited, "Google Play 요청 한도에 도달했습니다. 잠시 후 다시 조회해 주세요."),
}


class ArtifactPayload(BaseModel):
    versionCode: Annotated[int, Field(strict=True, gt=0)]


class ReleasePayload(BaseModel):
    releaseName: str = ""
    track: str
    activeArtifacts: list[ArtifactPayload] = Field(default_factory=list)
    releaseLifecycleState: str


class ReleasesPayload(BaseModel):
    releases: list[ReleasePayload] = Field(default_factory=list)


def parse_releases(payload: object, track: str) -> list[PlayRelease]:
    data = ReleasesPayload.model_validate(payload)
    return [
        PlayRelease(
            release_name=r.releaseName,
            lifecycle_state=r.releaseLifecycleState,
            version_codes=[str(code) for code in sorted({a.versionCode for a in r.activeArtifacts}, reverse=True)],
        )
        for r in data.releases
        if r.track == track
    ]


class PlayPublisher:
    def __init__(self, token: Callable[[], Awaitable[str]], transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.token = token
        self.transport = transport

    async def releases(self, package: str, track: str) -> list[PlayRelease]:
        token = await self.token()
        url = f"{BASE_URL}/applications/{quote(package, safe='')}/tracks/{quote(track, safe='')}/releases"
        try:
            async with httpx.AsyncClient(timeout=20, transport=self.transport, follow_redirects=False) as client:
                response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException:
            raise PlayTimeout("Google Play 조회 시간이 초과되었습니다.") from None
        except httpx.HTTPError:
            raise PlayError("Google Play에 연결할 수 없습니다.") from None
        log("app", "Google Play releases queried", package=package, track=track, status=response.status_code)
        if response.status_code != 200:
            error, detail = _ERRORS.get(response.status_code, (PlayError, "Google Play 조회에 실패했습니다."))
            raise error(detail)
        try:
            return parse_releases(response.json(), track)
        except (ValueError, ValidationError):
            raise PlayError("Google Play 응답 형식을 확인할 수 없습니다.") from None
