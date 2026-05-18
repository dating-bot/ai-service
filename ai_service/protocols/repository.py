from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from ai_service.domain.analysis import BioAnalysisResult
from ai_service.domain.moderation import ModerationFlag


class AIRepositoryProtocol[SessionT](ABC):
    @dataclass(slots=True)
    class ProfileSnapshot:
        profile_id: int
        telegram_id: int
        bio: str | None

    @dataclass(slots=True)
    class UpsertAnalysisRequest:
        profile_id: int
        analysis: BioAnalysisResult

    @dataclass(slots=True)
    class UpsertEmbeddingRequest:
        profile_id: int
        model: str
        embedding: list[float]

    @dataclass(slots=True)
    class UpdatePhotoModerationRequest:
        photo_id: int
        is_active: bool
        is_nsfw: bool
        nsfw_score: float

    @abstractmethod
    def context(self) -> AbstractAsyncContextManager[SessionT]: ...

    @abstractmethod
    async def get_profile_snapshot_by_telegram_id(
        self,
        session: SessionT,
        telegram_id: int,
    ) -> ProfileSnapshot | None: ...

    @abstractmethod
    async def upsert_analysis_result(
        self,
        session: SessionT,
        request: UpsertAnalysisRequest,
    ) -> None: ...

    @abstractmethod
    async def update_profile_quality_score(
        self,
        session: SessionT,
        *,
        profile_id: int,
        quality_score: float,
    ) -> None: ...

    @abstractmethod
    async def update_profile_active(
        self,
        session: SessionT,
        *,
        profile_id: int,
        is_active: bool,
    ) -> None: ...

    @abstractmethod
    async def insert_moderation_flag(
        self,
        session: SessionT,
        flag: ModerationFlag,
    ) -> None: ...

    @abstractmethod
    async def upsert_embedding(
        self,
        session: SessionT,
        request: UpsertEmbeddingRequest,
    ) -> None: ...

    @abstractmethod
    async def update_photo_moderation(
        self,
        session: SessionT,
        request: UpdatePhotoModerationRequest,
    ) -> None: ...
