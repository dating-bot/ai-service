import base64
import json
from contextlib import AbstractAsyncContextManager
from hashlib import sha256
from time import perf_counter
from typing import Protocol, cast, final

import aioboto3
import httpx
import structlog

from ai_service.infra.circuit_breaker import (
    CircuitBreakerOpenError,
    CircuitBreakerSettings,
    get_or_create_circuit_breaker,
)
from ai_service.infra.metrics import record_openrouter_fallback, record_openrouter_request
from ai_service.infra.minio import MinIOConfig, create_s3_client
from ai_service.infra.openai import OpenAIConfig
from ai_service.protocols import NSFWDetectorProtocol

log = structlog.stdlib.get_logger("ai_service.adapters.OpenAINSFWDetector")
_NSFW_SYSTEM_PROMPT = (
    "You are a strict NSFW classifier for profile photos. "
    "Return strict JSON only with keys nsfw_score (number 0..1) and confidence (number 0..1). "
    "Score high only for explicit sexual nudity. "
    "Do not penalize portraits, underwear, swimwear, sportswear, or beach photos unless explicit nudity is present."
)


class _S3Client(Protocol):
    # boto3-compatible method signature uses capitalized kwargs.
    async def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]: ...  # noqa: N803


class _BodyReader(Protocol):
    async def read(self) -> bytes: ...


@final
class OpenAINSFWDetectorAdapter(NSFWDetectorProtocol):
    def __init__(
        self,
        *,
        openai_cfg: OpenAIConfig,
        low_confidence_threshold: float,
        minio_cfg: MinIOConfig,
        session: aioboto3.Session,
    ) -> None:
        self._openai_cfg = openai_cfg
        self._low_confidence_threshold = low_confidence_threshold
        self._minio_cfg = minio_cfg
        self._session = session
        self._breaker = get_or_create_circuit_breaker(
            "openai-nsfw-detector",
            CircuitBreakerSettings(
                enabled=openai_cfg.circuit_breaker_enabled,
                failure_threshold=openai_cfg.circuit_breaker_failure_threshold,
                recovery_timeout_seconds=float(openai_cfg.circuit_breaker_recovery_timeout_seconds),
                half_open_success_threshold=openai_cfg.circuit_breaker_half_open_success_threshold,
            ),
        )

    async def detect(self, *, minio_key: str) -> float:
        key_hash = sha256(minio_key.encode()).hexdigest()[:12]
        if not self._openai_cfg.enabled or not self._openai_cfg.api_key:
            log.info("nsfw fallback used because llm disabled", minio_key_hash=key_hash)
            return self._fallback(minio_key)
        provider_name = self._openai_cfg.provider.lower()
        model_name = self._openai_cfg.nsfw_model

        async def _request() -> tuple[float, float]:
            image_bytes, content_type = await self._read_photo(minio_key)
            base64_data = base64.b64encode(image_bytes).decode("ascii")
            data_url = f"data:{content_type};base64,{base64_data}"

            payload = {
                "model": self._openai_cfg.nsfw_model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": _NSFW_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Assess image for explicit adult sexual nudity only. Output JSON only.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            },
                        ],
                    },
                ],
            }

            async with httpx.AsyncClient(timeout=self._openai_cfg.timeout_seconds) as client:
                resp = await client.post(
                    f"{self._openai_cfg.base_url.rstrip('/')}/chat/completions",
                    headers=self._openai_cfg.request_headers(),
                    json=payload,
                )
                resp.raise_for_status()
            data = resp.json()
            content = str(data["choices"][0]["message"]["content"])
            parsed = json.loads(content)
            raw_score = float(parsed.get("nsfw_score", 0.0))
            score = max(0.0, min(1.0, raw_score))
            confidence = float(max(0.0, min(1.0, parsed.get("confidence", 0.5))))
            return score, confidence

        started_at = perf_counter()
        status = "success"
        try:
            score, confidence = await self._breaker.call(_request, operation="chat.completions:nsfw")
        except CircuitBreakerOpenError:
            status = "circuit_open"
            record_openrouter_fallback(provider=provider_name, operation="chat.completions:nsfw", reason=status)
            log.warning(
                "openai nsfw detection skipped: circuit breaker OPEN, fallback is used",
                minio_key_hash=key_hash,
            )
            return self._fallback(minio_key)
        except httpx.HTTPStatusError as exc:
            status = f"http_{exc.response.status_code}"
            record_openrouter_fallback(provider=provider_name, operation="chat.completions:nsfw", reason=status)
            log.exception(
                "openai nsfw detection failed with http status, fallback is used",
                minio_key_hash=key_hash,
                status_code=exc.response.status_code,
            )
            return self._fallback(minio_key)
        except Exception:
            status = "error"
            record_openrouter_fallback(provider=provider_name, operation="chat.completions:nsfw", reason=status)
            log.exception("openai nsfw detection failed, fallback is used", minio_key_hash=key_hash)
            return self._fallback(minio_key)
        else:
            log.info(
                "nsfw scored by llm",
                minio_key_hash=key_hash,
                model=self._openai_cfg.nsfw_model,
                nsfw_score=score,
                confidence=confidence,
            )
            if confidence < self._low_confidence_threshold:
                log.warning(
                    "nsfw analysis low confidence, manual review recommended",
                    minio_key_hash=key_hash,
                    model=self._openai_cfg.nsfw_model,
                    confidence=confidence,
                    threshold=self._low_confidence_threshold,
                )
            return score
        finally:
            record_openrouter_request(
                provider=provider_name,
                operation="chat.completions:nsfw",
                model=model_name,
                status=status,
                duration_seconds=perf_counter() - started_at,
            )

    async def _read_photo(self, minio_key: str) -> tuple[bytes, str]:
        async with self._s3_client() as raw_client:
            client = cast("_S3Client", raw_client)
            response = await client.get_object(Bucket=self._minio_cfg.bucket, Key=minio_key)
            body = cast("_BodyReader", response["Body"])
            data = await body.read()
            content_type = str(response.get("ContentType") or "image/jpeg")
            return data, content_type

    def _s3_client(self) -> AbstractAsyncContextManager[_S3Client]:
        return cast(
            "AbstractAsyncContextManager[_S3Client]",
            create_s3_client(session=self._session, config=self._minio_cfg),
        )

    def _fallback(self, minio_key: str) -> float:
        key = minio_key.lower()
        if "nsfw" in key or "adult" in key:
            return 0.95
        digest = sha256(minio_key.encode()).digest()
        return (digest[0] / 255.0) * 0.25
