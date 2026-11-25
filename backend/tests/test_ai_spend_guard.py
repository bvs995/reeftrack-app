"""
Tope de gasto en Gemini: el escaneo con cámara cuenta para el presupuesto y se detiene al
alcanzarlo, y el costo estimado suma todas las llamadas y los tokens de razonamiento.
"""
import time
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, scan_quota_manager, auth_attempts
from backend.database import SessionLocal
from backend.models import DiagnosticAudit
from backend.services.ai_service import (
    VISION_AUDIT_STATUS,
    estimate_gemini_cost,
    record_diagnostic_audit,
)
from backend.vision import ScanMeasurementResponse

client = TestClient(app)
TINY_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _fake_response(prompt=0, candidates=0, thoughts=0):
    return SimpleNamespace(usage_metadata=SimpleNamespace(
        prompt_token_count=prompt, candidates_token_count=candidates, thoughts_token_count=thoughts,
    ))


def _register():
    auth_attempts.clear()
    email = f"spend_{time.time_ns()}@example.test"
    res = client.post("/api/auth/register", json={"email": email, "password": "Prueba#2026x", "full_name": "Spend"})
    assert res.status_code == 201, res.text
    return res.json()["access_token"], res.json()["user"]["id"]


def test_cost_sums_all_calls_and_thinking_tokens():
    with patch.dict("os.environ", {"GEMINI_PRICE_INPUT_PER_M": "1.0", "GEMINI_PRICE_OUTPUT_PER_M": "10.0"}):
        tin, tout, cost = estimate_gemini_cost(
            _fake_response(prompt=1_000_000, candidates=100_000, thoughts=100_000),
            _fake_response(prompt=500_000, candidates=0, thoughts=0),
            None,  # segunda pasada no ejecutada
        )
    assert (tin, tout) == (1_500_000, 200_000)
    assert cost == 1.5 + 2.0


def test_scan_blocked_when_monthly_budget_reached_without_consuming_quota():
    scan_quota_manager.reset_for_tests()
    token, user_id = _register()
    db = SessionLocal()
    try:
        record_diagnostic_audit(db=db, user_id=user_id, tank_id=None, prompt_version="test", inputs={},
                                rules_alerts=[], raw_ai_output=None, status="accepted", cost_usd=0.05)
    finally:
        db.close()

    with patch.dict("os.environ", {"GEMINI_MONTHLY_BUDGET_USD": "0.01"}), \
         patch("backend.routers.measurements.analyze_test_image") as gemini:
        res = client.post("/api/scan-measurement", json={"image_base64": TINY_PNG},
                          headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is False and body["status"] == "budget_exceeded"
    gemini.assert_not_called()  # no se llamó a Gemini
    quota = client.get("/api/scan-quota", headers={"Authorization": f"Bearer {token}"}).json()
    assert quota["remaining_today"] == quota["daily_quota"]  # no se gastó cuota


def test_scan_records_its_cost_for_the_budget():
    scan_quota_manager.reset_for_tests()
    token, user_id = _register()

    def fake_analyze(**kwargs):
        kwargs["usage_sink"]["response"] = _fake_response(prompt=2000, candidates=100, thoughts=50)
        kwargs["usage_sink"]["model"] = "gemini-test"
        return ScanMeasurementResponse(success=True, api_key_configured=True, parameter="kh", value=8.1, message="ok")

    with patch.dict("os.environ", {"GEMINI_MONTHLY_BUDGET_USD": "100000", "USER_MONTHLY_AI_BUDGET_USD": "100000"}), \
         patch("backend.routers.measurements.analyze_test_image", side_effect=fake_analyze):
        res = client.post("/api/scan-measurement", json={"image_base64": TINY_PNG},
                          headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        audit = db.query(DiagnosticAudit).filter(
            DiagnosticAudit.user_id == user_id, DiagnosticAudit.status == VISION_AUDIT_STATUS
        ).one()
        assert audit.cost_usd > 0
        assert audit.token_count == 2150
        assert audit.prompt_version == "vision:gemini-test"
    finally:
        db.close()
