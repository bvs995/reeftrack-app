"""
Módulo de Respaldo y Restauración Probada para AquaPulse (Fase 7 - Operación).
Soporta bases de datos PostgreSQL (Render/Supabase) y SQLite de desarrollo local.
Garantiza verificación de integridad comparando conteos de filas (COUNT(*)).
"""
import os
import sys
import sqlite3
import subprocess
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import create_engine, inspect, text

logger = logging.getLogger("aquapulse.backup")

TABLES_TO_VERIFY = [
    "users",
    "tanks",
    "measurements",
    "maintenance_tasks",
    "water_changes",
    "push_subscriptions",
    "diagnostic_feedback",
    "diagnostic_audits"
]


def is_postgres_url(url: str) -> bool:
    """Verifica si la URL corresponde a PostgreSQL."""
    return url.startswith("postgresql://") or url.startswith("postgres://")


def get_sqlite_path_from_url(url: str) -> str:
    """Extrae la ruta absoluta del archivo SQLite a partir de sqlite:///path."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return url


def create_database_backup(db_url: Optional[str] = None, output_file: Optional[str] = None) -> str:
    """
    Exporta un respaldo completo de la base de datos:
    - PostgreSQL: utiliza pg_dump (--schema=public --no-owner --no-acl).
    - SQLite: utiliza el protocolo nativo iterdump() para volcado SQL portable.
    """
    from backend.database import DATABASE_URL
    url = db_url or DATABASE_URL

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if not output_file:
        output_file = f"/tmp/aquapulse_backup_{timestamp}.sql"

    logger.info(f"Iniciando respaldo de base de datos hacia: {output_file}")

    if is_postgres_url(url):
        # Respaldo PostgreSQL mediante pg_dump
        cmd = [
            "pg_dump",
            url,
            "--schema=public",
            "--no-owner",
            "--no-acl",
            "-f", output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error ejecutando pg_dump: {result.stderr}")
    else:
        # Respaldo SQLite mediante iterdump
        sqlite_path = get_sqlite_path_from_url(url)
        if not os.path.isabs(sqlite_path):
            if os.path.exists(sqlite_path):
                sqlite_path = os.path.abspath(sqlite_path)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(base_dir)
                candidate1 = os.path.normpath(os.path.join(parent_dir, sqlite_path))
                candidate2 = os.path.normpath(os.path.join(base_dir, sqlite_path))
                if os.path.exists(candidate1):
                    sqlite_path = candidate1
                elif os.path.exists(candidate2):
                    sqlite_path = candidate2

        if not os.path.exists(sqlite_path):
            raise FileNotFoundError(f"Base de datos SQLite no encontrada en {sqlite_path}")

        con = sqlite3.connect(sqlite_path)
        with open(output_file, "w", encoding="utf-8") as f:
            for line in con.iterdump():
                f.write(f"{line}\n")
        con.close()

    if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
        raise RuntimeError("El archivo de respaldo no se generó o tiene tamaño 0 bytes.")

    logger.info(f"Respaldo generado con éxito ({os.path.getsize(output_file)} bytes).")
    return output_file


def restore_database_backup(backup_file: str, target_db_url: str) -> bool:
    """
    Restaura un respaldo SQL en una base de datos de destino.
    """
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Archivo de respaldo no encontrado: {backup_file}")

    logger.info(f"Iniciando restauración de {backup_file} en {target_db_url}")

    if is_postgres_url(target_db_url):
        cmd = [
            "psql",
            target_db_url,
            "-v", "ON_ERROR_STOP=1",
            "-f", backup_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error ejecutando psql: {result.stderr}")
    else:
        target_path = get_sqlite_path_from_url(target_db_url)
        con = sqlite3.connect(target_path)
        with open(backup_file, "r", encoding="utf-8") as f:
            sql_script = f.read()
        con.executescript(sql_script)
        con.close()

    logger.info("Restauración completada con éxito.")
    return True


def count_table_rows(db_url: str, table_name: str) -> Optional[int]:
    """Obtiene el conteo exacto de filas (COUNT(*)) de una tabla dada."""
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if table_name not in tables:
            return None
        with engine.connect() as conn:
            res = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            return int(res or 0)
    except Exception as e:
        logger.debug(f"Aviso contando filas de {table_name}: {e}")
        return None


def verify_backup_and_restore_parity(
    source_db_url: str,
    target_db_url: str,
    tables: Optional[list] = None
) -> Dict[str, Any]:
    """
    Comprueba paridad absoluta entre la base de datos original y la restaurada:
    Verifica que no se haya perdido ninguna fila en ninguna tabla crítica.
    """
    check_tables = tables or TABLES_TO_VERIFY
    comparison = {}
    is_parity = True

    for tbl in check_tables:
        src_count = count_table_rows(source_db_url, tbl)
        tgt_count = count_table_rows(target_db_url, tbl)

        matched = (src_count == tgt_count) and (src_count is not None)
        if not matched and src_count is not None:
            is_parity = False

        comparison[tbl] = {
            "source_rows": src_count,
            "restored_rows": tgt_count,
            "parity": matched
        }

    return {
        "is_parity": is_parity,
        "tables": comparison
    }
