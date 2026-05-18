import asyncio
from uuid import uuid4

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ai_service.adapters import (
    OpenAIBioAnalyzerAdapter,
    OpenAIEmbeddingAdapter,
    OpenAINSFWDetectorAdapter,
    PostgresAIRepositoryAdapter,
    RabbitMQEventPublisherAdapter,
)
from ai_service.app.celery import celery_app
from ai_service.infra import AIConfig, GlobalConfig
from ai_service.infra.minio import provide_aioboto3_session
from ai_service.infra.rabbitmq import provide_rabbitmq_connection
from ai_service.usecases import AnalyzeBio, GenerateEmbedding, NSFWCheck

log = structlog.stdlib.get_logger("ai_service.tasks")


async def _build_deps():
    config = GlobalConfig.load()
    engine = create_async_engine(config.postgres.url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    repo = PostgresAIRepositoryAdapter(session_factory=session_factory)
    analyzer = OpenAIBioAnalyzerAdapter(config.openai)
    embedding = OpenAIEmbeddingAdapter(config.openai, config.ai.embedding_size)
    detector = OpenAINSFWDetectorAdapter(
        openai_cfg=config.openai,
        low_confidence_threshold=config.ai.low_confidence_threshold,
        minio_cfg=config.minio,
        session=provide_aioboto3_session(),
    )

    connection_gen = provide_rabbitmq_connection(config.rabbitmq)
    connection = await anext(connection_gen)
    publisher = RabbitMQEventPublisherAdapter(connection)

    return (
        config.ai,
        config.openai.embedding_model,
        engine,
        connection_gen,
        repo,
        analyzer,
        embedding,
        detector,
        publisher,
    )


@shared_task(bind=True, app=celery_app, max_retries=3)
def analyze_bio_task(_self, telegram_id: int, trace_id: str | None = None):
    async def _run() -> None:
        (
            ai_config,
            _embedding_model,
            engine,
            connection_gen,
            repo,
            analyzer,
            _embedding,
            _detector,
            publisher,
        ) = await _build_deps()
        try:
            usecase = AnalyzeBio(
                repository=repo,
                analyzer=analyzer,
                publisher=publisher,
                low_confidence_threshold=ai_config.low_confidence_threshold,
            )
            await usecase.execute(AnalyzeBio.Request(telegram_id=telegram_id, trace_id=trace_id))
        finally:
            await engine.dispose()
            await connection_gen.aclose()

    run_trace_id = trace_id or uuid4().hex
    with structlog.contextvars.bound_contextvars(trace_id=run_trace_id):
        log.info("analyze_bio_task started", telegram_id=telegram_id)
        asyncio.run(_run())
        log.info("analyze_bio_task completed", telegram_id=telegram_id)


@shared_task(bind=True, app=celery_app, max_retries=3)
def generate_embedding_task(_self, telegram_id: int, trace_id: str | None = None):
    async def _run() -> None:
        (
            ai_config,
            embedding_model,
            engine,
            connection_gen,
            repo,
            _analyzer,
            embedding,
            _detector,
            _publisher,
        ) = await _build_deps()
        try:
            usecase = GenerateEmbedding(
                repository=repo,
                embedding_generator=embedding,
                model_name=embedding_model,
            )
            await usecase.execute(GenerateEmbedding.Request(telegram_id=telegram_id))
        finally:
            del ai_config
            await engine.dispose()
            await connection_gen.aclose()

    run_trace_id = trace_id or uuid4().hex
    with structlog.contextvars.bound_contextvars(trace_id=run_trace_id):
        log.info("generate_embedding_task started", telegram_id=telegram_id)
        asyncio.run(_run())
        log.info("generate_embedding_task completed", telegram_id=telegram_id)


@shared_task(bind=True, app=celery_app, max_retries=3)
def nsfw_check_task(
    _self,
    payload: dict[str, object],
    trace_id: str | None = None,
):
    async def _run() -> None:
        ai_config: AIConfig
        (
            ai_config,
            _embedding_model,
            engine,
            connection_gen,
            repo,
            _analyzer,
            _embedding,
            detector,
            publisher,
        ) = await _build_deps()
        telegram_id = int(payload["telegram_id"])
        profile_id = int(payload["profile_id"])
        photo_id = int(payload["photo_id"])
        minio_key = str(payload["minio_key"])
        try:
            usecase = NSFWCheck(
                repository=repo,
                detector=detector,
                publisher=publisher,
                threshold=ai_config.nsfw_threshold,
            )
            await usecase.execute(
                NSFWCheck.Request(
                    telegram_id=telegram_id,
                    profile_id=profile_id,
                    photo_id=photo_id,
                    minio_key=minio_key,
                    trace_id=trace_id,
                )
            )
        finally:
            await engine.dispose()
            await connection_gen.aclose()

    run_trace_id = trace_id or uuid4().hex
    photo_id = int(payload["photo_id"])
    profile_id = int(payload["profile_id"])
    with structlog.contextvars.bound_contextvars(trace_id=run_trace_id):
        log.info("nsfw_check_task started", photo_id=photo_id, profile_id=profile_id)
        asyncio.run(_run())
        log.info("nsfw_check_task completed", photo_id=photo_id, profile_id=profile_id)
