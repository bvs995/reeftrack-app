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
    email: str = Field(..., example="acuarista@reef.com", description="Correo electrónico del usuario")
    password: str = Field(
        ...,
        example="PasswordSeguro123!",
        description="Contraseña estricta: mínimo 8 caracteres, 1 mayúscula, 1 número y 1 carácter especial"
    )
    full_name: Optional[str] = Field(None, example="Alex Valadez", description="Nombre del acuarista")

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
    email: str = Field(..., example="acuarista@reef.com")
    password: str = Field(..., example="PasswordSeguro123")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., example="acuarista@reef.com", description="Correo para restablecer contraseña")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v

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

class AquariumCreate(BaseModel):
    name: str = Field(..., description="Nombre del acuario")
    volume_liters: float = Field(..., gt=0, description="Volumen en litros")
    tank_type: Literal["arrecife", "mixed", "marine_fish", "plantado", "dulce"] = Field(
        default="mixed", description="Biotipo del acuario"
    )
    reef_profile: Optional[str] = Field(None, description="Perfil marino: fish_only, soft_reef, lps_reef, mixed_reef, sps_reef")
    dosing_method: Optional[str] = Field(None, description="Método de dosificación: water_changes, manual_dosing, peristaltic_balling, kalkwasser, calcium_reactor")
    lighting_par: Optional[int] = Field(None, description="Intensidad lumínica estimada o medida en PAR")
    flow_profile: Optional[str] = Field(None, description="Perfil de flujo: low_moderate, moderate_indirect, high_turbulent")
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def handle_type_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tank_type" not in data and "type" in data:
                data["tank_type"] = data["type"]
            if "tank_type" in data:
                mapping = {
                    "reef": "arrecife",
                    "mixto": "mixed",
                    "peces_marinos": "marine_fish",
                    "freshwater_planted": "plantado",
                    "freshwater_community": "dulce"
                }
                data["tank_type"] = mapping.get(data["tank_type"], data["tank_type"])
        return data

    @property
    def type(self) -> str:
        return self.tank_type

class TankCreate(BaseModel):
    name: str = Field(..., example="Arrecife Mixto SPS/LPS")
    tank_type: Literal["arrecife", "mixed", "marine_fish", "plantado", "dulce"] = Field(
        default="mixed", description="Biotipo del acuario"
    )
    volume_liters: float = Field(280.0, gt=0, example=280.0)
    reef_profile: Optional[str] = Field(None, description="Perfil marino: fish_only, soft_reef, lps_reef, mixed_reef, sps_reef")
    dosing_method: Optional[str] = Field(None, description="Método de dosificación")
    lighting_par: Optional[int] = Field(None, description="Intensidad lumínica PAR")
    flow_profile: Optional[str] = Field(None, description="Perfil de flujo")
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def handle_type_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tank_type" not in data and "type" in data:
                data["tank_type"] = data["type"]
            if "tank_type" in data:
                mapping = {
                    "reef": "arrecife",
                    "mixto": "mixed",
                    "peces_marinos": "marine_fish",
                    "freshwater_planted": "plantado",
                    "freshwater_community": "dulce"
                }
                data["tank_type"] = mapping.get(data["tank_type"], data["tank_type"])
        return data

class TankUpdate(BaseModel):
    name: Optional[str] = None
    tank_type: Optional[str] = None
    volume_liters: Optional[float] = None
    reef_profile: Optional[str] = None
    dosing_method: Optional[str] = None
    lighting_par: Optional[int] = None
    flow_profile: Optional[str] = None
    notes: Optional[str] = None

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
    ph: Optional[float] = Field(None, example=8.2, description="Nivel de pH (ej: 8.1 - 8.4)")
    alkalinity_dkh: Optional[float] = Field(None, example=8.2, description="Alcalinidad en dKH")
    kh: Optional[float] = Field(None, example=8.2, description="Alcalinidad en dKH (alias)")
    calcium_ppm: Optional[float] = Field(None, example=420.0, description="Calcio en ppm")
    calcium: Optional[float] = Field(None, example=420.0, description="Calcio en ppm (alias)")
    magnesium_ppm: Optional[float] = Field(None, example=1350.0, description="Magnesio en ppm")
    magnesium: Optional[float] = Field(None, example=1350.0, description="Magnesio en ppm (alias)")
    nitrate_ppm: Optional[float] = Field(None, example=5.0, description="Nitrato (NO3) en ppm")
    nitrate: Optional[float] = Field(None, example=5.0, description="Nitrato (NO3) en ppm (alias)")
    phosphate_ppm: Optional[float] = Field(None, example=0.04, description="Fosfato (PO4) en ppm")
    phosphate: Optional[float] = Field(None, example=0.04, description="Fosfato (PO4) en ppm (alias)")
    salinity_ppt: Optional[float] = Field(None, example=35.0, description="Salinidad en ppt o Gravedad Específica")
    salinity: Optional[float] = Field(None, example=1.025, description="Salinidad en SG o ppt (alias)")
    temperature: Optional[float] = Field(None, example=25.5, description="Temperatura en °C (Ideal: 20.0 a 32.0 °C)")
    temperatura: Optional[float] = Field(None, example=25.5, description="Temperatura en °C")
    ammonia_ppm: Optional[float] = Field(None, example=0.0, description="Amoníaco en ppm")
    ammonia: Optional[float] = Field(None, example=0.0, description="Amoníaco en ppm (alias)")
    nitrite_ppm: Optional[float] = Field(None, example=0.0, description="Nitrito en ppm")
    nitrite: Optional[float] = Field(None, example=0.0, description="Nitrito en ppm (alias)")
    gh_dgh: Optional[float] = Field(None, example=6.0, description="Dureza General GH")

    trace_elements: Optional[Dict[str, Optional[float]]] = Field(None, description="Elementos traza (k, sr, i, fe)")
    test_methods: Optional[Dict[str, Optional[str]]] = Field(None, description="Métodos de test (ej: {'po4': 'photometer_ulr', 'kh': 'drop_kit'})")
    notes: Optional[str] = Field(None, example="Test Hanna Checker HI772", description="Notas o kit de test")

    # Campos de compatibilidad con entrada rápida Numpad
    parameter_code: Optional[str] = Field(None, description="Código de parámetro rápido")
    value: Optional[float] = Field(None, description="Valor numérico de la medición individual")
    measured_at: Optional[datetime] = Field(None, description="Timestamp alternativo de medición")

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
    tipo: Optional[str] = Field("mixto", example="peces_marinos", description="Tipo de acuario: peces_marinos, mixto, arrecife, plantado, dulce")
    tank_type: Optional[str] = Field(None, example="peces_marinos", description="Alias de tipo de acuario")
    acuario_id: Optional[int] = Field(None, example=1, description="ID del acuario para cargar historial automático")
    tank_id: Optional[int] = Field(None, example=1, description="ID del acuario (alias de acuario_id)")
    ph: Optional[float] = Field(None, example=8.2, description="Nivel de pH (Ideal: 8.1 - 8.4)")
    kh: Optional[float] = Field(None, example=8.3, description="Alcalinidad dKH (Ideal: 7.5 - 8.5)")
    calcio: Optional[float] = Field(None, example=420.0, description="Calcio en ppm (Ideal: 420 - 450)")
    magnesio: Optional[float] = Field(None, example=1350.0, description="Magnesio en ppm (Ideal: 1300 - 1450)")
    nitrato: Optional[float] = Field(None, example=5.0, description="Nitrato en ppm (Ideal: 5 - 10)")
    fosfato: Optional[float] = Field(None, example=0.04, description="Fosfato en ppm (Ideal: 0.03 - 0.08)")
    temperatura: Optional[float] = Field(None, example=25.5, description="Temperatura del agua en °C (Ideal: 24.5 - 26.5)")
    tendencia_reciente: str = Field("Estable en las últimas 24h", description="Historial o tendencia reciente de cambios")

class AquariumAnalysisResponse(BaseModel):
    status: str = "success"
    analisis: AnalisisAcuarioSchema

class PredictiveAnalysisJsonResponse(BaseModel):
    status: str = "success"
    data: AnalisisAcuarioResponse
