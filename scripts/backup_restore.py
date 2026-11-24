#!/usr/bin/env python3
"""
Script CLI para operaciones: Generar respaldo, restaurar y probar paridad de BD (Fase 7).
Uso:
  python scripts/backup_restore.py --backup
  python scripts/backup_restore.py --test-restore
"""
import os
import sys
import argparse

# Asegurar path para importar backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.backup import (
    create_database_backup,
    restore_database_backup,
    verify_backup_and_restore_parity
)
from backend.database import DATABASE_URL


def main():
    parser = argparse.ArgumentParser(description="AquaPulse Backup & Restore CLI")
    parser.add_argument("--backup", action="store_true", help="Generar respaldo SQL de la base de datos actual")
    parser.add_argument("--output", type=str, default=None, help="Ruta del archivo de salida")
    parser.add_argument("--test-restore", action="store_true", help="Probar ciclo completo de respaldo y restauración en BD temporal")

    args = parser.parse_args()

    if args.test_restore:
        print("🔄 [FASE 7] Ejecutando prueba de ciclo de vida completo: Respaldo -> Restauración -> Paridad...")
        backup_path = "/tmp/aquapulse_test_backup.sql"
        temp_target_db = "/tmp/aquapulse_test_restored.db"

        if os.path.exists(temp_target_db):
            os.remove(temp_target_db)

        # 1. Crear respaldo
        file_path = create_database_backup(db_url=DATABASE_URL, output_file=backup_path)
        print(f"✅ Respaldo creado: {file_path} ({os.path.getsize(file_path)} bytes)")

        # 2. Restaurar en destino temporal
        restore_target_url = f"sqlite:///{temp_target_db}"
        restore_database_backup(file_path, restore_target_url)
        print(f"✅ Restauración completada en: {restore_target_url}")

        # 3. Comprobar paridad
        res = verify_backup_and_restore_parity(DATABASE_URL, restore_target_url)
        print("\n📊 Tabla Comparativa de Integridad:")
        print(f"{'Tabla':<25} | {'Origen':<10} | {'Restaurado':<10} | {'Paridad'}")
        print("-" * 65)
        for tbl, data in res["tables"].items():
            if data["source_rows"] is not None:
                print(f"{tbl:<25} | {str(data['source_rows']):<10} | {str(data['restored_rows']):<10} | {'✅ OK' if data['parity'] else '❌ DISCREPANCIA'}")

        # 4. Limpieza
        if os.path.exists(backup_path):
            os.remove(backup_path)
        if os.path.exists(temp_target_db):
            os.remove(temp_target_db)

        if res["is_parity"]:
            print("\n🎉 Prueba de respaldo y restauración superada: 100% de paridad e integridad garantizada.")
            sys.exit(0)
        else:
            print("\n❌ Error: Se detectaron discrepancias en el conteo de filas.")
            sys.exit(1)

    elif args.backup:
        out = create_database_backup(db_url=DATABASE_URL, output_file=args.output)
        print(f"✅ Respaldo generado con éxito en: {out}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
