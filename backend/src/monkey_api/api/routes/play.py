"""Official Google Play production release metadata, independent of device connectivity."""

from fastapi import APIRouter, Depends, Path

from monkey_api.api.container import Container, get_container
from monkey_api.api.errors import problem_responses
from monkey_api.domain.models import PACKAGE_PATTERN
from monkey_api.domain.play import PlayPackage

router = APIRouter(prefix="/play", tags=["play"])


@router.get(
    "/packages/{package}",
    response_model=PlayPackage,
    responses=problem_responses(401, 403, 404, 422, 429, 502, 503, 504),
)
async def package_releases(
    package: str = Path(pattern=PACKAGE_PATTERN), c: Container = Depends(get_container)
) -> PlayPackage:
    return await c.play.get(package)
