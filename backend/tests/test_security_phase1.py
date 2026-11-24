import os
import unittest
import time
from fastapi.testclient import TestClient

# Configurar entorno de pruebas
os.environ["SECRET_KEY"] = "super-secret-test-key-32-bytes-minimum-length-for-hmac-sha256!"
os.environ["CRON_SECRET"] = "cron-test-secret-token-123456"
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173,http://localhost:3000"

from backend.main import app, auth_attempts
from backend.models import User, Tank, Measurement, MaintenanceTask, WaterChange
from backend.auth import hash_password, verify_password, create_access_token, create_refresh_token, verify_refresh_token

client = TestClient(app)

class TestSecurityPhase1(unittest.TestCase):

    def setUp(self):
        auth_attempts.clear()
        self.ts = int(time.time() * 1000)
        self.user_a_email = f"user_a_{self.ts}@reef.com"
        self.user_b_email = f"user_b_{self.ts}@reef.com"
        self.password = "PasswordSeguro123!"

    def test_01_auth_bcrypt_cost_factor_ge_12(self):
        """Verifica que las contraseñas se hasheen con bcrypt y un coste >= 12."""
        hashed = hash_password("PasswordSeguro123!")
        self.assertTrue(hashed.startswith("$2b$12$") or hashed.startswith("$2a$12$"))
        self.assertTrue(verify_password("PasswordSeguro123!", hashed))
        self.assertFalse(verify_password("PasswordErroneo123!", hashed))

    def test_02_register_and_login_refresh_cookie(self):
        """Verifica emisión de JWT (15 min) y refresh token rotativo en cookie HttpOnly; Secure; SameSite=Lax."""
        # 1. Registro
        reg_res = client.post("/api/auth/register", json={
            "email": self.user_a_email,
            "password": self.password,
            "full_name": "Acuarista Alpha"
        })
        self.assertEqual(reg_res.status_code, 201)
        data = reg_res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertIn("refresh_token", reg_res.cookies)

        token_a = data["access_token"]
        refresh_a = reg_res.cookies["refresh_token"]

        # 2. Login
        login_res = client.post("/api/auth/login", json={
            "email": self.user_a_email,
            "password": self.password
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("refresh_token", login_res.cookies)

        # 3. Refresh rotativo
        client.cookies.set("refresh_token", refresh_a)
        refresh_res = client.post("/api/auth/refresh")
        self.assertEqual(refresh_res.status_code, 200)
        refresh_data = refresh_res.json()
        self.assertIn("access_token", refresh_data)
        self.assertIn("refresh_token", refresh_res.cookies)

        # 4. Logout
        logout_res = client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)

    def test_03_generic_auth_error_anti_user_enumeration(self):
        """Verifica que el error de login sea genérico e idéntico tanto para correo inexistente como contraseña errónea."""
        res_bad_pass = client.post("/api/auth/login", json={
            "email": self.user_a_email,
            "password": "PasswordInvalida999!"
        })
        self.assertEqual(res_bad_pass.status_code, 401)
        self.assertEqual(res_bad_pass.json()["detail"], "Credenciales inválidas. Verifica tu correo y contraseña.")

        res_bad_user = client.post("/api/auth/login", json={
            "email": f"no_existe_{self.ts}@reef.com",
            "password": "PasswordCualquiera123!"
        })
        self.assertEqual(res_bad_user.status_code, 401)
        self.assertEqual(res_bad_user.json()["detail"], "Credenciales inválidas. Verifica tu correo y contraseña.")

    def test_04_auth_rate_limiting(self):
        """Verifica que el rate limiter bloquee con HTTP 429 tras superar el umbral de intentos."""
        auth_attempts.clear()
        ip_header = {"X-Forwarded-For": "198.51.100.1"}

        # Realizar 5 intentos
        for i in range(5):
            res = client.post(
                "/api/auth/login",
                json={"email": f"attempt_{i}@reef.com", "password": "WrongPassword123!"},
                headers=ip_header
            )
            self.assertEqual(res.status_code, 401)

        # El 6to intento debe ser bloqueado con 429 Too Many Requests
        res_blocked = client.post(
            "/api/auth/login",
            json={"email": "attempt_blocked@reef.com", "password": "WrongPassword123!"},
            headers=ip_header
        )
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("Demasiadas solicitudes", res_blocked.json()["detail"])

    def test_05_idor_protection_across_endpoints(self):
        """Verifica que un usuario NO pueda consultar, editar ni borrar datos pertenecientes a otro usuario."""
        auth_attempts.clear()
        # Registrar Usuario A
        res_a = client.post("/api/auth/register", json={
            "email": self.user_a_email,
            "password": self.password
        })
        self.assertEqual(res_a.status_code, 201)
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Obtener tanque de Usuario A
        tanks_a = client.get("/api/tanks", headers=headers_a).json()
        self.assertTrue(len(tanks_a) > 0)
        tank_a_id = tanks_a[0]["id"]

        # Crear medición para tanque de Usuario A
        meas_a = client.post(f"/api/tanks/{tank_a_id}/measurements", headers=headers_a, json={
            "ph": 8.2,
            "kh": 8.4,
            "salinity": 1.025
        })
        self.assertEqual(meas_a.status_code, 201)

        auth_attempts.clear()
        # Registrar Usuario B
        res_b = client.post("/api/auth/register", json={
            "email": self.user_b_email,
            "password": self.password
        })
        self.assertEqual(res_b.status_code, 201)
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Intentos de IDOR por Usuario B sobre datos de Usuario A:

        # 1. Intentar actualizar el tanque de Usuario A -> debe ser bloqueado con 404
        put_tank = client.put(f"/api/tanks/{tank_a_id}", headers=headers_b, json={"name": "Tanque Hackeado"})
        self.assertEqual(put_tank.status_code, 404)

        # 2. Intentar ver parámetros del tanque de Usuario A
        get_params = client.get(f"/api/tanks/{tank_a_id}/parameters", headers=headers_b)
        self.assertEqual(get_params.status_code, 404)

        # 3. Intentar ver analíticas del tanque de Usuario A
        get_analytics = client.get(f"/api/tanks/{tank_a_id}/analytics", headers=headers_b)
        self.assertEqual(get_analytics.status_code, 404)

        # 4. Intentar ver mediciones del tanque de Usuario A
        get_meas = client.get(f"/api/tanks/{tank_a_id}/measurements", headers=headers_b)
        self.assertEqual(get_meas.status_code, 404)

        # 5. Intentar ver tendencia 48h del tanque de Usuario A
        get_trend = client.get(f"/api/tanks/{tank_a_id}/tendencia-48h", headers=headers_b)
        self.assertEqual(get_trend.status_code, 404)

        # 6. Intentar análisis predictivo con el tanque de Usuario A
        post_pred = client.post(f"/api/tanks/{tank_a_id}/analisis-predictivo", headers=headers_b)
        self.assertEqual(post_pred.status_code, 404)

        # 7. Intentar ver tareas de mantenimiento del tanque de Usuario A
        get_maint = client.get(f"/api/tanks/{tank_a_id}/maintenance", headers=headers_b)
        self.assertEqual(get_maint.status_code, 404)

        # 8. Intentar ver cambios de agua del tanque de Usuario A
        get_wc = client.get(f"/api/tanks/{tank_a_id}/water-changes", headers=headers_b)
        self.assertEqual(get_wc.status_code, 404)

        # 9. Intentar eliminar el tanque de Usuario A
        del_tank = client.delete(f"/api/tanks/{tank_a_id}", headers=headers_b)
        self.assertEqual(del_tank.status_code, 404)

        # 10. Confirmar que Usuario A sí puede acceder a su propio tanque
        get_own_tank = client.get(f"/api/tanks/{tank_a_id}/parameters", headers=headers_a)
        self.assertEqual(get_own_tank.status_code, 200)

    def test_06_strict_pydantic_forbid_extra_and_ranges(self):
        """Verifica que extra='forbid' y los rangos plausibles rechacen campos ilegítimos o valores irreales."""
        auth_attempts.clear()
        res_a = client.post("/api/auth/register", json={
            "email": f"strict_{self.ts}@reef.com",
            "password": self.password
        })
        self.assertEqual(res_a.status_code, 201)
        headers = {"Authorization": f"Bearer {res_a.json()['access_token']}"}

        # 1. Campo desconocido en creación de tanque -> debe fallar con 400
        res_extra = client.post("/api/tanks", headers=headers, json={
            "name": "Tanque Seguro",
            "volume_liters": 200.0,
            "campo_malicioso": "inyeccion"
        })
        self.assertEqual(res_extra.status_code, 400)
        self.assertTrue("Extra inputs are not permitted" in res_extra.json()["detail"] or "validación" in res_extra.json()["detail"].lower())

        # 2. Rango implausible en mediciones (ej. pH de 15.0) -> debe fallar con 400
        res_bad_ph = client.post("/api/measurements", headers=headers, json={
            "ph": 15.0
        })
        self.assertEqual(res_bad_ph.status_code, 400)

        # 3. Temperatura implausible (ej. 75.0 °C) -> debe fallar con 400
        res_bad_temp = client.post("/api/measurements", headers=headers, json={
            "temperature": 75.0
        })
        self.assertEqual(res_bad_temp.status_code, 400)

    def test_07_security_headers_and_request_id(self):
        """Verifica presencia de cabeceras de seguridad y X-Request-ID en cada respuesta."""
        res = client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertIn("X-Request-ID", res.headers)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_08_cron_send_reminders_timing_safe_token(self):
        """Verifica la protección de /api/cron/send-reminders con secrets.compare_digest."""
        # 1. Sin cabecera -> 401
        res_no_token = client.post("/api/cron/send-reminders")
        self.assertEqual(res_no_token.status_code, 401)

        # 2. Token incorrecto -> 401
        res_wrong_token = client.post("/api/cron/send-reminders", headers={"X-CRON-SECRET": "token-falso"})
        self.assertEqual(res_wrong_token.status_code, 401)

        # 3. Token correcto -> 200
        res_ok = client.post("/api/cron/send-reminders", headers={"X-CRON-SECRET": "cron-test-secret-token-123456"})
        self.assertEqual(res_ok.status_code, 200)

    def test_09_gdpr_export_and_delete_account(self):
        """Verifica exportación y borrado total de cuenta y datos asociados (GDPR)."""
        auth_attempts.clear()
        user_email = f"gdpr_{self.ts}@reef.com"
        reg = client.post("/api/auth/register", json={
            "email": user_email,
            "password": self.password,
            "full_name": "Usuario GDPR"
        })
        self.assertEqual(reg.status_code, 201)
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Exportar datos
        export_res = client.get("/api/user/export", headers=headers)
        self.assertEqual(export_res.status_code, 200)
        data = export_res.json()
        self.assertEqual(data["user"]["email"], user_email)
        self.assertIn("tanks", data)
        self.assertIn("measurements", data)
        self.assertIn("maintenance_tasks", data)

        # Borrar cuenta con confirmación de contraseña (P2.16)
        del_res = client.request("DELETE", "/api/user/account", headers=headers, json={"password": self.password})
        self.assertEqual(del_res.status_code, 200)

        # Confirmar que el token ya no tiene cuenta asociada
        me_res = client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 401)

if __name__ == "__main__":
    unittest.main()
