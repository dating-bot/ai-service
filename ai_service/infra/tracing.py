import os
from collections.abc import Mapping
from contextlib import contextmanager

import structlog
from opentelemetry import context as otel_context
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log = structlog.stdlib.get_logger("ai_service.infra.tracing")
_INITIALIZED = False


def setup_tracing(*, service_name: str) -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317").strip()
    if not endpoint:
        _INITIALIZED = True
        log.info("otel tracing disabled: empty OTLP endpoint")
        return

    insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").strip().lower() in {"1", "true", "yes", "y"}

    try:
        provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _INITIALIZED = True
        log.info("otel tracing initialized", service_name=service_name, endpoint=endpoint, insecure=insecure)
    except Exception:
        log.exception("failed to initialize otel tracing")
        _INITIALIZED = True


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def _normalize_carrier(carrier: Mapping[str, object] | None) -> dict[str, str]:
    if not carrier:
        return {}
    return {str(k): _as_text(v) for k, v in carrier.items()}


def inject_trace_headers(headers: Mapping[str, object] | None = None) -> dict[str, object]:
    carrier = _normalize_carrier(headers)
    propagate.inject(carrier)
    out: dict[str, object] = dict(headers or {})
    out.update(carrier)
    return out


def inject_grpc_metadata(existing: list[tuple[str, str]] | None = None) -> list[tuple[str, str]] | None:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    if not carrier and not existing:
        return None

    merged: dict[str, str] = {}
    for key, value in existing or []:
        merged[str(key)] = str(value)
    merged.update(carrier)
    return list(merged.items())


def extract_trace_carrier(carrier: Mapping[str, object] | None) -> dict[str, str]:
    return _normalize_carrier(carrier)


@contextmanager
def attach_context_from_headers(headers: Mapping[str, object] | None):
    carrier = extract_trace_carrier(headers)
    if not carrier:
        yield
        return

    token = otel_context.attach(propagate.extract(carrier))
    try:
        yield
    finally:
        otel_context.detach(token)


def current_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")
