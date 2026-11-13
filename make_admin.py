#!/usr/bin/env python3
"""
Script de Utilidad CLI - AquaPulse
Convierte un usuario existente en Administrador (is_admin = True)
o crea uno nuevo con privilegios administrativos.

Uso:
    python make_admin.py tu-correo@ejemplo.com
    o simplemente:
    python make_admin.py
"""

import sys
import os
from datetime import datetime

# Asegurar que el directorio raíz del proyecto esté en el PYTHONPATH
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database import get_db, init_db
from backend.models import User, Tank
from backend.auth import hash_password

def promote_or_create_admin(target_email: str):
    email = target_email.strip().lower()
    if not email or "@" not in email:
        print(f"❌ Error: '{email}' no parece ser un correo electrónico válido.")
        sys.exit(1)

    print(f"\n🌊 AquaPulse Admin Provisioner")
    print(f"================================")
    print(f"🔍 Buscando usuario con correo: {email} ...")

    # Inicializar tablas y auto-migrar si hiciera falta
    init_db()

    db = next(get_db())
    try:
        user = db.query(User).filter(User.email == email).first()

        if user:
            already_admin = getattr(user, "is_admin", False)
            user.is_admin = True
            user.is_active = True
            db.commit()
            db.refresh(user)

            if already_admin:
                print(f"ℹ️  El usuario {email} ya contaba con privilegios de Administrador.")
            else:
                print(f"✅ ¡Éxito! El usuario {email} ha sido promovido a ADMINISTRADOR (is_admin = True).")

            print(f"   • ID: {user.id}")
            print(f"   • Nombre: {user.full_name or '(Sin nombre)'}")
            print(f"   • Plan: {user.subscription_tier}")
            print(f"   • Administrador: {user.is_admin}")
            print(f"   • Estado: {'Activo' if user.is_active else 'Inactivo'}")
        else:
            print(f"⚠️  No se encontró ninguna cuenta registrada con: {email}")
            create_choice = input("¿Deseas crear esta cuenta como Administrador ahora mismo? (s/n): ").strip().lower()

            if create_choice in ["s", "si", "y", "yes"]:
                import getpass
                password = getpass.getpass("Ingresa una contraseña para la cuenta (mínimo 6 caracteres): ")
                while len(password) < 6:
                    print("La contraseña debe tener al menos 6 caracteres.")
                    password = getpass.getpass("Ingresa una contraseña válida: ")

                full_name = input("Nombre del Administrador (opcional, ej: Alex Valadez): ").strip() or "Administrador"

                new_admin = User(
                    email=email,
                    hashed_password=hash_password(password),
                    full_name=full_name,
                    unit_preference="liters",
                    subscription_tier="premium",
                    is_admin=True,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(new_admin)
                db.commit()
                db.refresh(new_admin)

                # Crear acuario principal para el nuevo admin
                admin_tank = Tank(
                    user_id=new_admin.id,
                    name="Acuario de Administración",
                    tank_type="reef",
                    volume_liters=300.0,
                    notes="Tanque de prueba del administrador"
                )
                db.add(admin_tank)
                db.commit()

                print(f"\n🎉 ¡Cuenta Administradora creada con éxito!")
                print(f"   • Correo: {new_admin.email}")
                print(f"   • Plan: Premium")
                print(f"   • is_admin: True")
            else:
                print("\nOperación cancelada. Puedes registrarte primero en la web y luego ejecutar este script.")
                # Mostrar usuarios existentes para referencia
                existing = db.query(User).all()
                if existing:
                    print("\nUsuarios registrados actualmente en la base de datos:")
                    for u in existing:
                        admin_badge = " [ADMIN]" if getattr(u, "is_admin", False) else ""
                        print(f"  - ID {u.id}: {u.email}{admin_badge} ({u.subscription_tier})")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_email = sys.argv[1]
    else:
        target_email = input("Ingresa el correo electrónico a convertir en Administrador: ")

    promote_or_create_admin(target_email)
