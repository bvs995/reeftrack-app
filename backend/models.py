import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, model_validator
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text, Boolean, func
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


class Tank(Base):
    __tablename__ = "tanks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    tank_type = Column(String(50), default="reef", nullable=False) # 'reef', 'freshwater_planted', 'freshwater_community'
    volume_liters = Column(Float, default=280.0, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Sinónimos para compatibilidad bilingüe
    nombre = synonym("name")
    volumen = synonym("volume_liters")

    owner = relationship("User", back_populates="tanks")
    measurements = relationship("Measurement", back_populates="tank", cascade="all, delete-orphan")


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    tank_id = Column(Integer, ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ph = Column(Float, nullable=True)
    alkalinity_dkh = Column(Float, nullable=True)
    calcium_ppm = Column(Float, nullable=True)
    magnesium_ppm = Column(Float, nullable=True)
    nitrate_ppm = Column(Float, nullable=True)
    phosphate_ppm = Column(Float, nullable=True)
    salinity_ppt = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Sinónimos para consultas nativas en español (MedicionAcuario)
    acuario_id = synonym("tank_id")
    fecha_registro = synonym("timestamp")
    kh = synonym("alkalinity_dkh")
    calcio = synonym("calcium_ppm")
    magnesio = synonym("magnesium_ppm")
    nitrato = synonym("nitrate_ppm")
    fosfato = synonym("phosphate_ppm")

    user = relationship("User", back_populates="measurements")
    tank = relationship("Tank", back_populates="measurements")
    acuario = synonym("tank")

# ==============================================================================
# MODELOS SQLALCHEMY ORM OFICIALES EN ESPAÑOL (acuarios y mediciones)
# ==============================================================================

class Acuario(Base):
    __tablename__ = "acuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    volumen_litros = Column(Float, nullable=False)
    usuario_id = Column(String(100), nullable=False, default="1", index=True)
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
    magnesio = Column(Float, nullable=True)
    nitrato = Column(Float, nullable=True)
    fosfato = Column(Float, nullable=True)
    fecha_registro = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False, index=True)

    # Sinónimos para interoperabilidad total
    tank_id = synonym("acuario_id")
    alkalinity_dkh = synonym("kh")
    calcium_ppm = synonym("calcio")
    magnesium_ppm = synonym("magnesio")
    nitrate_ppm = synonym("nitrato")
    phosphate_ppm = synonym("fosfato")
    timestamp = synonym("fecha_registro")

    acuario = relationship("Acuario", back_populates="mediciones")
    tank = synonym("acuario")


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - AUTENTICACIÓN Y USUARIOS
# ==============================================================================

class UserRegister(BaseModel):
    email: str = Field(..., example="acuarista@reef.com", description="Correo electrónico del usuario")
    password: str = Field(
        ...,
        example="PasswordSeguro123!",
        description="Contraseña estricta: mínimo 8 caracteres, 1 mayúscula, 1 número y 1 carácter especial"
    )
    full_name: Optional[str] = Field(None, example="Alex Valadez", description="Nombre del acuarista")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        check_password_complexity(v)
        return v

class UserLogin(BaseModel):
    email: str = Field(..., example="acuarista@reef.com")
    password: str = Field(..., example="PasswordSeguro123")

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., example="acuarista@reef.com", description="Correo para restablecer contraseña")

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Token seguro de restablecimiento")
    new_password: str = Field(
        ...,
        example="NuevaPassSegura2026!",
        description="Nueva contraseña estricta (mínimo 8 caracteres, 1 mayúscula, 1 número y 1 carácter especial)"
    )

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
    full_name: Optional[str] = None
    unit_preference: Optional[str] = Field(None, pattern="^(liters|gallons)$", description="'liters' o 'gallons'")

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
    full_name: Optional[str] = None

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
    user: UserResponse


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - ACUARIOS (TANKS)
# ==============================================================================

class TankCreate(BaseModel):
    name: str = Field(..., example="Arrecife Mixto SPS/LPS")
    tank_type: str = Field("reef", example="reef")
    volume_liters: float = Field(280.0, example=280.0)
    notes: Optional[str] = None

class TankResponse(BaseModel):
    id: int
    user_id: int
    name: str
    tank_type: str
    volume_liters: float
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - MEDICIONES (MEASUREMENTS)
# ==============================================================================

class MeasurementBase(BaseModel):
    tank_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    ph: Optional[float] = Field(None, example=8.2, description="Nivel de pH (ej: 8.1 - 8.4)")
    alkalinity_dkh: Optional[float] = Field(None, example=8.2, description="Alcalinidad en dKH")
    calcium_ppm: Optional[float] = Field(None, example=420.0, description="Calcio en ppm")
    magnesium_ppm: Optional[float] = Field(None, example=1350.0, description="Magnesio en ppm")
    nitrate_ppm: Optional[float] = Field(None, example=5.0, description="Nitrato (NO3) en ppm")
    phosphate_ppm: Optional[float] = Field(None, example=0.04, description="Fosfato (PO4) en ppm")
    salinity_ppt: Optional[float] = Field(None, example=35.0, description="Salinidad en ppt o Gravedad Específica")
    notes: Optional[str] = Field(None, example="Test Hanna Checker HI772", description="Notas o kit de test")

    # Campos de compatibilidad con entrada rápida Numpad
    parameter_code: Optional[str] = Field(None, description="Código de parámetro rápido (ej: dkh, ca, mg, no3, po4, salinity)")
    value: Optional[float] = Field(None, description="Valor numérico de la medición individual")
    measured_at: Optional[datetime] = Field(None, description="Timestamp alternativo de medición")

    @model_validator(mode="after")
    def map_parameter_code_if_present(self):
        """Mapea automáticamente campos individuales tipo {parameter_code: 'dkh', value: 8.3} a la columna correcta."""
        code_map = {
            "ph": "ph",
            "dkh": "alkalinity_dkh",
            "alkalinity": "alkalinity_dkh",
            "alkalinity_dkh": "alkalinity_dkh",
            "ca": "calcium_ppm",
            "calcium": "calcium_ppm",
            "calcium_ppm": "calcium_ppm",
            "mg": "magnesium_ppm",
            "magnesium": "magnesium_ppm",
            "magnesium_ppm": "magnesium_ppm",
            "no3": "nitrate_ppm",
            "nitrate": "nitrate_ppm",
            "nitrate_ppm": "nitrate_ppm",
            "po4": "phosphate_ppm",
            "phosphate": "phosphate_ppm",
            "phosphate_ppm": "phosphate_ppm",
            "salinity": "salinity_ppt",
            "salinity_ppt": "salinity_ppt",
        }
        if self.parameter_code and self.value is not None:
            field_name = code_map.get(str(self.parameter_code).lower().strip())
            if field_name:
                setattr(self, field_name, self.value)
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
    status: str                                     # 'safe', 'warning_approaching', 'critical_below_safe', 'critical_above_safe'
    alert_message: str

class WaterChangePrediction(BaseModel):
    current_nitrate_ppm: Optional[float] = None
    daily_accumulation_rate: Optional[float] = None # ppm/día
    threshold_ppm: float = 20.0
    days_until_threshold: Optional[float] = None
    suggested_water_change_date: Optional[str] = None
    suggested_percentage: int = 20
    urgency: str                                    # 'safe', 'approaching', 'immediate'
    message: str

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
    nombre_acuario: str = Field("Principal", example="Arrecife Mixto SPS/LPS", description="Nombre del acuario")
    volumen_litros: float = Field(280.0, example=280.0, description="Volumen del acuario en litros")
    acuario_id: Optional[int] = Field(None, example=1, description="ID del acuario para cargar historial automático")
    tank_id: Optional[int] = Field(None, example=1, description="ID del acuario (alias de acuario_id)")
    ph: Optional[float] = Field(None, example=8.2, description="Nivel de pH (Ideal: 8.1 - 8.4)")
    kh: Optional[float] = Field(None, example=8.3, description="Alcalinidad dKH (Ideal: 7.5 - 8.5)")
    calcio: Optional[float] = Field(None, example=420.0, description="Calcio en ppm (Ideal: 420 - 450)")
    magnesio: Optional[float] = Field(None, example=1350.0, description="Magnesio en ppm (Ideal: 1300 - 1450)")
    nitrato: Optional[float] = Field(None, example=5.0, description="Nitrato en ppm (Ideal: 5 - 10)")
    fosfato: Optional[float] = Field(None, example=0.04, description="Fosfato en ppm (Ideal: 0.03 - 0.08)")
    tendencia_reciente: str = Field("Estable en las últimas 24h", description="Historial o tendencia reciente de cambios")

class AquariumAnalysisResponse(BaseModel):
    status: str = "success"
    analisis: AnalisisAcuarioSchema

class PredictiveAnalysisJsonResponse(BaseModel):
    status: str = "success"
    data: AnalisisAcuarioResponse
