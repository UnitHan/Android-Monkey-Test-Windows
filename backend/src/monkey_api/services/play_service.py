"""Query selected apps using the connected Play Console account's permissions."""

from datetime import UTC, datetime

from monkey_api.adapters.play.publisher import PlayPublisher
from monkey_api.domain.play import PlayPackage


class PlayService:
    def __init__(self, publisher: PlayPublisher, packages: list[str]) -> None:
        self.publisher = publisher
        self.packages = frozenset(packages)  # Connection-check candidates, not a lookup allowlist.

    async def get(self, package: str) -> PlayPackage:
        releases = await self.publisher.releases(package, "production")
        return PlayPackage(package=package, track="production", checked_at=datetime.now(UTC), releases=releases)
