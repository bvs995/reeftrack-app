"""
Esquemas Pydantic v2 oficiales para AquaPulse.
Re-exporta y centraliza los esquemas para validación de API.
"""
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models import (
    MeasurementBase,
    MeasurementCreate,
    MeasurementResponse,
    TankCreate,
    AquariumCreate,
    TankResponse,
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    PasswordResetResponse,
    UserUpdate,
    AdminUserUpdate,
    AdminUserListItem,
    ParameterConsumption,
    WaterChangePrediction,
    PredictionResponse,
    DosisRecomendada,
    AnalisisAcuarioSchema,
    AnalisisAcuarioResponse,
    AquariumDataRequest,
    AquariumAnalysisResponse,
    PredictiveAnalysisJsonResponse
)

__all__ = [
    "MeasurementBase",
    "MeasurementCreate",
    "MeasurementResponse",
    "TankCreate",
    "AquariumCreate",
    "TankResponse",
    "UserRegister",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "PasswordResetResponse",
    "UserUpdate",
    "AdminUserUpdate",
    "AdminUserListItem",
    "ParameterConsumption",
    "WaterChangePrediction",
    "PredictionResponse",
    "DosisRecomendada",
    "AnalisisAcuarioSchema",
    "AnalisisAcuarioResponse",
    "AquariumDataRequest",
    "AquariumAnalysisResponse",
    "PredictiveAnalysisJsonResponse"
]
