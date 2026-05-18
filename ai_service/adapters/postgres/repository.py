from contextlib import asynccontextmanager
from typing import final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from ai_service.adapters.postgres.models import (
    AIAnalysisResultORM,
    ModerationFlagORM,
    PhotoORM,
    ProfileEmbeddingORM,
    ProfileORM,
    UserORM,
)
from ai_service.domain.moderation import ModerationFlag
from ai_service.infra import AsyncSessionFactory
from ai_service.protocols import AIRepositoryProtocol


@final
class PostgresAIRepositoryAdapter(AIRepositoryProtocol):
    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def context(self):
        async with self._session_factory.begin() as session:
            yield session

    async def get_profile_snapshot_by_telegram_id(self, session, telegram_id: int):
        query = (
            sa
            .select(ProfileORM.id, UserORM.telegram_id, ProfileORM.bio)
            .join(UserORM, UserORM.id == ProfileORM.user_id)
            .where(UserORM.telegram_id == telegram_id)
        )
        row = (await session.execute(query)).first()
        if row is None:
            return None
        return AIRepositoryProtocol.ProfileSnapshot(
            profile_id=int(row.id),
            telegram_id=int(row.telegram_id),
            bio=row.bio,
        )

    async def upsert_analysis_result(self, session, request: AIRepositoryProtocol.UpsertAnalysisRequest) -> None:
        payload = {
            "profile_id": request.profile_id,
            "quality_score": request.analysis.quality_score,
            "issues": request.analysis.issues,
            "suggestions": request.analysis.suggestions,
            "safe": request.analysis.safe,
            "contact_detected": request.analysis.contact_detected,
            "raw_payload": {
                "quality_score": request.analysis.quality_score,
                "issues": request.analysis.issues,
                "suggestions": request.analysis.suggestions,
                "safe": request.analysis.safe,
                "contact_detected": request.analysis.contact_detected,
                "confidence": request.analysis.confidence,
            },
            "updated_at": sa.func.now(),
        }
        stmt = insert(AIAnalysisResultORM).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AIAnalysisResultORM.profile_id],
            set_=payload,
        )
        await session.execute(stmt)

    async def update_profile_quality_score(self, session, *, profile_id: int, quality_score: float) -> None:
        stmt = sa.update(ProfileORM).where(ProfileORM.id == profile_id).values(ai_quality_score=quality_score)
        await session.execute(stmt)

    async def update_profile_active(self, session, *, profile_id: int, is_active: bool) -> None:
        stmt = sa.update(ProfileORM).where(ProfileORM.id == profile_id).values(is_active=is_active)
        await session.execute(stmt)

    async def insert_moderation_flag(self, session, flag: ModerationFlag) -> None:
        stmt = sa.insert(ModerationFlagORM).values(
            profile_id=flag.profile_id,
            photo_id=flag.photo_id,
            flag_type=flag.flag_type,
            severity=flag.severity,
            reason=flag.reason,
            nsfw_score=flag.nsfw_score,
        )
        await session.execute(stmt)

    async def upsert_embedding(self, session, request: AIRepositoryProtocol.UpsertEmbeddingRequest) -> None:
        payload = {
            "profile_id": request.profile_id,
            "model": request.model,
            "embedding": request.embedding,
            "updated_at": sa.func.now(),
        }
        stmt = insert(ProfileEmbeddingORM).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProfileEmbeddingORM.profile_id],
            set_=payload,
        )
        await session.execute(stmt)

    async def update_photo_moderation(
        self,
        session,
        request: AIRepositoryProtocol.UpdatePhotoModerationRequest,
    ) -> None:
        stmt = (
            sa
            .update(PhotoORM)
            .where(PhotoORM.id == request.photo_id)
            .values(
                is_active=request.is_active,
                is_nsfw=request.is_nsfw,
                nsfw_score=request.nsfw_score,
            )
        )
        await session.execute(stmt)
