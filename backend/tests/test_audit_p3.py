"""
AquaReef - Tests de Auditoría y Verificación P3 (Antes de publicar en tienda)
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

    def test_legal_endpoints_serve_full_documents_in_docker_image(self):
        """El texto servido debe ser el de PRIVACY.md/TERMS.md, no el de respaldo, y el
        Dockerfile debe copiarlos: sin eso producción servía una sola línea."""
        assert client.get("/api/legal/privacy").json()["content"] == (REPO_ROOT / "PRIVACY.md").read_text(encoding="utf-8")
        assert client.get("/api/legal/terms").json()["content"] == (REPO_ROOT / "TERMS.md").read_text(encoding="utf-8")

        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        copy_lines = [l for l in dockerfile.splitlines() if l.strip().upper().startswith("COPY")]
        for name in ("PRIVACY.md", "TERMS.md"):
            assert any(name in l for l in copy_lines), f"El Dockerfile debe copiar {name} a /app"

    def test_auth_modal_links_to_public_legal_pages(self):
        """El aviso del registro debe enlazar a las páginas públicas, no ser texto plano."""
        auth = (REPO_ROOT / "frontend" / "src" / "components" / "AuthModal.jsx").read_text(encoding="utf-8")
        assert 'href="/terminos"' in auth and 'href="/privacidad"' in auth
        main = (REPO_ROOT / "frontend" / "src" / "main.jsx").read_text(encoding="utf-8")
        assert "LegalPage" in main

    def test_frontend_settings_and_auth_include_privacy_and_terms(self):
        # Frontend SettingsView.jsx debe incluir botón o sección de términos y privacidad
        settings_path = REPO_ROOT / "frontend" / "src" / "components" / "SettingsView.jsx"
        settings_content = settings_path.read_text(encoding="utf-8").lower()
        assert "privacidad" in settings_content or "privacy" in settings_content, "SettingsView debe enlazar a privacidad y términos"

        # Frontend AuthModal.jsx debe informar sobre términos y diagnóstico orientativo por IA
        auth_path = REPO_ROOT / "frontend" / "src" / "components" / "AuthModal.jsx"
        auth_content = auth_path.read_text(encoding="utf-8").lower()
        assert "términos" in auth_content or "terminos" in auth_content or "privacidad" in auth_content


# ==============================================================================
# P3.19 - Confirmación de nivel de pago en API de Gemini (privacidad de datos)
# ==============================================================================
class TestAuditP3Point19:
    def test_gemini_paid_tier_enforced_in_production(self, monkeypatch):
        import backend.services.ai_service as ai_srv
        assert hasattr(ai_srv, "validate_gemini_tier"), "Debe existir validate_gemini_tier en ai_service"

        # En producción con tier 'free' debe fallar
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("GEMINI_TIER", "free")
        with pytest.raises((ValueError, RuntimeError)) as exc:
            ai_srv.validate_gemini_tier()
        assert "pago" in str(exc.value).lower() or "paid" in str(exc.value).lower() or "entrenar" in str(exc.value).lower()

        # En producción con tier 'pay-as-you-go' o 'paid' debe ser válido
        monkeypatch.setenv("GEMINI_TIER", "pay-as-you-go")
        assert ai_srv.validate_gemini_tier() is True

        monkeypatch.setenv("GEMINI_TIER", "paid")
        assert ai_srv.validate_gemini_tier() is True

    def test_privacy_and_security_docs_specify_paid_tier_no_training(self):
        privacy_path = REPO_ROOT / "PRIVACY.md"
        priv_text = privacy_path.read_text(encoding="utf-8").lower()
        assert "pago" in priv_text or "comercial" in priv_text or "no se utilizan para entrenar" in priv_text or "entrenar" in priv_text, (
            "PRIVACY.md debe confirmar explícitamente que la API de Gemini es de nivel de pago donde los datos no se usan para entrenar modelos"
        )


# ==============================================================================
# P3.20 - Backups automáticos con restauración probada y hosting sin pausa
# ==============================================================================
class TestAuditP3Point20:
    def test_backup_module_has_cli_and_automated_drill(self):
        import backend.backup as bkp
        assert hasattr(bkp, "run_backup_drill"), "backend.backup debe definir run_backup_drill"
        result = bkp.run_backup_drill()
        assert result.get("is_parity") is True, f"El simulacro de respaldo y restauración debe tener paridad total: {result}"

    def test_automated_backup_workflow_exists(self):
        wf_path = REPO_ROOT / ".github" / "workflows" / "backup.yml"
        assert wf_path.exists(), ".github/workflows/backup.yml debe existir para backups automáticos"
        content = wf_path.read_text(encoding="utf-8")
        assert "schedule" in content or "cron" in content, "El workflow de backup debe tener programación cron recurrente"
        assert "python -m backend.backup" in content or "run_backup_drill" in content or "backup" in content.lower()

    def test_deployment_guide_specifies_no_sleep_hosting(self):
        deploy_md = REPO_ROOT / "DEPLOYMENT.md"
        assert deploy_md.exists(), "DEPLOYMENT.md debe existir en la raíz del repositorio"
        content = deploy_md.read_text(encoding="utf-8").lower()
        assert "inactividad" in content or "sleep" in content or "starter" in content or "pausa" in content, (
            "DEPLOYMENT.md debe especificar un plan de hosting sin pausa por inactividad"
        )
        assert "backup" in content or "respaldo" in content, "DEPLOYMENT.md debe documentar backups y restauración"
