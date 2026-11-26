"""Atomic local cache, keyed by the exact numerical evidence sent to Gemini."""

from pathlib import Path

from pydantic import ValidationError

from monkey_api.core.logging import log
from monkey_api.domain.ai_performance import POLICY_VERSION, PerformanceAnalysis


def read_analysis(directory: Path, input_hash: str) -> PerformanceAnalysis | None:
    path = directory / "performance-analysis.json"
    if not path.exists():
        return None
    try:
        result = PerformanceAnalysis.model_validate_json(path.read_text("utf-8"))
    except (OSError, ValidationError):
        log("app", "Performance analysis cache unreadable", "WARNING")
        return None
    return result if result.input_hash == input_hash and result.policy_version == POLICY_VERSION else None


def write_analysis(directory: Path, result: PerformanceAnalysis) -> None:
    path = directory / "performance-analysis.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
