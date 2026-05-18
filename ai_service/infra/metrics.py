from prometheus_client import Counter, Histogram

openrouter_requests_total = Counter(
    "ai_openrouter_requests_total",
    "Total OpenRouter API requests by operation/model/status.",
    labelnames=("provider", "operation", "model", "status"),
)

openrouter_request_duration_seconds = Histogram(
    "ai_openrouter_request_duration_seconds",
    "OpenRouter API request latency in seconds.",
    labelnames=("provider", "operation", "model", "status"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30),
)

openrouter_fallback_total = Counter(
    "ai_openrouter_fallback_total",
    "Total OpenRouter fallbacks.",
    labelnames=("provider", "operation", "reason"),
)


def record_openrouter_request(
    *,
    provider: str,
    operation: str,
    model: str,
    status: str,
    duration_seconds: float,
) -> None:
    labels = {
        "provider": provider,
        "operation": operation,
        "model": model,
        "status": status,
    }
    openrouter_requests_total.labels(**labels).inc()
    openrouter_request_duration_seconds.labels(**labels).observe(duration_seconds)


def record_openrouter_fallback(*, provider: str, operation: str, reason: str) -> None:
    openrouter_fallback_total.labels(provider=provider, operation=operation, reason=reason).inc()
