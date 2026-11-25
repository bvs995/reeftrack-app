"""add_deletion_scheduled_at_to_users

Revision ID: 6e7f8a9b0c1d
Revises: 5d6e7f8a9b0c
Create Date: 2026-11-23 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6e7f8a9b0c1d'
down_revision: Union[str, Sequence[str], None] = '5d6e7f8a9b0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "users" in table_names:
        cols = [c["name"] for c in inspector.get_columns("users")]
        with op.batch_alter_table("users") as batch_op:
            if "deletion_scheduled_at" not in cols:
                batch_op.add_column(sa.Column("deletion_scheduled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "users" in table_names:
        cols = [c["name"] for c in inspector.get_columns("users")]
        with op.batch_alter_table("users") as batch_op:
            if "deletion_scheduled_at" in cols:
                batch_op.drop_column("deletion_scheduled_at")
