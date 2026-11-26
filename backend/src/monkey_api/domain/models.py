"""Domain models. Pure data; shared with the API layer as the contract source."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ConnectionType = Literal["usb", "wifi"]
SeedMode = Literal["random", "fixed", "manual"]
PACKAGE_PATTERN = r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$"
IssueKind = Literal["crash", "anr", "native_crash"]
RunEndReason = Literal["completed", "time_limit", "aborted", "stopped", "failed_to_start", "device_lost"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- devices & packages ----------


class Device(Model):
    serial: str
    state: str = Field(description="adb state: device, offline, unauthorized, ...")
    connection: ConnectionType
    model: str | None = None


class DeviceInfo(Model):
    serial: str
    connection: ConnectionType
    model: str
    android_version: str
    api_level: str


class PackageItem(Model):
    name: str
    display_name: str


class PackageVersion(Model):
    package: str
    version_name: str | None
    version_code: str | None


# ---------- configuration ----------


class EventMix(Model):
    """Monkey --pct-* percentages. None = monkey default."""

    touch: int | None = Field(default=None, ge=0, le=100)
    motion: int | None = Field(default=None, ge=0, le=100)
    trackball: int | None = Field(default=None, ge=0, le=100)
    nav: int | None = Field(default=None, ge=0, le=100)
    majornav: int | None = Field(default=None, ge=0, le=100)
    syskeys: int | None = Field(default=None, ge=0, le=100)
    appswitch: int | None = Field(default=None, ge=0, le=100)
    anyevent: int | None = Field(default=None, ge=0, le=100)
    pinchzoom: int | None = Field(default=None, ge=0, le=100)
    rotation: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _sum_le_100(self) -> EventMix:
        total = sum(v for v in self.model_dump().values() if v is not None)
        if total > 100:
            raise ValueError(f"event mix percentages sum to {total} (> 100)")
        return self


class Preset(Model):
    id: str
    name: str
    description: str
    events: int = Field(gt=0)
    repeats: int = Field(gt=0)
    throttle_ms: int = Field(ge=0)
    target_minutes_per_run: float | None = Field(default=None, gt=0)
    seed_mode: SeedMode
    fixed_seed: int | None = None
    event_mix: EventMix
    bugreport: bool = False
    adaptive_margin: float = Field(default=0.0, ge=0, le=1, description="max +ratio for adaptive events")


class SessionOverrides(Model):
    events: int | None = Field(default=None, gt=0)
    repeats: int | None = Field(default=None, gt=0, le=100)
    throttle_ms: int | None = Field(default=None, ge=0, le=10_000)
    seed: int | None = Field(default=None, ge=0)
    target_minutes_per_run: float | None = Field(default=None, gt=0)
    adaptive: bool | None = None


class SessionConfig(Model):
    device_serial: str
    package: str = Field(pattern=PACKAGE_PATTERN)
    preset_id: str
    events: int = Field(gt=0)
    repeats: int = Field(gt=0)
    throttle_ms: int = Field(ge=0)
    seed_mode: SeedMode
    seed: int | None = None
    target_minutes_per_run: float | None = None
    event_mix: EventMix
    bugreport: bool = False
    adaptive: bool = True
    adaptive_margin: float = 0.0
    keep_foreground: bool = True
    network_guard: bool = True


# ---------- session ----------


class SessionState(StrEnum):
    CREATED = "created"
    PREPARING = "preparing"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Progress(Model):
    current_run: int = 0
    total_runs: int = 0
    run_percent: int = Field(default=0, ge=0, le=100)
    events_sent: int = 0
    events_target: int = 0
    elapsed_s: float = 0.0


class IssueCounts(Model):
    crash: int = 0
    anr: int = 0
    native_crash: int = 0


class Issue(Model):
    id: str
    kind: IssueKind
    run: int
    at: datetime
    summary: str
    lines: list[str]


class PerfSample(Model):
    at: datetime
    run: int
    memory_mb: float | None
    cpu_percent: float | None


class RunResult(Model):
    run: int
    seed: int
    events_target: int
    events_sent: int
    throttle_ms: int
    started_at: datetime
    ended_at: datetime
    duration_s: float
    exit_code: int | None
    end_reason: RunEndReason
    crashes: int = 0
    anrs: int = 0
    mem_peak_mb: float | None = None
    cpu_peak_percent: float | None = None


class Session(Model):
    id: str
    state: SessionState
    config: SessionConfig
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    device: DeviceInfo | None = None
    app_version: PackageVersion | None = None
    progress: Progress = Field(default_factory=Progress)
    runs: list[RunResult] = Field(default_factory=list)
    issue_counts: IssueCounts = Field(default_factory=IssueCounts)
    estimated_total_s: int | None = None
    error: str | None = None


class SessionEvent(Model):
    seq: int
    type: str = Field(description="state_changed | progress | run_started | run_finished | issue | perf | log")
    at: datetime
    data: dict[str, Any]
