"""Google Play release metadata. Release names are not Android versionName values."""

from datetime import datetime
from typing import Literal

from monkey_api.domain.models import Model

PUBLISHED = "RELEASE_LIFECYCLE_STATE_PUBLISHED"


class PlayRelease(Model):
    release_name: str
    lifecycle_state: str
    version_codes: list[str]


class PlayPackage(Model):
    package: str
    source: Literal["google_play_developer_api"] = "google_play_developer_api"
    track: str
    checked_at: datetime
    releases: list[PlayRelease]
