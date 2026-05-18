from typing import final

import aio_pika
import aioboto3
import dishka
from sqlalchemy.ext.asyncio import AsyncSession

from ai_service import adapters, infra, protocols, usecases
from ai_service.app.consumers.events_consumer import EventsConsumer
from ai_service.app.server import grpc_handler


@final
class InfraProvider(dishka.Provider):
    scope = dishka.Scope.APP

    global_config = dishka.provide(staticmethod(infra.GlobalConfig.load))
    subconfigs = dishka.provide_all(*infra.GlobalConfig.subconfigs())
    async_engine = dishka.provide(staticmethod(infra.provide_async_engine))
    async_session_factory = dishka.provide(staticmethod(infra.provide_async_session_factory))
    rabbitmq_connection = dishka.provide(staticmethod(infra.provide_rabbitmq_connection))
    aioboto3_session = dishka.provide(staticmethod(infra.provide_aioboto3_session))


@final
class AdapterProvider(dishka.Provider):
    scope = dishka.Scope.APP

    @dishka.provide
    def provide_repository(self, session_factory: infra.AsyncSessionFactory) -> protocols.AIRepositoryProtocol:
        return adapters.PostgresAIRepositoryAdapter(session_factory)

    @dishka.provide
    def provide_analyzer(self, openai_cfg: infra.OpenAIConfig) -> protocols.BioAnalyzerProtocol:
        return adapters.OpenAIBioAnalyzerAdapter(openai_cfg)

    @dishka.provide
    def provide_embedding_generator(
        self,
        openai_cfg: infra.OpenAIConfig,
        ai_cfg: infra.AIConfig,
    ) -> protocols.EmbeddingGeneratorProtocol:
        return adapters.OpenAIEmbeddingAdapter(openai_cfg, ai_cfg.embedding_size)

    @dishka.provide
    def provide_nsfw_detector(
        self,
        openai_cfg: infra.OpenAIConfig,
        ai_cfg: infra.AIConfig,
        minio_cfg: infra.MinIOConfig,
        aioboto3_session: aioboto3.Session,
    ) -> protocols.NSFWDetectorProtocol:
        return adapters.OpenAINSFWDetectorAdapter(
            openai_cfg=openai_cfg,
            low_confidence_threshold=ai_cfg.low_confidence_threshold,
            minio_cfg=minio_cfg,
            session=aioboto3_session,
        )

    @dishka.provide
    def provide_event_publisher(
        self,
        rabbitmq_connection: aio_pika.abc.AbstractRobustConnection,
    ) -> protocols.EventPublisherProtocol:
        return adapters.RabbitMQEventPublisherAdapter(rabbitmq_connection)


@final
class AppProvider(dishka.Provider):
    scope = dishka.Scope.APP

    @dishka.provide
    def provide_analyze_bio(
        self,
        repository: protocols.AIRepositoryProtocol[AsyncSession],
        analyzer: protocols.BioAnalyzerProtocol,
        publisher: protocols.EventPublisherProtocol,
        ai_cfg: infra.AIConfig,
    ) -> usecases.AnalyzeBio:
        return usecases.AnalyzeBio(
            repository=repository,
            analyzer=analyzer,
            publisher=publisher,
            low_confidence_threshold=ai_cfg.low_confidence_threshold,
        )

    @dishka.provide
    def provide_generate_embedding(
        self,
        repository: protocols.AIRepositoryProtocol[AsyncSession],
        embedding_generator: protocols.EmbeddingGeneratorProtocol,
        openai_cfg: infra.OpenAIConfig,
    ) -> usecases.GenerateEmbedding:
        return usecases.GenerateEmbedding(
            repository=repository,
            embedding_generator=embedding_generator,
            model_name=openai_cfg.embedding_model,
        )

    @dishka.provide
    def provide_nsfw_check(
        self,
        repository: protocols.AIRepositoryProtocol[AsyncSession],
        detector: protocols.NSFWDetectorProtocol,
        publisher: protocols.EventPublisherProtocol,
        ai_cfg: infra.AIConfig,
    ) -> usecases.NSFWCheck:
        return usecases.NSFWCheck(
            repository=repository,
            detector=detector,
            publisher=publisher,
            threshold=ai_cfg.nsfw_threshold,
        )

    @dishka.provide
    def provide_events_consumer(
        self,
        rabbitmq_connection: aio_pika.abc.AbstractRobustConnection,
    ) -> EventsConsumer:
        return EventsConsumer(rabbitmq_connection)

    @dishka.provide
    def provide_gateway_handler(self) -> grpc_handler.GatewayServiceHandler:
        return grpc_handler.GatewayServiceHandler()


container = dishka.make_async_container(InfraProvider(), AdapterProvider(), AppProvider())
