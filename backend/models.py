from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base

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

    owner = relationship("User", back_populates="tanks")
    measurements = relationship("Measurement", back_populates="tank", cascade="all, delete-orphan")


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    tank_id = Column(Integer, ForeignKey("tanks.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    alkalinity_dkh = Column(Float, nullable=True)
    calcium_ppm = Column(Float, nullable=True)
    magnesium_ppm = Column(Float, nullable=True)
    nitrate_ppm = Column(Float, nullable=True)
    phosphate_ppm = Column(Float, nullable=True)
    salinity_ppt = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="measurements")
    tank = relationship("Tank", back_populates="measurements")


# ==============================================================================
# ESQUEMAS PYDANTIC v2 - AUTENTICACIÓN Y USUARIOS
# ==============================================================================

class UserRegister(BaseModel):
    email: str = Field(..., example="acuarista@reef.com", description="Correo electrónico del usuario")
    password: str = Field(..., min_length=6, example="PasswordSeguro123", description="Contraseña mínimo 6 caracteres")
    full_name: Optional[str] = Field(None, example="Alex Valadez", description="Nombre del acuarista")

class UserLogin(BaseModel):
    email: str = Field(..., example="acuarista@reef.com")
    password: str = Field(..., example="PasswordSeguro123")

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., example="acuarista@reef.com", description="Correo para restablecer contraseña")

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Token seguro de restablecimiento")
    new_password: str = Field(..., min_length=6, description="Nueva contraseña (mínimo 6 caracteres)")

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
    alkalinity_dkh: Optional[float] = Field(None, example=8.2, description="Alcalinidad en dKH")
    calcium_ppm: Optional[float] = Field(None, example=420.0, description="Calcio en ppm")
    magnesium_ppm: Optional[float] = Field(None, example=1350.0, description="Magnesio en ppm")
    nitrate_ppm: Optional[float] = Field(None, example=5.0, description="Nitrato (NO3) en ppm")
    phosphate_ppm: Optional[float] = Field(None, example=0.04, description="Fosfato (PO4) en ppm")
    salinity_ppt: Optional[float] = Field(None, example=35.0, description="Salinidad en ppt o Gravedad Específica")
    notes: Optional[str] = Field(None, example="Test Hanna Checker HI772", description="Notas o kit de test")

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
