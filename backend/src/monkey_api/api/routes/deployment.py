"""First-launch unlock of the encrypted settings carried by the installer."""

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, SecretStr

from monkey_api.api.container import Container, get_container
from monkey_api.api.errors import problem_responses
from monkey_api.api.routes.play_auth import require_local_settings
from monkey_api.core.errors import Conflict
from monkey_api.services.deployment_settings import ACCOUNT, credential_paths, restore
from monkey_api.services.secure_settings import load_ai

router = APIRouter(prefix="/settings/deployment", tags=["system"])
_lock = asyncio.Lock()


class DeploymentStatus(BaseModel):
    available: bool
    configured: bool
    account: str


class UnlockIn(BaseModel):
    password: SecretStr = Field(min_length=1, max_length=512)


@router.get("", response_model=DeploymentStatus)
async def status(c: Container = Depends(get_container)) -> DeploymentStatus:
    return DeploymentStatus(
        available=c.settings.deployment_bundle.is_file(),
        configured=all(path.is_file() for path in credential_paths(c.settings).values()),
        account=ACCOUNT,
    )


@router.post(
    "/unlock",
    response_model=DeploymentStatus,
    responses=problem_responses(403, 404, 409, 422),
    dependencies=[Depends(require_local_settings)],
)
async def unlock(body: UnlockIn, c: Container = Depends(get_container)) -> DeploymentStatus:
    async with _lock:
        if c.play_auth.phase == "pending":
            raise Conflict("진행 중인 Google 로그인을 먼저 완료하거나 취소해 주세요.")
        await asyncio.to_thread(restore, c.settings, body.password.get_secret_value())
        c.apply_ai(*load_ai(c.settings))
        c.play_auth.provider.invalidate()
        c.play_auth.phase = "idle"
        c.play_auth.message = "설치 패키지의 기존 Google 인증을 복원했습니다. 저장된 인증으로 조회합니다."
        return await status(c)
