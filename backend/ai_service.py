# Re-export de conveniencia para backend.ai_service
from backend.services.ai_service import (
    analizar_parametros_estructurado,
    analizar_parametros_acuario,
    PRIMARY_MODEL,
    FALLBACK_MODELS
)
from backend.models import (
    DosisRecomendada,
    AnalisisAcuarioSchema,
    AnalisisAcuarioResponse,
    AquariumAnalysisResponse,
    AquariumDataRequest,
    PredictiveAnalysisJsonResponse
)

__all__ = [
    "analizar_parametros_estructurado",
    "analizar_parametros_acuario",
    "DosisRecomendada",
    "AnalisisAcuarioSchema",
    "AnalisisAcuarioResponse",
    "AquariumAnalysisResponse",
    "AquariumDataRequest",
    "PredictiveAnalysisJsonResponse",
    "PRIMARY_MODEL",
    "FALLBACK_MODELS"
]
