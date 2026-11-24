import os
import unittest
import time
import math
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

# Configuración de variables de entorno para tests
os.environ["SECRET_KEY"] = "super-secret-test-key-32-bytes-minimum-length-for-hmac-sha256!"
os.environ["CRON_SECRET"] = "cron-test-secret-token-123456"
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173,http://localhost:3000"

from backend.main import app, auth_attempts
from backend.uncertainty import (
    DEFAULT_MEASUREMENT_ERRORS,
    KIT_CATALOG_SPECS,
    MeasurementInterval,
    get_kit_error_for_parameter,
    calculate_measurement_uncertainty,
    evaluate_parameter_with_interval,
    evaluate_delta_24h_uncertainty,
    calculate_safe_correction,
    coordinate_chemical_corrections,
    project_trend_with_uncertainty,
    normalize_param_key
)
from backend.models import Tank, Measurement
from backend.database import SessionLocal

client = TestClient(app)


class TestUncertaintyPhase3(unittest.TestCase):

    def setUp(self):
        auth_attempts.clear()
        self.ts = int(time.time() * 1000)
        self.user_email = f"uncertainty_{self.ts}@reeftrack.com"
        self.password = "PasswordSeguro123!"

        # Registrar usuario y obtener token
        reg_res = client.post("/api/auth/register", json={
            "email": self.user_email,
            "password": self.password,
            "full_name": "Dr. Metrología Marina"
        })
        self.assertEqual(reg_res.status_code, 201)
        self.token = reg_res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Obtener el tanque creado automáticamente en el registro
        tanks_res = client.get("/api/tanks", headers=self.headers)
        self.assertEqual(tanks_res.status_code, 200)
        tanks_list = tanks_res.json()
        self.assertTrue(len(tanks_list) > 0)
        self.tank_id = tanks_list[0]["id"]

        # Configurar perfil SPS Reef para el tanque
        client.put(f"/api/tanks/{self.tank_id}", json={
            "name": f"Laboratorio SPS {self.ts}",
            "volume_liters": 300.0,
            "tank_type": "sps_reef",
            "reef_profile": "sps_reef"
        }, headers=self.headers)

    # ==========================================================================
    # 3.1 METROLOGÍA: ERROR BASE POR PARÁMETRO Y CÁMARA
    # ==========================================================================

    def test_3_1_base_errors_and_kit_specs(self):
        """Verifica errores base de fichas técnicas para KH, Ca, Mg, NO3, PO4, Salinidad, Temperatura."""
        # 1. KH base
        e_kh = get_kit_error_for_parameter("kh", 8.0)
        self.assertAlmostEqual(e_kh, 0.3)

        # 2. Ca base
        e_ca = get_kit_error_for_parameter("calcium", 420.0)
        self.assertAlmostEqual(e_ca, 20.0)

        # 3. Mg base
        e_mg = get_kit_error_for_parameter("magnesium", 1350.0)
        self.assertAlmostEqual(e_mg, 50.0)

        # 4. PO4 base
        e_po4 = get_kit_error_for_parameter("phosphate", 0.05)
        self.assertAlmostEqual(e_po4, 0.02)

        # 5. Salinidad base
        e_sal = get_kit_error_for_parameter("salinity", 35.0)
        self.assertAlmostEqual(e_sal, 1.0)

        # 6. Temperatura base
        e_temp = get_kit_error_for_parameter("temperature", 25.5)
        self.assertAlmostEqual(e_temp, 0.5)

        # 7. NO3: regla de 20% o 0.5 ppm (el mayor)
        # Para NO3 bajo (1.0 ppm): 20% es 0.2 ppm < 0.5 -> debe devolver 0.5
        e_no3_low = get_kit_error_for_parameter("nitrate", 1.0)
        self.assertAlmostEqual(e_no3_low, 0.5)

        # Para NO3 alto (10.0 ppm): 20% es 2.0 ppm > 0.5 -> debe devolver 2.0
        e_no3_high = get_kit_error_for_parameter("nitrate", 10.0)
        self.assertAlmostEqual(e_no3_high, 2.0)

        # 8. Kits de fabricantes reconocidos (Hanna, Salifert, Red Sea)
        e_salifert_ca = get_kit_error_for_parameter("calcium", 400.0, kit="Salifert Profi Test")
        self.assertAlmostEqual(e_salifert_ca, 15.0)

        e_redsea_mg = get_kit_error_for_parameter("magnesium", 1300.0, kit="Red Sea Pro")
        self.assertAlmostEqual(e_redsea_mg, 40.0)

    def test_3_1_camera_scan_uncertainty_expansion(self):
        """Verifica que si la medición vino de cámara: e_total = sqrt(e_kit² + e_vision²) con e_vision = 10%."""
        val = 8.0  # KH nominal = 8.0 dKH
        e_kit = 0.3
        e_vision = 0.10 * val  # 0.8 dKH
        expected_total = math.sqrt(e_kit ** 2 + e_vision ** 2)  # sqrt(0.09 + 0.64) = sqrt(0.73) ≈ 0.8544

        # Manual vs Cámara
        interval_manual = calculate_measurement_uncertainty("kh", val, is_camera_scan=False)
        self.assertAlmostEqual(interval_manual.error, 0.3)
        self.assertEqual(interval_manual.min_val, 7.7)
        self.assertEqual(interval_manual.max_val, 8.3)

        interval_cam = calculate_measurement_uncertainty("kh", val, is_camera_scan=True)
        self.assertAlmostEqual(interval_cam.error, round(expected_total, 4), places=3)
        self.assertEqual(interval_cam.is_camera_scan, True)
        self.assertAlmostEqual(interval_cam.min_val, round(val - expected_total, 4), places=3)
        self.assertAlmostEqual(interval_cam.max_val, round(val + expected_total, 4), places=3)

    def test_3_1_detection_limit_nutrients_display(self):
        """Verifica que un valor de 0 en NO3/PO4 se muestra como '< e' y nunca como '0.00' exacto."""
        # PO4 = 0.00
        po4_interval = calculate_measurement_uncertainty("phosphate", 0.0)
        self.assertTrue(po4_interval.is_below_detection_limit)
        self.assertEqual(po4_interval.display_value, "< 0.02")

        # NO3 = 0.00
        no3_interval = calculate_measurement_uncertainty("nitrate", 0.0)
        self.assertTrue(no3_interval.is_below_detection_limit)
        self.assertEqual(no3_interval.display_value, "< 0.50")

        # PO4 con valor medible real
        po4_measurable = calculate_measurement_uncertainty("phosphate", 0.08)
        self.assertFalse(po4_measurable.is_below_detection_limit)
        self.assertEqual(po4_measurable.display_value, "0.08")

    # ==========================================================================
    # 3.2 REGLAS DE ALERTA CON INTERVALOS (CONFIRMADA vs PROBABLE)
    # ==========================================================================

    def test_3_2_interval_alerts_confirmed_vs_probable_upper(self):
        """Verifica alerta confirmada vs probable cuando se cruza el límite superior."""
        safe_max = 9.0  # KH máximo para SPS
        error = 0.3

        # Caso Probable: valor = 9.1, intervalo = [8.8, 9.4].
        # Cruza safe_max (9.4 > 9.0), pero el extremo inferior (8.8) está dentro del rango seguro.
        inter_probable = MeasurementInterval(
            parameter="kh", value=9.1, error=error, min_val=8.8, max_val=9.4, display_value="9.10"
        )
        res_probable = evaluate_parameter_with_interval("kh", inter_probable, safe_min=7.0, safe_max=safe_max)
        self.assertEqual(res_probable.status, "probable")
        self.assertEqual(res_probable.severity, "watch")
        self.assertIn("retest en 1–2 h", res_probable.recommendation)
        self.assertTrue(res_probable.is_alert)

        # Caso Confirmada: valor = 9.6, intervalo = [9.3, 9.9].
        # TODO el intervalo cruza (incluso 9.3 > 9.0).
        inter_confirmed = MeasurementInterval(
            parameter="kh", value=9.6, error=error, min_val=9.3, max_val=9.9, display_value="9.60"
        )
        res_confirmed = evaluate_parameter_with_interval("kh", inter_confirmed, safe_min=7.0, safe_max=safe_max)
        self.assertEqual(res_confirmed.status, "confirmed")
        self.assertIn(res_confirmed.severity, ["warning", "critical"])
        self.assertIn("confirmada", res_confirmed.title.lower())

    def test_3_2_interval_alerts_confirmed_vs_probable_lower(self):
        """Verifica alerta confirmada vs probable cuando se cruza el límite inferior."""
        safe_min = 7.5  # KH mínimo para SPS
        error = 0.3

        # Caso Probable: valor = 7.4, intervalo = [7.1, 7.7].
        # El extremo inferior (7.1) cruza bajo safe_min, pero el superior (7.7) está en rango.
        inter_probable = MeasurementInterval(
            parameter="kh", value=7.4, error=error, min_val=7.1, max_val=7.7, display_value="7.40"
        )
        res_probable = evaluate_parameter_with_interval("kh", inter_probable, safe_min=safe_min, safe_max=9.0)
        self.assertEqual(res_probable.status, "probable")
        self.assertEqual(res_probable.severity, "watch")
        self.assertIn("retest en 1–2 h", res_probable.recommendation)

        # Caso Confirmada: valor = 7.1, intervalo = [6.8, 7.4].
        # TODO el intervalo cruza (incluso el extremo superior 7.4 < 7.5).
        inter_confirmed = MeasurementInterval(
            parameter="kh", value=7.1, error=error, min_val=6.8, max_val=7.4, display_value="7.10"
        )
        res_confirmed = evaluate_parameter_with_interval("kh", inter_confirmed, safe_min=safe_min, safe_max=9.0)
        self.assertEqual(res_confirmed.status, "confirmed")
        self.assertIn(res_confirmed.severity, ["warning", "critical"])

    def test_3_2_delta_24h_uncertainty_propagation(self):
        """Verifica oscilación de KH en 24h con propagación u = sqrt(e1² + e2²)."""
        # Dos mediciones manuales con error e = 0.3
        e1 = 0.3
        e2 = 0.3
        u = math.sqrt(e1 ** 2 + e2 ** 2)  # sqrt(0.18) ≈ 0.4243
        threshold = 0.50

        # Caso 1: Delta = 0.60 dKH (|Δ| = 0.60 > 0.50)
        # Pero |Δ| - u = 0.60 - 0.424 = 0.176 <= 0.50 -> PROBABLE (watch + retest en 1-2 h)
        res_probable = evaluate_delta_24h_uncertainty(prev_val=8.0, prev_error=e1, curr_val=8.6, curr_error=e2, threshold=threshold)
        self.assertEqual(res_probable["status"], "probable")
        self.assertEqual(res_probable["severity"], "watch")
        self.assertIn("retest en 1–2 h", res_probable["recommendation"].lower())

        # Caso 2: Delta = 1.10 dKH (|Δ| = 1.10)
        # |Δ| - u = 1.10 - 0.424 = 0.676 > 0.50 -> CONFIRMADA (critical)
        res_confirmed = evaluate_delta_24h_uncertainty(prev_val=8.0, prev_error=e1, curr_val=9.1, curr_error=e2, threshold=threshold)
        self.assertEqual(res_confirmed["status"], "confirmed")
        self.assertEqual(res_confirmed["severity"], "critical")

        # Caso 3: Delta = 0.20 dKH -> SEGURO
        res_safe = evaluate_delta_24h_uncertainty(prev_val=8.0, prev_error=e1, curr_val=8.2, curr_error=e2, threshold=threshold)
        self.assertEqual(res_safe["status"], "safe")

    # ==========================================================================
    # 3.3 ACCIONES CORRECTORAS ANTI-COLAPSO
    # ==========================================================================

    def test_3_3_no_action_when_correction_less_than_error(self):
        """Si la corrección necesaria es menor que el error -> no actuar: 'dentro del margen de error, repite la prueba'."""
        current_kh = 7.85
        target_kh = 8.0
        error_kh = 0.3  # desviación = 0.15 <= 0.30
        profile_max_daily = 0.5

        action = calculate_safe_correction(
            parameter="kh",
            current_value=current_kh,
            target_value=target_kh,
            error=error_kh,
            profile_max_daily_change=profile_max_daily
        )
        self.assertFalse(action.can_act)
        self.assertEqual(action.status, "no_action_within_error")
        self.assertEqual(action.recommended_today, 0.0)
        self.assertTrue(action.retest_required)
        self.assertIn("dentro del margen de error", action.message.lower())

    def test_3_3_least_correction_and_daily_safe_limit(self):
        """
        Verifica:
        1. Extremo que menos corrige: para subir, usa target - (v + e).
        2. Cambio diario permitido = límite_del_perfil - error.
        3. Retest obligatorio.
        """
        current_kh = 7.0
        target_kh = 8.2
        error_kh = 0.3
        profile_max_daily = 0.5  # SPS máx cambio diario = 0.5 dKH

        # Extremo superior del intervalo es 7.0 + 0.3 = 7.3
        # least_correction = 8.2 - 7.3 = 0.90 dKH
        # daily_allowed = 0.5 - 0.3 = 0.20 dKH
        # recommended_today = min(0.90, 0.20) = 0.20 dKH
        action = calculate_safe_correction(
            parameter="kh",
            current_value=current_kh,
            target_value=target_kh,
            error=error_kh,
            profile_max_daily_change=profile_max_daily
        )
        self.assertTrue(action.can_act)
        self.assertEqual(action.status, "adjust_conservative")
        self.assertAlmostEqual(action.least_correction_needed, 0.90)
        self.assertAlmostEqual(action.daily_allowed_change, 0.20)
        self.assertAlmostEqual(action.recommended_today, 0.20)
        self.assertTrue(action.retest_required)
        self.assertIn("retest obligatorio", action.message.lower())

    def test_3_3_chemical_interactions_priority_mg_kh_ca(self):
        """
        Verifica que nunca se recomiende corregir dos parámetros a la vez si interactúan (KH/Ca/Mg).
        Prioridad estricta: 1º Mg, 2º KH, 3º Ca.
        """
        # Supongamos que Mg, KH y Ca necesitan corrección a la vez
        mg_act = calculate_safe_correction("magnesium", 1200.0, 1350.0, error=50.0, profile_max_daily_change=50.0)
        kh_act = calculate_safe_correction("kh", 6.8, 8.2, error=0.3, profile_max_daily_change=0.5)
        ca_act = calculate_safe_correction("calcium", 380.0, 430.0, error=20.0, profile_max_daily_change=20.0)

        corrections = {
            "magnesium": mg_act,
            "kh": kh_act,
            "calcium": ca_act
        }

        coordinated = coordinate_chemical_corrections(corrections)

        # Solo Mg debe tener can_act=True
        self.assertTrue(coordinated["magnesium"].can_act)
        self.assertEqual(coordinated["magnesium"].status, "adjust_conservative")

        # KH y Ca deben haber sido pausados por interacción química
        self.assertFalse(coordinated["kh"].can_act)
        self.assertEqual(coordinated["kh"].status, "paused_interaction")
        self.assertIn("interacción química", coordinated["kh"].message.lower())
        self.assertEqual(coordinated["kh"].recommended_today, 0.0)

        self.assertFalse(coordinated["calcium"].can_act)
        self.assertEqual(coordinated["calcium"].status, "paused_interaction")
        self.assertIn("interacción química", coordinated["calcium"].message.lower())
        self.assertEqual(coordinated["calcium"].recommended_today, 0.0)

        # Si Mg está en rango y solo compiten KH y Ca -> Gana KH (2º lugar de prioridad)
        corrections_kh_ca = {
            "kh": calculate_safe_correction("kh", 6.8, 8.2, error=0.3, profile_max_daily_change=0.5),
            "calcium": calculate_safe_correction("calcium", 380.0, 430.0, error=20.0, profile_max_daily_change=20.0)
        }
        coordinated_kh_ca = coordinate_chemical_corrections(corrections_kh_ca)
        self.assertTrue(coordinated_kh_ca["kh"].can_act)
        self.assertFalse(coordinated_kh_ca["calcium"].can_act)
        self.assertEqual(coordinated_kh_ca["calcium"].status, "paused_interaction")

    # ==========================================================================
    # 3.4 TENDENCIAS Y PROYECCIONES: R² >= 0.50, BANDA ± Y MIN 3 PUNTOS
    # ==========================================================================

    def test_3_4_projections_require_minimum_3_points(self):
        """Verifica que se exija un mínimo de 3 mediciones para proyectar."""
        points_2 = [(0.0, 8.2), (1.0, 8.0)]
        res = project_trend_with_uncertainty("kh", "dKH", points_2, safe_min=7.5, safe_max=9.0)
        self.assertFalse(res.is_conclusive)
        self.assertEqual(res.status, "insufficient_data")
        self.assertIsNone(res.days_remaining_safe)
        self.assertIn("al menos 3 mediciones", res.message)

    def test_3_4_inconclusive_trend_when_r_squared_below_threshold(self):
        """Si R² < 0.50 -> 'tendencia no concluyente', sin 'días al límite'."""
        # 3 mediciones ruidosas y dispersas
        # (día 0: 8.0, día 1: 8.6, día 2: 7.9)
        noisy_points = [(0.0, 8.0), (1.0, 8.6), (2.0, 7.9)]
        res = project_trend_with_uncertainty("kh", "dKH", noisy_points, safe_min=7.5, safe_max=9.0)
        self.assertFalse(res.is_conclusive)
        self.assertEqual(res.status, "inconclusive_trend")
        self.assertLess(res.r_squared, 0.50)
        self.assertIsNone(res.days_remaining_safe)
        self.assertIsNone(res.estimated_exit_date)
        self.assertIn("no concluyente", res.message.lower())
        self.assertIsNotNone(res.uncertainty_band)

    def test_3_4_conclusive_projection_with_uncertainty_band(self):
        """Regresión lineal consistente (R² >= 0.50) mostrando banda ± y proyección de días restantes."""
        # Consumo lineal consistente: día 0 = 8.5, día 1 = 8.3, día 2 = 8.1
        # slope = -0.2 dKH/día, R² = 1.0
        points = [(0.0, 8.5), (1.0, 8.3), (2.0, 8.1)]
        res = project_trend_with_uncertainty(
            "kh", "dKH", points, safe_min=7.5, safe_max=9.0, latest_error=0.3
        )
        self.assertTrue(res.is_conclusive)
        self.assertGreaterEqual(res.r_squared, 0.95)
        self.assertAlmostEqual(res.slope_per_day, -0.20, places=2)
        # Margen hasta safe_min (7.5): (8.1 - 7.5) / 0.2 = 3.0 días
        self.assertAlmostEqual(res.days_remaining_safe, 3.0, places=1)
        self.assertIsNotNone(res.estimated_exit_date)
        self.assertEqual(res.status, "warning_approaching")
        # Banda de incertidumbre actual
        self.assertEqual(res.uncertainty_band, [7.8, 8.4])

    # ==========================================================================
    # 3.5 ENDPOINT INTEGRATION & PERSISTENCE
    # ==========================================================================

    def test_3_5_measurement_creation_with_kit_and_camera_flag(self):
        """Verifica que el endpoint de mediciones persista `kit` e `is_camera_scan`."""
        meas_res = client.post(f"/api/tanks/{self.tank_id}/measurements", json={
            "alkalinity_dkh": 7.4,
            "calcium_ppm": 390.0,
            "magnesium_ppm": 1220.0,
            "nitrate_ppm": 0.0,
            "phosphate_ppm": 0.0,
            "kit": "Hanna Instruments Checker",
            "is_camera_scan": True,
            "notes": "Escaneo inicial por visión IA"
        }, headers=self.headers)
        self.assertEqual(meas_res.status_code, 201)
        data = meas_res.json()
        self.assertEqual(data["kit"], "Hanna Instruments Checker")
        self.assertEqual(data["is_camera_scan"], True)

    def test_3_5_corrective_actions_endpoint_anti_collapse(self):
        """Verifica el endpoint GET /api/tanks/{tank_id}/corrective-actions con reglas anti-colapso."""
        # 1. Registrar una medición con deficiencia múltiple fuera del error (Mg=1200, KH=6.8, Ca=380)
        client.post(f"/api/tanks/{self.tank_id}/measurements", json={
            "alkalinity_dkh": 6.8,
            "calcium_ppm": 380.0,
            "magnesium_ppm": 1200.0,
            "kit": "Salifert Profi Test",
            "is_camera_scan": False
        }, headers=self.headers)

        # 2. Consultar acciones correctoras
        res = client.get(f"/api/tanks/{self.tank_id}/corrective-actions", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()

        self.assertEqual(body["tank_id"], self.tank_id)
        self.assertEqual(body["water_type"], "sps_reef")
        self.assertIn("actions", body)
        actions = body["actions"]

        # Verificar prioridad de interacción química: Mg debe estar activo, KH y Ca en espera
        self.assertIn("magnesium", actions)
        self.assertIn("kh", actions)
        self.assertIn("calcium", actions)

        self.assertTrue(actions["magnesium"]["can_act"])
        self.assertFalse(actions["kh"]["can_act"])
        self.assertEqual(actions["kh"]["status"], "paused_interaction")
        self.assertFalse(actions["calcium"]["can_act"])
        self.assertEqual(actions["calcium"]["status"], "paused_interaction")

        # Verificar advertencia de anti-colapso en summary
        self.assertIn("interacción química", body["summary"].lower())
        self.assertTrue(body["has_active_corrections"])


if __name__ == "__main__":
    unittest.main()
