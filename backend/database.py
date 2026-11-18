import os
import logging
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger("aquapulse.database")

# Cargar variables de entorno locales si existen
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv()

# 1. Lectura obligatoria de DATABASE_URL sin fallback a SQLite
# Soporta DATEBASE_URL como alias defensivo por error tipográfico común
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATEBASE_URL")

# Si no está configurada la variable en el entorno, fallar de forma estricta y ruidosa
if not SQLALCHEMY_DATABASE_URL or not SQLALCHEMY_DATABASE_URL.strip():
    error_msg = (
        "🚨 ERROR CRÍTICO DE BASE DE DATOS: La variable de entorno DATABASE_URL no está configurada o está vacía.\n"
        "No existe ningún fallback a SQLite en producción. La aplicación requiere estrictamente "
        "la URL de conexión a PostgreSQL (Connection Pooler de Supabase en el puerto 6543 o 5432).\n"
        "Configura DATABASE_URL en el panel de Render con la URI Transaction Pooler de Supabase."
    )
    logger.critical(error_msg)
    raise ValueError(error_msg)

SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.strip().strip("'\"")

# Saneamiento automático de contraseñas con corchetes literales [password] o caracteres especiales (#, /, @)
import re
import urllib.parse

url_match = re.match(
    r"^(?P<proto>postgresql(?:\+[a-zA-Z0-9_]+)?://|postgres://)(?P<user>[^:]+):(?P<pass>.+?)@(?P<rest>[^@]+)$",
    SQLALCHEMY_DATABASE_URL
)
if url_match:
    proto = url_match.group("proto")
    user = url_match.group("user")
    pwd = url_match.group("pass")
    rest = url_match.group("rest")
    # Remover corchetes si fueron dejados literalmente desde el placeholder de documentación
    if pwd.startswith("[") and pwd.endswith("]"):
        pwd = pwd[1:-1]
    # Codificar caracteres especiales en la contraseña para no romper el parser URI
    pwd = urllib.parse.quote_plus(urllib.parse.unquote_plus(pwd))
    SQLALCHEMY_DATABASE_URL = f"{proto}{user}:{pwd}@{rest}"

# 2. Corrección crítica: SQLAlchemy exige 'postgresql://' pero algunos proveedores (como Render) entregan 'postgres://'
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Asegurar driver psycopg2 si no está disponible psycopg v3
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://") and not SQLALCHEMY_DATABASE_URL.startswith("postgresql+"):
    try:
        import psycopg
    except ImportError:
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

DATABASE_URL = SQLALCHEMY_DATABASE_URL

# 3. Conexión estricta a PostgreSQL (o SQLite solo si explícitamente se configuró en DATABASE_URL para tests)
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    logger.warning("⚠️ Usando base de datos SQLite según variable explícita DATABASE_URL.")
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()
else:
    logger.info("🐘 Conectando a base de datos PostgreSQL / Supabase Pooler en modo producción.")
    connect_args = {}
    if "sslmode" not in SQLALCHEMY_DATABASE_URL:
        connect_args["sslmode"] = "require"

    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        pool_pre_ping=True,
        pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "300")),
        pool_timeout=30,
        connect_args=connect_args
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator:
    """Generador de sesión SQLAlchemy con cierre garantizado."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Crea las tablas en la base de datos si aún no existen y migra columnas requeridas."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as ddl_err:
        logger.info(f"Aviso durante create_all (posible creación concurrente por otro worker): {ddl_err}")

    # Ejecuta esto después de Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            # Cambia 'parameter_logs' por el nombre real de tu tabla en __tablename__ (measurements y mediciones)
            conn.execute(text("ALTER TABLE measurements ADD COLUMN IF NOT EXISTS temperature FLOAT;"))
            conn.execute(text("ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS temperature FLOAT;"))
            conn.commit()
        except Exception as e:
            print(f"Verificación de columna temperature: {e}")

    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        # Auto-migración para measurements
        if "measurements" in table_names:
            columns = [c["name"] for c in inspector.get_columns("measurements")]
            with engine.begin() as conn:
                if "user_id" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN user_id INTEGER;"))
                    logger.info("Auto-migración: Columna user_id añadida a measurements.")
                if "tank_id" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN tank_id INTEGER;"))
                    logger.info("Auto-migración: Columna tank_id añadida a measurements.")
                if "ph" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN ph FLOAT;"))
                    logger.info("Auto-migración: Columna ph añadida a measurements.")
                if "temperature" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN temperature FLOAT;"))
                    logger.info("Auto-migración: Columna temperature añadida a measurements.")
                if "temperatura" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN temperatura FLOAT;"))
                    logger.info("Auto-migración: Columna temperatura añadida a measurements.")

        # Auto-migración para mediciones
        if "mediciones" in table_names:
            med_columns = [c["name"] for c in inspector.get_columns("mediciones")]
            with engine.begin() as conn:
                if "temperature" not in med_columns:
                    conn.execute(text("ALTER TABLE mediciones ADD COLUMN temperature FLOAT;"))
                    logger.info("Auto-migración: Columna temperature añadida a mediciones.")
                if "temperatura" not in med_columns:
                    conn.execute(text("ALTER TABLE mediciones ADD COLUMN temperatura FLOAT;"))
                    logger.info("Auto-migración: Columna temperatura añadida a mediciones.")

        # Auto-migración para users (campos requeridos con defaults seguros)
        if "users" in table_names:
            user_columns = [c["name"] for c in inspector.get_columns("users")]
            with engine.begin() as conn:
                if "is_admin" not in user_columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;"))
                    logger.info("Auto-migración: Columna is_admin añadida a users.")
                if "is_active" not in user_columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;"))
                    logger.info("Auto-migración: Columna is_active añadida a users.")
                if "unit_preference" not in user_columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN unit_preference VARCHAR(50) DEFAULT 'liters';"))
                    logger.info("Auto-migración: Columna unit_preference añadida a users.")
                if "subscription_tier" not in user_columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(50) DEFAULT 'free';"))
                    logger.info("Auto-migración: Columna subscription_tier añadida a users.")

                # Saneamiento de posibles valores nulos preexistentes para evitar IntegrityError
                try:
                    conn.execute(text("UPDATE users SET is_admin = FALSE WHERE is_admin IS NULL;"))
                    conn.execute(text("UPDATE users SET is_active = TRUE WHERE is_active IS NULL;"))
                    conn.execute(text("UPDATE users SET unit_preference = 'liters' WHERE unit_preference IS NULL;"))
                    conn.execute(text("UPDATE users SET subscription_tier = 'free' WHERE subscription_tier IS NULL;"))
                except Exception as sanitize_err:
                    logger.debug(f"Aviso en saneamiento users: {sanitize_err}")

        # Sincronización y consistencia bidireccional entre tanks/measurements y acuarios/mediciones
        if "acuarios" in table_names and "tanks" in table_names:
            with engine.begin() as conn:
                try:
                    if engine.dialect.name == "sqlite":
                        conn.execute(text("""
                            INSERT OR IGNORE INTO acuarios (id, nombre, volumen_litros, usuario_id, creado_en)
                            SELECT id, name, volume_liters, CAST(user_id AS TEXT), created_at FROM tanks;
                        """))
                        conn.execute(text("""
                            INSERT OR IGNORE INTO mediciones (id, acuario_id, ph, kh, calcio, magnesio, nitrato, fosfato, temperatura, fecha_registro)
                            SELECT id, tank_id, ph, alkalinity_dkh, calcium_ppm, magnesium_ppm, nitrate_ppm, phosphate_ppm, temperatura, timestamp 
                            FROM measurements WHERE tank_id IN (SELECT id FROM acuarios);
                        """))
                    else:
                        conn.execute(text("""
                            INSERT INTO acuarios (id, nombre, volumen_litros, usuario_id, creado_en)
                            SELECT id, name, volume_liters, CAST(user_id AS TEXT), created_at FROM tanks
                            ON CONFLICT (id) DO NOTHING;
                        """))
                        conn.execute(text("""
                            INSERT INTO mediciones (id, acuario_id, ph, kh, calcio, magnesio, nitrato, fosfato, temperatura, fecha_registro)
                            SELECT id, tank_id, ph, alkalinity_dkh, calcium_ppm, magnesium_ppm, nitrate_ppm, phosphate_ppm, temperatura, timestamp 
                            FROM measurements WHERE tank_id IN (SELECT id FROM acuarios)
                            ON CONFLICT (id) DO NOTHING;
                        """))
                except Exception as sync_err:
                    logger.debug(f"Aviso en sincronización inicial acuarios/mediciones: {sync_err}")
    except Exception as e:
        logger.warning(f"Aviso durante auto-migración de tablas: {e}")

def check_db_connection() -> bool:
    """Verifica si la base de datos está alcanzable para health checks."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Error verificando conexión a base de datos: {e}")
        return False
