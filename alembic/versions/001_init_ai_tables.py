"""init ai tables

Revision ID: 001
Revises:
Create Date: 2026-05-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_analysis_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("safe", sa.Boolean(), nullable=False),
        sa.Column("contact_detected", sa.Boolean(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_analysis_results_profile_id", "ai_analysis_results", ["profile_id"], unique=True)

    op.create_table(
        "moderation_flags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("photo_id", sa.BigInteger(), nullable=True),
        sa.Column("flag_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("nsfw_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_moderation_flags_profile_id", "moderation_flags", ["profile_id"], unique=False)
    op.create_index("ix_moderation_flags_flag_type", "moderation_flags", ["flag_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_moderation_flags_flag_type", table_name="moderation_flags")
    op.drop_index("ix_moderation_flags_profile_id", table_name="moderation_flags")
    op.drop_table("moderation_flags")

    op.drop_index("ix_ai_analysis_results_profile_id", table_name="ai_analysis_results")
    op.drop_table("ai_analysis_results")
