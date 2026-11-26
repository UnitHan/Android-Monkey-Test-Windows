"""HTTP request/response schemas (the parts of the contract that are not domain models)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from monkey_api.core.logging import LogLevel, LogSource
from monkey_api.domain.models import (
    PACKAGE_PATTERN,
    Device,
    Issue,
    PackageItem,
    PerfSample,
    Preset,
    Session,
    SessionEvent,
)
from monkey_api.domain.models import SessionOverrides as SessionOverrides


class In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdbStatus(BaseModel):
    path: str
    available: bool
    version: str | None


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    adb: AdbStatus


class DeviceList(BaseModel):
    items: list[Device]


class ConnectIn(In):
    host: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.\-]+$")
    port: int = Field(default=5555, ge=1, le=65535)


class PairIn(ConnectIn):
    code: str = Field(pattern=r"^\d{6}$")


class ConnectOut(BaseModel):
    serial: str


class PairOut(BaseModel):
    message: str


class PackageList(BaseModel):
    items: list[PackageItem]
    total: int


class PresetList(BaseModel):
    items: list[Preset]


class EstimateIn(In):
    events: int = Field(gt=0)
    repeats: int = Field(gt=0, le=100)
    throttle_ms: int = Field(ge=0, le=10_000)
    target_minutes_per_run: float | None = Field(default=None, gt=0)


class SessionCreateIn(In):
    device_serial: str = Field(min_length=1, max_length=128)
    package: str = Field(max_length=255, pattern=PACKAGE_PATTERN)
    preset_id: str = "standard"
    overrides: SessionOverrides | None = None


class SessionList(BaseModel):
    items: list[Session]


class EventList(BaseModel):
    items: list[SessionEvent]
    last_seq: int


class IssueList(BaseModel):
    items: list[Issue]


class PerfList(BaseModel):
    items: list[PerfSample]


class LogRecordOut(BaseModel):
    seq: int
    at: str
    level: LogLevel
    source: LogSource
    message: str
    request_id: str | None
    session_id: str | None
    data: dict[str, Any]


class LogList(BaseModel):
    items: list[LogRecordOut]
    last_seq: int
