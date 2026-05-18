import asyncio
import json
from typing import final

import aio_pika
import structlog
from aio_pika import ExchangeType

from ai_service.app.celery import AI_TASK_QUEUE
from ai_service.app.tasks.pipeline import analyze_bio_task, generate_embedding_task, nsfw_check_task
from ai_service.infra.tracing import attach_context_from_headers, current_trace_id

log = structlog.stdlib.get_logger("ai_service.consumers.EventsConsumer")

PROFILE_EXCHANGE = "profile_exchange"
PROFILE_UPDATED_QUEUE = "ai.profile.updated"
PHOTO_UPLOADED_QUEUE = "ai.photo.uploaded"


@final
class EventsConsumer:
    def __init__(self, connection: aio_pika.abc.AbstractRobustConnection) -> None:
        self._connection = connection
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def run(self) -> None:
        channel = await self._connection.channel()
        self._channel = channel
        _ = await channel.set_qos(prefetch_count=32)

        exchange = await channel.declare_exchange(PROFILE_EXCHANGE, ExchangeType.TOPIC, durable=True)
        profile_updated_queue = await channel.declare_queue(PROFILE_UPDATED_QUEUE, durable=True)
        _ = await profile_updated_queue.bind(exchange, routing_key="profile.updated")

        photo_uploaded_queue = await channel.declare_queue(PHOTO_UPLOADED_QUEUE, durable=True)
        _ = await photo_uploaded_queue.bind(exchange, routing_key="photo.uploaded")

        try:
            async with asyncio.TaskGroup() as tg:
                _ = tg.create_task(self._consume_profile_updated(profile_updated_queue))
                _ = tg.create_task(self._consume_photo_uploaded(photo_uploaded_queue))
        finally:
            self._channel = None

    async def stop(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()

    async def _consume_profile_updated(self, queue: aio_pika.abc.AbstractQueue) -> None:
        try:
            async with queue.iterator() as iterator:
                async for message in iterator:
                    async with message.process(ignore_processed=True):
                        payload = json.loads(message.body)
                        telegram_id = int(payload["telegram_id"])
                        with attach_context_from_headers(message.headers):
                            trace_id = _extract_trace_id(message.headers) or current_trace_id()
                            analyze_bio_task.apply_async(
                                kwargs={"telegram_id": telegram_id, "trace_id": trace_id},
                                queue=AI_TASK_QUEUE,
                            )
                            generate_embedding_task.apply_async(
                                kwargs={"telegram_id": telegram_id, "trace_id": trace_id},
                                queue=AI_TASK_QUEUE,
                            )
                            log.info("profile.updated accepted", telegram_id=telegram_id, trace_id=trace_id)
        except (asyncio.CancelledError, aio_pika.exceptions.ChannelInvalidStateError):
            log.info("profile.updated consumer stopped")

    async def _consume_photo_uploaded(self, queue: aio_pika.abc.AbstractQueue) -> None:
        try:
            async with queue.iterator() as iterator:
                async for message in iterator:
                    async with message.process(ignore_processed=True):
                        payload = json.loads(message.body)
                        with attach_context_from_headers(message.headers):
                            trace_id = _extract_trace_id(message.headers) or current_trace_id()
                            nsfw_check_task.apply_async(
                                kwargs={"payload": payload, "trace_id": trace_id},
                                queue=AI_TASK_QUEUE,
                            )
                            log.info("photo.uploaded accepted", photo_id=payload["photo_id"], trace_id=trace_id)
        except (asyncio.CancelledError, aio_pika.exceptions.ChannelInvalidStateError):
            log.info("photo.uploaded consumer stopped")


def _extract_trace_id(headers: dict[str, object] | None) -> str | None:
    if not headers:
        return None
    trace_id = headers.get("trace_id")
    if isinstance(trace_id, bytes):
        return trace_id.decode("utf-8", errors="ignore")
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    traceparent = headers.get("traceparent")
    if isinstance(traceparent, bytes):
        traceparent = traceparent.decode("utf-8", errors="ignore")
    if isinstance(traceparent, str):
        parts = traceparent.split("-")
        if len(parts) >= 4 and len(parts[1]) == 32:
            return parts[1]
        return traceparent or None
    return None
