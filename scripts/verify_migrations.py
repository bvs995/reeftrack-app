"""Verifica las migraciones de Alembic contra una base PostgreSQL de PRUEBA.

Uso:
    DATABASE_URL=postgresql://... python scripts/verify_migrations.py [--roundtrip]

Pasos:
  1. Muestra la revisión actual y las tablas que ya existen.
  2. Ejecuta `alembic upgrade head`.
  3. Comprueba que cada columna de cada modelo exista en la base, que todas las
     tablas de public tengan RLS y que anon/authenticated no tengan permisos.
  4. Hace un SELECT con el ORM sobre cada modelo.
  5. Con --roundtrip: downgrade a base y upgrade de nuevo (BORRA TODAS LAS TABLAS).

Nunca imprime la cadena de conexión completa.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def main() -> int:
    roundtrip = "--roundtrip" in sys.argv
    url = (os.getenv("DATABASE_URL") or "").strip().strip("'\"")
    if not url.startswith(("postgres://", "postgresql")):
        print("DATABASE_URL debe apuntar a PostgreSQL.")
        return 2

    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine, inspect, select
    from sqlalchemy.orm import Session

    cfg = Config(str(ROOT / "alembic.ini"))  # env.py toma DATABASE_URL y la normaliza
    import backend.models as models
    from backend.database import Base

    def engine():
        return create_engine(cfg.get_main_option("sqlalchemy.url"))

    # env.py fija la URL al cargarse; forzamos esa carga con un comando inocuo.
    command.current(cfg)
    eng = engine()
    print(f"Servidor: {eng.url.host} / base: {eng.url.database}")

    with eng.connect() as conn:
        rev = MigrationContext.configure(conn).get_current_revision()
        tables = sorted(inspect(conn).get_table_names())
    print(f"Revisión actual: {rev or '(ninguna: sin tabla alembic_version)'}")
    print(f"Tablas existentes ({len(tables)}): {', '.join(tables) or '(vacía)'}")
    if rev is None and tables:
        print("\nAVISO: hay tablas pero ninguna revisión de Alembic. La migración inicial no es "
              "idempotente y fallará con 'already exists'. Usa una base vacía.")
        return 1

    print("\n== alembic upgrade head")
    command.upgrade(cfg, "head")

    def check() -> list[str]:
        problems = []
        with engine().connect() as conn:
            insp = inspect(conn)
            db_tables = set(insp.get_table_names())
            for table in Base.metadata.sorted_tables:
                if table.name not in db_tables:
                    problems.append(f"falta tabla {table.name}")
                    continue
                cols = {c["name"] for c in insp.get_columns(table.name)}
                problems += [f"falta columna {table.name}.{c.name}" for c in table.columns if c.name not in cols]
            # La API de Supabase no debe poder tocar ninguna tabla de public.
            rows = conn.exec_driver_sql(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity"
            ).all()
            problems += [f"RLS apagado en {r[0]}" for r in rows]
            rows = conn.exec_driver_sql(
                "SELECT DISTINCT grantee, table_name FROM information_schema.role_table_grants "
                "WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated')"
            ).all()
            problems += [f"{r[0]} tiene permisos sobre {r[1]}" for r in rows]
        with Session(engine()) as s:
            for mapper in Base.registry.mappers:
                try:
                    s.execute(select(mapper.class_).limit(1)).all()
                except Exception as e:  # noqa: BLE001
                    problems.append(f"SELECT {mapper.class_.__name__}: {type(e).__name__}: {str(e).splitlines()[0]}")
                    s.rollback()
        return problems

    problems = check()
    print("== esquema vs modelos:", "OK" if not problems else "")
    for p in problems:
        print("  -", p)
    if problems:
        return 1

    if roundtrip:
        print("\n== downgrade base + upgrade head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        problems = check()
        print("== tras roundtrip:", "OK" if not problems else problems)
        if problems:
            return 1

    print("\nTodo bien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
