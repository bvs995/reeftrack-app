# Re-export de conveniencia
from backend.services.ai_service import (
    analizar_parametros_acuario,
    PRIMARY_MODEL,
    FALLBACK_MODELS
)

__all__ = ["analizar_parametros_acuario", "PRIMARY_MODEL", "FALLBACK_MODELS"]
