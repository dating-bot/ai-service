from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class PostgresConfig(BaseModel):
    host: str = Field(description="Host")
    port: int = Field(description="Port")
    username: str = Field(description="Username")
    password: str = Field(description="Password")
    database: str = Field(description="Database name")
    should_log_sql: bool | None = Field(default=False, description="Enable SQL query logging")
    pool_size: int = Field(default=10, description="Max pool connections")
    pool_max_overflow: int | None = Field(default=20, description="Max overflow connections")

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class AsyncSessionFactory(async_sessionmaker[AsyncSession]): ...


async def provide_async_engine(config: PostgresConfig) -> AsyncGenerator[AsyncEngine]:
    kw: dict[str, Any] = {}
    if config.should_log_sql is not None:
        kw["echo"] = config.should_log_sql
    if config.pool_max_overflow is not None:
        kw["max_overflow"] = config.pool_max_overflow

    engine = create_async_engine(config.url, **kw)
    try:
        yield engine
    finally:
        await engine.dispose()


async def provide_async_session_factory(engine: AsyncEngine) -> AsyncSessionFactory:
    return AsyncSessionFactory(engine, class_=AsyncSession, expire_on_commit=False)
