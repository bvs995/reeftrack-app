"""audit_tables_and_tokens

Revision ID: 5d6e7f8a9b0c
Revises: 4c3d2e1f0a9b
Create Date: 2026-11-23 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5d6e7f8a9b0c'
down_revision: Union[str, Sequence[str], None] = '4c3d2e1f0a9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()
    json_type = postgresql.JSONB(astext_type=sa.Text()) if conn.dialect.name == "postgresql" else sa.JSON()

    # 1. Columnas en users
    if "users" in table_names:
        cols = [c["name"] for c in inspector.get_columns("users")]
        with op.batch_alter_table("users") as batch_op:
            if "token_version" not in cols:
                batch_op.add_column(sa.Column("token_version", sa.Integer(), server_default="1", nullable=True))
            if "email_verified" not in cols:
                batch_op.add_column(sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=True))

    # 2. Columnas en measurements
    if "measurements" in table_names:
        cols = [c["name"] for c in inspector.get_columns("measurements")]
        with op.batch_alter_table("measurements") as batch_op:
            if "is_camera_scan" not in cols:
                batch_op.add_column(sa.Column("is_camera_scan", sa.Boolean(), server_default=sa.text("false"), nullable=True))
            if "is_draft" not in cols:
                batch_op.add_column(sa.Column("is_draft", sa.Boolean(), server_default=sa.text("false"), nullable=True))
            if "client_uuid" not in cols:
                batch_op.add_column(sa.Column("client_uuid", sa.String(100), nullable=True))
                batch_op.create_unique_constraint("uq_measurements_client_uuid", ["client_uuid"])
            if "kit" not in cols:
                batch_op.add_column(sa.Column("kit", sa.String(100), nullable=True))

    # 3. Tabla diagnostic_feedback
    if "diagnostic_feedback" not in table_names:
        op.create_table(
            "diagnostic_feedback",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("tank_id", sa.Integer(), sa.ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("diagnosis_summary", sa.Text(), nullable=True),
            sa.Column("severity", sa.String(50), nullable=True),
            sa.Column("user_comment", sa.Text(), nullable=False),
            sa.Column("category", sa.String(50), server_default="incorrect_diagnosis", nullable=False),
            sa.Column("consent_given", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )

    # 4. Tabla diagnostic_audits
    if "diagnostic_audits" not in table_names:
        op.create_table(
            "diagnostic_audits",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("tank_id", sa.Integer(), sa.ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("prompt_version", sa.String(50), server_default="v1", nullable=False),
            sa.Column("inputs", json_type, nullable=False),
            sa.Column("rules_alerts", json_type, nullable=False),
            sa.Column("raw_ai_output", sa.Text(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, index=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("cost_usd", sa.Float(), server_default="0.0", nullable=False),
            sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("latency_ms", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True)
        )

    # 5. Tabla password_reset_tokens
    if "password_reset_tokens" not in table_names:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("token_hash", sa.String(128), nullable=False, unique=True, index=True),
            sa.Column("jti", sa.String(64), nullable=False, unique=True, index=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )

    # 6. Tabla refresh_tokens
    if "refresh_tokens" not in table_names:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("token_hash", sa.String(128), nullable=False, unique=True, index=True),
            sa.Column("jti", sa.String(64), nullable=False, unique=True, index=True),
            sa.Column("family_id", sa.String(64), nullable=False, index=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )

    # 7. Tabla user_daily_quotas
    if "user_daily_quotas" not in table_names:
        op.create_table(
            "user_daily_quotas",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("date", sa.String(10), nullable=False, index=True),
            sa.Column("count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "date", name="uq_user_daily_quota")
        )

    # 8. Tabla rate_limit_records
    if "rate_limit_records" not in table_names:
        op.create_table(
            "rate_limit_records",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("key", sa.String(255), nullable=False, index=True),
            sa.Column("action", sa.String(50), nullable=False, index=True),
            sa.Column("timestamp", sa.Float(), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "rate_limit_records" in table_names:
        op.drop_table("rate_limit_records")
    if "user_daily_quotas" in table_names:
        op.drop_table("user_daily_quotas")
    if "refresh_tokens" in table_names:
        op.drop_table("refresh_tokens")
    if "password_reset_tokens" in table_names:
        op.drop_table("password_reset_tokens")
    if "diagnostic_audits" in table_names:
        op.drop_table("diagnostic_audits")
    if "diagnostic_feedback" in table_names:
        op.drop_table("diagnostic_feedback")
