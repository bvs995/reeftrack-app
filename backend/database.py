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
    # Optimización para Session/Transaction Pooler de Supabase (evita desconexiones por timeout de red)
    connect_args["keepalives"] = 1
    connect_args["keepalives_idle"] = 30
    connect_args["keepalives_interval"] = 10
    connect_args["keepalives_count"] = 5

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
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    disable_ddl = os.getenv("DISABLE_DEFENSIVE_DDL", "").strip().lower() in ("true", "1", "yes")

    if env == "production" or disable_ddl:
        logger.info("ℹ️ Entorno de producción detectado: DDL defensivo desactivado en init_db. El esquema es gestionado por Alembic.")
        return

    try:
        import backend.models  # Asegurar registro de modelos en metadata
        Base.metadata.create_all(bind=engine)
    except Exception as ddl_err:
        logger.info(f"Aviso durante create_all (posible creación concurrente por otro worker): {ddl_err}")

    # Ejecuta esto después de Base.metadata.create_all(bind=engine) para PostgreSQL
    if engine.dialect.name != "sqlite":
        with engine.connect() as conn:
            try:
                # Columnas de perfiles marinos en tanks y acuarios
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 1;"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE tanks ADD COLUMN IF NOT EXISTS reef_profile VARCHAR(50);"))
                conn.execute(text("ALTER TABLE tanks ADD COLUMN IF NOT EXISTS dosing_method VARCHAR(50);"))
                conn.execute(text("ALTER TABLE tanks ADD COLUMN IF NOT EXISTS lighting_par INTEGER;"))
                conn.execute(text("ALTER TABLE tanks ADD COLUMN IF NOT EXISTS flow_profile VARCHAR(50);"))

                conn.execute(text("ALTER TABLE acuarios ADD COLUMN IF NOT EXISTS reef_profile VARCHAR(50);"))
                conn.execute(text("ALTER TABLE acuarios ADD COLUMN IF NOT EXISTS dosing_method VARCHAR(50);"))
                conn.execute(text("ALTER TABLE acuarios ADD COLUMN IF NOT EXISTS lighting_par INTEGER;"))
                conn.execute(text("ALTER TABLE acuarios ADD COLUMN IF NOT EXISTS flow_profile VARCHAR(50);"))

                # Columnas en measurements y mediciones
                meas_alter_statements = [
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS salinity FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS temperature FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS temperatura FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS ph FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS ammonia FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS nitrite FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS kh FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS calcium FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS magnesium FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS nitrate FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS phosphate FLOAT;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS trace_elements JSONB;",
                    "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS test_methods JSONB;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS salinity FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS temperature FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS temperatura FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS ph FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS ammonia FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS nitrite FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS kh FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS calcium FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS magnesium FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS nitrate FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS phosphate FLOAT;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS trace_elements JSONB;",
                    "ALTER TABLE mediciones ADD COLUMN IF NOT EXISTS test_methods JSONB;",
                ]
                for stmt in meas_alter_statements:
                    conn.execute(text(stmt))

                # Columnas para maintenance_tasks
                maint_task_statements = [
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS task_key VARCHAR(50);",
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS title VARCHAR(120);",
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'mechanical';",
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS frequency_days INTEGER DEFAULT 7;",
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS last_completed_at TIMESTAMP WITH TIME ZONE;",
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS next_due_at TIMESTAMP WITH TIME ZONE;",
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS is_enabled BOOLEAN DEFAULT TRUE;",
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS notes TEXT;",
                    "ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();",
                    "ALTER TABLE maintenance_logs ADD COLUMN IF NOT EXISTS task_id INTEGER;",
                    "ALTER TABLE maintenance_logs ADD COLUMN IF NOT EXISTS aquarium_id INTEGER;",
                    "ALTER TABLE maintenance_logs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();",
                    "ALTER TABLE maintenance_logs ADD COLUMN IF NOT EXISTS linked_water_change_id INTEGER;",
                    "ALTER TABLE maintenance_logs ADD COLUMN IF NOT EXISTS notes TEXT;",
                    "ALTER TABLE water_changes ADD COLUMN IF NOT EXISTS tank_id INTEGER;",
                    "ALTER TABLE water_changes ADD COLUMN IF NOT EXISTS user_id INTEGER;",
                    "ALTER TABLE water_changes ADD COLUMN IF NOT EXISTS volume_liters FLOAT;",
                    "ALTER TABLE water_changes ADD COLUMN IF NOT EXISTS percentage FLOAT;",
                    "ALTER TABLE water_changes ADD COLUMN IF NOT EXISTS performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();",
                    "ALTER TABLE water_changes ADD COLUMN IF NOT EXISTS notes TEXT;",
                    "ALTER TABLE water_changes ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"
                ]
                for stmt in maint_task_statements:
                    try:
                        conn.execute(text(stmt))
                    except Exception:
                        pass

                # Tabla de suscripciones push (VAPID)
                try:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS push_subscriptions (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            endpoint TEXT NOT NULL UNIQUE,
                            p256dh VARCHAR(255) NOT NULL,
                            auth VARCHAR(255) NOT NULL,
                            user_agent VARCHAR(500),
                            notify_maintenance BOOLEAN DEFAULT TRUE,
                            notify_alerts BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                    """))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_push_subs_user_id ON push_subscriptions(user_id);"))
                except Exception as push_err:
                    logger.debug(f"Aviso creando tabla push_subscriptions: {push_err}")

                # Vistas de compatibilidad
                try:
                    conn.execute(text("CREATE OR REPLACE VIEW aquariums AS SELECT * FROM tanks;"))
                    conn.execute(text("CREATE OR REPLACE VIEW parameter_logs AS SELECT * FROM measurements;"))
                except Exception:
                    pass

                conn.commit()
            except Exception as e:
                logger.debug(f"Verificación de columnas directas: {e}")

    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        # Auto-migración compatible para tanks (SQLite fallback)
        if "tanks" in table_names:
            t_cols = [c["name"] for c in inspector.get_columns("tanks")]
            with engine.begin() as conn:
                if "reef_profile" not in t_cols:
                    conn.execute(text("ALTER TABLE tanks ADD COLUMN reef_profile VARCHAR(50);"))
                if "dosing_method" not in t_cols:
                    conn.execute(text("ALTER TABLE tanks ADD COLUMN dosing_method VARCHAR(50);"))
                if "lighting_par" not in t_cols:
                    conn.execute(text("ALTER TABLE tanks ADD COLUMN lighting_par INTEGER;"))
                if "flow_profile" not in t_cols:
                    conn.execute(text("ALTER TABLE tanks ADD COLUMN flow_profile VARCHAR(50);"))

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
                if "salinity" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN salinity FLOAT;"))
                if "ammonia" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN ammonia FLOAT;"))
                if "nitrite" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN nitrite FLOAT;"))
                if "kh" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN kh FLOAT;"))
                if "calcium" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN calcium FLOAT;"))
                if "magnesium" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN magnesium FLOAT;"))
                if "nitrate" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN nitrate FLOAT;"))
                if "phosphate" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN phosphate FLOAT;"))
                if "trace_elements" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN trace_elements JSON;"))
                if "test_methods" not in columns:
                    conn.execute(text("ALTER TABLE measurements ADD COLUMN test_methods JSON;"))

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
                if "token_version" not in user_columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 1;"))
                    logger.info("Auto-migración: Columna token_version añadida a users.")
                if "email_verified" not in user_columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;"))
                    logger.info("Auto-migración: Columna email_verified añadida a users.")

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
