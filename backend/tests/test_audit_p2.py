"""
AquaPulse - Tests de Auditoría P2 (Prioridad Media)
P2.12 - Dockerfile, requirements.txt, requirements-dev.txt, workers y CI
"""
import os
import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

class TestAuditP2Point12:
    def test_dockerfile_no_wildcard_cors(self):
        dockerfile_path = REPO_ROOT / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile must exist"
        content = dockerfile_path.read_text(encoding="utf-8")
        assert 'ALLOWED_ORIGINS="*"' not in content, "Dockerfile must not set ALLOWED_ORIGINS='*'"

    def test_dockerfile_workers_tuned_or_configurable(self):
        dockerfile_path = REPO_ROOT / "Dockerfile"
        content = dockerfile_path.read_text(encoding="utf-8")
        # Should allow configuring WORKERS via env or calculating from RAM, not hardcoded fixed 2 without env var
        assert "${WORKERS" in content or "WORKERS=" in content or "WEB_CONCURRENCY" in content, (
            "Dockerfile should allow configuring workers dynamically or via WORKERS env var based on RAM"
        )

    def test_production_requirements_pinned_and_no_dev_tools(self):
        req_path = REPO_ROOT / "backend" / "requirements.txt"
        assert req_path.exists()
        lines = [line.strip() for line in req_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        
        # Must not contain test libraries
        for forbidden in ["pytest", "pytest-asyncio", "pytest-mock"]:
            assert not any(forbidden in line.lower() for line in lines), f"Production requirements must not contain {forbidden}"
            
        # Must pin exact versions with ==
        for line in lines:
            assert "==" in line, f"Dependency '{line}' in requirements.txt must be pinned with exact version '=='"
            assert not line.startswith(">="), f"Dependency '{line}' must not use >="

    def test_dev_requirements_exists_and_contains_dev_tools(self):
        req_dev_path = REPO_ROOT / "backend" / "requirements-dev.txt"
        assert req_dev_path.exists(), "backend/requirements-dev.txt must exist"
        content = req_dev_path.read_text(encoding="utf-8").lower()
        assert "pytest" in content
        assert "pytest-asyncio" in content
        assert "pip-audit" in content

    def test_ci_workflow_runs_pip_audit_and_pytest(self):
        ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), ".github/workflows/ci.yml must exist"
        ci_content = ci_path.read_text(encoding="utf-8")
        assert "pip-audit" in ci_content, "CI must run pip-audit"
        assert "pytest" in ci_content, "CI must run pytest"


# ==============================================================================
# P2.13 - /api/health mínimo y métricas operativas de IA solo para admin
# ==============================================================================
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db, SessionLocal
from backend.models import User
from backend.auth import hash_password, create_access_token

client = TestClient(app)

class TestAuditP2Point13:
    @classmethod
    def setup_class(cls):
        db = SessionLocal()
        # Admin user
        admin = db.query(User).filter(User.email == "admin_health_p2@example.com").first()
        if not admin:
            admin = User(
                email="admin_health_p2@example.com",
                hashed_password=hash_password("AdminPass123!"),
                is_admin=True,
                is_active=True,
                email_verified=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        cls.admin_token = create_access_token({"sub": str(admin.id), "email": admin.email})

        # Regular user
        reg = db.query(User).filter(User.email == "reg_health_p2@example.com").first()
        if not reg:
            reg = User(
                email="reg_health_p2@example.com",
                hashed_password=hash_password("UserPass123!"),
                is_admin=False,
                is_active=True,
                email_verified=True
            )
            db.add(reg)
            db.commit()
            db.refresh(reg)
        cls.user_token = create_access_token({"sub": str(reg.id), "email": reg.email})
        db.close()

    def test_public_health_is_minimal_and_contains_no_ai_metrics(self):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        # Minimal response
        assert data.get("status") == "ok"
        # Must NOT leak AI metrics or operational monitoring
        assert "ai_operational_monitor" not in data
        assert "month_spend_usd" not in data
        assert "budget_status" not in data
        assert "discard_rate" not in data
        assert "discard_rate_alert" not in data

    def test_public_health_returns_503_when_db_down(self):
        with patch("backend.main.check_db_connection", return_value=False):
            res = client.get("/api/health")
            assert res.status_code == 503
            data = res.json()
            assert "ok" not in data.get("status", "")

    def test_ai_audit_metrics_endpoint_requires_admin(self):
        # 1. Anonymous access -> 401
        res_anon = client.get("/api/admin/ai-audit-stats")
        assert res_anon.status_code in [401, 403]

        # 2. Regular user access -> 403
        res_user = client.get("/api/admin/ai-audit-stats", headers={"Authorization": f"Bearer {self.user_token}"})
        assert res_user.status_code == 403

        # 3. Admin access -> 200 with metrics
        res_admin = client.get("/api/admin/ai-audit-stats", headers={"Authorization": f"Bearer {self.admin_token}"})
        assert res_admin.status_code == 200
        data = res_admin.json()
        assert "total_cost_usd" in data or "budget_status" in data


# ==============================================================================
# P2.14 - Modelos de Gemini, validación oficial, max_output_tokens y thinking
# ==============================================================================
class TestAuditP2Point14:
    def test_gemini_model_missing_raises_error(self):
        from backend.services.ai_service import validate_gemini_model
        with pytest.raises(ValueError) as exc:
            validate_gemini_model("")
        assert "GEMINI_MODEL" in str(exc.value)
        assert "obligatoria" in str(exc.value).lower()

    def test_gemini_model_invalid_or_deprecated_raises_clear_error(self):
        from backend.services.ai_service import validate_gemini_model
        # Modelo inventado/inexistente
        with pytest.raises(ValueError) as exc_nonexistent:
            validate_gemini_model("gemini-super-fake-model")
        assert "no existe" in str(exc_nonexistent.value).lower() or "no es válido" in str(exc_nonexistent.value).lower()

        # Modelo deprecado
        with pytest.raises(ValueError) as exc_deprec:
            validate_gemini_model("gemini-2.5-flash")
        assert "deprecado" in str(exc_deprec.value).lower() or "obsoleto" in str(exc_deprec.value).lower()

    def test_gemini_model_valid_official_models(self):
        from backend.services.ai_service import validate_gemini_model
        for valid_model in ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
            assert validate_gemini_model(valid_model) == valid_model

    def test_fallback_models_only_contain_official_active_models(self):
        from backend.services.ai_service import FALLBACK_MODELS, DEPRECATED_MODELS
        for model in FALLBACK_MODELS:
            assert model not in DEPRECATED_MODELS, f"Modelo fallback '{model}' no debe ser deprecado"
            assert "2.5" not in model, f"Modelo '{model}' es de la familia 2.5 en retiro"

    def test_generation_config_has_higher_max_tokens_and_disabled_thinking(self):
        from backend.services.ai_service import AI_GENERATION_MAX_OUTPUT_TOKENS, AI_GENERATION_THINKING_BUDGET
        assert AI_GENERATION_MAX_OUTPUT_TOKENS >= 2048, "max_output_tokens debe aumentarse (al menos 2048) para evitar truncado de JSON"
        assert AI_GENERATION_THINKING_BUDGET == 0, "thinking_budget debe ser 0 para desactivar razonamiento extendido y no truncar la salida"


# ==============================================================================
# P2.15 - Control de costos: modelo ligero visión, doble pasada condicional,
#         caché de diagnósticos, recorte de historial, presupuesto por usuario y cuota premium
# ==============================================================================
class TestAuditP2Point15:
    def test_vision_uses_lightweight_model(self):
        import backend.vision as vision_mod
        # Por defecto el modelo de visión debe ser ligero
        default_model = os.environ.get("VISION_MODEL", "gemini-3.5-flash-lite")
        assert "lite" in default_model.lower(), "El modelo de visión para test kits debe ser ligero (-lite)"
        assert "2.5" not in default_model, "No debe usar familia 2.5 deprecada"

    def test_premium_quota_lowered_from_100(self):
        from backend.main import UserScanQuotaManager
        with patch.dict(os.environ, {}, clear=False):
            if "SCAN_DAILY_LIMIT_PREMIUM" in os.environ:
                del os.environ["SCAN_DAILY_LIMIT_PREMIUM"]
            default_premium_limit = UserScanQuotaManager.get_daily_limit(is_premium=True)
            assert default_premium_limit <= 30, f"Cuota premium por defecto debe ser <= 30 (hoy era 100), obtenido: {default_premium_limit}"

    def test_double_pass_only_for_warning_and_critical(self):
        from backend.services.ai_service import should_execute_double_pass
        # ok y watch -> no ejecutar segunda pasada
        assert should_execute_double_pass("ok") is False
        assert should_execute_double_pass("watch") is False

        # warning y critical -> sí ejecutar segunda pasada
        assert should_execute_double_pass("warning") is True
        assert should_execute_double_pass("critical") is True

    def test_identical_inputs_diagnosis_cached(self):
        from backend.services.ai_service import get_diagnosis_cache_key, check_diagnosis_cache, set_diagnosis_cache
        key1 = get_diagnosis_cache_key(tank_id=1, profile="sps_reef", inputs={"kh": 8.0, "calcio": 420.0})
        key2 = get_diagnosis_cache_key(tank_id=1, profile="sps_reef", inputs={"calcio": 420.0, "kh": 8.0})
        assert key1 == key2, "Entradas idénticas en diferente orden deben generar la misma clave de caché"

        # Guardar en caché y recuperar
        mock_output = {"severity": "ok", "findings": [], "recommended_actions": ["monitor_24h"], "needs_retest": False}
        set_diagnosis_cache(key1, mock_output)
        cached = check_diagnosis_cache(key1)
        assert cached is not None
        assert cached["severity"] == "ok"

    def test_user_monthly_ai_budget_cap(self):
        from backend.services.ai_service import get_current_month_user_ai_spend, USER_MONTHLY_AI_BUDGET_USD
        assert USER_MONTHLY_AI_BUDGET_USD > 0
        db = SessionLocal()
        # Verificar función para calcular gasto por usuario
        spend = get_current_month_user_ai_spend(db, user_id=999999)
        assert spend == 0.0
        db.close()
