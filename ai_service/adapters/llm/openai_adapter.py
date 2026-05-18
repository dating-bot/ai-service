import json
import re
from time import perf_counter
from typing import final

import httpx
import structlog

from ai_service.domain.analysis import BioAnalysisResult
from ai_service.infra import OpenAIConfig
from ai_service.infra.circuit_breaker import (
    CircuitBreakerOpenError,
    CircuitBreakerSettings,
    get_or_create_circuit_breaker,
)
from ai_service.infra.metrics import record_openrouter_fallback, record_openrouter_request
from ai_service.protocols import BioAnalyzerProtocol

log = structlog.stdlib.get_logger("ai_service.adapters.OpenAIBioAnalyzer")
_CONTACT_RE = re.compile(r"(@\w+)|(https?://)|(t\.me/)|([+]?\d[\d\s\-()]{9,})", re.IGNORECASE)
_MIN_BIO_LEN = 40
_SYSTEM_PROMPT = (
    "You analyze dating profile bios. Return strict JSON only with keys: "
    "quality_score (number 0..10), issues (string[]), suggestions (string[]), "
    "safe (boolean), contact_detected (boolean), confidence (number 0..1). "
    "Rules: contact_detected=true if bio contains direct contact details "
    "(phone, @username, t.me/ links, email, WhatsApp/Telegram handles). "
    "safe=false only for explicit sexual content, minors, violence, hate, drugs, or illegal services. "
    "Do not add extra keys."
)


@final
class OpenAIBioAnalyzerAdapter(BioAnalyzerProtocol):
    def __init__(self, config: OpenAIConfig) -> None:
        self._config = config
        self._breaker = get_or_create_circuit_breaker(
            "openai-bio-analyzer",
            CircuitBreakerSettings(
                enabled=config.circuit_breaker_enabled,
                failure_threshold=config.circuit_breaker_failure_threshold,
                recovery_timeout_seconds=float(config.circuit_breaker_recovery_timeout_seconds),
                half_open_success_threshold=config.circuit_breaker_half_open_success_threshold,
            ),
        )

    async def analyze_bio(self, *, profile_id: int, bio: str | None) -> BioAnalysisResult:
        text = (bio or "").strip()
        if not self._config.enabled or not self._config.api_key:
            return self._fallback(text)
        model_name = self._config.resolved_bio_model
        provider_name = self._config.provider.lower()

        payload = {
            "model": model_name,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"profile_id={profile_id}\nbio={text}\nOutput JSON only.",
                },
            ],
        }

        async def _request() -> BioAnalysisResult:
            async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                resp = await client.post(
                    f"{self._config.base_url.rstrip('/')}/chat/completions",
                    headers=self._config.request_headers(),
                    json=payload,
                )
                _ = resp.raise_for_status()
            data = resp.json()
            content = str(data["choices"][0]["message"]["content"])
            parsed = json.loads(content)
            return BioAnalysisResult(
                quality_score=float(max(0.0, min(10.0, parsed.get("quality_score", 0.0)))),
                issues=[str(x) for x in parsed.get("issues", [])],
                suggestions=[str(x) for x in parsed.get("suggestions", [])],
                safe=bool(parsed.get("safe", True)),
                contact_detected=bool(parsed.get("contact_detected", False)),
                confidence=float(max(0.0, min(1.0, parsed.get("confidence", 0.5)))),
            )

        started_at = perf_counter()
        status = "success"
        try:
            result = await self._breaker.call(_request, operation="chat.completions")
        except CircuitBreakerOpenError:
            status = "circuit_open"
            record_openrouter_fallback(provider=provider_name, operation="chat.completions", reason=status)
            log.warning(
                "openai analyze skipped: circuit breaker OPEN, fallback is used",
                profile_id=profile_id,
                model=model_name,
            )
            return self._fallback(text)
        except httpx.HTTPStatusError as exc:
            status = f"http_{exc.response.status_code}"
            record_openrouter_fallback(provider=provider_name, operation="chat.completions", reason=status)
            log.exception(
                "openai analyze failed with http status, fallback is used",
                profile_id=profile_id,
                model=model_name,
                status_code=exc.response.status_code,
            )
            return self._fallback(text)
        except Exception:
            status = "error"
            record_openrouter_fallback(provider=provider_name, operation="chat.completions", reason=status)
            log.exception("openai analyze failed, fallback is used", profile_id=profile_id, model=model_name)
            return self._fallback(text)
        else:
            log.info(
                "bio analyzed by llm",
                profile_id=profile_id,
                model=model_name,
                quality_score=result.quality_score,
                safe=result.safe,
                contact_detected=result.contact_detected,
                confidence=result.confidence,
                issues_count=len(result.issues),
            )
            return result
        finally:
            record_openrouter_request(
                provider=provider_name,
                operation="chat.completions",
                model=model_name,
                status=status,
                duration_seconds=perf_counter() - started_at,
            )

    def _fallback(self, bio: str) -> BioAnalysisResult:
        length = len(bio)
        issues: list[str] = []
        suggestions: list[str] = []

        if length < _MIN_BIO_LEN:
            issues.append("too short")
            suggestions.append("Расскажи подробнее о себе и хобби")

        contact_detected = bool(_CONTACT_RE.search(bio))
        if contact_detected:
            issues.append("contains contact info")
            suggestions.append("Убери прямые контакты из анкеты")

        unsafe_words = {"escort", "наркот", "18+", "секс", "обнажен"}
        safe = not any(word in bio.lower() for word in unsafe_words)

        raw_score = min(10.0, max(0.5, length / 30)) if bio else 0.5
        if contact_detected:
            raw_score = max(0.0, raw_score - 2.0)
        if not safe:
            raw_score = max(0.0, raw_score - 3.0)

        return BioAnalysisResult(
            quality_score=float(round(raw_score, 2)),
            issues=issues,
            suggestions=suggestions,
            safe=safe,
            contact_detected=contact_detected,
            confidence=0.35,
        )
