"""
AquaPulse - Router de Documentos Legales y Términos de Servicio (P3.18)
"""
import os
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger("aquapulse.legal")

router = APIRouter(tags=["Legal"])

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@router.get(
    "/api/legal/privacy",
    summary="Consultar Política de Privacidad oficial de AquaPulse"
)
def get_privacy_policy():
    """Retorna la Política de Privacidad en formato estructurado y texto Markdown."""
    privacy_file = REPO_ROOT / "PRIVACY.md"
    content = ""
    if privacy_file.exists():
        content = privacy_file.read_text(encoding="utf-8")
    else:
        content = "# Política de Privacidad\nAquaPulse protege tus datos y utiliza diagnósticos orientativos."

    return {
        "status": "success",
        "title": "Política de Privacidad de AquaPulse",
        "version": "1.0",
        "is_ai_orientative": True,
        "ai_provider": "Google Gemini",
        "user_rights": ["acceso", "rectificacion", "borrado_permanente", "revocacion"],
        "content": content
    }


@router.get(
    "/api/legal/terms",
    summary="Consultar Términos y Condiciones de Uso de AquaPulse"
)
def get_terms_of_service():
    """Retorna los Términos de Servicio y Condiciones de Uso en formato estructurado y texto Markdown."""
    terms_file = REPO_ROOT / "TERMS.md"
    content = ""
    if terms_file.exists():
        content = terms_file.read_text(encoding="utf-8")
    else:
        content = "# Términos de Uso\nLos diagnósticos de IA en AquaPulse son de carácter orientativo."

    return {
        "status": "success",
        "title": "Términos y Condiciones de Uso de AquaPulse",
        "version": "1.0",
        "is_ai_orientative": True,
        "ai_provider": "Google Gemini",
        "user_rights": ["acceso", "rectificacion", "borrado_permanente"],
        "disclaimer": "Diagnóstico de carácter estrictamente orientativo; no constituye prescripción veterinaria ni garantía biológica.",
        "content": content
    }
