"""
Configuración común de pytest para AquaReef.

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

# 5. Nunca se llama a Gemini real desde las pruebas (ni se gasta con tu clave de desarrollo).
#    Las pruebas que necesitan una clave "presente" la fijan con patch.dict.
os.environ["GEMINI_API_KEY"] = ""

# 6b. Resolución de IP del cliente sin proxies de confianza salvo loopback, sea cual sea el .env
#     de desarrollo (allí suele estar FORWARDED_ALLOW_IPS=*). Las pruebas de IP los fijan aparte.
os.environ["FORWARDED_ALLOW_IPS"] = "127.0.0.1,::1"
os.environ["TRUSTED_PROXY_HOPS"] = "0"
os.environ["PROXY_SHARED_SECRET"] = ""

# 6. PWA mínima y propia de las pruebas: frontend/dist no está en git, así que sin esto
#    las rutas de la SPA solo existirían en máquinas donde alguien compiló el frontend.
import tempfile
from pathlib import Path

_dist = Path(tempfile.mkdtemp(prefix="aquapulse-dist-"))
(_dist / "assets").mkdir()
(_dist / "index.html").write_text("<!doctype html><title>AquaReef test</title>", encoding="utf-8")
os.environ["FRONTEND_DIST_DIR"] = str(_dist)
