"""HTTP request/response schemas (the parts of the contract that are not domain models)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from monkey_api.core.logging import LogLevel, LogSource
from monkey_api.domain.models import (
    PACKAGE_PATTERN,
    Device,
    Issue,
    PackageItem,
    PerfSample,
    Preset,
    Progress,
    RunResult,
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
    ai_advisor: bool


class AiSettingsOut(BaseModel):
    configured: bool = Field(description="A non-empty key was loaded; does not imply a successful API call")
    enabled: bool
    model: str
    config_file: str
    restart_required: bool = False
    usage: Literal["next_run_event_suggestion"] = "next_run_event_suggestion"


class AiSettingsIn(In):
    api_key: SecretStr = Field(min_length=1, max_length=512)
    model: str = Field(default="gemini-3.5-flash-lite", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")


class SessionTimingOut(BaseModel):
    session_id: str
    mode: Literal["time", "events"]
    time_basis: Literal["monotonic_wall_time"] = "monotonic_wall_time"
    completion_policy: Literal["extend_until_deadline", "event_count"]
    target_per_run_s: float | None
    target_total_s: float | None = Field(description="Execution only; excludes preparation, cleanup and AI wait")
    completed_execution_s: float | None = Field(description="Null if historical runs have no separate execution timing")
    extension_count: int
    progress: Progress
    runs: list[RunResult]


class DeviceList(BaseModel):
    items: list[Device]


class ConnectIn(In):
    host: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.\-]+$")
    port: int = Field(default=5555, ge=1, le=65535)


class PairIn(ConnectIn):
    code: str = Field(pattern=r"^\d{6}$")


class TcpipIn(In):
    port: int = Field(default=5555, ge=1, le=65535)


class ConnectOut(BaseModel):
    serial: str


class AcceptedOut(BaseModel):
    message: str


class PairOut(BaseModel):
    message: str


class PackageList(BaseModel):
    items: list[PackageItem]
    total: int


class PresetList(BaseModel):
    items: list[Preset]


class EstimateIn(In):
    events: int | None = Field(
        default=None, gt=0, le=1_000_000, description="required unless target_minutes_per_run is set"
    )
    repeats: int = Field(gt=0, le=100)
    throttle_ms: int = Field(ge=0, le=10_000)
    target_minutes_per_run: float | None = Field(default=None, gt=0, le=240)


class SessionCreateIn(In):
    device_serial: str = Field(min_length=1, max_length=128)
    package: str = Field(max_length=255, pattern=PACKAGE_PATTERN)
    preset_id: str = "standard"
    overrides: SessionOverrides | None = None


class SessionList(BaseModel):
    items: list[Session]


class ReportExportOut(BaseModel):
    path: str
    filename: str


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
