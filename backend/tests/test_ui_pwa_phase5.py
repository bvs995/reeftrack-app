import os
import unittest
import time
from pathlib import Path
from fastapi.testclient import TestClient

# Configurar entorno de pruebas
os.environ["SECRET_KEY"] = "super-secret-test-key-32-bytes-minimum-length-for-hmac-sha256!"
os.environ["CRON_SECRET"] = "cron-test-secret-token-123456"
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173,http://localhost:3000"

from backend.main import app, auth_attempts
from backend.ai_validator import AIDiagnosisOutput, validate_and_sanitize_ai_diagnosis
from backend.marine_profiles import MARINE_PROFILES

client = TestClient(app)

class TestUIPWAPhase5(unittest.TestCase):

    def setUp(self):
        auth_attempts.clear()
        self.ts = int(time.time() * 1000)
        self.user_email = f"pwa_user_{self.ts}@aquapulse.com"
        self.other_user_email = f"other_user_{self.ts}@aquapulse.com"
        self.password = "AquaSafe2026!"

        # Crear usuario principal
        reg_res = client.post("/api/auth/register", json={
            "email": self.user_email,
            "password": self.password,
            "full_name": "Usuario PWA"
        })
        self.assertEqual(reg_res.status_code, 201)
        self.token = reg_res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Obtener el tanque inicial creado automáticamente en el registro
        tank_res = client.get("/api/tanks", headers=self.headers)
        self.assertEqual(tank_res.status_code, 200)
        self.tank_id = tank_res.json()[0]["id"]

        # Crear segundo usuario (para pruebas de IDOR en feedback)
        other_reg = client.post("/api/auth/register", json={
            "email": self.other_user_email,
            "password": self.password,
            "full_name": "Otro Usuario"
        })
        self.assertEqual(other_reg.status_code, 201)
        self.other_token = other_reg.json()["access_token"]
        self.other_headers = {"Authorization": f"Bearer {self.other_token}"}

    def test_01_backend_fixed_disclaimer(self):
        """Verifica que el modelo AIDiagnosisOutput y la respuesta contengan el aviso fijo del backend."""
        expected_disclaimer = "Orientativo, generado por IA y puede contener errores. Verifica con un retest."
        
        # 1. Verificación directa en el modelo Pydantic
        output = AIDiagnosisOutput(
            severity="ok",
            overall_confidence=0.9,
            summary="Parámetros estables.",
            findings=[],
            recommended_actions=["monitor_24h"],
            needs_retest=False
        )
        self.assertEqual(output.disclaimer, expected_disclaimer)

        # 2. Verificación mediante endpoint de análisis predictivo
        payload = {
            "nombre_acuario": "Arrecife SPS PWA",
            "volumen_litros": 300,
            "ph": 8.2,
            "kh": 8.0,
            "calcio": 420.0,
            "magnesio": 1320.0,
            "nitrato": 5.0,
            "fosfato": 0.03,
            "salinity": 1.025,
            "temperatura": 25.0,
            "tipo": "sps_reef"
        }
        res = client.post("/api/analisis-predictivo", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("data", data)
        self.assertEqual(data["data"].get("disclaimer"), expected_disclaimer)

    def test_02_marine_profiles_endpoint(self):
        """Verifica que GET /api/marine-profiles devuelva el catálogo oficial con todos los biotipos."""
        res = client.get("/api/marine-profiles")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        profiles = data.get("profiles", [])
        self.assertIsInstance(profiles, list)
        self.assertGreaterEqual(len(profiles), 6)

        profile_ids = [p["id"] for p in profiles]
        expected_profiles = ["sps_reef", "lps_reef", "mixed_reef", "fish_only", "freshwater", "planted"]
        for p_id in expected_profiles:
            self.assertIn(p_id, profile_ids)

        # Comprobar estructura de uno de los perfiles
        sps = next(p for p in profiles if p["id"] == "sps_reef")
        self.assertIn("targets", sps)
        self.assertIn("visible_fields", sps)
        self.assertTrue(sps["visible_fields"]["calcium"])
        self.assertTrue(sps["visible_fields"]["kh"])

    def test_03_diagnostic_feedback_consent_requirement(self):
        """Verifica que el reporte de diagnóstico incorrecto exija consentimiento explícito."""
        endpoint = "/api/diagnostics/feedback"

        # 1. Sin autenticación -> 401
        res = client.post(endpoint, json={
            "tank_id": self.tank_id,
            "diagnosis_summary": "Diagnóstico de prueba",
            "severity": "watch",
            "user_comment": "La IA sugirió dosis incorrecta",
            "consent_given": True
        })
        self.assertEqual(res.status_code, 401)

        # 2. Con autenticación pero SIN consentimiento (consent_given = False) -> 400
        res = client.post(endpoint, json={
            "tank_id": self.tank_id,
            "diagnosis_summary": "Diagnóstico de prueba",
            "severity": "watch",
            "user_comment": "La IA sugirió dosis incorrecta",
            "consent_given": False
        }, headers=self.headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("consentimiento explícito", res.json()["detail"].lower())

        # 3. Con autenticación y consentimiento explícito (consent_given = True) -> 200
        res = client.post(endpoint, json={
            "tank_id": self.tank_id,
            "diagnosis_summary": "Diagnóstico de prueba válido",
            "severity": "warning",
            "user_comment": "Falso positivo en caída de KH",
            "category": "incorrect_diagnosis",
            "consent_given": True
        }, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertTrue(data.get("consent_given"))
        self.assertIsNotNone(data.get("feedback_id"))

        # 4. Anti-IDOR: Intentar enviar reporte con tank_id que pertenece a otro usuario -> 404
        res = client.post(endpoint, json={
            "tank_id": self.tank_id,
            "diagnosis_summary": "Intento de IDOR",
            "severity": "watch",
            "user_comment": "Reportando tanque ajeno",
            "consent_given": True
        }, headers=self.other_headers)
        self.assertEqual(res.status_code, 404)

    def test_04_idempotent_offline_measurements(self):
        """Verifica que el envío duplicado con el mismo client_uuid sea idempotente y no duplique filas."""
        client_uuid = f"offline-sync-uuid-{self.ts}"

        measurement_payload = {
            "tank_id": self.tank_id,
            "temperature": 25.5,
            "ph": 8.25,
            "kh": 8.3,
            "salinity": 1.025,
            "calcium": 430.0,
            "magnesium": 1350.0,
            "nitrate": 4.5,
            "phosphate": 0.03,
            "client_uuid": client_uuid,
            "is_camera_scan": False
        }

        # 1. Primer envío (cuando vuelve la conexión o primer POST)
        res1 = client.post(f"/api/tanks/{self.tank_id}/measurements", json=measurement_payload, headers=self.headers)
        self.assertIn(res1.status_code, [200, 201])
        data1 = res1.json()
        meas_id_1 = data1["id"]
        self.assertEqual(data1.get("client_uuid"), client_uuid)

        # 2. Segundo envío accidental (reintento de sync offline con el mismo client_uuid)
        res2 = client.post(f"/api/tanks/{self.tank_id}/measurements", json=measurement_payload, headers=self.headers)
        self.assertIn(res2.status_code, [200, 201])
        data2 = res2.json()
        meas_id_2 = data2["id"]

        # Debe retornar la misma medición existente sin crear una nueva
        self.assertEqual(meas_id_1, meas_id_2)

        # 3. Verificar en el listado de mediciones del tanque que solo hay 1 registro
        list_res = client.get(f"/api/tanks/{self.tank_id}/measurements", headers=self.headers)
        self.assertEqual(list_res.status_code, 200)
        measurements = list_res.json()
        matching = [m for m in measurements if m.get("client_uuid") == client_uuid]
        self.assertEqual(len(matching), 1)

    def test_05_pwa_security_and_cleanup_audits(self):
        """Verifica que notifications.js haya sido eliminado, que no haya dangerouslySetInnerHTML y que sw.js no cachee /api/."""
        frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"

        # 1. notifications.js DEBE haber sido eliminado
        notifications_js = frontend_dir / "src" / "utils" / "notifications.js"
        self.assertFalse(notifications_js.exists(), "notifications.js debe haber sido eliminado completamente.")

        # 2. sw.js DEBE ignorar y no cachear peticiones a /api/
        sw_js = frontend_dir / "public" / "sw.js"
        self.assertTrue(sw_js.exists(), "sw.js debe existir en public.")
        sw_content = sw_js.read_text(encoding="utf-8")
        self.assertIn("/api", sw_content)
        self.assertTrue(
            "url.pathname.startsWith('/api')" in sw_content or "url.pathname.includes('/api')" in sw_content or "includes('/api/')" in sw_content,
            "sw.js debe excluir explícitamente las rutas /api/ del CacheStorage."
        )

        # 3. Ningún archivo en frontend/src debe tener dangerouslySetInnerHTML
        src_dir = frontend_dir / "src"
        dangerous_occurrences = []
        for file_path in src_dir.rglob("*.jsx"):
            content = file_path.read_text(encoding="utf-8")
            if "dangerouslySetInnerHTML" in content:
                dangerous_occurrences.append(str(file_path))
        for file_path in src_dir.rglob("*.js"):
            content = file_path.read_text(encoding="utf-8")
            if "dangerouslySetInnerHTML" in content:
                dangerous_occurrences.append(str(file_path))

        self.assertEqual(
            dangerous_occurrences,
            [],
            f"No se permite dangerouslySetInnerHTML en el frontend: encontrados en {dangerous_occurrences}"
        )

if __name__ == "__main__":
    unittest.main()
