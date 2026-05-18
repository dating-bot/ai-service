import json
from typing import final

import aio_pika
import structlog
from aio_pika import ExchangeType

from ai_service.infra.tracing import inject_trace_headers
from ai_service.protocols import EventPublisherProtocol

log = structlog.stdlib.get_logger("ai_service.adapters.EventPublisher")

EVENTS_EXCHANGE = "events_exchange"


@final
class RabbitMQEventPublisherAdapter(EventPublisherProtocol):
    def __init__(self, connection: aio_pika.abc.AbstractRobustConnection) -> None:
        self._connection = connection

    async def publish(
        self,
        routing_key: str,
        payload: dict[str, object],
        headers: dict[str, object] | None = None,
    ) -> None:
        channel = await self._connection.channel()
        try:
            exchange = await channel.declare_exchange(EVENTS_EXCHANGE, ExchangeType.TOPIC, durable=True)
            message = aio_pika.Message(
                body=json.dumps(payload).encode(),
                content_type="application/json",
                headers=inject_trace_headers(headers) or None,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            _ = await exchange.publish(message, routing_key=routing_key)
            log.debug("event published", routing_key=routing_key)
        finally:
            if not channel.is_closed:
                await channel.close()
