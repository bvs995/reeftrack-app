"""agregar columna temperatura

Revision ID: 20d473ef6706
Revises: 0016702f41ed
Create Date: 2026-11-13 20:04:46.279997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20d473ef6706'
down_revision: Union[str, Sequence[str], None] = '0016702f41ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "mediciones" in table_names:
        med_cols = [c["name"] for c in inspector.get_columns("mediciones")]
        if "temperatura" not in med_cols:
            op.add_column('mediciones', sa.Column('temperatura', sa.Float(), nullable=True))

    if "measurements" in table_names:
        meas_cols = [c["name"] for c in inspector.get_columns("measurements")]
        if "temperatura" not in meas_cols:
            op.add_column('measurements', sa.Column('temperatura', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "mediciones" in table_names:
        med_cols = [c["name"] for c in inspector.get_columns("mediciones")]
        if "temperatura" in med_cols:
            op.drop_column('mediciones', 'temperatura')

    if "measurements" in table_names:
        meas_cols = [c["name"] for c in inspector.get_columns("measurements")]
        if "temperatura" in meas_cols:
            op.drop_column('measurements', 'temperatura')
