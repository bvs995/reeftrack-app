"""Fija la contraseña de una cuenta directamente en la base, sin pasar por el correo.

Uso (la contraseña se pide oculta, nunca va en la línea de comandos):
    python scripts/set_password.py correo@ejemplo.com [--env-file ~/.aquatracker-pgtest]

Además de cambiar la contraseña:
  * marca el correo como verificado,
  * sube token_version y borra los refresh tokens (cierra sesiones abiertas),
  * marca como usados los enlaces de restablecimiento pendientes.
"""
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip("'\"")


def main() -> int:
    args = sys.argv[1:]
    if "--env-file" in args:
        i = args.index("--env-file")
        load_env_file(Path(args[i + 1]).expanduser())
        del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    email = args[0].strip().lower()

    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgres://", "postgresql")):
        print("DATABASE_URL debe apuntar a PostgreSQL (usa --env-file).")
        return 2

    import bcrypt
    import psycopg2
    from backend.models import check_password_complexity

    conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"), connect_timeout=15)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE lower(email) = %s", (email,))
    row = cur.fetchone()
    if not row:
        print(f"No existe una cuenta con el correo {email}.")
        return 1
    user_id = row[0]

    while True:
        pwd = getpass.getpass("Contraseña nueva (no se muestra): ")
        try:
            check_password_complexity(pwd)
        except Exception as e:  # noqa: BLE001
            print(f"  No cumple las reglas: {getattr(e, 'detail', e)}")
            continue
        if getpass.getpass("Repítela: ") != pwd:
            print("  No coinciden, intenta de nuevo.")
            continue
        break

    hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    cur.execute(
        "UPDATE users SET hashed_password = %s, email_verified = TRUE, is_active = TRUE, "
        "token_version = COALESCE(token_version, 1) + 1 WHERE id = %s",
        (hashed, user_id),
    )
    cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
    cur.execute("UPDATE password_reset_tokens SET used_at = now() WHERE user_id = %s AND used_at IS NULL", (user_id,))
    conn.commit()
    print(f"Listo: contraseña actualizada y correo verificado para {email}. Ya puedes iniciar sesión.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
