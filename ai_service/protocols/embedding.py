from abc import ABC, abstractmethod


class EmbeddingGeneratorProtocol(ABC):
    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]: ...
