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
