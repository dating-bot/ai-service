from time import perf_counter
from typing import final

import httpx
import structlog

from ai_service.adapters.embeddings.simple import DeterministicEmbeddingAdapter
from ai_service.infra import OpenAIConfig
from ai_service.infra.circuit_breaker import (
    CircuitBreakerOpenError,
    CircuitBreakerSettings,
    get_or_create_circuit_breaker,
)
from ai_service.infra.metrics import record_openrouter_fallback, record_openrouter_request
from ai_service.protocols import EmbeddingGeneratorProtocol

log = structlog.stdlib.get_logger("ai_service.adapters.OpenAIEmbedding")


@final
class OpenAIEmbeddingAdapter(EmbeddingGeneratorProtocol):
    def __init__(self, config: OpenAIConfig, fallback_size: int) -> None:
        self._config = config
        self._fallback = DeterministicEmbeddingAdapter(fallback_size)
        self._breaker = get_or_create_circuit_breaker(
            "openai-embedding-generator",
            CircuitBreakerSettings(
                enabled=config.circuit_breaker_enabled,
                failure_threshold=config.circuit_breaker_failure_threshold,
                recovery_timeout_seconds=float(config.circuit_breaker_recovery_timeout_seconds),
                half_open_success_threshold=config.circuit_breaker_half_open_success_threshold,
            ),
        )

    async def generate_embedding(self, text: str) -> list[float]:
        if not self._config.enabled or not self._config.api_key:
            return await self._fallback.generate_embedding(text)
        provider_name = self._config.provider.lower()
        model_name = self._config.embedding_model

        payload: dict[str, object] = {
            "model": model_name,
            "input": text or " ",
            "encoding_format": "float",
        }
        if self._config.embedding_dimensions > 0:
            payload["dimensions"] = self._config.embedding_dimensions

        async def _request() -> list[float]:
            async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                resp = await client.post(
                    f"{self._config.base_url.rstrip('/')}/embeddings",
                    headers=self._config.request_headers(),
                    json=payload,
                )
                resp.raise_for_status()
            data = resp.json()
            embedding_raw = data["data"][0]["embedding"]
            if not isinstance(embedding_raw, list):
                msg = "openai embedding response does not contain list embedding"
                raise TypeError(msg)
            return [float(x) for x in embedding_raw]

        started_at = perf_counter()
        status = "success"
        try:
            return await self._breaker.call(_request, operation="embeddings")
        except CircuitBreakerOpenError:
            status = "circuit_open"
            record_openrouter_fallback(provider=provider_name, operation="embeddings", reason=status)
            log.warning("openai embedding skipped: circuit breaker OPEN, deterministic fallback is used")
            return await self._fallback.generate_embedding(text)
        except httpx.HTTPStatusError as exc:
            status = f"http_{exc.response.status_code}"
            record_openrouter_fallback(provider=provider_name, operation="embeddings", reason=status)
            log.exception(
                "openai embedding failed with http status, deterministic fallback is used",
                status_code=exc.response.status_code,
            )
            return await self._fallback.generate_embedding(text)
        except Exception:
            status = "error"
            record_openrouter_fallback(provider=provider_name, operation="embeddings", reason=status)
            log.exception("openai embedding failed, deterministic fallback is used")
            return await self._fallback.generate_embedding(text)
        finally:
            record_openrouter_request(
                provider=provider_name,
                operation="embeddings",
                model=model_name,
                status=status,
                duration_seconds=perf_counter() - started_at,
            )
