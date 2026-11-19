"""add_reef_profiles_and_trace_elements

Revision ID: 3a1b4c5d6e7f
Revises: 20d473ef6706
Create Date: 2026-11-19 11:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3a1b4c5d6e7f'
down_revision: Union[str, Sequence[str], None] = '20d473ef6706'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    # Columnas en tanks
    if "tanks" in table_names:
        cols = [c["name"] for c in inspector.get_columns("tanks")]
        if "reef_profile" not in cols:
            op.add_column("tanks", sa.Column("reef_profile", sa.String(50), nullable=True))
        if "dosing_method" not in cols:
            op.add_column("tanks", sa.Column("dosing_method", sa.String(50), nullable=True))
        if "lighting_par" not in cols:
            op.add_column("tanks", sa.Column("lighting_par", sa.Integer(), nullable=True))
        if "flow_profile" not in cols:
            op.add_column("tanks", sa.Column("flow_profile", sa.String(50), nullable=True))

    # Columnas en acuarios
    if "acuarios" in table_names:
        cols = [c["name"] for c in inspector.get_columns("acuarios")]
        if "reef_profile" not in cols:
            op.add_column("acuarios", sa.Column("reef_profile", sa.String(50), nullable=True))
        if "dosing_method" not in cols:
            op.add_column("acuarios", sa.Column("dosing_method", sa.String(50), nullable=True))
        if "lighting_par" not in cols:
            op.add_column("acuarios", sa.Column("lighting_par", sa.Integer(), nullable=True))
        if "flow_profile" not in cols:
            op.add_column("acuarios", sa.Column("flow_profile", sa.String(50), nullable=True))

    # Columnas en measurements
    if "measurements" in table_names:
        cols = [c["name"] for c in inspector.get_columns("measurements")]
        json_type = postgresql.JSONB(astext_type=sa.Text()) if conn.dialect.name == "postgresql" else sa.JSON()

        meas_columns = [
            ("salinity", sa.Float()),
            ("ammonia", sa.Float()),
            ("nitrite", sa.Float()),
            ("kh", sa.Float()),
            ("calcium", sa.Float()),
            ("magnesium", sa.Float()),
            ("nitrate", sa.Float()),
            ("phosphate", sa.Float()),
            ("trace_elements", json_type),
            ("test_methods", json_type),
        ]
        for col_name, col_type in meas_columns:
            if col_name not in cols:
                op.add_column("measurements", sa.Column(col_name, col_type, nullable=True))

    # Columnas en mediciones
    if "mediciones" in table_names:
        cols = [c["name"] for c in inspector.get_columns("mediciones")]
        json_type = postgresql.JSONB(astext_type=sa.Text()) if conn.dialect.name == "postgresql" else sa.JSON()

        med_columns = [
            ("salinity", sa.Float()),
            ("ammonia", sa.Float()),
            ("nitrite", sa.Float()),
            ("kh", sa.Float()),
            ("calcium", sa.Float()),
            ("magnesium", sa.Float()),
            ("nitrate", sa.Float()),
            ("phosphate", sa.Float()),
            ("trace_elements", json_type),
            ("test_methods", json_type),
        ]
        for col_name, col_type in med_columns:
            if col_name not in cols:
                op.add_column("mediciones", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = inspector.get_table_names()

    if "tanks" in table_names:
        cols = [c["name"] for c in inspector.get_columns("tanks")]
        for col in ["reef_profile", "dosing_method", "lighting_par", "flow_profile"]:
            if col in cols:
                op.drop_column("tanks", col)

    if "measurements" in table_names:
        cols = [c["name"] for c in inspector.get_columns("measurements")]
        for col in ["salinity", "ammonia", "nitrite", "kh", "calcium", "magnesium", "nitrate", "phosphate", "trace_elements", "test_methods"]:
            if col in cols:
                op.drop_column("measurements", col)
