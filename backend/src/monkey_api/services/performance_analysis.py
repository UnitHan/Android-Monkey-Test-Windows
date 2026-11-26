"""Explicit preview/consent boundary, duplicate-call protection, persisted interpretation."""

import asyncio

from monkey_api.adapters.ai.performance import GeminiPerformance
from monkey_api.adapters.storage.performance_analysis import write_analysis
from monkey_api.core.errors import AppError, Conflict
from monkey_api.domain.ai_evidence import AnalysisPreview, evidence_for, evidence_hash
from monkey_api.domain.ai_performance import AnalysisRequest, PerformanceAnalysis
from monkey_api.domain.state_machine import TERMINAL_STATES
from monkey_api.services.session_ledger import SessionLedger
from monkey_api.services.session_runner import build_session_report


class PerformanceAnalysisService:
    def __init__(self, ledger: SessionLedger, analyzer: GeminiPerformance) -> None:
        self.ledger, self.analyzer = ledger, analyzer
        self._lock = asyncio.Lock()

    def preview(self, session_id: str) -> AnalysisPreview:
        report = build_session_report(self.ledger, session_id)
        if report.session.state not in TERMINAL_STATES:
            raise Conflict("테스트 종료 후 AI 성능 분석을 실행해 주세요.")
        evidence = evidence_for(report)
        return AnalysisPreview(
            input_hash=evidence_hash(evidence),
            model=self.analyzer.model,
            configured=bool(self.analyzer.key),
            evidence=evidence,
        )

    async def analyze(self, session_id: str, request: AnalysisRequest) -> PerformanceAnalysis:
        async with self._lock:
            preview = self.preview(session_id)
            if request.input_hash != preview.input_hash:
                raise Conflict("통계가 변경됐습니다. 전송 내용을 다시 확인해 주세요.")
            report = build_session_report(self.ledger, session_id)
            if report.ai_performance and report.ai_performance.model == self.analyzer.model:
                return report.ai_performance
            result = await self.analyzer.analyze(preview.evidence)
            self.ledger.get(session_id)  # A deleted session must not be recreated by a late response.
            if self.preview(session_id).input_hash != preview.input_hash:
                raise Conflict("분석 중 통계가 변경됐습니다. 새 통계로 다시 분석해 주세요.")
            try:
                write_analysis(self.ledger.repo.dir_for(session_id), result)
            except OSError:
                raise AppError("AI 분석 결과를 저장하지 못했습니다. 저장 폴더를 확인해 주세요.") from None
            return result
