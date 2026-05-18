from abc import ABC, abstractmethod


class NSFWDetectorProtocol(ABC):
    @abstractmethod
    async def detect(self, *, minio_key: str) -> float: ...
