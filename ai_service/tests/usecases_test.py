from contextlib import asynccontextmanager

import pytest

from ai_service.domain.analysis import BioAnalysisResult
from ai_service.protocols.repository import AIRepositoryProtocol
from ai_service.usecases import AnalyzeBio, GenerateEmbedding, NSFWCheck


class FakeRepo(AIRepositoryProtocol):
    def __init__(self) -> None:
        self.profile = AIRepositoryProtocol.ProfileSnapshot(profile_id=11, telegram_id=101, bio="hi @user")
        self.analysis: BioAnalysisResult | None = None
        self.quality_score: float | None = None
        self.profile_active_updates: list[tuple[int, bool]] = []
        self.flags: list[tuple[str, str]] = []
        self.embedding: list[float] | None = None
        self.photo_updates: list[tuple[int, bool, bool, float]] = []

    @asynccontextmanager
    async def context(self):
        yield object()

    async def get_profile_snapshot_by_telegram_id(self, session, telegram_id: int):
        del session, telegram_id
        return self.profile

    async def upsert_analysis_result(self, session, request):
        del session
        self.analysis = request.analysis

    async def update_profile_quality_score(self, session, *, profile_id: int, quality_score: float):
        del session, profile_id
        self.quality_score = quality_score

    async def update_profile_active(self, session, *, profile_id: int, is_active: bool):
        del session
        self.profile_active_updates.append((profile_id, is_active))

    async def insert_moderation_flag(self, session, flag):
        del session
        self.flags.append((flag.flag_type, flag.reason))

    async def upsert_embedding(self, session, request):
        del session
        self.embedding = request.embedding

    async def update_photo_moderation(self, session, request):
        del session
        self.photo_updates.append((request.photo_id, request.is_active, request.is_nsfw, request.nsfw_score))


class FakeAnalyzer:
    async def analyze_bio(self, *, profile_id: int, bio: str | None) -> BioAnalysisResult:
        del profile_id, bio
        return BioAnalysisResult(
            quality_score=4.2,
            issues=["contains contact info"],
            suggestions=["remove contacts"],
            safe=True,
            contact_detected=True,
            confidence=0.92,
        )


class FakeEmbedding:
    async def generate_embedding(self, text: str) -> list[float]:
        del text
        return [0.1, 0.2, 0.3]


class FakeDetector:
    async def detect(self, *, minio_key: str) -> float:
        del minio_key
        return 0.95


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def publish(self, routing_key: str, payload, headers=None) -> None:
        del payload, headers
        self.events.append(routing_key)


class FakeUnsafeAnalyzer:
    async def analyze_bio(self, *, profile_id: int, bio: str | None) -> BioAnalysisResult:
        del profile_id, bio
        return BioAnalysisResult(
            quality_score=1.0,
            issues=["unsafe content"],
            suggestions=["remove explicit content"],
            safe=False,
            contact_detected=False,
            confidence=0.95,
        )


@pytest.mark.asyncio
async def test_analyze_bio_soft_flag() -> None:
    repo = FakeRepo()
    publisher = FakePublisher()
    usecase = AnalyzeBio(
        repository=repo,
        analyzer=FakeAnalyzer(),
        publisher=publisher,
        low_confidence_threshold=0.6,
    )

    await usecase.execute(AnalyzeBio.Request(telegram_id=101, trace_id="t-1"))

    assert repo.analysis is not None
    assert repo.quality_score == 4.2
    assert repo.profile_active_updates == []
    assert ("bio", "contact_detected") in repo.flags
    assert "ai.analysis.completed" in publisher.events
    assert "moderation.flagged" in publisher.events


@pytest.mark.asyncio
async def test_analyze_bio_unsafe_deactivates_profile() -> None:
    repo = FakeRepo()
    publisher = FakePublisher()
    usecase = AnalyzeBio(
        repository=repo,
        analyzer=FakeUnsafeAnalyzer(),
        publisher=publisher,
        low_confidence_threshold=0.6,
    )

    await usecase.execute(AnalyzeBio.Request(telegram_id=101, trace_id="t-unsafe"))

    assert repo.profile_active_updates == [(11, False)]
    assert ("bio", "unsafe_content") in repo.flags
    assert "moderation.flagged" in publisher.events


@pytest.mark.asyncio
async def test_generate_embedding_upsert() -> None:
    repo = FakeRepo()
    usecase = GenerateEmbedding(repository=repo, embedding_generator=FakeEmbedding(), model_name="m")

    await usecase.execute(GenerateEmbedding.Request(telegram_id=101))

    assert repo.embedding == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_nsfw_check_publishes_rejected() -> None:
    repo = FakeRepo()
    publisher = FakePublisher()
    usecase = NSFWCheck(repository=repo, detector=FakeDetector(), publisher=publisher, threshold=0.7)

    await usecase.execute(
        NSFWCheck.Request(
            telegram_id=101,
            profile_id=11,
            photo_id=55,
            minio_key="profiles/11/nsfw.jpg",
            trace_id="t-2",
        )
    )

    assert repo.photo_updates == [(55, False, True, 0.95)]
    assert ("nsfw", "nsfw threshold exceeded") in repo.flags
    assert "moderation.photo_rejected" in publisher.events
