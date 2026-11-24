"""
AquaPulse - Tests de Auditoría y Verificación P3 (Antes de publicar en tienda)
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import SessionLocal
from backend.models import User

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ==============================================================================
# P3.18 - Aviso de privacidad y términos de uso en la app
# ==============================================================================
class TestAuditP3Point18:
    def test_terms_of_service_md_exists_and_contains_mandatory_clauses(self):
        terms_path = REPO_ROOT / "TERMS.md"
        assert terms_path.exists(), "TERMS.md debe existir en la raíz del repositorio"
        content = terms_path.read_text(encoding="utf-8")
        assert "Términos de Uso" in content or "Condiciones de Servicio" in content
        assert "orientativo" in content.lower(), "Debe advertir que el diagnóstico de IA es de carácter orientativo"
        assert "gemini" in content.lower(), "Debe mencionar el uso de Google Gemini para procesamiento de mediciones"
        assert "borrado" in content.lower() or "eliminación" in content.lower(), "Debe estipular el derecho de borrado de cuenta"

    def test_privacy_md_contains_gemini_and_user_rights(self):
        privacy_path = REPO_ROOT / "PRIVACY.md"
        assert privacy_path.exists(), "PRIVACY.md debe existir en la raíz del repositorio"
        content = privacy_path.read_text(encoding="utf-8")
        assert "orientativo" in content.lower(), "Debe especificar que el diagnóstico es orientativo"
        assert "gemini" in content.lower(), "Debe especificar el uso de Google Gemini"
        assert "acceso" in content.lower() and "borrado" in content.lower(), "Debe contemplar derechos de acceso, corrección y borrado"

    def test_legal_endpoints_available_on_backend(self):
        # GET /api/legal/privacy
        res_privacy = client.get("/api/legal/privacy")
        assert res_privacy.status_code == 200, f"/api/legal/privacy debe retornar 200: {res_privacy.text}"
        data_p = res_privacy.json()
        assert "content" in data_p or "privacy_policy" in data_p or "text" in data_p

        # GET /api/legal/terms
        res_terms = client.get("/api/legal/terms")
        assert res_terms.status_code == 200, f"/api/legal/terms debe retornar 200: {res_terms.text}"
        data_t = res_terms.json()
        assert "content" in data_t or "terms" in data_t or "text" in data_t

    def test_frontend_settings_and_auth_include_privacy_and_terms(self):
        # Frontend SettingsView.jsx debe incluir botón o sección de términos y privacidad
        settings_path = REPO_ROOT / "frontend" / "src" / "components" / "SettingsView.jsx"
        settings_content = settings_path.read_text(encoding="utf-8").lower()
        assert "privacidad" in settings_content or "privacy" in settings_content, "SettingsView debe enlazar a privacidad y términos"

        # Frontend AuthModal.jsx debe informar sobre términos y diagnóstico orientativo por IA
        auth_path = REPO_ROOT / "frontend" / "src" / "components" / "AuthModal.jsx"
        auth_content = auth_path.read_text(encoding="utf-8").lower()
        assert "términos" in auth_content or "terminos" in auth_content or "privacidad" in auth_content
