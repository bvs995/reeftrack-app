# Re-export de conveniencia para backend.ai_service
from backend.services.ai_service import (
    analizar_parametros_estructurado,
    analizar_parametros_acuario,
    analizar_acuario_estructurado,
    obtener_tendencia_ultimas_48h,
    PRIMARY_MODEL,
    FALLBACK_MODELS
)
from backend.models import (
    DosisRecomendada,
    AnalisisAcuarioSchema,
    AnalisisAcuarioResponse,
    AquariumAnalysisResponse,
    AquariumDataRequest,
    PredictiveAnalysisJsonResponse,
    MedicionAcuario,
    Acuario
)

__all__ = [
    "analizar_parametros_estructurado",
    "analizar_parametros_acuario",
    "analizar_acuario_estructurado",
    "obtener_tendencia_ultimas_48h",
    "DosisRecomendada",
    "AnalisisAcuarioSchema",
    "AnalisisAcuarioResponse",
    "AquariumAnalysisResponse",
    "AquariumDataRequest",
    "PredictiveAnalysisJsonResponse",
    "MedicionAcuario",
    "Acuario",
    "PRIMARY_MODEL",
    "FALLBACK_MODELS"
]
