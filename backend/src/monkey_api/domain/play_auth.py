from typing import Literal

from monkey_api.domain.models import Model


class PlayAuthStatus(Model):
    client_configured: bool
    credentials_saved: bool
    phase: Literal["idle", "pending", "connected", "error"]
    message: str
