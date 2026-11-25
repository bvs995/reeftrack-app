"""
Configuración común de pytest para AquaPulse.

Los módulos de la app llaman a load_dotenv() al importarse, y load_dotenv NO pisa las
variables que ya existen en el entorno. Fijarlas aquí, antes de importar la app, hace que
las pruebas sean independientes de tu backend/.env de desarrollo (verificación de correo
obligatoria, proveedor real de correo, base de datos de Supabase, etc.).

Las pruebas que necesitan otro valor lo fijan por su cuenta con patch.dict(os.environ, ...).
"""
import os

# 1. Las cuentas de prueba no pasan por verificación de correo salvo que la prueba lo pida.
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"

# 2. Nunca se envían correos reales ni se usa la clave de Resend desde las pruebas.
os.environ["EMAIL_PROVIDER"] = "mock"
os.environ["EMAIL_API_KEY"] = ""

# 3. Nunca se corren las pruebas contra una base que no sea SQLite local.
_db_url = os.environ.get("DATABASE_URL", "")
if not _db_url.startswith("sqlite"):
    os.environ["DATABASE_URL"] = "sqlite:///./test_pytest.db"

# 4. Clave de firma solo para pruebas si no se definió una.
os.environ.setdefault("SECRET_KEY", "clave-solo-para-pruebas-automaticas-no-usar-en-produccion")
