from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog.stdlib
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from grpclib.server import Stream
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from ai_service.infra.tracing import attach_context_from_headers, current_trace_id

type UnaryHandler[T, I: Message, O: Message] = Callable[[T, I], Awaitable[O]]

log = structlog.stdlib.get_logger("ai_service.grpc.handler")
tracer = trace.get_tracer("ai_service.grpc.server")


def unary[T, I: Message, O: Message](handler: UnaryHandler[T, I, O]):
    async def wrapper(self: T, stream: Stream[I, O]) -> None:
        with attach_context_from_headers(getattr(stream, "metadata", None)):
            with tracer.start_as_current_span(f"grpc.{wrapper.__qualname__}", kind=SpanKind.SERVER) as span:
                span.set_attribute("rpc.system", "grpc")
                span.set_attribute("rpc.service", self.__class__.__name__)
                span.set_attribute("rpc.method", handler.__name__)

                trace_id = _extract_trace_id(stream) or current_trace_id() or uuid4().hex
                with structlog.contextvars.bound_contextvars(trace_id=trace_id):
                    request = await stream.recv_message()
                    if request is None:
                        log.warning("received None (no request), skipping handlers", handler=wrapper.__qualname__)
                        return

                    log.debug(
                        "grpc handler invoked",
                        handler=wrapper.__qualname__,
                        request=MessageToDict(request, preserving_proto_field_name=True),
                    )

                    response = await handler(self, request)

                    log.debug(
                        "grpc handler response",
                        handler=wrapper.__qualname__,
                        response=MessageToDict(response, preserving_proto_field_name=True),
                    )

                    await stream.send_message(response)

    wrapper.__qualname__ = handler.__qualname__
    wrapper.__name__ = handler.__name__
    wrapper.__doc__ = handler.__doc__

    return wrapper


def _extract_trace_id(stream: Stream[Message, Message]) -> str | None:
    metadata = getattr(stream, "metadata", None)
    if metadata is None:
        return None
    trace_id = _as_text(metadata.get("trace_id"))
    if trace_id:
        return trace_id
    traceparent = _as_text(metadata.get("traceparent"))
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) >= 4 and len(parts[1]) == 32:
            return parts[1]
        return traceparent
    return None


def _as_text(value: object) -> str | None:
    if isinstance(value, bytes):
        decoded = value.decode("utf-8", errors="ignore")
        return decoded or None
    if value is None:
        return None
    text = str(value)
    return text or None
