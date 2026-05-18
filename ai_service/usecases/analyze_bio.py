from dataclasses import dataclass
from typing import final

import structlog

from ai_service.domain.moderation import ModerationFlag
from ai_service.infra.tracing import current_trace_id, inject_trace_headers
from ai_service.protocols import AIRepositoryProtocol, BioAnalyzerProtocol, EventPublisherProtocol

log = structlog.stdlib.get_logger("ai_service.usecases.AnalyzeBio")


@final
class AnalyzeBio:
    def __init__(
        self,
        *,
        repository: AIRepositoryProtocol,
        analyzer: BioAnalyzerProtocol,
        publisher: EventPublisherProtocol,
        low_confidence_threshold: float,
    ) -> None:
        self._repository = repository
        self._analyzer = analyzer
        self._publisher = publisher
        self._low_confidence_threshold = low_confidence_threshold

    @dataclass(slots=True)
    class Request:
        telegram_id: int
        trace_id: str | None = None

    async def execute(self, request: Request) -> None:
        async with self._repository.context() as session:
            snapshot = await self._repository.get_profile_snapshot_by_telegram_id(session, request.telegram_id)
            if snapshot is None:
                log.warning("profile not found for analyze", telegram_id=request.telegram_id)
                return

            result = await self._analyzer.analyze_bio(profile_id=snapshot.profile_id, bio=snapshot.bio)
            log.info(
                "bio analyzed",
                telegram_id=snapshot.telegram_id,
                profile_id=snapshot.profile_id,
                quality_score=result.quality_score,
                safe=result.safe,
                contact_detected=result.contact_detected,
                confidence=result.confidence,
                issues_count=len(result.issues),
                suggestions_count=len(result.suggestions),
            )
            if result.confidence < self._low_confidence_threshold:
                log.warning(
                    "bio analysis low confidence, manual review recommended",
                    telegram_id=snapshot.telegram_id,
                    profile_id=snapshot.profile_id,
                    confidence=result.confidence,
                    threshold=self._low_confidence_threshold,
                )
            await self._repository.upsert_analysis_result(
                session,
                AIRepositoryProtocol.UpsertAnalysisRequest(profile_id=snapshot.profile_id, analysis=result),
            )
            await self._repository.update_profile_quality_score(
                session,
                profile_id=snapshot.profile_id,
                quality_score=result.quality_score,
            )
            if not result.safe:
                await self._repository.update_profile_active(
                    session,
                    profile_id=snapshot.profile_id,
                    is_active=False,
                )

            if result.contact_detected or not result.safe:
                reason = "contact_detected" if result.contact_detected else "unsafe_content"
                await self._repository.insert_moderation_flag(
                    session,
                    ModerationFlag(
                        profile_id=snapshot.profile_id,
                        photo_id=None,
                        flag_type="bio",
                        severity="high",
                        reason=reason,
                    ),
                )

        trace_id = request.trace_id or current_trace_id()
        headers = inject_trace_headers({"trace_id": trace_id} if trace_id else None)
        await self._publisher.publish(
            "ai.analysis.completed",
            {
                "profile_id": snapshot.profile_id,
                "telegram_id": snapshot.telegram_id,
                "quality_score": result.quality_score,
                "safe": result.safe,
                "contact_detected": result.contact_detected,
                "confidence": result.confidence,
            },
            headers=headers,
        )

        if result.contact_detected or not result.safe:
            await self._publisher.publish(
                "moderation.flagged",
                {
                    "profile_id": snapshot.profile_id,
                    "telegram_id": snapshot.telegram_id,
                    "flag_type": "bio",
                    "severity": "high",
                },
                headers=headers,
            )
