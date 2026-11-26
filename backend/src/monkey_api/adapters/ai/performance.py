"""Button-triggered Gemini structured interpretation; sanitized errors and metadata-only logs."""

import time
from datetime import UTC, datetime
from urllib.parse import quote

import httpx

from monkey_api.core.ai_errors import AIResponseError, AITimeout, AIUnavailable
from monkey_api.core.logging import log
from monkey_api.domain.ai_evidence import PerformanceEvidence, constrain_conclusion, evidence_hash
from monkey_api.domain.ai_performance import AIConclusion, PerformanceAnalysis

INSTRUCTIONS = """Android QA 성능 보고서를 한국어로 해석하세요. 아래 JSON 수치만 근거로 사용하세요.
판정: normal=관측 범위 정상, attention=주의, abnormal=이상 징후, inconclusive=판단 보류.
정상은 관측 구간에서 뚜렷한 이상 징후가 없다는 뜻이지 앱의 성능 인증/출시 합격이 아닙니다.
평균, 시간가중평균, 최소/최대, 표준편차, P90/P95, 관측시간/커버리지, 회차별 추이를 함께 보세요.
메모리 최대값만으로 누수/개선 필요를 단정하지 마세요. 예산과 기준 버전이 없으면 그 한계를 명시하세요.
코어 합산 CPU는 100% 초과 가능. 기기 용량 대비 CPU만 0~100% 기준으로 해석하세요.
단발 피크와 지속 부하를 구분하세요. 미완료/이벤트 없음/불충분한 표본은 전체 판단 보류입니다.
assessment.findings의 insufficient 항목은 판단 보류. 크래시/ANR 기록이 있으면 안정성은 이상 징후입니다.
수치나 관측되지 않은 동작, 누수 원인, 재현 경로, FPS를 만들어내지 마세요.
memory/cpu/stability 각각 verdict와 구체적 수치 근거 reason을 적으세요. recommendations는 실행 가능한 확인 방법,
limitations는 자료의 한계입니다. raw logs/앱 식별정보/기준 버전은 제공되지 않았습니다.
JSON 스키마에 맞춰 응답하세요."""


class GeminiPerformance:
    def __init__(self, key: str | None, model: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.key, self.model, self.transport = key, model, transport

    async def analyze(self, evidence: PerformanceEvidence) -> PerformanceAnalysis:
        if not self.key:
            raise AIUnavailable(".env에 Gemini API Key를 등록한 뒤 프로그램을 다시 실행해 주세요.")
        started = time.monotonic()
        try:
            payload = await self._request(_body(evidence))
            candidate = payload["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError("incomplete response")
            output = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
            conclusion = AIConclusion.model_validate_json(output)
            conclusion, guards = constrain_conclusion(conclusion, evidence)
            usage = payload.get("usageMetadata", {})
            result = PerformanceAnalysis(
                input_hash=evidence_hash(evidence),
                model=self.model,
                created_at=datetime.now(UTC),
                conclusion=conclusion,
                guardrails=guards,
                duration_ms=round((time.monotonic() - started) * 1000),
                input_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
            )
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            log(
                "app",
                "Gemini performance response invalid",
                "WARNING",
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            raise AIResponseError(
                "AI 응답이 완전한 분석 형식이 아닙니다. 다시 시도해 주세요. 기존 통계는 유지됩니다."
            ) from None
        log(
            "app",
            "Gemini performance analyzed",
            duration_ms=result.duration_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        return result

    async def _request(self, body: dict) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(self.model, safe='')}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
                response = await client.post(url, json=body, headers={"x-goog-api-key": self.key})
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise AITimeout("Gemini 분석 응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.") from None
        except httpx.HTTPError:
            raise AIResponseError("Gemini 호출에 실패했습니다. API 키·모델·사용량 한도를 확인해 주세요.") from None


def _body(evidence: PerformanceEvidence) -> dict:
    return {
        "systemInstruction": {"parts": [{"text": INSTRUCTIONS}]},
        "contents": [{"role": "user", "parts": [{"text": evidence.model_dump_json()}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": AIConclusion.model_json_schema(),
            "temperature": 0.1,
            "maxOutputTokens": 8192,
        },
    }
