"""
Perfiles bioquímicos y motor de evaluación para acuarios marinos y de arrecife en AquaPulse.
Soporta:
1. fowlr_soft: Solo Peces / Corales Blandos
2. lps_reef: Arrecife LPS (Pólipo Largo)
3. sps_reef: Arrecife SPS (Pólipo Corto)
"""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

MARINE_PROFILES: Dict[str, Dict[str, Any]] = {
    "fowlr_soft": {
        "id": "fowlr_soft",
        "name": "Solo Peces / Corales Blandos",
        "short_name": "Peces / Blandos",
        "description": "Acuarios marinos solo con peces o corales blandos resistentes (Zoanthus, Sarcophyton, Discosomas).",
        "environment": {
            "par_min": 50,
            "par_max": 100,
            "flow_profile": "low_moderate",
            "flow_label": "Bajo a moderado"
        },
        "targets": {
            "salinity": {"min": 1.023, "max": 1.025, "unit": "SG", "step": 0.001, "name": "Salinidad"},
            "temperature": {"min": 24.0, "max": 26.0, "unit": "°C", "step": 0.1, "name": "Temperatura"},
            "ph": {"min": 8.0, "max": 8.3, "unit": "pH", "step": 0.01, "name": "pH"},
            "ammonia": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Amoníaco (NH3)"},
            "nitrite": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Nitrito (NO2)"},
            "kh": {"min": 7.0, "max": 10.0, "unit": "dKH", "step": 0.1, "max_daily_delta": 1.0, "name": "Alcalinidad (KH)"},
            "calcium": {"min": 380.0, "max": 420.0, "unit": "ppm", "step": 1.0, "name": "Calcio (Ca)"},
            "magnesium": {"min": 1250.0, "max": 1350.0, "unit": "ppm", "step": 1.0, "name": "Magnesio (Mg)"},
            "nitrate": {"min": 5.0, "max": 20.0, "unit": "ppm", "step": 0.1, "alert_on_zero": False, "name": "Nitrato (NO3)"},
            "phosphate": {"min": 0.03, "max": 0.15, "unit": "ppm", "step": 0.001, "alert_on_zero": False, "recommend_photometer": False, "name": "Fosfato (PO4)"}
        },
        "trace_elements": {}
    },

    "lps_reef": {
        "id": "lps_reef",
        "name": "Arrecife LPS (Pólipo Largo)",
        "short_name": "Arrecife LPS",
        "description": "Corales de pólipo largo (Euphyllias, Acanthastreas, Trachyphyllias, Duncans). Requieren nutrientes detectables y flujo indirecto.",
        "environment": {
            "par_min": 100,
            "par_max": 200,
            "flow_profile": "moderate_indirect",
            "flow_label": "Moderado e indirecto",
            "flow_warning": "Un chorro directo puede rasgar o desprender el tejido carnoso del coral."
        },
        "targets": {
            "salinity": {"min": 1.025, "max": 1.026, "unit": "SG", "step": 0.001, "name": "Salinidad"},
            "temperature": {"min": 24.5, "max": 25.5, "unit": "°C", "step": 0.1, "name": "Temperatura"},
            "ph": {"min": 8.1, "max": 8.3, "unit": "pH", "step": 0.01, "name": "pH"},
            "ammonia": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Amoníaco (NH3)"},
            "nitrite": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Nitrito (NO2)"},
            "kh": {"min": 8.0, "max": 9.0, "unit": "dKH", "step": 0.1, "max_daily_delta": 0.6, "name": "Alcalinidad (KH)"},
            "calcium": {"min": 400.0, "max": 440.0, "unit": "ppm", "step": 1.0, "name": "Calcio (Ca)"},
            "magnesium": {"min": 1300.0, "max": 1350.0, "unit": "ppm", "step": 1.0, "name": "Magnesio (Mg)"},
            "nitrate": {"min": 5.0, "max": 10.0, "unit": "ppm", "step": 0.1, "alert_on_zero": True, "name": "Nitrato (NO3)"},
            "phosphate": {"min": 0.03, "max": 0.08, "ideal": 0.05, "unit": "ppm", "step": 0.001, "alert_on_zero": True, "recommend_photometer": True, "name": "Fosfato (PO4)"}
        },
        "trace_elements": {
            "k": {"min": 380.0, "max": 410.0, "unit": "ppm", "step": 1.0, "name": "Potasio (K)"},
            "sr": {"min": 8.0, "max": 10.0, "unit": "ppm", "step": 0.1, "name": "Estroncio (Sr)"},
            "i": {"min": 0.03, "max": 0.06, "unit": "ppm", "step": 0.01, "name": "Yodo (I)"},
            "fe": {"min": 0.001, "max": 0.005, "unit": "ppm", "step": 0.001, "name": "Hierro (Fe)"}
        }
    },

    "sps_reef": {
        "id": "sps_reef",
        "name": "Arrecife SPS (Pólipo Corto)",
        "short_name": "Arrecife SPS",
        "description": "Corales de pólipo corto (Acroporas, Montiporas, Pocilloporas, Seriatoporas). Exigen altísima estabilidad química, radiación PAR intensa y flujo turbulento.",
        "environment": {
            "par_min": 250,
            "par_max": 450,
            "flow_profile": "high_turbulent",
            "flow_label": "Muy alto, turbulento y variable"
        },
        "targets": {
            "salinity": {"min": 1.025, "max": 1.026, "unit": "SG", "step": 0.001, "name": "Salinidad"},
            "temperature": {"min": 24.5, "max": 25.5, "max_24h_delta": 0.5, "unit": "°C", "step": 0.1, "name": "Temperatura"},
            "ph": {"min": 8.2, "max": 8.3, "unit": "pH", "step": 0.01, "name": "pH"},
            "ammonia": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Amoníaco (NH3)"},
            "nitrite": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Nitrito (NO2)"},
            "kh": {"min": 7.5, "max": 8.5, "unit": "dKH", "step": 0.1, "warn_daily_delta": 0.3, "critical_daily_delta": 0.5, "name": "Alcalinidad (KH)"},
            "calcium": {"min": 420.0, "max": 450.0, "unit": "ppm", "step": 1.0, "name": "Calcio (Ca)"},
            "magnesium": {"min": 1300.0, "max": 1400.0, "unit": "ppm", "step": 1.0, "name": "Magnesio (Mg)"},
            "nitrate": {"min": 1.0, "max": 5.0, "unit": "ppm", "step": 0.1, "alert_on_zero": True, "name": "Nitrato (NO3)"},
            "phosphate": {"min": 0.01, "max": 0.04, "unit": "ppm", "step": 0.001, "alert_on_zero": True, "recommend_photometer": True, "name": "Fosfato (PO4)"}
        },
        "trace_elements": {
            "k": {"min": 390.0, "max": 410.0, "unit": "ppm", "step": 1.0, "name": "Potasio (K)"},
            "sr": {"min": 8.0, "max": 10.0, "unit": "ppm", "step": 0.1, "name": "Estroncio (Sr)"},
            "i": {"min": 0.03, "max": 0.06, "unit": "ppm", "step": 0.01, "name": "Yodo (I)"},
            "fe": {"min": 0.001, "max": 0.005, "unit": "ppm", "step": 0.001, "name": "Hierro (Fe)"}
        }
    }
}

DOSING_METHOD_LABELS = {
    "water_changes": "Cambios de Agua",
    "manual_dosing": "Dosificación Manual",
    "peristaltic_balling": "Balling / Bombas Peristálticas",
    "kalkwasser": "Kalkwasser (Agua de Cal)",
    "calcium_reactor": "Reactor de Calcio (CaRx)"
}

FLOW_PROFILE_LABELS = {
    "low_moderate": "Bajo a Moderado",
    "moderate_indirect": "Moderado e Indirecto",
    "high_turbulent": "Alto, Turbulento y Variable"
}


def get_marine_profile(profile_key: Optional[str]) -> Dict[str, Any]:
    """Retorna la configuración del perfil marino. Fallback seguro a lps_reef."""
    if not profile_key:
        return MARINE_PROFILES["lps_reef"]
    norm = str(profile_key).strip().lower()
    if norm in MARINE_PROFILES:
        return MARINE_PROFILES[norm]
    # Mapeo de sinónimos
    if norm in ["fowlr", "soft", "fish_only", "peces_marinos", "solo_peces"]:
        return MARINE_PROFILES["fowlr_soft"]
    if norm in ["sps", "acropora"]:
        return MARINE_PROFILES["sps_reef"]
    return MARINE_PROFILES["lps_reef"]


def _parse_dt(val: Any) -> Optional[datetime]:
    from datetime import timezone
    if not val:
        return None
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return None
    if isinstance(val, datetime):
        if val.tzinfo:
            return val.astimezone(timezone.utc).replace(tzinfo=None)
        return val
    return None

def _get_field(obj: Any, *keys: str) -> Any:
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] is not None:
                return obj[k]
    else:
        for k in keys:
            if hasattr(obj, k):
                val = getattr(obj, k)
                if val is not None:
                    return val
    return None

def evaluate_marine_alerts(
    reef_profile: Optional[str],
    current_data: Dict[str, Any],
    history_measurements: Optional[List[Any]] = None,
    dosing_method: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Evalúa las 4 reglas dinámicas críticas para acuarios marinos:
    1. Detector Delta 24h de KH
    2. Alerta de nutrientes en cero (piso mínimo)
    3. Nota de resolución del test (Drop kit en PO4 vs Fotómetro ULR)
    4. Sugerencia de dosificación automatizada
    """
    alerts: List[Dict[str, Any]] = []
    profile_data = get_marine_profile(reef_profile)
    profile_id = profile_data["id"]

    # Extraer valores actuales respetando 0.0 como valor válido
    kh = _get_field(current_data, "kh", "alkalinity_dkh")
    nitrate = _get_field(current_data, "nitrate", "nitrate_ppm")
    phosphate = _get_field(current_data, "phosphate", "phosphate_ppm")
    test_methods = current_data.get("test_methods") or {}
    if not isinstance(test_methods, dict):
        test_methods = {}

    current_time = _parse_dt(current_data.get("timestamp")) or datetime.utcnow()

    # -------------------------------------------------------------
    # 1. DETECTOR DELTA 24H DE KH
    # -------------------------------------------------------------
    if kh is not None and history_measurements:
        kh_float = float(kh)
        hace_24h = current_time - timedelta(hours=24)
        prev_reading = None
        for m in history_measurements:
            m_time = _parse_dt(_get_field(m, "timestamp", "fecha_registro"))
            if not m_time:
                continue
            if hace_24h <= m_time <= current_time:
                m_kh = _get_field(m, "kh", "alkalinity_dkh")
                if m_kh is not None:
                    prev_reading = (float(m_kh), m_time)
                    break

        if prev_reading:
            prev_kh, prev_time = prev_reading
            delta = kh_float - prev_kh
            abs_delta = abs(delta)

            if profile_id == "sps_reef":
                if abs_delta > 0.5:
                    alerts.append({
                        "rule": "kh_delta_24h",
                        "severity": "critical",
                        "parameter": "kh",
                        "title": "Alerta Crítica: Oscilación Severa de KH en 24h",
                        "message": (
                            f"Oscilación crítica de KH de {delta:+.2f} dKH en 24h "
                            f"(previo: {prev_kh} -> actual: {kh_float} dKH, límite crítico: ±0.5 dKH). "
                            "Alto riesgo inminente de RTN/STN (necrosis rápida/lenta de tejido) en corales SPS, "
                            "incluso si el valor absoluto se encuentra dentro del rango."
                        ),
                        "recommendation": "Suspender o estabilizar de inmediato la dosificación; no realizar correcciones bruscas."
                    })
                elif abs_delta > 0.3:
                    alerts.append({
                        "rule": "kh_delta_24h",
                        "severity": "warning",
                        "parameter": "kh",
                        "title": "Advertencia: Variación Diaria de KH Elevada",
                        "message": (
                            f"Variación de KH de {delta:+.2f} dKH en 24h "
                            f"(previo: {prev_kh} -> actual: {kh_float} dKH, advertencia: >±0.3 dKH). "
                            "Los corales SPS son sensibles a cambios diarios superiores a 0.3 dKH."
                        ),
                        "recommendation": "Verificar temporizador o flujo de bombas peristálticas para estabilizar a dosis más pequeñas a lo largo del día."
                    })
            elif profile_id == "lps_reef":
                if abs_delta > 0.6:
                    alerts.append({
                        "rule": "kh_delta_24h",
                        "severity": "warning",
                        "parameter": "kh",
                        "title": "Advertencia: Salto de KH Superior al Seguro",
                        "message": (
                            f"Oscilación de KH de {delta:+.2f} dKH en 24h "
                            f"(previo: {prev_kh} -> actual: {kh_float} dKH, límite seguro LPS: ±0.6 dKH). "
                            "Puede causar retracción de pólipos carnosos y estrés osmótico."
                        ),
                        "recommendation": "Dosificar buffers en horas de menor variación y diluir la adición."
                    })

    # -------------------------------------------------------------
    # 2. ALERTA DE NUTRIENTES EN CERO (PISO MÍNIMO)
    # -------------------------------------------------------------
    if profile_id in ["lps_reef", "sps_reef"]:
        no3_val = float(nitrate) if nitrate is not None else None
        po4_val = float(phosphate) if phosphate is not None else None

        zero_no3 = (no3_val is not None and no3_val <= 0.001)
        zero_po4 = (po4_val is not None and po4_val <= 0.001)

        if zero_no3 or zero_po4:
            nutrientes_en_cero = []
            if zero_no3:
                nutrientes_en_cero.append("Nitratos (NO3 = 0.00 ppm)")
            if zero_po4:
                nutrientes_en_cero.append("Fosfatos (PO4 = 0.00 ppm)")

            sintomas = (
                "inanición de zooxantelas y encogimiento severo de tejido carnoso"
                if profile_id == "lps_reef" else
                "blanqueamiento por inanición (bleaching), pérdida de color y brote inminente de dinoflagelados"
            )

            alerts.append({
                "rule": "zero_nutrient_floor",
                "severity": "critical" if (zero_no3 and zero_po4) else "warning",
                "parameter": "nutrients",
                "title": "Piso Mínimo de Nutrientes Comprometido",
                "message": (
                    f"Nutrientes en cero detectados: {', '.join(nutrientes_en_cero)}. "
                    f"En {profile_data['name']}, el agua ultra oligotrófica (cero absoluto) provoca {sintomas}."
                ),
                "recommendation": (
                    "Retirar temporalmente resinas GFO / absorbentes de fosfatos, reducir skimmer "
                    "o dosificar nitrato (ej. NaNO3) y fósforo (ej. KH2PO4) para mantener NO3 >= 2 ppm y PO4 >= 0.03 ppm."
                )
            })

    # -------------------------------------------------------------
    # 3. NOTA DE RESOLUCIÓN DEL TEST
    # -------------------------------------------------------------
    if profile_id in ["lps_reef", "sps_reef"]:
        po4_method = test_methods.get("po4") or test_methods.get("phosphate")
        if po4_method == "drop_kit" and phosphate is not None:
            alerts.append({
                "rule": "test_resolution",
                "severity": "info",
                "parameter": "po4",
                "title": "Resolución de Test de Fosfatos (Gotas)",
                "message": (
                    "El test de fosfatos se registró con método 'Gotas'. "
                    "Los kits colorimétricos visuales de gotas carecen de resolución por debajo de 0.05 ppm, "
                    f"rango crítico para {profile_data['name']} (0.01 - 0.08 ppm)."
                ),
                "recommendation": "Se recomienda verificar con fotómetro digital ULR (ej. Hanna HI774 o HI736) o análisis ICP de laboratorio."
            })

    # -------------------------------------------------------------
    # 4. SUGERENCIA DE DOSIFICACIÓN AUTOMATIZADA
    # -------------------------------------------------------------
    method = (dosing_method or "water_changes").lower()
    if method in ["water_changes", "manual_dosing"] and history_measurements:
        hace_7d = current_time - timedelta(days=7)
        kh_readings: List[Tuple[datetime, float]] = []
        for m in history_measurements:
            m_time = _parse_dt(_get_field(m, "timestamp", "fecha_registro"))
            if m_time and m_time >= hace_7d:
                m_kh = _get_field(m, "kh", "alkalinity_dkh")
                if m_kh is not None:
                    kh_readings.append((m_time, float(m_kh)))

        if len(kh_readings) >= 3:
            kh_readings.sort(key=lambda x: x[0])
            caidas_significativas = 0
            for i in range(1, len(kh_readings)):
                dt_days = (kh_readings[i][0] - kh_readings[i-1][0]).total_seconds() / 86400.0
                drop = kh_readings[i-1][1] - kh_readings[i][1]
                if 1.0 <= dt_days <= 3.5 and drop >= 0.45:
                    caidas_significativas += 1

            if caidas_significativas >= 2:
                metodo_actual = DOSING_METHOD_LABELS.get(method, method)
                alerts.append({
                    "rule": "automated_dosing_suggestion",
                    "severity": "info",
                    "parameter": "dosing",
                    "title": "Sugerencia de Dosificación Automatizada",
                    "message": (
                        f"El acuario muestra caídas recurrentes de KH > 0.5 dKH cada 2–3 días bajo '{metodo_actual}'. "
                        "El consumo activo de calcificación coralina supera la estabilidad que los cambios de agua o la dosificación manual pueden proporcionar."
                    ),
                    "recommendation": "Migrar a dosificación diaria automatizada con bombas peristálticas (Método Balling 2/3 partes), Kalkwasser o Reactor de Calcio."
                })

    return alerts
