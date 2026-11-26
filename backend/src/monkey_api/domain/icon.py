from typing import Literal

from monkey_api.domain.models import Model


class AppIcon(Model):
    package: str
    mime_type: Literal["image/png"] = "image/png"
    data_base64: str
    fingerprint: str
    cached: bool
