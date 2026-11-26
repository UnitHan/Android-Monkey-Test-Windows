"""Local desktop settings for Google OAuth. No tokens or client secrets in responses."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, SecretStr

from monkey_api.api.container import Container, get_container
from monkey_api.api.errors import problem_responses
from monkey_api.core.play_errors import PlayForbidden
from monkey_api.domain.play_auth import PlayAuthStatus

router = APIRouter(prefix="/play/auth", tags=["play"])
_ERRORS = problem_responses(401, 403, 404, 409, 422, 429, 502, 503, 504)


class PlayClientIn(BaseModel):
    client_json: SecretStr


def require_local_settings(request: Request, c: Container = Depends(get_container)) -> None:
    """Prevent other web origins or remote clients from changing local OAuth credentials."""
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise PlayForbidden("Google 계정 설정은 이 PC에서만 변경할 수 있습니다.")
    if request.url.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise PlayForbidden("로컬 주소로 앱에 접속해 주세요.")
    origin = request.headers.get("origin")
    allowed = {*c.settings.cors_origins, str(request.base_url).rstrip("/")}
    if origin and origin not in allowed:
        raise PlayForbidden("허용되지 않은 앱에서 인증 설정을 요청했습니다.")


@router.get("", response_model=PlayAuthStatus, responses=_ERRORS)
async def auth_status(c: Container = Depends(get_container)) -> PlayAuthStatus:
    return c.play_auth.status()


@router.post(
    "/client", response_model=PlayAuthStatus, responses=_ERRORS, dependencies=[Depends(require_local_settings)]
)
async def configure_client(body: PlayClientIn, c: Container = Depends(get_container)) -> PlayAuthStatus:
    return c.play_auth.configure(body.client_json.get_secret_value())


@router.post(
    "/connect", response_model=PlayAuthStatus, responses=_ERRORS, dependencies=[Depends(require_local_settings)]
)
async def connect(c: Container = Depends(get_container)) -> PlayAuthStatus:
    return await c.play_auth.start()


@router.post("/check", response_model=PlayAuthStatus, responses=_ERRORS, dependencies=[Depends(require_local_settings)])
async def verify(c: Container = Depends(get_container)) -> PlayAuthStatus:
    return await c.play_auth.verify()


@router.delete("", response_model=PlayAuthStatus, responses=_ERRORS, dependencies=[Depends(require_local_settings)])
async def disconnect(c: Container = Depends(get_container)) -> PlayAuthStatus:
    return await c.play_auth.disconnect()
