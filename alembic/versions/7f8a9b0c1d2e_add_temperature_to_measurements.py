"""add_temperature_to_measurements

El modelo Measurement tiene las columnas `temperature` y `temperatura`, pero las
migraciones solo creaban `temperatura`. En desarrollo init_db() agrega la columna
con ALTER TABLE; en producción ese DDL defensivo está apagado y el esquema depende
solo de Alembic, así que cualquier SELECT sobre measurements fallaba con
"column measurements.temperature does not exist".

Revision ID: 7f8a9b0c1d2e
Revises: 6e7f8a9b0c1d
Create Date: 2026-11-25 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7f8a9b0c1d2e'
down_revision: Union[str, Sequence[str], None] = '6e7f8a9b0c1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "measurements" not in inspector.get_table_names():
        return

    cols = [c["name"] for c in inspector.get_columns("measurements")]
    if "temperature" not in cols:
        with op.batch_alter_table("measurements") as batch_op:
            batch_op.add_column(sa.Column("temperature", sa.Float(), nullable=True))

    # Rellenar desde la columna en español para no perder lecturas ya guardadas.
    if "temperatura" in cols:
        op.execute(
            "UPDATE measurements SET temperature = temperatura "
            "WHERE temperature IS NULL AND temperatura IS NOT NULL"
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "measurements" not in inspector.get_table_names():
        return

    cols = [c["name"] for c in inspector.get_columns("measurements")]
    if "temperature" in cols:
        with op.batch_alter_table("measurements") as batch_op:
            batch_op.drop_column("temperature")
