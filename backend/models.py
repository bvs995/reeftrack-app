import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, model_validator
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text, Boolean, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, synonym
from backend.database import Base

PASSWORD_REGEX = r"^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]).{8,}$"
PASSWORD_REQUIREMENTS_ERROR = (
    "La contraseña debe tener al menos 8 caracteres, incluir al menos una letra mayúscula, "
    "un número y un carácter especial (!@#$%^&* etc.)."
)

def check_password_complexity(password: str) -> None:
    """Valida los requisitos estrictos de complejidad para contraseñas usando Regex."""
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
    if not re.search(r"\d", password):
        raise ValueError("La contraseña debe incluir al menos un número.")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        raise ValueError("La contraseña debe incluir al menos un carácter especial (!@#$%^&* etc.).")

# ==============================================================================
# MODELOS SQLALCHEMY ORM (Multi-usuario y Aislamiento en PostgreSQL / SQLite)
# ==============================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    unit_preference = Column(String(50), default="liters", nullable=False) # 'liters' o 'gallons'
    subscription_tier = Column(String(50), default="free", nullable=False) # 'free', 'premium'
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones estrictas por usuario
    tanks = relationship("Tank", back_populates="owner", cascade="all, delete-orphan")
    measurements = relationship("Measurement", back_populates="user", cascade="all, delete-orphan")
    maintenance_tasks = relationship("MaintenanceTask", back_populates="user", cascade="all, delete-orphan")
    water_changes = relationship("WaterChange", back_populates="user", cascade="all, delete-orphan")
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")


class Tank(Base):
    __tablename__ = "tanks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    tank_type = Column(String(50), default="reef", nullable=False) # 'reef', 'freshwater_planted', 'freshwater_community'
    volume_liters = Column(Float, default=280.0, nullable=False)
    reef_profile = Column(String(50), nullable=True) # "fish_only", "soft_reef", "lps_reef", "mixed_reef", "sps_reef"
    dosing_method = Column(String(50), nullable=True) # "water_changes", "manual_dosing", "peristaltic_balling", "kalkwasser", "calcium_reactor"
    lighting_par = Column(Integer, nullable=True) # PAR
    flow_profile = Column(String(50), nullable=True) # "low_moderate", "moderate_indirect", "high_turbulent"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Sinónimos para compatibilidad bilingüe
    nombre = synonym("name")
    volumen = synonym("volume_liters")
    tipo = synonym("tank_type")

    owner = relationship("User", back_populates="tanks")
    measurements = relationship("Measurement", back_populates="tank", cascade="all, delete-orphan")
    maintenance_tasks = relationship("MaintenanceTask", back_populates="tank", cascade="all, delete-orphan")
    water_changes = relationship("WaterChange", back_populates="tank", cascade="all, delete-orphan")

# Alias para compatibilidad
Aquarium = Tank


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    tank_id = Column(Integer, ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ph = Column(Float, nullable=True)
    alkalinity_dkh = Column(Float, nullable=True)
    kh = Column(Float, nullable=True)
    calcium_ppm = Column(Float, nullable=True)
    calcium = Column(Float, nullable=True)
    magnesium_ppm = Column(Float, nullable=True)
    magnesium = Column(Float, nullable=True)
    nitrate_ppm = Column(Float, nullable=True)
    nitrate = Column(Float, nullable=True)
    phosphate_ppm = Column(Float, nullable=True)
    phosphate = Column(Float, nullable=True)
    salinity_ppt = Column(Float, nullable=True)
    salinity = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    temperatura = Column(Float, nullable=True)
    ammonia = Column(Float, nullable=True)
    nitrite = Column(Float, nullable=True)
    trace_elements = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    test_methods = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    notes = Column(Text, nullable=True)
    kit = Column(String(100), nullable=True)
    is_camera_scan = Column(Boolean, default=False, nullable=True)
    is_draft = Column(Boolean, default=False, nullable=True)
    client_uuid = Column(String(100), unique=True, nullable=True, index=True)

    # Sinónimos para consultas nativas en español (MedicionAcuario)
    acuario_id = synonym("tank_id")
    fecha_registro = synonym("timestamp")
    calcio = synonym("calcium")
    magnesio = synonym("magnesium")
    nitrato = synonym("nitrate")
    fosfato = synonym("phosphate")
    temperature_c = synonym("temperature")

    user = relationship("User", back_populates="measurements")
    tank = relationship("Tank", back_populates="measurements")
    acuario = synonym("tank")

# Alias canónico de tabla
ParameterLog = Measurement


class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    aquarium_id = Column(Integer, ForeignKey("tanks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_key = Column(String(50), nullable=True) # "glass_cleaning", "mechanical_filter", "skimmer_cup", "carbon_gfo", "pumps_cleaning", "skimmer_body", "doser_probes", "custom"
    title = Column(String(120), nullable=False)
    category = Column(String(50), default="mechanical", nullable=False) # "mechanical", "equipment", "chemical", "calibration"
    frequency_days = Column(Integer, nullable=False, default=7)
    last_completed_at = Column(DateTime(timezone=True), nullable=True)
    next_due_at = Column(DateTime(timezone=True), nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now())

    # Sinónimos para interoperabilidad
    tank_id = synonym("aquarium_id")

    user = relationship("User", back_populates="maintenance_tasks")
    tank = relationship("Tank", back_populates="maintenance_tasks")
    logs = relationship("MaintenanceLog", back_populates="task", cascade="all, delete-orphan")


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    aquarium_id = Column(Integer, nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now())
    linked_water_change_id = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    task = relationship("MaintenanceTask", back_populates="logs")


class WaterChange(Base):
    __tablename__ = "water_changes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tank_id = Column(Integer, ForeignKey("tanks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    volume_liters = Column(Float, nullable=False)
    percentage = Column(Float, nullable=True)
    performed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now())

    aquarium_id = synonym("tank_id")

    user = relationship("User", back_populates="water_changes")
    tank = relationship("Tank", back_populates="water_changes")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(Text, unique=True, nullable=False)
    p256dh = Column(String(255), nullable=False)
    auth = Column(String(255), nullable=False)
    user_agent = Column(String(500), nullable=True)
    notify_maintenance = Column(Boolean, default=True, nullable=False)
    notify_alerts = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="push_subscriptions")


class DiagnosticFeedback(Base):
    __tablename__ = "diagnostic_feedback"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tank_id = Column(Integer, ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True)
    diagnosis_summary = Column(Text, nullable=True)
    severity = Column(String(50), nullable=True)
    user_comment = Column(Text, nullable=False)
    category = Column(String(50), default="incorrect_diagnosis", nullable=False)
    consent_given = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False)

    user = relationship("User")
    tank = relationship("Tank")


class DiagnosticAudit(Base):
    """
    Auditoría por diagnóstico (Fase 7):
    Registra versión de prompt, entradas, alertas de reglas, salida cruda,
    motivo de rechazo, costo y tokens consumidos.
    """
    __tablename__ = "diagnostic_audits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tank_id = Column(Integer, ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True)
    prompt_version = Column(String(50), default="v1", nullable=False)
    inputs = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    rules_alerts = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    raw_ai_output = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, index=True)  # accepted, sanitized, discarded, fallback, budget_exceeded
    rejection_reason = Column(Text, nullable=True)
    cost_usd = Column(Float, default=0.0, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False, index=True)

    user = relationship("User")
    tank = relationship("Tank")


# ==============================================================================
# MODELOS SQLALCHEMY ORM OFICIALES EN ESPAÑOL (acuarios y mediciones)
# ==============================================================================

class Acuario(Base):
    __tablename__ = "acuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    volumen_litros = Column(Float, nullable=False)
    usuario_id = Column(String(100), nullable=False, default="1", index=True)
    reef_profile = Column(String(50), nullable=True)
    dosing_method = Column(String(50), nullable=True)
    lighting_par = Column(Integer, nullable=True)
    flow_profile = Column(String(50), nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    # Sinónimos para interoperabilidad total
    volumen = synonym("volumen_litros")
    name = synonym("nombre")
    volume_liters = synonym("volumen_litros")
    user_id = synonym("usuario_id")
    created_at = synonym("creado_en")

    mediciones = relationship("MedicionAcuario", back_populates="acuario", cascade="all, delete-orphan")


class MedicionAcuario(Base):
    __tablename__ = "mediciones"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    acuario_id = Column(Integer, ForeignKey("acuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    ph = Column(Float, nullable=True)
    kh = Column(Float, nullable=True)
    calcio = Column(Float, nullable=True)
    calcium = Column(Float, nullable=True)
    magnesio = Column(Float, nullable=True)
    magnesium = Column(Float, nullable=True)
    nitrato = Column(Float, nullable=True)
    nitrate = Column(Float, nullable=True)
    fosfato = Column(Float, nullable=True)
    phosphate = Column(Float, nullable=True)
    salinity = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    temperatura = Column(Float, nullable=True)
    ammonia = Column(Float, nullable=True)
    nitrite = Column(Float, nullable=True)
    trace_elements = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    test_methods = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    fecha_registro = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False, index=True)

    # Sinónimos para interoperabilidad total
    tank_id = synonym("acuario_id")
    alkalinity_dkh = synonym("kh")
    calcium_ppm = synonym("calcio")
    magnesium_ppm = synonym("magnesio")
    nitrate_ppm = synonym("nitrato")
    phosphate_ppm = synonym("fosfato")
    temperature_c = synonym("temperature")
    timestamp = synonym("fecha_registro")

    acuario = relationship("Acuario", back_populates="mediciones")
    tank = synonym("acuario")

# Alias canónicos para modelos de base de datos
Medicion = MedicionAcuario


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - AUTENTICACIÓN Y USUARIOS
# ==============================================================================

class UserRegister(BaseModel):
    email: str = Field(..., max_length=255, example="acuarista@reef.com", description="Correo electrónico del usuario")
    password: str = Field(
        ...,
        max_length=128,
        example="PasswordSeguro123!",
        description="Contraseña estricta: mínimo 8 caracteres, 1 mayúscula, 1 número y 1 carácter especial"
    )
    full_name: Optional[str] = Field(None, max_length=100, example="Alex Valadez", description="Nombre del acuarista")

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        check_password_complexity(v)
        return v

class UserLogin(BaseModel):
    email: str = Field(..., max_length=255, example="acuarista@reef.com")
    password: str = Field(..., max_length=128, example="PasswordSeguro123")

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=255, example="acuarista@reef.com", description="Correo para restablecer contraseña")

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., max_length=512, description="Token seguro de restablecimiento")
    new_password: str = Field(
        ...,
        max_length=128,
        example="NuevaPassSegura2026!",
        description="Nueva contraseña estricta (mínimo 8 caracteres, 1 mayúscula, 1 número y 1 carácter especial)"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, v: str) -> str:
        check_password_complexity(v)
        return v

class PasswordResetResponse(BaseModel):
    ok: bool = True
    message: str
    reset_url_dev: Optional[str] = None
    reset_token_dev: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    unit_preference: Optional[str] = Field(None, pattern="^(liters|gallons)$", description="'liters' o 'gallons'")

    model_config = ConfigDict(extra="forbid")

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    unit_preference: str = "liters"
    subscription_tier: str = "free"
    is_admin: bool = False
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AdminUserUpdate(BaseModel):
    subscription_tier: Optional[str] = Field(None, pattern="^(free|premium)$", description="'free' o 'premium'")
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    full_name: Optional[str] = Field(None, max_length=100)

    model_config = ConfigDict(extra="forbid")

class AdminUserListItem(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    unit_preference: str = "liters"
    subscription_tier: str = "free"
    is_admin: bool = False
    is_active: bool = True
    tank_count: int = 0
    measurement_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    user: UserResponse


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - ACUARIOS (TANKS)
# ==============================================================================

def normalize_tank_type_value(raw: Any) -> str:
    """Normaliza cualquier biotipo o sinónimo a una de las 6 opciones maestras."""
    if not raw:
        return "lps_reef"
    k = str(raw).lower().strip()
    mapping = {
        "freshwater": "freshwater",
        "dulce": "freshwater",
        "freshwater_community": "freshwater",
        "planted": "planted",
        "plantado": "planted",
        "freshwater_planted": "planted",
        "fish_only": "fish_only",
        "marine_fish": "fish_only",
        "peces_marinos": "fish_only",
        "peces": "fish_only",
        "fowlr": "fish_only",
        "fowlr_soft": "fish_only",
        "mixed_reef": "mixed_reef",
        "mixed": "mixed_reef",
        "mixto": "mixed_reef",
        "sps_reef": "sps_reef",
        "sps": "sps_reef",
        "lps_reef": "lps_reef",
        "lps": "lps_reef",
        "arrecife": "lps_reef",
        "reef": "lps_reef",
        "soft_reef": "lps_reef",
        "soft": "lps_reef"
    }
    return mapping.get(k, "lps_reef")

class AquariumCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Nombre del acuario")
    volume_liters: float = Field(..., gt=0, le=100000.0, description="Volumen en litros")
    tank_type: str = Field(
        default="lps_reef", max_length=50, description="Biotipo del acuario: freshwater, planted, fish_only, mixed_reef, lps_reef, sps_reef"
    )
    reef_profile: Optional[str] = Field(None, max_length=50, description="Perfil marino: fish_only, mixed_reef, lps_reef, sps_reef")
    dosing_method: Optional[str] = Field(None, max_length=50, description="Método de dosificación: water_changes, manual_dosing, peristaltic_balling, kalkwasser, calcium_reactor")
    lighting_par: Optional[int] = Field(None, ge=0, le=2000, description="Intensidad lumínica estimada o medida en PAR")
    flow_profile: Optional[str] = Field(None, max_length=50, description="Perfil de flujo: low_moderate, moderate_indirect, high_turbulent")
    notes: Optional[str] = Field(None, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def handle_type_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw_type = data.pop("type", None) or data.get("tank_type")
            norm_type = normalize_tank_type_value(raw_type)
            data["tank_type"] = norm_type
            if norm_type in ["fish_only", "mixed_reef", "lps_reef", "sps_reef"]:
                data["reef_profile"] = norm_type
            else:
                data["reef_profile"] = None
        return data

    @property
    def type(self) -> str:
        return self.tank_type

class TankCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="Arrecife Mixto SPS/LPS")
    tank_type: str = Field(
        default="lps_reef", max_length=50, description="Biotipo del acuario: freshwater, planted, fish_only, mixed_reef, lps_reef, sps_reef"
    )
    volume_liters: float = Field(280.0, gt=0, le=100000.0, example=280.0)
    reef_profile: Optional[str] = Field(None, max_length=50, description="Perfil marino: fish_only, mixed_reef, lps_reef, sps_reef")
    dosing_method: Optional[str] = Field(None, max_length=50, description="Método de dosificación")
    lighting_par: Optional[int] = Field(None, ge=0, le=2000, description="Intensidad lumínica PAR")
    flow_profile: Optional[str] = Field(None, max_length=50, description="Perfil de flujo")
    notes: Optional[str] = Field(None, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def handle_type_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw_type = data.pop("type", None) or data.get("tank_type")
            norm_type = normalize_tank_type_value(raw_type)
            data["tank_type"] = norm_type
            if norm_type in ["fish_only", "mixed_reef", "lps_reef", "sps_reef"]:
                data["reef_profile"] = norm_type
            else:
                data["reef_profile"] = None
        return data

class TankUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tank_type: Optional[str] = Field(None, max_length=50)
    volume_liters: Optional[float] = Field(None, gt=0, le=100000.0)
    reef_profile: Optional[str] = Field(None, max_length=50)
    dosing_method: Optional[str] = Field(None, max_length=50)
    lighting_par: Optional[int] = Field(None, ge=0, le=2000)
    flow_profile: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def handle_type_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "type" in data:
                raw_type = data.pop("type")
                if raw_type:
                    data["tank_type"] = normalize_tank_type_value(raw_type)
        return data

class AquariumUpdate(TankUpdate):
    pass
    
class TankResponse(BaseModel):
    id: int
    user_id: int
    name: str
    tank_type: str
    volume_liters: float
    reef_profile: Optional[str] = None
    dosing_method: Optional[str] = None
    lighting_par: Optional[int] = None
    flow_profile: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AquariumResponse(TankResponse):
    pass


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - MEDICIONES (MEASUREMENTS / PARAMETERS)
# ==============================================================================

class MeasurementBase(BaseModel):
    tank_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    ph: Optional[float] = Field(None, ge=4.0, le=10.0, example=8.2, description="Nivel de pH (4.0 - 10.0)")
    alkalinity_dkh: Optional[float] = Field(None, ge=0.0, le=25.0, example=8.2, description="Alcalinidad en dKH (0 - 25)")
    kh: Optional[float] = Field(None, ge=0.0, le=25.0, example=8.2, description="Alcalinidad en dKH (alias)")
    calcium_ppm: Optional[float] = Field(None, ge=0.0, le=1000.0, example=420.0, description="Calcio en ppm (0 - 1000)")
    calcium: Optional[float] = Field(None, ge=0.0, le=1000.0, example=420.0, description="Calcio en ppm (alias)")
    calcio: Optional[float] = Field(None, ge=0.0, le=1000.0, example=420.0, description="Calcio en ppm (alias es)")
    magnesium_ppm: Optional[float] = Field(None, ge=0.0, le=2500.0, example=1350.0, description="Magnesio en ppm (0 - 2500)")
    magnesium: Optional[float] = Field(None, ge=0.0, le=2500.0, example=1350.0, description="Magnesio en ppm (alias)")
    magnesio: Optional[float] = Field(None, ge=0.0, le=2500.0, example=1350.0, description="Magnesio en ppm (alias es)")
    nitrate_ppm: Optional[float] = Field(None, ge=0.0, le=200.0, example=5.0, description="Nitrato (NO3) en ppm (0 - 200)")
    nitrate: Optional[float] = Field(None, ge=0.0, le=200.0, example=5.0, description="Nitrato (NO3) en ppm (alias)")
    nitrato: Optional[float] = Field(None, ge=0.0, le=200.0, example=5.0, description="Nitrato (NO3) en ppm (alias es)")
    phosphate_ppm: Optional[float] = Field(None, ge=0.0, le=10.0, example=0.04, description="Fosfato (PO4) en ppm (0 - 10)")
    phosphate: Optional[float] = Field(None, ge=0.0, le=10.0, example=0.04, description="Fosfato (PO4) en ppm (alias)")
    fosfato: Optional[float] = Field(None, ge=0.0, le=10.0, example=0.04, description="Fosfato (PO4) en ppm (alias es)")
    salinity_ppt: Optional[float] = Field(None, ge=0.0, le=60.0, example=35.0, description="Salinidad en ppt o Gravedad Específica")
    salinity: Optional[float] = Field(None, ge=0.0, le=60.0, example=1.025, description="Salinidad en SG o ppt (alias)")
    temperature: Optional[float] = Field(None, ge=10.0, le=40.0, example=25.5, description="Temperatura en °C (10.0 a 40.0 °C)")
    temperatura: Optional[float] = Field(None, ge=10.0, le=40.0, example=25.5, description="Temperatura en °C")
    ammonia_ppm: Optional[float] = Field(None, ge=0.0, le=20.0, example=0.0, description="Amoníaco en ppm (0 - 20)")
    ammonia: Optional[float] = Field(None, ge=0.0, le=20.0, example=0.0, description="Amoníaco en ppm (alias)")
    nitrite_ppm: Optional[float] = Field(None, ge=0.0, le=20.0, example=0.0, description="Nitrito en ppm (0 - 20)")
    nitrite: Optional[float] = Field(None, ge=0.0, le=20.0, example=0.0, description="Nitrito en ppm (alias)")
    gh_dgh: Optional[float] = Field(None, ge=0.0, le=50.0, example=6.0, description="Dureza General GH (0 - 50)")

    trace_elements: Optional[Dict[str, Optional[float]]] = Field(None, description="Elementos traza (k, sr, i, fe)")
    test_methods: Optional[Dict[str, Optional[str]]] = Field(None, description="Métodos de test (ej: {'po4': 'photometer_ulr', 'kh': 'drop_kit'})")
    notes: Optional[str] = Field(None, max_length=1000, example="Test Hanna Checker HI772", description="Notas o kit de test")
    kit: Optional[str] = Field(None, max_length=100, example="hanna", description="Kit de medición utilizado (ej: hanna, salifert, red_sea)")
    is_camera_scan: Optional[bool] = Field(False, description="Indica si la medición provino del escáner de cámara IA")
    is_draft: Optional[bool] = Field(False, description="Indica si la medición es un borrador no confirmado")
    client_uuid: Optional[str] = Field(None, max_length=100, description="Identificador único idempotente para sincronización offline PWA")

    # Campos de compatibilidad con entrada rápida Numpad
    parameter_code: Optional[str] = Field(None, max_length=50, description="Código de parámetro rápido")
    value: Optional[float] = Field(None, description="Valor numérico de la medición individual")
    measured_at: Optional[datetime] = Field(None, description="Timestamp alternativo de medición")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def map_parameter_code_if_present(self):
        """Sincroniza y mapea automáticamente nombres canónicos y alias de parámetros."""
        code_map = {
            "ph": "ph",
            "dkh": "kh",
            "alkalinity": "kh",
            "alkalinity_dkh": "kh",
            "kh": "kh",
            "ca": "calcium",
            "calcium": "calcium",
            "calcium_ppm": "calcium",
            "mg": "magnesium",
            "magnesium": "magnesium",
            "magnesium_ppm": "magnesium",
            "no3": "nitrate",
            "nitrate": "nitrate",
            "nitrate_ppm": "nitrate",
            "po4": "phosphate",
            "phosphate": "phosphate",
            "phosphate_ppm": "phosphate",
            "salinity": "salinity",
            "salinity_ppt": "salinity",
            "ammonia": "ammonia",
            "ammonia_ppm": "ammonia",
            "nitrite": "nitrite",
            "nitrite_ppm": "nitrite",
            "temp": "temperature",
            "temperatura": "temperature",
            "temperature": "temperature",
        }
        if self.parameter_code and self.value is not None:
            field_name = code_map.get(str(self.parameter_code).lower().strip())
            if field_name:
                setattr(self, field_name, self.value)

        # Sincronización bidireccional estricta
        if self.kh is not None and self.alkalinity_dkh is None:
            self.alkalinity_dkh = self.kh
        elif self.alkalinity_dkh is not None and self.kh is None:
            self.kh = self.alkalinity_dkh

        if self.calcium is not None and self.calcium_ppm is None:
            self.calcium_ppm = self.calcium
        elif self.calcium_ppm is not None and self.calcium is None:
            self.calcium = self.calcium_ppm

        if self.magnesium is not None and self.magnesium_ppm is None:
            self.magnesium_ppm = self.magnesium
        elif self.magnesium_ppm is not None and self.magnesium is None:
            self.magnesium = self.magnesium_ppm

        if self.nitrate is not None and self.nitrate_ppm is None:
            self.nitrate_ppm = self.nitrate
        elif self.nitrate_ppm is not None and self.nitrate is None:
            self.nitrate = self.nitrate_ppm

        if self.phosphate is not None and self.phosphate_ppm is None:
            self.phosphate_ppm = self.phosphate
        elif self.phosphate_ppm is not None and self.phosphate is None:
            self.phosphate = self.phosphate_ppm

        if self.salinity is not None and self.salinity_ppt is None:
            self.salinity_ppt = self.salinity
        elif self.salinity_ppt is not None and self.salinity is None:
            self.salinity = self.salinity_ppt

        if self.ammonia is not None and self.ammonia_ppm is None:
            self.ammonia_ppm = self.ammonia
        elif self.ammonia_ppm is not None and self.ammonia is None:
            self.ammonia = self.ammonia_ppm

        if self.nitrite is not None and self.nitrite_ppm is None:
            self.nitrite_ppm = self.nitrite
        elif self.nitrite_ppm is not None and self.nitrite is None:
            self.nitrite = self.nitrite_ppm

        if self.temperature is not None and self.temperatura is None:
            self.temperatura = self.temperature
        elif self.temperatura is not None and self.temperature is None:
            self.temperature = self.temperatura

        if not self.timestamp and self.measured_at:
            self.timestamp = self.measured_at
        return self

class MeasurementCreate(MeasurementBase):
    pass

class MeasurementResponse(MeasurementBase):
    id: int
    user_id: Optional[int] = None
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

# Esquemas y alias para compatibilidad con Parameter / ParameterLog
class ParameterCreate(MeasurementCreate):
    pass

class ParameterResponse(MeasurementResponse):
    pass

ParameterBase = MeasurementBase
ParameterLog = Measurement
Parameter = Measurement


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - PREDICCIONES Y ALERTAS
# ==============================================================================

class ParameterConsumption(BaseModel):
    parameter: str
    unit: str
    latest_value: Optional[float] = None
    daily_consumption_rate: Optional[float] = None  # Cantidad consumida por día (positiva si desciende)
    daily_slope: Optional[float] = None             # Pendiente matemática (negativa si cae)
    safe_range: List[float]                         # [min, max]
    days_remaining_safe: Optional[float] = None     # Días hasta salirse del rango
    estimated_exit_date: Optional[str] = None       # Fecha proyectada YYYY-MM-DD
    status: str                                     # 'safe', 'warning_approaching', 'critical_below_safe', 'critical_above_safe', 'inconclusive_trend'
    alert_message: str
    # Campos de metrología e incertidumbre Fase 3
    uncertainty: Optional[float] = None             # ± error de la medición
    uncertainty_band: Optional[List[float]] = None  # [min_band, max_band]
    r_squared: Optional[float] = None              # R² de la regresión
    is_conclusive: bool = True                      # False si R² < 0.5 o banda cruza ambos lados
    display_value: Optional[str] = None             # Ej: "< 0.02 ppm"

class WaterChangePrediction(BaseModel):
    current_nitrate_ppm: Optional[float] = None
    daily_accumulation_rate: Optional[float] = None # ppm/día
    threshold_ppm: float = 20.0
    days_until_threshold: Optional[float] = None
    suggested_water_change_date: Optional[str] = None
    suggested_percentage: int = 20
    urgency: str                                    # 'safe', 'approaching', 'immediate', 'inconclusive_trend'
    message: str
    # Campos de metrología e incertidumbre Fase 3
    uncertainty: Optional[float] = None
    uncertainty_band: Optional[List[float]] = None
    r_squared: Optional[float] = None
    is_conclusive: bool = True
    display_value: Optional[str] = None

class PredictionResponse(BaseModel):
    confidence_level: str                           # 'high', 'medium', 'low'
    confidence_message: str
    measurements_count_last_14_days: int
    total_measurements: int
    alkalinity: ParameterConsumption
    calcium: ParameterConsumption
    water_change_prediction: WaterChangePrediction
    active_alerts: List[str]


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - ANÁLISIS CLÍNICO CON IA ESTRUCTURADO (GEMINI)
# ==============================================================================

class DosisRecomendada(BaseModel):
    parametro: str = Field(description="Nombre del parámetro a ajustar (ej. Alcalinidad, Calcio)")
    producto: str = Field(description="Nombre comercial o genérico del aditivo (ej. Bicarbonato de sodio, Cloruro de calcio)")
    cantidad_sugerida: str = Field(description="Dosis exacta con unidades (ej. 15 ml o 5 gramos)")

class AnalisisAcuarioSchema(BaseModel):
    diagnostico_general: str = Field(description="Resumen clínico del estado químico actual del tanque.")
    nivel_riesgo: str = Field(description="Clasificación del riesgo: 'Bajo', 'Moderado', 'Crítico' o 'Colapso Inminente'")
    alerta_predictiva: str = Field(description="Predicción de lo que ocurrirá en las próximas 48 horas si no se actúa.")
    acciones_correctoras: List[DosisRecomendada] = Field(description="Lista de acciones y dosificaciones requeridas.")

# Alias de compatibilidad directa para AnalisisAcuarioResponse
AnalisisAcuarioResponse = AnalisisAcuarioSchema

class AquariumDataRequest(BaseModel):
    nombre_acuario: str = Field("Principal", max_length=100, example="Arrecife Mixto SPS/LPS", description="Nombre del acuario")
    volumen_litros: float = Field(280.0, gt=0, le=100000.0, example=280.0, description="Volumen del acuario en litros")
    tipo: Optional[str] = Field("mixto", max_length=50, example="peces_marinos", description="Tipo de acuario: peces_marinos, mixto, arrecife, plantado, dulce")
    tank_type: Optional[str] = Field(None, max_length=50, example="peces_marinos", description="Alias de tipo de acuario")
    reef_profile: Optional[str] = Field(None, max_length=50)
    dosing_method: Optional[str] = Field(None, max_length=50)
    lighting_par: Optional[int] = Field(None, ge=0, le=2000)
    flow_profile: Optional[str] = Field(None, max_length=50)
    acuario_id: Optional[int] = Field(None, example=1, description="ID del acuario para cargar historial automático")
    tank_id: Optional[int] = Field(None, example=1, description="ID del acuario (alias de acuario_id)")
    ph: Optional[float] = Field(None, ge=4.0, le=10.0, example=8.2, description="Nivel de pH (Ideal: 8.1 - 8.4)")
    kh: Optional[float] = Field(None, ge=0.0, le=25.0, example=8.3, description="Alcalinidad dKH (Ideal: 7.5 - 8.5)")
    calcio: Optional[float] = Field(None, ge=0.0, le=1000.0, example=420.0, description="Calcio en ppm (Ideal: 420 - 450)")
    magnesio: Optional[float] = Field(None, ge=0.0, le=2500.0, example=1350.0, description="Magnesio en ppm (Ideal: 1300 - 1450)")
    nitrato: Optional[float] = Field(None, ge=0.0, le=200.0, example=5.0, description="Nitrato en ppm (Ideal: 5 - 10)")
    fosfato: Optional[float] = Field(None, ge=0.0, le=10.0, example=0.04, description="Fosfato en ppm (Ideal: 0.03 - 0.08)")
    temperatura: Optional[float] = Field(None, ge=10.0, le=40.0, example=25.5, description="Temperatura del agua en °C (Ideal: 24.5 - 26.5)")
    salinity: Optional[float] = Field(None, ge=0.0, le=60.0, example=1.025, description="Salinidad")
    ammonia: Optional[float] = Field(None, ge=0.0, le=20.0, description="Amoníaco")
    nitrite: Optional[float] = Field(None, ge=0.0, le=20.0, description="Nitrito")
    is_draft: Optional[bool] = Field(False, description="Indica si los datos corresponden a un borrador no confirmado")
    tendencia_reciente: str = Field("Estable en las últimas 24h", max_length=2000, description="Historial o tendencia reciente de cambios")

    model_config = ConfigDict(extra="forbid")

class AquariumAnalysisResponse(BaseModel):
    status: str = "success"
    analisis: AnalisisAcuarioSchema

class PredictiveAnalysisJsonResponse(BaseModel):
    status: str = "success"
    data: Any

class DiagnosticFeedbackCreate(BaseModel):
    tank_id: Optional[int] = None
    diagnosis_summary: Optional[str] = None
    severity: Optional[str] = None
    user_comment: str = Field(..., min_length=3, max_length=1500, description="Explicación de la inconsistencia detectada")
    category: Optional[str] = Field("incorrect_diagnosis", max_length=50)
    consent_given: bool = Field(..., description="Consentimiento explícito para compartir datos anónimos para auditoría del modelo.")

    model_config = ConfigDict(extra="forbid")

class DiagnosticFeedbackResponse(BaseModel):
    status: str = "success"
    message: str = "Reporte recibido correctamente. Gracias por colaborar con la seguridad y precisión de AquaPulse."
    feedback_id: Optional[int] = None
    consent_given: bool = True

class DiagnosticAuditResponse(BaseModel):
    id: int
    prompt_version: str
    status: str
    rejection_reason: Optional[str] = None
    cost_usd: float
    token_count: int
    latency_ms: Optional[float] = 0.0
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DiagnosticAuditStatsResponse(BaseModel):
    total_evaluations: int
    discarded_count: int
    accepted_count: int
    sanitized_count: int
    fallback_count: int
    discard_rate: float
    discard_rate_alert: bool
    total_cost_usd: float
    budget_limit_usd: float
    budget_status: str

# ==============================================================================
# ESQUEMAS PYDANTIC: MANTENIMIENTO MECÁNICO Y CAMBIOS DE AGUA
# ==============================================================================

class MaintenanceTaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    task_key: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field("mechanical", max_length=50)
    frequency_days: int = Field(7, ge=1, le=365)
    is_enabled: bool = True
    notes: Optional[str] = Field(None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

class MaintenanceTaskCreate(MaintenanceTaskBase):
    pass

class MaintenanceTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    category: Optional[str] = Field(None, max_length=50)
    frequency_days: Optional[int] = Field(None, ge=1, le=365)
    is_enabled: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

class MaintenanceTaskResponse(BaseModel):
    id: int
    aquarium_id: int
    user_id: int
    task_key: Optional[str] = None
    title: str
    category: str
    frequency_days: int
    last_completed_at: Optional[datetime] = None
    next_due_at: Optional[datetime] = None
    is_enabled: bool
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    days_since_last: Optional[int] = None
    days_until_due: Optional[int] = None
    status: str = "pending" # "ok" | "due_soon" | "overdue" | "pending"

    model_config = ConfigDict(from_attributes=True)

class MaintenanceCompleteRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=1000)
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")

class WaterChangeCreate(BaseModel):
    volume_liters: float = Field(..., gt=0, le=100000.0)
    percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    performed_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=1000)
    completed_task_ids: Optional[List[int]] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

class WaterChangeResponse(BaseModel):
    id: int
    tank_id: int
    user_id: int
    volume_liters: float
    percentage: Optional[float] = None
    performed_at: datetime
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - NOTIFICACIONES PUSH (VAPID)
# ==============================================================================

class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(..., max_length=2000)
    p256dh: str = Field(..., max_length=255)
    auth: str = Field(..., max_length=255)
    user_agent: Optional[str] = Field(None, max_length=500)
    notify_maintenance: Optional[bool] = True
    notify_alerts: Optional[bool] = True

    model_config = ConfigDict(extra="forbid")

class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., max_length=2000)

    model_config = ConfigDict(extra="forbid")

class PushPreferencesUpdate(BaseModel):
    notify_maintenance: Optional[bool] = None
    notify_alerts: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")
    notify_maintenance: Optional[bool] = None
    notify_alerts: Optional[bool] = None

class PushSubscriptionResponse(BaseModel):
    id: int
    endpoint: str
    notify_maintenance: bool
    notify_alerts: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

