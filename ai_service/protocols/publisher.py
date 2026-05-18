from abc import ABC, abstractmethod


class EventPublisherProtocol(ABC):
    @abstractmethod
    async def publish(
        self,
        routing_key: str,
        payload: dict[str, object],
        headers: dict[str, object] | None = None,
    ) -> None: ...
