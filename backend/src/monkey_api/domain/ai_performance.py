"""Validated AI interpretation, separate from deterministic observations."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["normal", "attention", "abnormal", "inconclusive"]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
LABELS = {"normal": "관측 범위 정상", "attention": "주의", "abnormal": "이상 징후", "inconclusive": "판단 보류"}
POLICY_VERSION = "performance-v1"


class AIFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Verdict
    reason: Text


class AIConclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Verdict
    summary: Text
    memory: AIFinding
    cpu: AIFinding
    stability: AIFinding
    recommendations: list[Text] = Field(min_length=1, max_length=6)
    limitations: list[Text] = Field(min_length=1, max_length=6)


class PerformanceAnalysis(BaseModel):
    input_hash: str
    model: str
    policy_version: str = POLICY_VERSION
    created_at: datetime
    conclusion: AIConclusion
    guardrails: list[str] = Field(default_factory=list)
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: Literal[True]
