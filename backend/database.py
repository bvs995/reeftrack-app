import os
import logging
from typing import Generator
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger("aquapulse.database")

# Obtener URL de conexión desde variables de entorno
DATABASE_URL = os.environ.get("DATABASE_URL")

# Manejo de compatibilidad con proveedores cloud (Render, Supabase, Heroku, Neon)
# que asignan 'postgres://' o 'postgresql://' sin especificar el driver psycopg2
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    
    # Configuración de producción para PostgreSQL
    if "postgresql" in DATABASE_URL:
        logger.info("🐘 Conectando a base de datos PostgreSQL en modo producción.")
        engine = create_engine(
            DATABASE_URL,
            pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
            max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "20")),
            pool_pre_ping=True,      # Verifica conexión antes de consulta, previene socket timeouts
            pool_recycle=300         # Recicla conexiones cada 5 minutos
        )
    else:
        # URL explícita de otro tipo (ej: sqlite:///...)
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
        )
else:
    # Modo desarrollo local: persistencia en SQLite
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.environ.get("AQUATRACKER_DB", os.path.join(BASE_DIR, "aquatracker.db"))
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    logger.info(f"💾 Modo desarrollo: Usando SQLite local en {DB_PATH}")
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
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
