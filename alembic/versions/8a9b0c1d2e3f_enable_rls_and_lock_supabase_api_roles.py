"""enable_rls_and_lock_supabase_api_roles

La app autentica con su propio JWT y el backend se conecta como dueño de las tablas,
así que no usa la API de datos de Supabase (PostgREST). Para que esa API no exponga
nada con la anon key:

  * RLS activado SIN políticas en todas las tablas de public: para anon/authenticated
    no hay filas visibles ni escribibles. El dueño (el backend) no queda sujeto a RLS
    porque NO se usa FORCE ROW LEVEL SECURITY.
  * Se revocan todos los privilegios de anon y authenticated sobre tablas y secuencias
    de public, también los predeterminados para tablas futuras.

Solo actúa en PostgreSQL; en SQLite no hace nada. Las migraciones que creen tablas
nuevas deben activar RLS también (lo comprueba scripts/verify_migrations.py).

Revision ID: 8a9b0c1d2e3f
Revises: 7f8a9b0c1d2e
Create Date: 2026-11-25 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8a9b0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = '7f8a9b0c1d2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

API_ROLES = ("anon", "authenticated")


def _public_tables(conn) -> list[str]:
    rows = conn.execute(sa.text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    ))
    return [r[0] for r in rows]


def _existing_roles(conn) -> list[str]:
    rows = conn.execute(
        sa.text("SELECT rolname FROM pg_roles WHERE rolname = ANY(:names)"),
        {"names": list(API_ROLES)},
    )
    return [r[0] for r in rows]


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    for table in _public_tables(conn):
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')

    roles = _existing_roles(conn)
    if roles:
        who = ", ".join(roles)
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {who}")
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {who}")
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {who}")
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {who}")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    # Solo se apaga RLS; los privilegios revocados no se devuelven a propósito.
    for table in _public_tables(conn):
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
