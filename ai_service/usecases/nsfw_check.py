from dataclasses import dataclass
from typing import final

import structlog

from ai_service.domain.moderation import ModerationFlag
from ai_service.infra.tracing import current_trace_id, inject_trace_headers
from ai_service.protocols import AIRepositoryProtocol, EventPublisherProtocol, NSFWDetectorProtocol

log = structlog.stdlib.get_logger("ai_service.usecases.NSFWCheck")


@final
class NSFWCheck:
    def __init__(
        self,
        *,
        repository: AIRepositoryProtocol,
        detector: NSFWDetectorProtocol,
        publisher: EventPublisherProtocol,
        threshold: float,
    ) -> None:
        self._repository = repository
        self._detector = detector
        self._publisher = publisher
        self._threshold = threshold

    @dataclass(slots=True)
    class Request:
        telegram_id: int
        profile_id: int
        photo_id: int
        minio_key: str
        trace_id: str | None = None

    async def execute(self, request: Request) -> None:
        score = await self._detector.detect(minio_key=request.minio_key)
        flagged = score > self._threshold
        log.info(
            "photo nsfw scored",
            telegram_id=request.telegram_id,
            profile_id=request.profile_id,
            photo_id=request.photo_id,
            nsfw_score=score,
            threshold=self._threshold,
            flagged=flagged,
        )

        async with self._repository.context() as session:
            await self._repository.update_photo_moderation(
                session,
                AIRepositoryProtocol.UpdatePhotoModerationRequest(
                    photo_id=request.photo_id,
                    is_active=not flagged,
                    is_nsfw=flagged,
                    nsfw_score=score,
                ),
            )
            if flagged:
                await self._repository.insert_moderation_flag(
                    session,
                    ModerationFlag(
                        profile_id=request.profile_id,
                        photo_id=request.photo_id,
                        flag_type="nsfw",
                        severity="high",
                        reason="nsfw threshold exceeded",
                        nsfw_score=score,
                    ),
                )

        if flagged:
            trace_id = request.trace_id or current_trace_id()
            headers = inject_trace_headers({"trace_id": trace_id} if trace_id else None)
            await self._publisher.publish(
                "moderation.photo_rejected",
                {
                    "profile_id": request.profile_id,
                    "telegram_id": request.telegram_id,
                    "photo_id": request.photo_id,
                    "nsfw_score": score,
                },
                headers=headers,
            )
