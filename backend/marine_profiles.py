"""
Perfiles bioquímicos y motor de evaluación para acuarios marinos y de arrecife en AquaPulse.
Soporta exactamente 5 perfiles marinos:
1. fish_only: Solo Peces / FOWLR
2. soft_reef: Corales Blandos
3. lps_reef: Arrecife LPS (Pólipo Largo)
4. mixed_reef: Arrecife Mixto (Blandos + LPS + SPS)
5. sps_reef: Arrecife SPS (Pólipo Corto)
"""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone

MARINE_PROFILES: Dict[str, Dict[str, Any]] = {
    # 1. SOLO PECES / FOWLR
    "fish_only": {
        "id": "fish_only",
        "name": "Solo Peces / FOWLR",
        "short_name": "Peces / FOWLR",
        "description": "Acuarios marinos dedicados exclusivamente a peces o roca viva (Fish Only With Live Rock). Sin demanda de calcificación coralina.",
        "environment": {
            "par_min": None,
            "par_max": None,
            "flow_profile": "low_moderate",
            "flow_label": "Bajo a moderado"
        },
        "visible_fields": {
            "salinity": True,
            "temperature": True,
            "ph": True,
            "ammonia": True,
            "nitrite": True,
            "nitrate": True,
            "kh": True,
            "phosphate": True,
            "calcium": False,
            "magnesium": False,
            "trace_elements": False,
            "test_methods": False,
            "lighting_par": False,
            "flow_profile": False,
            "dosing_method": False
        },
        "enabled_rules": {
            "kh_delta_24h": False,
            "zero_nutrient_floor": False,
            "test_resolution_po4": False,
            "automated_dosing_suggestion": False,
            "flow_tissue_warning": False
        },
        "targets": {
            "salinity": {"min": 1.020, "max": 1.025, "unit": "SG", "step": 0.001, "name": "Salinidad"},
            "temperature": {"min": 24.0, "max": 26.0, "unit": "°C", "step": 0.1, "name": "Temperatura"},
            "ph": {"min": 8.0, "max": 8.3, "unit": "pH", "step": 0.01, "name": "pH"},
            "ammonia": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Amoníaco (NH3)"},
            "nitrite": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Nitrito (NO2)"},
            "nitrate": {"min": 0.0, "max": 30.0, "unit": "ppm", "step": 0.5, "alert_on_zero": False, "name": "Nitrato (NO3)"},
            "kh": {"min": 7.0, "max": 11.0, "unit": "dKH", "step": 0.1, "name": "Alcalinidad (KH)"},
            "phosphate": {"min": 0.0, "max": 0.25, "unit": "ppm", "step": 0.01, "alert_on_zero": False, "name": "Fosfato (PO4)"}
        },
        "trace_elements": {}
    },

    # 2. CORALES BLANDOS
    "soft_reef": {
        "id": "soft_reef",
        "name": "Corales Blandos",
        "short_name": "Blandos (Soft)",
        "description": "Corales blandos y coloniales resistentes (Zoanthus, Sarcophyton, Discosomas, Clavularia, Sinularia). Toleran nutrientes y no requieren dosificación de trazas.",
        "environment": {
            "par_min": 50,
            "par_max": 120,
            "flow_profile": "low_moderate",
            "flow_label": "Bajo a moderado"
        },
        "visible_fields": {
            "salinity": True,
            "temperature": True,
            "ph": True,
            "ammonia": True,
            "nitrite": True,
            "nitrate": True,
            "kh": True,
            "phosphate": True,
            "calcium": True,
            "magnesium": True,
            "trace_elements": False,
            "test_methods": False,
            "lighting_par": True,
            "flow_profile": True,
            "dosing_method": True
        },
        "enabled_rules": {
            "kh_delta_24h": True,
            "zero_nutrient_floor": True,  # Leve
            "test_resolution_po4": False,
            "automated_dosing_suggestion": False,
            "flow_tissue_warning": False
        },
        "targets": {
            "salinity": {"min": 1.023, "max": 1.025, "unit": "SG", "step": 0.001, "name": "Salinidad"},
            "temperature": {"min": 24.0, "max": 26.0, "unit": "°C", "step": 0.1, "name": "Temperatura"},
            "ph": {"min": 8.0, "max": 8.3, "unit": "pH", "step": 0.01, "name": "pH"},
            "ammonia": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Amoníaco (NH3)"},
            "nitrite": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Nitrito (NO2)"},
            "kh": {"min": 7.5, "max": 9.5, "unit": "dKH", "step": 0.1, "max_daily_delta": 1.0, "name": "Alcalinidad (KH)"},
            "calcium": {"min": 380.0, "max": 420.0, "unit": "ppm", "step": 1.0, "name": "Calcio (Ca)"},
            "magnesium": {"min": 1250.0, "max": 1350.0, "unit": "ppm", "step": 1.0, "name": "Magnesio (Mg)"},
            "nitrate": {"min": 5.0, "max": 15.0, "unit": "ppm", "step": 0.1, "alert_on_zero": True, "name": "Nitrato (NO3)"},
            "phosphate": {"min": 0.05, "max": 0.15, "unit": "ppm", "step": 0.001, "alert_on_zero": True, "name": "Fosfato (PO4)"}
        },
        "trace_elements": {}
    },

    # 3. ARRECIFE LPS (Pólipo Largo)
    "lps_reef": {
        "id": "lps_reef",
        "name": "Arrecife LPS (Pólipo Largo)",
        "short_name": "Arrecife LPS",
        "description": "Corales duros de pólipo largo (Euphyllias, Torch, Frogspawn, Acanthastreas, Trachyphyllias, Duncans). Requieren nutrientes detectables y flujo indirecto para no rasgar tejido.",
        "environment": {
            "par_min": 100,
            "par_max": 200,
            "flow_profile": "moderate_indirect",
            "flow_label": "Moderado e indirecto",
            "flow_warning": "Un chorro directo fuerte rasga o desprende el tejido carnoso de los corales LPS."
        },
        "visible_fields": {
            "salinity": True,
            "temperature": True,
            "ph": True,
            "ammonia": True,
            "nitrite": True,
            "nitrate": True,
            "kh": True,
            "phosphate": True,
            "calcium": True,
            "magnesium": True,
            "trace_elements": True,
            "test_methods": True,
            "lighting_par": True,
            "flow_profile": True,
            "dosing_method": True
        },
        "enabled_rules": {
            "kh_delta_24h": True,
            "zero_nutrient_floor": True,
            "test_resolution_po4": True,
            "automated_dosing_suggestion": True,
            "flow_tissue_warning": True
        },
        "targets": {
            "salinity": {"min": 1.025, "max": 1.026, "unit": "SG", "step": 0.001, "name": "Salinidad"},
            "temperature": {"min": 24.5, "max": 25.5, "unit": "°C", "step": 0.1, "name": "Temperatura"},
            "ph": {"min": 8.1, "max": 8.3, "unit": "pH", "step": 0.01, "name": "pH"},
            "ammonia": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Amoníaco (NH3)"},
            "nitrite": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Nitrito (NO2)"},
            "kh": {"min": 8.0, "max": 9.0, "unit": "dKH", "step": 0.1, "max_daily_delta": 0.6, "warn_daily_delta": 0.6, "name": "Alcalinidad (KH)"},
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

    # 4. ARRECIFE MIXTO (Blandos + LPS + SPS)
    "mixed_reef": {
        "id": "mixed_reef",
        "name": "Arrecife Mixto (Blandos + LPS + SPS)",
        "short_name": "Arrecife Mixto",
        "description": "Composición balanceada de corales blandos, LPS y SPS. Demanda equilibrio químico para alimentar LPS sin saturar ni blanquear los SPS.",
        "environment": {
            "par_min": 150,
            "par_max": 300,
            "flow_profile": "moderate_indirect",
            "flow_label": "Medio-alto variable por zonas"
        },
        "visible_fields": {
            "salinity": True,
            "temperature": True,
            "ph": True,
            "ammonia": True,
            "nitrite": True,
            "nitrate": True,
            "kh": True,
            "phosphate": True,
            "calcium": True,
            "magnesium": True,
            "trace_elements": True,
            "test_methods": True,
            "lighting_par": True,
            "flow_profile": True,
            "dosing_method": True
        },
        "enabled_rules": {
            "kh_delta_24h": True,
            "zero_nutrient_floor": True,
            "test_resolution_po4": True,
            "automated_dosing_suggestion": True,
            "flow_tissue_warning": True
        },
        "targets": {
            "salinity": {"min": 1.025, "max": 1.026, "unit": "SG", "step": 0.001, "name": "Salinidad"},
            "temperature": {"min": 24.5, "max": 25.5, "unit": "°C", "step": 0.1, "name": "Temperatura"},
            "ph": {"min": 8.1, "max": 8.3, "unit": "pH", "step": 0.01, "name": "pH"},
            "ammonia": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Amoníaco (NH3)"},
            "nitrite": {"min": 0.0, "max": 0.0, "safe_max": 0.0, "unit": "ppm", "step": 0.01, "name": "Nitrito (NO2)"},
            "kh": {"min": 8.0, "max": 8.5, "unit": "dKH", "step": 0.1, "warn_daily_delta": 0.4, "critical_daily_delta": 0.5, "name": "Alcalinidad (KH)"},
            "calcium": {"min": 420.0, "max": 440.0, "unit": "ppm", "step": 1.0, "name": "Calcio (Ca)"},
            "magnesium": {"min": 1300.0, "max": 1350.0, "unit": "ppm", "step": 1.0, "name": "Magnesio (Mg)"},
            "nitrate": {"min": 3.0, "max": 8.0, "unit": "ppm", "step": 0.1, "alert_on_zero": True, "name": "Nitrato (NO3)"},
            "phosphate": {"min": 0.03, "max": 0.06, "unit": "ppm", "step": 0.001, "alert_on_zero": True, "recommend_photometer": True, "name": "Fosfato (PO4)"}
        },
        "trace_elements": {
            "k": {"min": 390.0, "max": 410.0, "unit": "ppm", "step": 1.0, "name": "Potasio (K)"},
            "sr": {"min": 8.0, "max": 10.0, "unit": "ppm", "step": 0.1, "name": "Estroncio (Sr)"},
            "i": {"min": 0.03, "max": 0.06, "unit": "ppm", "step": 0.01, "name": "Yodo (I)"},
            "fe": {"min": 0.001, "max": 0.005, "unit": "ppm", "step": 0.001, "name": "Hierro (Fe)"}
        }
    },

    # 5. ARRECIFE SPS (Pólipo Corto)
    "sps_reef": {
        "id": "sps_reef",
        "name": "Arrecife SPS (Pólipo Corto)",
        "short_name": "Arrecife SPS",
        "description": "Corales duros de pólipo corto (Acroporas, Montiporas, Pocilloporas, Seriatoporas). Exigen altísima estabilidad química, radiación PAR intensa (250-450+) y flujo turbulento.",
        "environment": {
            "par_min": 250,
            "par_max": 450,
            "flow_profile": "high_turbulent",
            "flow_label": "Muy alto, turbulento y variable"
        },
        "visible_fields": {
            "salinity": True,
            "temperature": True,
            "ph": True,
            "ammonia": True,
            "nitrite": True,
            "nitrate": True,
            "kh": True,
            "phosphate": True,
            "calcium": True,
            "magnesium": True,
            "trace_elements": True,
            "test_methods": True,
            "lighting_par": True,
            "flow_profile": True,
            "dosing_method": True
        },
        "enabled_rules": {
            "kh_delta_24h": True,
            "zero_nutrient_floor": True,
            "test_resolution_po4": True,
            "automated_dosing_suggestion": True,
            "flow_tissue_warning": False
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

    # Mapeo de sinónimos y compatibilidad con versiones previas
    if norm in ["fish_only", "fowlr", "fowlr_soft", "solo_peces", "peces_marinos", "marine_fish"]:
        return MARINE_PROFILES["fish_only"]
    if norm in ["soft_reef", "soft", "blandos", "corales_blandos", "soft_corals"]:
        return MARINE_PROFILES["soft_reef"]
    if norm in ["mixed_reef", "mixed", "mixto", "arrecife_mixto"]:
        return MARINE_PROFILES["mixed_reef"]
    if norm in ["sps_reef", "sps", "acropora", "acroporas"]:
        return MARINE_PROFILES["sps_reef"]
    if norm in ["lps_reef", "lps", "arrecife", "reef"]:
        return MARINE_PROFILES["lps_reef"]

    return MARINE_PROFILES["lps_reef"]


def _parse_dt(val: Any) -> Optional[datetime]:
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
    Evalúa las 4 reglas dinámicas críticas para acuarios marinos respetando
    estrictamente la propiedad enabled_rules del perfil específico.
    """
    alerts: List[Dict[str, Any]] = []
    profile_data = get_marine_profile(reef_profile)
    profile_id = profile_data["id"]
    enabled_rules = profile_data.get("enabled_rules", {})

    # Extraer valores actuales respetando 0.0 como valor numérico válido
    kh = _get_field(current_data, "kh", "alkalinity_dkh")
    nitrate = _get_field(current_data, "nitrate", "nitrate_ppm")
    phosphate = _get_field(current_data, "phosphate", "phosphate_ppm")
    test_methods = current_data.get("test_methods") or {}
    if not isinstance(test_methods, dict):
        test_methods = {}

    current_time = _parse_dt(current_data.get("timestamp")) or datetime.utcnow()

    # -------------------------------------------------------------
    # 1. DETECTOR DELTA 24H DE KH (Solo si habilitado en enabled_rules)
    # -------------------------------------------------------------
    if enabled_rules.get("kh_delta_24h") and kh is not None and history_measurements:
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
                        "recommendation": "Verificar temporizador o calibrar dosificadora peristáltica a microdosis a lo largo del fotoperiodo."
                    })
            elif profile_id == "mixed_reef":
                if abs_delta > 0.5:
                    alerts.append({
                        "rule": "kh_delta_24h",
                        "severity": "critical",
                        "parameter": "kh",
                        "title": "Alerta Crítica: Inestabilidad de KH en Arrecife Mixto",
                        "message": (
                            f"Oscilación de KH de {delta:+.2f} dKH en 24h (límite crítico: ±0.5 dKH). "
                            "Amenaza la supervivencia de SPS y provoca retracción en corales LPS."
                        ),
                        "recommendation": "Revisar rutina de adición y ajustar parámetros suavemente."
                    })
                elif abs_delta > 0.4:
                    alerts.append({
                        "rule": "kh_delta_24h",
                        "severity": "warning",
                        "parameter": "kh",
                        "title": "Advertencia: Fluctuación de KH en Arrecife Mixto",
                        "message": (
                            f"Variación de KH de {delta:+.2f} dKH en 24h (advertencia: >±0.4 dKH). "
                            "Supera el umbral óptimo diario para la zona SPS del tanque."
                        ),
                        "recommendation": "Fraccionar adiciones manuales o configurar bombas peristálticas."
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
            elif profile_id == "soft_reef":
                if abs_delta > 1.0:
                    alerts.append({
                        "rule": "kh_delta_24h",
                        "severity": "warning",
                        "parameter": "kh",
                        "title": "Advertencia: Variación Amplia de KH en Blandos",
                        "message": f"Oscilación de KH de {delta:+.2f} dKH en 24h. Mantener delta < 1.0 dKH para evitar estrés celular.",
                        "recommendation": "Moderar cambios bruscos de agua."
                    })

    # -------------------------------------------------------------
    # 2. ALERTA DE NUTRIENTES EN CERO (PISO MÍNIMO)
    # -------------------------------------------------------------
    if enabled_rules.get("zero_nutrient_floor"):
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

            if profile_id == "soft_reef":
                alerts.append({
                    "rule": "zero_nutrient_floor",
                    "severity": "info",
                    "parameter": "nutrients",
                    "title": "Piso Mínimo de Nutrientes Bajo",
                    "message": (
                        f"Nutrientes en cero detectados: {', '.join(nutrientes_en_cero)}. "
                        "Los corales blandos toleran nutrientes bajos pero necesitan un piso detectable para alimentar sus zooxantelas."
                    ),
                    "recommendation": "Alimentar ligeramente más a los peces o pausar resinas adsorbentes."
                })
            elif profile_id == "lps_reef":
                alerts.append({
                    "rule": "zero_nutrient_floor",
                    "severity": "critical" if (zero_no3 and zero_po4) else "warning",
                    "parameter": "nutrients",
                    "title": "Alerta de Inanición: Nutrientes en Cero (0.00 ppm)",
                    "message": (
                        f"Nutrientes en cero detectados: {', '.join(nutrientes_en_cero)}. "
                        "En Arrecife LPS, el agua ultra oligotrófica provoca inanición de zooxantelas y encogimiento severo de tejido carnoso."
                    ),
                    "recommendation": "Dosificar nitrato y fosfato o apagar temporalmente el skimmer para recuperar NO3 >= 5 ppm y PO4 >= 0.03 ppm."
                })
            elif profile_id == "mixed_reef":
                alerts.append({
                    "rule": "zero_nutrient_floor",
                    "severity": "critical" if (zero_no3 and zero_po4) else "warning",
                    "parameter": "nutrients",
                    "title": "Piso Mínimo Comprometido en Arrecife Mixto",
                    "message": (
                        f"Nutrientes en cero detectados: {', '.join(nutrientes_en_cero)}. "
                        "Riesgo de inanición en corales LPS y riesgo de blanqueamiento o brote inminente de dinoflagelados en SPS."
                    ),
                    "recommendation": "Mantener equilibrio dosificando nutrientes hasta NO3: 3-5 ppm y PO4: 0.03 ppm."
                })
            elif profile_id == "sps_reef":
                alerts.append({
                    "rule": "zero_nutrient_floor",
                    "severity": "critical",
                    "parameter": "nutrients",
                    "title": "Alerta Crítica: Agua Ultra Oligotrófica en SPS (0.00 ppm)",
                    "message": (
                        f"Nutrientes en cero absoluto: {', '.join(nutrientes_en_cero)}. "
                        "Alto riesgo inminente de blanqueamiento por inanición (bleaching) y proliferación agresiva de dinoflagelados."
                    ),
                    "recommendation": "Retirar de inmediato resinas GFO / absorbentes y dosificar nitrato y fósforo inorgánico."
                })

    # -------------------------------------------------------------
    # 3. NOTA DE RESOLUCIÓN DEL TEST (Solo si habilitado)
    # -------------------------------------------------------------
    if enabled_rules.get("test_resolution_po4"):
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
                    f"rango crítico para {profile_data['name']} (0.01 - 0.06 ppm)."
                ),
                "recommendation": "Se recomienda verificar con fotómetro digital ULR (ej. Hanna HI774 o HI736) o análisis ICP de laboratorio."
            })

    # -------------------------------------------------------------
    # 4. SUGERENCIA DE DOSIFICACIÓN AUTOMATIZADA (Solo si habilitado)
    # -------------------------------------------------------------
    if enabled_rules.get("automated_dosing_suggestion"):
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
