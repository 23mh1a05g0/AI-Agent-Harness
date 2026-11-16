"""Initial database schema migration creating all 4 required tables plus audit tables.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-16 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. content_queue
    op.create_table(
        "content_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_queue_id"), "content_queue", ["id"], unique=False)
    op.create_index(op.f("ix_content_queue_status"), "content_queue", ["status"], unique=False)

    # 2. trust_store
    op.create_table(
        "trust_store",
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("action_type"),
        sa.CheckConstraint("success_count >= 0", name="check_success_count_non_negative"),
    )

    # 3. action_log
    op.create_table(
        "action_log",
        sa.Column("action_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_row_id", sa.Integer(), nullable=True),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("is_restored", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["target_row_id"], ["content_queue.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index(op.f("ix_action_log_action_type"), "action_log", ["action_type"], unique=False)
    op.create_index(op.f("ix_action_log_target_row_id"), "action_log", ["target_row_id"], unique=False)

    # 4. pending_intents
    op.create_table(
        "pending_intents",
        sa.Column("intent_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_row_id", sa.Integer(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("validated_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("intent_id"),
    )
    op.create_index(op.f("ix_pending_intents_action_type"), "pending_intents", ["action_type"], unique=False)
    op.create_index(op.f("ix_pending_intents_status"), "pending_intents", ["status"], unique=False)
    op.create_index(op.f("ix_pending_intents_target_row_id"), "pending_intents", ["target_row_id"], unique=False)

    # 5. restoration_log (Audit for restorations)
    op.create_table(
        "restoration_log",
        sa.Column("restoration_id", sa.String(length=36), nullable=False),
        sa.Column("action_id", sa.String(length=36), nullable=False),
        sa.Column("target_row_id", sa.Integer(), nullable=True),
        sa.Column("restored_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["action_id"], ["action_log.action_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("restoration_id"),
    )
    op.create_index(op.f("ix_restoration_log_action_id"), "restoration_log", ["action_id"], unique=False)


def downgrade() -> None:
    op.drop_table("restoration_log")
    op.drop_table("pending_intents")
    op.drop_table("action_log")
    op.drop_table("trust_store")
    op.drop_table("content_queue")
