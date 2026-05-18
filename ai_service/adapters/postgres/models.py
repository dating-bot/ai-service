from datetime import UTC, datetime
from typing import final

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


@final
class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)


@final
class ProfileORM(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    bio: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    ai_quality_score: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, server_default=sa.true())


@final
class PhotoORM(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, server_default=sa.true())
    is_nsfw: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, server_default=sa.false())
    nsfw_score: Mapped[float] = mapped_column(sa.Float(), nullable=False, server_default=sa.text("0"))


@final
class AIAnalysisResultORM(Base):
    __tablename__ = "ai_analysis_results"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False, unique=True)
    quality_score: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    issues: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    suggestions: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    safe: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    contact_detected: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    raw_payload: Mapped[dict[str, object]] = mapped_column(sa.JSON(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), default=lambda: datetime.now(UTC)
    )


@final
class ModerationFlagORM(Base):
    __tablename__ = "moderation_flags"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    photo_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    flag_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    nsfw_score: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


@final
class ProfileEmbeddingORM(Base):
    __tablename__ = "profile_embeddings"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False, unique=True)
    model: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), default=lambda: datetime.now(UTC)
    )
