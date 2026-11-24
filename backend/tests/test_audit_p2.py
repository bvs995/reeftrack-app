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
