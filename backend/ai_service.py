# Re-export de conveniencia para backend.ai_service
from backend.services.ai_service import (
    analizar_parametros_estructurado,
    analizar_parametros_acuario,
    analizar_acuario_estructurado,
    obtener_tendencia_ultimas_48h,
    PRIMARY_MODEL,
    FALLBACK_MODELS,
    SUPPORTED_GEMINI_MODELS,
    DEPRECATED_MODELS,
    validate_gemini_model,
    AI_GENERATION_MAX_OUTPUT_TOKENS,
    AI_GENERATION_THINKING_BUDGET,
    USER_MONTHLY_AI_BUDGET_USD,
    get_current_month_user_ai_spend,
    should_execute_double_pass,
    get_diagnosis_cache_key,
    check_diagnosis_cache,
    set_diagnosis_cache
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
    "FALLBACK_MODELS",
    "SUPPORTED_GEMINI_MODELS",
    "DEPRECATED_MODELS",
    "validate_gemini_model",
    "AI_GENERATION_MAX_OUTPUT_TOKENS",
    "AI_GENERATION_THINKING_BUDGET",
    "USER_MONTHLY_AI_BUDGET_USD",
    "get_current_month_user_ai_spend",
    "should_execute_double_pass",
    "get_diagnosis_cache_key",
    "check_diagnosis_cache",
    "set_diagnosis_cache"
]
