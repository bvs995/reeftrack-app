import pytest
import time
from fastapi.testclient import TestClient
from backend.main import app, get_client_ip, scan_quota_manager, auth_attempts
from backend.database import SessionLocal
from backend.models import User, UserDailyQuota, RateLimitRecord, Tank, Measurement
from backend.auth import hash_password, create_access_token

client = TestClient(app)

class TestAuditP1Point7:
    """Tests para Punto 7: Cuotas y rate limits persistentes en BD, compartidos y anti-spoofing IP."""

    def setup_method(self):
        auth_attempts.clear()
        scan_quota_manager.reset_for_tests()
        db = SessionLocal()
        db.query(RateLimitRecord).delete()
        db.query(UserDailyQuota).delete()

        # Limpiar usuarios de prueba anteriores
        for email in ["p1_quota_user@aquapulse.io", "p1_other_user@aquapulse.io"]:
            u = db.query(User).filter(User.email == email).first()
            if u:
                db.delete(u)
        db.commit()

        # Crear usuario de prueba (free tier)
        test_user = User(
            email="p1_quota_user@aquapulse.io",
            hashed_password=hash_password("Password123!"),
            full_name="P1 Quota User",
            subscription_tier="free",
            is_active=True,
            is_admin=False,
            token_version=1
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        # Crear tanque y medición
        test_tank = Tank(
            user_id=test_user.id,
            name="Tanque P1",
            tank_type="sps_reef",
            volume_liters=250.0
        )
        db.add(test_tank)
        db.commit()
        db.refresh(test_tank)

        self.user_id = test_user.id
        self.tank_id = test_tank.id
        self.token = create_access_token({"sub": str(test_user.id), "user_id": test_user.id, "email": test_user.email, "token_version": 1})
        self.headers = {"Authorization": f"Bearer {self.token}"}
        db.close()

    def test_daily_quota_persists_in_db_and_survives_memory_reset(self):
        """La cuota de usuario debe guardarse en la tabla user_daily_quotas y sobrevivir reinicios de memoria."""
        # Consumir 2 operaciones de diagnóstico IA
        payload = {
            "nombre_acuario": "Tanque P1",
            "volumen_litros": 250.0,
            "tipo": "sps_reef",
            "kh": 8.0,
            "calcio": 420.0
        }
        res1 = client.post("/api/analizar-ia", json=payload, headers=self.headers)
        assert res1.status_code == 200
        res2 = client.post("/api/analizar-ia", json=payload, headers=self.headers)
        assert res2.status_code == 200

        # Verificar en base de datos que existe el registro UserDailyQuota con count == 2
        db = SessionLocal()
        quota_rec = db.query(UserDailyQuota).filter(UserDailyQuota.user_id == self.user_id).first()
        assert quota_rec is not None, "Debe existir un registro persistente en UserDailyQuota"
        assert quota_rec.count == 2, f"El contador persistido en BD debe ser 2, obtenido: {quota_rec.count}"

        # Simular reinicio de memoria (vaciar cualquier estructura en RAM)
        if hasattr(scan_quota_manager, "_usage"):
            scan_quota_manager._usage.clear()

        # Consultar la cuota: debe leer el count de la BD
        info = scan_quota_manager.get_quota_info(self.user_id, "free", False)
        assert info["used_today"] == 2, f"Tras limpiar RAM, debe reflejar 2 desde BD: {info}"
        assert info["remaining_today"] == 3
        db.close()

    def test_quota_shared_between_vision_and_ai_diagnosis(self):
        """La cuota diaria (5 en plan free) debe ser compartida entre escaneos y diagnósticos IA."""
        diag_payload = {
            "nombre_acuario": "Tanque P1",
            "volumen_litros": 250.0,
            "tipo": "sps_reef",
            "kh": 8.0
        }

        # 1. Consumir 3 diagnósticos IA
        for _ in range(3):
            r = client.post("/api/analizar-ia", json=diag_payload, headers=self.headers)
            assert r.status_code == 200

        # 2. Consumir 2 diagnósticos predictivos (/api/analisis-predictivo)
        for _ in range(2):
            r = client.post("/api/analisis-predictivo", json=diag_payload, headers=self.headers)
            assert r.status_code == 200

        # En este punto se han consumido 3 + 2 = 5 operaciones (límite del plan free)
        # La 6ta operación debe ser rechazada con 429
        res_exhausted = client.post("/api/analizar-ia", json=diag_payload, headers=self.headers)
        assert res_exhausted.status_code == 429, f"La 6ta llamada debe dar 429 por cuota compartida: {res_exhausted.text}"

    def test_client_ip_spoofing_prevented_untrusted_proxy(self):
        """No debe confiarse en X-Forwarded-For crudo de orígenes no confiables."""
        from unittest.mock import MagicMock
        req = MagicMock()
        req.client.host = "203.0.113.195"  # IP pública externa no confiable
        req.headers = {"X-Forwarded-For": "198.51.100.1"}

        resolved_ip = get_client_ip(req)
        assert resolved_ip == "203.0.113.195", f"Debe rechazar X-Forwarded-For si el peer no es proxy confiable: {resolved_ip}"

        # Si el peer es un proxy local confiable (127.0.0.1)
        req_trusted = MagicMock()
        req_trusted.client.host = "127.0.0.1"
        req_trusted.headers = {"X-Forwarded-For": "198.51.100.1, 10.0.0.1"}
        resolved_trusted = get_client_ip(req_trusted)
        assert resolved_trusted == "198.51.100.1", f"Debe aceptar X-Forwarded-For solo de proxy confiable: {resolved_trusted}"

    def test_auth_rate_limiting_by_email_and_ip_persists_in_db(self):
        """Rate limit de autenticación debe registrarse en BD y limitar tanto por email como por IP."""
        db = SessionLocal()
        # Verificar que RateLimitRecord existe
        records_before = db.query(RateLimitRecord).count()

        # Realizar llamadas de login fallidas consecutivas con un email específico
        for _ in range(5):
            client.post("/api/auth/login", json={"email": "p1_quota_user@aquapulse.io", "password": "WrongPassword123!"})

        # La 6ta con el mismo email debe ser bloqueada con 429
        res_blocked = client.post("/api/auth/login", json={"email": "p1_quota_user@aquapulse.io", "password": "WrongPassword123!"})
        assert res_blocked.status_code == 429, f"Debe bloquear por rate limit de email con 429: {res_blocked.text}"

        # Los eventos deben estar guardados en RateLimitRecord en base de datos
        records_after = db.query(RateLimitRecord).count()
        assert records_after > records_before, "Los intentos de autenticación deben persistirse en RateLimitRecord"
        db.close()
