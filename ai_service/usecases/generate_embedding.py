from dataclasses import dataclass
from typing import final

import structlog

from ai_service.protocols import AIRepositoryProtocol, EmbeddingGeneratorProtocol

log = structlog.stdlib.get_logger("ai_service.usecases.GenerateEmbedding")


@final
class GenerateEmbedding:
    def __init__(
        self,
        *,
        repository: AIRepositoryProtocol,
        embedding_generator: EmbeddingGeneratorProtocol,
        model_name: str,
    ) -> None:
        self._repository = repository
        self._embedding_generator = embedding_generator
        self._model_name = model_name

    @dataclass(slots=True)
    class Request:
        telegram_id: int

    async def execute(self, request: Request) -> None:
        async with self._repository.context() as session:
            snapshot = await self._repository.get_profile_snapshot_by_telegram_id(session, request.telegram_id)
            if snapshot is None:
                log.warning("profile not found for embedding", telegram_id=request.telegram_id)
                return

            embedding = await self._embedding_generator.generate_embedding(snapshot.bio or "")
            log.info(
                "embedding generated",
                telegram_id=snapshot.telegram_id,
                profile_id=snapshot.profile_id,
                model=self._model_name,
                dimensions=len(embedding),
            )
            await self._repository.upsert_embedding(
                session,
                AIRepositoryProtocol.UpsertEmbeddingRequest(
                    profile_id=snapshot.profile_id,
                    model=self._model_name,
                    embedding=embedding,
                ),
            )
