from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, Integer, Float, String, DateTime
from backend.database import Base

# ----------------- MODELO SQLALCHEMY ORM -----------------

class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    alkalinity_dkh = Column(Float, nullable=True)
    calcium_ppm = Column(Float, nullable=True)
    magnesium_ppm = Column(Float, nullable=True)
    nitrate_ppm = Column(Float, nullable=True)
    phosphate_ppm = Column(Float, nullable=True)
    salinity_ppt = Column(Float, nullable=True)
    notes = Column(String, nullable=True)


# ----------------- ESQUEMAS PYDANTIC v2 -----------------

class MeasurementBase(BaseModel):
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
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# ----------------- ESQUEMAS DE PREDICCIÓN Y ALERTAS -----------------

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
