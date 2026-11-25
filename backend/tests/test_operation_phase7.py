import os
import unittest
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Configurar entorno de pruebas
os.environ["SECRET_KEY"] = "super-secret-test-key-32-bytes-minimum-length-for-hmac-sha256!"
os.environ["CRON_SECRET"] = "cron-test-secret-token-123456"
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173,http://localhost:3000"
os.environ["GEMINI_MONTHLY_BUDGET_USD"] = "20.0"

from backend.main import app, auth_attempts
from backend.models import User, Tank, Measurement, DiagnosticAudit
from backend.database import SessionLocal, DATABASE_URL
from backend.services.ai_service import (
    analizar_parametros_estructurado,
    get_current_month_ai_spend,
    record_diagnostic_audit,
    check_discard_rate_alert,
    get_ai_audit_statistics,
)
from backend.backup import (
    create_database_backup,
    restore_database_backup,
    verify_backup_and_restore_parity
)

client = TestClient(app)

class TestOperationPhase7:
    """
    Suite oficial de pruebas operativas FASE 7:
    - Auditoría por diagnóstico (prompt_version, inputs, rules_alerts, salida cruda, costo, motivo).
    - Alerta si sube la tasa de descarte de IA.
    - Límite de gasto mensual en Gemini.
    - Monitor en /api/health y /api/admin/ai-audit-stats.
    - Backups con restauración probada y paridad de registros.
    - Existencia y validez de SECURITY.md y PRIVACY.md (Play Store).
    - Criterios de aceptación globales.
    """

    @pytest.fixture(autouse=True)
    def setup_session_and_user(self):
        auth_attempts.clear()
        self.email = f"op_user_{os.urandom(4).hex()}@aquapulse.com"
        self.password = "SafeOperation2026!"

        reg_res = client.post("/api/auth/register", json={
            "email": self.email,
            "password": self.password,
            "full_name": "Operador de Sistema"
        })
        assert reg_res.status_code == 201
        self.token = reg_res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        tanks_res = client.get("/api/tanks", headers=self.headers)
        assert tanks_res.status_code == 200
        self.tank_id = tanks_res.json()[0]["id"]
        self.db = SessionLocal()
        yield
        self.db.close()

    # --------------------------------------------------------------------------
    # 1. AUDITORÍA POR DIAGNÓSTICO
    # --------------------------------------------------------------------------
    def test_01_diagnostic_audit_logging_and_fields(self):
        """
        Cada diagnóstico ejecutado debe persistir un registro en DiagnosticAudit con:
        - prompt_version ('v1')
        - inputs y rules_alerts
        - status ('accepted', 'sanitized', 'discarded', 'fallback' o 'budget_exceeded')
        - costo en USD y tokens estimados
        """
        initial_count = self.db.query(DiagnosticAudit).count()

        # Ejecutamos una petición de análisis predictivo
        payload = {
            "tank_id": self.tank_id,
            "nombre_acuario": "Arrecife Operación",
            "volumen_litros": 280.0,
            "ph": 8.2,
            "kh": 8.1,
            "calcio": 420.0,
            "magnesio": 1320.0,
            "nitrato": 5.0,
            "fosfato": 0.04,
            "tipo": "sps_reef"
        }
        res = client.post("/api/analisis-predictivo", json=payload, headers=self.headers)
        assert res.status_code == 200

        # Verificar que se registró una nueva auditoría
        final_count = self.db.query(DiagnosticAudit).count()
        assert final_count > initial_count

        latest_audit = self.db.query(DiagnosticAudit).order_by(DiagnosticAudit.id.desc()).first()
        assert latest_audit is not None
        assert latest_audit.prompt_version == "v1"
        assert latest_audit.inputs is not None
        assert "kh" in latest_audit.inputs
        assert latest_audit.rules_alerts is not None
        assert latest_audit.status in ["accepted", "sanitized", "discarded", "fallback", "budget_exceeded"]
        assert latest_audit.cost_usd >= 0.0
        assert latest_audit.token_count >= 0

    # --------------------------------------------------------------------------
    # 2. ALERTA SI SUBE LA TASA DE DESCARTE DE IA
    # --------------------------------------------------------------------------
    def test_02_discard_rate_alert_trigger(self):
        """
        Si la tasa de descarte de respuestas de la IA supera el umbral crítico (> 25% en la muestra),
        el sistema emite una alerta operativa (discard_rate_alert=True).
        """
        # Limpiar auditorías anteriores o registrar una secuencia de descartes
        for i in range(8):
            record_diagnostic_audit(
                db=self.db,
                user_id=None,
                tank_id=self.tank_id,
                prompt_version="v1",
                inputs={"kh": 8.0},
                rules_alerts=[],
                raw_ai_output="output con dosis no autorizada",
                status="discarded",
                rejection_reason="Prescripción de dosis en ml no permitida",
                cost_usd=0.0001,
                token_count=600
            )

        for i in range(2):
            record_diagnostic_audit(
                db=self.db,
                user_id=None,
                tank_id=self.tank_id,
                prompt_version="v1",
                inputs={"kh": 8.0},
                rules_alerts=[],
                raw_ai_output="output aceptado",
                status="accepted",
                cost_usd=0.0001,
                token_count=600
            )

        stats = get_ai_audit_statistics(self.db, sample_size=10)
        assert stats["total_evaluations"] >= 10
        # 8 descartadas de 10 -> tasa de descarte = 80% > 25%
        assert stats["discard_rate"] >= 0.25
        assert stats["discard_rate_alert"] is True

        # Verificar que /api/health es minimal y no filtra métricas operativas
        health_res = client.get("/api/health")
        assert health_res.status_code == 200
        health_data = health_res.json()
        assert health_data["status"] == "ok"
        assert "ai_operational_monitor" not in health_data

        # Verificar que /api/admin/ai-audit-stats reporta la alerta al administrador
        user = self.db.query(User).filter(User.email == self.email).first()
        user.is_admin = True
        self.db.commit()

        admin_res = client.get("/api/admin/ai-audit-stats", headers=self.headers)
        assert admin_res.status_code == 200
        admin_data = admin_res.json()
        assert admin_data["discard_rate_alert"] is True

    # --------------------------------------------------------------------------
    # 3. LÍMITE DE GASTO EN GEMINI (BUDGET OVERRIDE)
    # --------------------------------------------------------------------------
    def test_03_gemini_spending_budget_limit(self):
        """
        Si el gasto mensual acumulado alcanza o supera GEMINI_MONTHLY_BUDGET_USD,
        las llamadas externas a Gemini se bloquean proactivamente y se retorna diagnóstico por reglas determinísticas.
        """
        # Fijamos un límite bajo para la prueba (ej: 0.05 USD)
        # Clave falsa: el bloqueo por presupuesto ocurre antes de cualquier llamada a Gemini.
        with patch.dict(os.environ, {"GEMINI_MONTHLY_BUDGET_USD": "0.05", "GEMINI_API_KEY": "clave-falsa-solo-pruebas"}):
            # Simulamos gasto previo de 0.06 USD en auditoría
            record_diagnostic_audit(
                db=self.db,
                user_id=None,
                tank_id=self.tank_id,
                prompt_version="v1",
                inputs={"kh": 8.0},
                rules_alerts=[],
                raw_ai_output=None,
                status="accepted",
                cost_usd=0.06,  # Supera los 0.05 USD
                token_count=1000
            )

            current_spend = get_current_month_ai_spend(self.db)
            assert current_spend >= 0.05

            payload = {
                "nombre_acuario": "Tanque Presupuesto Excedido",
                "volumen_litros": 200.0,
                "ph": 8.2,
                "kh": 8.0,
                "calcio": 420.0,
                "tipo": "sps_reef"
            }

            # La petición al endpoint debe responder con 200 OK determinístico (sin error 500)
            res = client.post("/api/analisis-predictivo", json=payload, headers=self.headers)
            assert res.status_code == 200
            data = res.json()["data"]
            assert data.get("disclaimer") is not None
            assert data["severity"] in ["ok", "watch", "warning", "critical"]

            # Comprobar que la última auditoría registró status 'budget_exceeded'
            latest = self.db.query(DiagnosticAudit).order_by(DiagnosticAudit.id.desc()).first()
            assert latest.status == "budget_exceeded"
            assert "presupuesto" in latest.rejection_reason.lower() or "límite" in latest.rejection_reason.lower()

    # --------------------------------------------------------------------------
    # 4. MONITOR EN /api/health
    # --------------------------------------------------------------------------
    def test_04_health_monitor_endpoint_structure(self):
        """
        /api/health debe ser minimal (P2.13):
        - Estado de base de datos
        - Sin métricas operativas de IA (éstas se exponen en /api/admin/ai-audit-stats).
        """
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "database" in data
        assert data["database"] == "connected"
        assert "ai_operational_monitor" not in data

    # --------------------------------------------------------------------------
    # 5. BACKUPS CON RESTAURACIÓN PROBADA Y PARIDAD
    # --------------------------------------------------------------------------
    def test_05_backup_creation_restoration_and_parity(self):
        """
        Comprueba que el sistema sea capaz de generar un respaldo de la base de datos actual,
        restaurarlo en una base de datos de contingencia y verificar que el conteo de filas coincida al 100%.
        """
        temp_backup = "/tmp/test_phase7_backup.sql"
        temp_restored_db = "/tmp/test_phase7_restored.db"

        if os.path.exists(temp_backup):
            os.remove(temp_backup)
        if os.path.exists(temp_restored_db):
            os.remove(temp_restored_db)

        # 1. Crear respaldo
        backup_file = create_database_backup(db_url=DATABASE_URL, output_file=temp_backup)
        assert os.path.exists(backup_file)
        assert os.path.getsize(backup_file) > 0

        # 2. Restaurar en destino temporal
        target_url = f"sqlite:///{temp_restored_db}"
        restored_ok = restore_database_backup(backup_file, target_url)
        assert restored_ok is True
        assert os.path.exists(temp_restored_db)

        # 3. Comprobar paridad
        parity_result = verify_backup_and_restore_parity(DATABASE_URL, target_url)
        assert parity_result["is_parity"] is True, f"Discrepancia en restauración: {parity_result['tables']}"

        # 4. Limpieza
        if os.path.exists(temp_backup):
            os.remove(temp_backup)
        if os.path.exists(temp_restored_db):
            os.remove(temp_restored_db)

    # --------------------------------------------------------------------------
    # 6. ARCHIVOS DE POLÍTICA: SECURITY.md Y PRIVACY.md (PLAY STORE)
    # --------------------------------------------------------------------------
    def test_06_security_and_privacy_policies_exist_and_valid(self):
        """
        Verifica la presencia y contenido completo de SECURITY.md y PRIVACY.md en la raíz del repositorio.
        """
        project_root = Path(__file__).resolve().parent.parent.parent

        security_md = project_root / "SECURITY.md"
        assert security_md.exists(), "SECURITY.md debe existir en la raíz del repositorio."
        sec_content = security_md.read_text(encoding="utf-8")
        assert "IDOR" in sec_content
        assert "SECRET_KEY" in sec_content
        assert "bcrypt" in sec_content
        assert "retest" in sec_content
        assert "catálogo cerrado" in sec_content.lower()

        privacy_md = project_root / "PRIVACY.md"
        assert privacy_md.exists(), "PRIVACY.md debe existir en la raíz del repositorio (Play Store)."
        priv_content = privacy_md.read_text(encoding="utf-8")
        assert "Política de Privacidad" in priv_content
        assert "EXIF" in priv_content
        assert "borrador" in priv_content.lower()
        assert "GDPR" in priv_content or "derechos" in priv_content.lower()
        assert "delete" in priv_content.lower()
