# Re-export de conveniencia para backend.ai_service
from backend.services.ai_service import (
    analizar_parametros_estructurado,
    analizar_parametros_acuario,
    analizar_acuario_estructurado,
    obtener_tendencia_ultimas_48h,
    PRIMARY_MODEL,
    FALLBACK_MODELS
)
from backend.ai_validator import (
    AIDiagnosisOutput,
    DiagnosticFinding,
    AllowedAction,
    ALLOWED_ACTIONS,
    SEVERITY_HIERARCHY,
    load_versioned_system_prompt,
    validate_and_sanitize_ai_diagnosis,
    execute_double_pass_verification,
    generate_rules_deterministic_diagnosis
)
from backend.models import (
    AquariumAnalysisResponse,
    AquariumDataRequest,
    PredictiveAnalysisJsonResponse
)

__all__ = [
    "analizar_parametros_estructurado",
    "analizar_parametros_acuario",
    "analizar_acuario_estructurado",
    "obtener_tendencia_ultimas_48h",
    "AIDiagnosisOutput",
    "DiagnosticFinding",
    "AllowedAction",
    "ALLOWED_ACTIONS",
    "SEVERITY_HIERARCHY",
    "load_versioned_system_prompt",
    "validate_and_sanitize_ai_diagnosis",
    "execute_double_pass_verification",
    "generate_rules_deterministic_diagnosis",
    "AquariumAnalysisResponse",
    "AquariumDataRequest",
    "PredictiveAnalysisJsonResponse",
    "PRIMARY_MODEL",
    "FALLBACK_MODELS"
]
