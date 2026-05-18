from collections.abc import Callable
from typing import ClassVar, override

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource

from ai_service.infra.ai import AIConfig
from ai_service.infra.grpc import GrpcServerConfig
from ai_service.infra.minio import MinIOConfig
from ai_service.infra.openai import OpenAIConfig
from ai_service.infra.postgres import PostgresConfig
from ai_service.infra.rabbitmq import RabbitMQConfig


class GlobalConfig(BaseSettings):
    debug: bool = False

    postgres: PostgresConfig
    grpc_server: GrpcServerConfig
    rabbitmq: RabbitMQConfig
    minio: MinIOConfig
    openai: OpenAIConfig = OpenAIConfig()
    ai: AIConfig = AIConfig()

    @classmethod
    def load(cls) -> "GlobalConfig":
        return GlobalConfig()

    @classmethod
    def subconfigs(cls) -> list[Callable[["GlobalConfig"], object]]:
        getters: list[Callable[[GlobalConfig], object]] = []
        types_met: set[str] = set()

        for field_name, model_field in GlobalConfig.model_fields.items():
            target_type = model_field.annotation
            if target_type is None:
                continue
            if str(target_type) in types_met:
                continue
            types_met.add(str(target_type))

            def factory(field_name: str, output_type: type) -> Callable[["GlobalConfig"], object]:
                def getter(cfg: "GlobalConfig") -> object:
                    return getattr(cfg, field_name)

                getter.__annotations__["return"] = output_type
                return staticmethod(getter)

            getters.append(factory(field_name, target_type))

        return getters

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="AI_SERVICE_",
        case_sensitive=False,
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        toml_file="config.toml",
    )

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )
