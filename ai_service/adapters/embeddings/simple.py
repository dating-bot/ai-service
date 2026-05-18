from hashlib import sha256
from typing import final

from ai_service.protocols import EmbeddingGeneratorProtocol


@final
class DeterministicEmbeddingAdapter(EmbeddingGeneratorProtocol):
    def __init__(self, embedding_size: int = 384) -> None:
        self._embedding_size = embedding_size

    async def generate_embedding(self, text: str) -> list[float]:
        seed = sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        idx = 0
        state = bytearray(seed)
        while len(values) < self._embedding_size:
            if idx >= len(state):
                state = bytearray(sha256(bytes(state)).digest())
                idx = 0
            values.append(((state[idx] / 255.0) * 2.0) - 1.0)
            idx += 1
        return values
