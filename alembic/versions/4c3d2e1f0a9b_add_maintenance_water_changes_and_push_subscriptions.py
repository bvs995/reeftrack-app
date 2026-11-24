"""add_maintenance_water_changes_and_push_subscriptions

Revision ID: 4c3d2e1f0a9b
Revises: 3a1b4c5d6e7f
Create Date: 2026-11-23 16:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4c3d2e1f0a9b'
down_revision: Union[str, Sequence[str], None] = '3a1b4c5d6e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    # 1. Tabla maintenance_tasks
    if "maintenance_tasks" not in table_names:
        op.create_table(
            "maintenance_tasks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("aquarium_id", sa.Integer(), sa.ForeignKey("tanks.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("task_key", sa.String(50), nullable=True),
            sa.Column("title", sa.String(120), nullable=False),
            sa.Column("category", sa.String(50), nullable=False, server_default="mechanical"),
            sa.Column("frequency_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )

    # 2. Tabla maintenance_logs
    if "maintenance_logs" not in table_names:
        op.create_table(
            "maintenance_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("aquarium_id", sa.Integer(), nullable=False, index=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("linked_water_change_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True)
        )

    # 3. Tabla water_changes
    if "water_changes" not in table_names:
        op.create_table(
            "water_changes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tank_id", sa.Integer(), sa.ForeignKey("tanks.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("volume_liters", sa.Float(), nullable=False),
            sa.Column("percentage", sa.Float(), nullable=True),
            sa.Column("performed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )

    # 4. Tabla push_subscriptions
    if "push_subscriptions" not in table_names:
        op.create_table(
            "push_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("endpoint", sa.Text(), unique=True, nullable=False),
            sa.Column("p256dh", sa.String(255), nullable=False),
            sa.Column("auth", sa.String(255), nullable=False),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("notify_maintenance", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("notify_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "push_subscriptions" in table_names:
        op.drop_table("push_subscriptions")
    if "water_changes" in table_names:
        op.drop_table("water_changes")
    if "maintenance_logs" in table_names:
        op.drop_table("maintenance_logs")
    if "maintenance_tasks" in table_names:
        op.drop_table("maintenance_tasks")
