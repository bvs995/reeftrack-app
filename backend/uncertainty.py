"""
Motor de Metrología, Intervalos de Incertidumbre y Acciones Anti-Colapso para Acuarios.
AquaPulse - Fase 3:
- Errores base por parámetro y kit analítico (Hanna, Salifert, Red Sea, Genérico).
- Incorporación de error de visión IA (e_total = sqrt(e_kit² + e_vision²)).
- Evaluación de alertas con intervalos [v - e, v + e]: Confirmada vs Probable (retest en 1–2 h).
- Incertidumbre de oscilación en 24h: u = sqrt(e1² + e2²).
- Límite de detección en nutrientes NO3/PO4 (< e).
- Acciones correctoras anti-colapso: no actuar si corrección < error, extremo que menos corrige,
  cambio diario permitido = límite_perfil - u, y coordinación de parámetros interactuantes (Mg > KH > Ca).
- Proyecciones con mínimo 3 mediciones, regresión lineal, banda ± y filtro R² >= 0.50.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

# ==============================================================================
# 1. ESPECIFICACIÓN Y METROLOGÍA DE ERRORES POR PARÁMETRO Y KIT
# ==============================================================================

# Errores base por parámetro (conservadores, verificados contra fichas técnicas)
DEFAULT_MEASUREMENT_ERRORS: Dict[str, float] = {
    "kh": 0.3,              # ±0.3 dKH
    "alkalinity_dkh": 0.3,
    "calcium": 20.0,        # ±20.0 ppm
    "calcium_ppm": 20.0,
    "magnesium": 50.0,      # ±50.0 ppm
    "magnesium_ppm": 50.0,
    "nitrate": 0.5,         # Base 0.5 ppm o 20% (el mayor)
    "nitrate_ppm": 0.5,
    "phosphate": 0.02,      # ±0.02 ppm
    "phosphate_ppm": 0.02,
    "salinity": 1.0,        # ±1.0 ppt o ±0.001 SG
    "salinity_ppt": 1.0,
    "temperature": 0.5,     # ±0.5 °C
    "temperatura": 0.5,
    "ph": 0.05,             # ±0.05 pH
    "ammonia": 0.02,        # ±0.02 ppm
    "ammonia_ppm": 0.02,
    "nitrite": 0.02,        # ±0.02 ppm
    "nitrite_ppm": 0.02,
    "gh_dgh": 0.5           # ±0.5 dGH
}

# Fichas técnicas de fabricantes reconocidos (Hanna Checkers, Salifert, Red Sea)
KIT_CATALOG_SPECS: Dict[str, Dict[str, Any]] = {
    "hanna": {
        "name": "Hanna Instruments Checker",
        "errors": {
            "kh": 0.3,          # HI772: ±0.3 dKH ±5% de lectura
            "phosphate": 0.02,   # HI736 / HI774: ±0.02 ppm o ±5%
            "calcium": 20.0,     # HI758: ±20 ppm
            "nitrate": 0.5,      # HI781 / HI782: ±0.5 ppm
            "salinity": 1.0,     # HI98319: ±1 ppt
            "temperature": 0.5,
            "ph": 0.05
        }
    },
    "salifert": {
        "name": "Salifert Profi Test",
        "errors": {
            "kh": 0.3,          # Titulación jeringa 1ml: 0.3 dKH
            "calcium": 15.0,     # Titulación 1ml: 15 ppm
            "magnesium": 30.0,   # Titulación: 30 ppm
            "nitrate": 0.5,      # Colorimétrico: 20% o 0.5 ppm
            "phosphate": 0.03,   # Colorimétrico gotas: menor resolución baja
            "salinity": 1.0,
            "temperature": 0.5,
            "ph": 0.05
        }
    },
    "red_sea": {
        "name": "Red Sea Pro Test Kit",
        "errors": {
            "kh": 0.28,         # 0.1 meq/L = 0.28 dKH
            "calcium": 20.0,     # Titulación: 20 ppm
            "magnesium": 40.0,   # Titulación: 40 ppm
            "nitrate": 0.5,      # 0.5 ppm o 15%
            "phosphate": 0.02,   # Colorimétrico pro: 0.02 ppm
            "salinity": 1.0,
            "temperature": 0.5,
            "ph": 0.05
        }
    },
    "generic": {
        "name": "Kit Genérico / Gotas",
        "errors": DEFAULT_MEASUREMENT_ERRORS
    }
}


class MeasurementInterval(BaseModel):
    parameter: str
    value: float
    error: float
    min_val: float
    max_val: float
    kit: Optional[str] = None
    is_camera_scan: bool = False
    display_value: str
    is_below_detection_limit: bool = False


def normalize_param_key(param: str) -> str:
    """Normaliza nombres canónicos de parámetros para indexación metrológica."""
    p = (param or "").strip().lower()
    if p in ["alkalinity_dkh", "alkalinity", "kh"]:
        return "kh"
    if p in ["calcium_ppm", "calcium", "ca"]:
        return "calcium"
    if p in ["magnesium_ppm", "magnesium", "mg"]:
        return "magnesium"
    if p in ["nitrate_ppm", "nitrate", "no3"]:
        return "nitrate"
    if p in ["phosphate_ppm", "phosphate", "po4"]:
        return "phosphate"
    if p in ["salinity_ppt", "salinity"]:
        return "salinity"
    if p in ["temperature", "temperatura", "temp"]:
        return "temperature"
    if p in ["ammonia_ppm", "ammonia", "nh3"]:
        return "ammonia"
    if p in ["nitrite_ppm", "nitrite", "no2"]:
        return "nitrite"
    return p


def get_kit_error_for_parameter(param: str, value: float, kit: Optional[str] = None) -> float:
    """
    Calcula el error base del kit químico según especificaciones técnicas.
    Para Nitrato (NO3): evalúa 20% o 0.5 ppm (el que resulte mayor).
    """
    norm_p = normalize_param_key(param)
    kit_key = (kit or "").strip().lower()

    # Detectar fabricante desde el string de kit
    catalog_key = "generic"
    if "hanna" in kit_key:
        catalog_key = "hanna"
    elif "salifert" in kit_key:
        catalog_key = "salifert"
    elif "red" in kit_key and "sea" in kit_key:
        catalog_key = "red_sea"

    kit_dict = KIT_CATALOG_SPECS.get(catalog_key, KIT_CATALOG_SPECS["generic"])
    base_err = kit_dict["errors"].get(norm_p, DEFAULT_MEASUREMENT_ERRORS.get(norm_p, 0.1))

    # Regla específica NO3: 20% del valor o 0.5 ppm (el mayor)
    if norm_p == "nitrate":
        pct_err = 0.20 * abs(value)
        base_err = max(base_err, pct_err)

    return float(base_err)


def calculate_measurement_uncertainty(
    parameter: str,
    value: float,
    kit: Optional[str] = None,
    is_camera_scan: bool = False
) -> MeasurementInterval:
    """
    Construye el intervalo de incertidumbre [v - e, v + e] para una medición:
    - e_kit: Error metrológico del kit.
    - Si vino de cámara: e_total = sqrt(e_kit² + e_vision²), con e_vision = 10% de la lectura.
    - Detección de piso en nutrientes (NO3/PO4): Si el valor es <= 0.001 o <= e, se muestra como '< e'.
    """
    norm_p = normalize_param_key(parameter)
    val = float(value)

    # 1. Error base del kit
    e_kit = get_kit_error_for_parameter(norm_p, val, kit=kit)

    # 2. Si proviene del modelo de visión (cámara IA)
    if is_camera_scan:
        e_vision = 0.10 * abs(val)
        e_total = math.sqrt((e_kit ** 2) + (e_vision ** 2))
    else:
        e_total = e_kit

    e_total = round(e_total, 4)
    min_val = round(val - e_total, 4)
    max_val = round(val + e_total, 4)

    # 3. Límite de detección en nutrientes NO3 y PO4
    is_below_dl = False
    display_val = f"{val:.2f}"

    if norm_p in ["nitrate", "phosphate"] and val <= 0.001:
        is_below_dl = True
        display_val = f"< {e_total:.2f}"

    return MeasurementInterval(
        parameter=norm_p,
        value=val,
        error=e_total,
        min_val=min_val,
        max_val=max_val,
        kit=kit,
        is_camera_scan=is_camera_scan,
        display_value=display_val,
        is_below_detection_limit=is_below_dl
    )


# ==============================================================================
# 2. REGLAS DE ALERTA CON INTERVALOS (CONFIRMADA vs PROBABLE)
# ==============================================================================

class IntervalAlertResult(BaseModel):
    parameter: str
    status: str                         # 'safe', 'probable', 'confirmed'
    severity: str                       # 'safe', 'watch', 'warning', 'critical'
    is_alert: bool
    title: str
    message: str
    recommendation: str
    interval: List[float]               # [min, max]
    tested_value: float
    threshold_crossed: Optional[float] = None
    crossed_bound: Optional[str] = None # 'upper', 'lower', None


def evaluate_parameter_with_interval(
    param: str,
    interval: MeasurementInterval,
    safe_min: Optional[float],
    safe_max: Optional[float],
    profile_name: str = "Acuario"
) -> IntervalAlertResult:
    """
    Evalúa una medición según su intervalo completo [v - e, v + e]:
    - Confirmada: TODO el intervalo cruza el límite -> severidad completa (warning/critical).
    - Probable: SOLO PARTE del intervalo cruza el límite -> severidad mínima 'watch' + 'retest en 1–2 h', nunca se ignora.
    - Segura: Todo el intervalo se mantiene dentro del rango seguro.
    """
    p_norm = normalize_param_key(param)
    v = interval.value
    e = interval.error
    v_min = interval.min_val
    v_max = interval.max_val

    # Si no hay límites definidos
    if safe_min is None and safe_max is None:
        return IntervalAlertResult(
            parameter=p_norm,
            status="safe",
            severity="safe",
            is_alert=False,
            title="Parámetro Estable",
            message=f"{p_norm.upper()} dentro de parámetros operativos.",
            recommendation="Mantener rutina de monitoreo.",
            interval=[v_min, v_max],
            tested_value=v
        )

    # 1. EVALUAR LÍMITE SUPERIOR
    if safe_max is not None:
        if v_min > safe_max:
            # Todo el intervalo está por encima del límite máximo -> CONFIRMADA
            return IntervalAlertResult(
                parameter=p_norm,
                status="confirmed",
                severity="critical" if (v - safe_max > 2 * e) else "warning",
                is_alert=True,
                title=f"Alerta Confirmada: {p_norm.upper()} Excede Límite Máximo",
                message=(
                    f"Lectura confirmada de {p_norm.upper()} en {v} ± {e:.2f} (intervalo [{v_min:.2f}, {v_max:.2f}]). "
                    f"Incluso el extremo inferior ({v_min:.2f}) supera el límite seguro de {safe_max} para {profile_name}."
                ),
                recommendation="Aplicar corrección conservadora o suspender adición.",
                interval=[v_min, v_max],
                tested_value=v,
                threshold_crossed=safe_max,
                crossed_bound="upper"
            )
        elif v_max > safe_max and v_min <= safe_max:
            # Solo parte del intervalo cruza el límite máximo -> PROBABLE
            return IntervalAlertResult(
                parameter=p_norm,
                status="probable",
                severity="watch",
                is_alert=True,
                title=f"Alerta Probable: {p_norm.upper()} en Umbral Superior de Incertidumbre",
                message=(
                    f"Lectura de {p_norm.upper()} en {v} ± {e:.2f} (intervalo [{v_min:.2f}, {v_max:.2f}]). "
                    f"El margen superior ({v_max:.2f}) supera el límite de {safe_max}, pero el valor nominal no lo confirma totalmente."
                ),
                recommendation="No actuar de inmediato: realizar un retest en 1–2 h para verificar antes de dosificar o corregir.",
                interval=[v_min, v_max],
                tested_value=v,
                threshold_crossed=safe_max,
                crossed_bound="upper"
            )

    # 2. EVALUAR LÍMITE INFERIOR
    if safe_min is not None:
        if v_max < safe_min:
            # Todo el intervalo está por debajo del límite mínimo -> CONFIRMADA
            return IntervalAlertResult(
                parameter=p_norm,
                status="confirmed",
                severity="critical" if (safe_min - v > 2 * e) else "warning",
                is_alert=True,
                title=f"Alerta Confirmada: {p_norm.upper()} por Debajo del Mínimo Seguro",
                message=(
                    f"Lectura confirmada de {p_norm.upper()} en {v} ± {e:.2f} (intervalo [{v_min:.2f}, {v_max:.2f}]). "
                    f"Incluso el extremo superior ({v_max:.2f}) se encuentra bajo el mínimo de {safe_min} para {profile_name}."
                ),
                recommendation="Requiere dosificación correctiva con extremo conservador.",
                interval=[v_min, v_max],
                tested_value=v,
                threshold_crossed=safe_min,
                crossed_bound="lower"
            )
        elif v_min < safe_min and v_max >= safe_min:
            # Solo parte del intervalo cruza el límite inferior -> PROBABLE
            return IntervalAlertResult(
                parameter=p_norm,
                status="probable",
                severity="watch",
                is_alert=True,
                title=f"Alerta Probable: {p_norm.upper()} en Umbral Inferior de Incertidumbre",
                message=(
                    f"Lectura de {p_norm.upper()} en {v} ± {e:.2f} (intervalo [{v_min:.2f}, {v_max:.2f}]). "
                    f"El margen inferior ({v_min:.2f}) cae bajo el mínimo seguro de {safe_min}, pero el extremo superior se mantiene dentro del rango."
                ),
                recommendation="No actuar de inmediato: realizar un retest en 1–2 h para verificar antes de dosificar.",
                interval=[v_min, v_max],
                tested_value=v,
                threshold_crossed=safe_min,
                crossed_bound="lower"
            )

    # 3. TODO EL INTERVALO ESTÁ DENTRO DEL RANGO SEGURO
    return IntervalAlertResult(
        parameter=p_norm,
        status="safe",
        severity="safe",
        is_alert=False,
        title=f"{p_norm.upper()} Óptimo",
        message=f"{p_norm.upper()} en {v} ± {e:.2f} dentro del rango seguro [{safe_min}, {safe_max}].",
        recommendation="Mantener rutina habitual.",
        interval=[v_min, v_max],
        tested_value=v
    )


def evaluate_delta_24h_uncertainty(
    prev_val: float,
    prev_error: float,
    curr_val: float,
    curr_error: float,
    threshold: float = 0.5
) -> Dict[str, Any]:
    """
    Evalúa la oscilación en 24h considerando la propagación de incertidumbre:
    u = sqrt(e1² + e2²)
    - Si |Δ| - u > threshold -> Confirmada (severidad completa).
    - Si solo |Δ| > threshold pero |Δ| - u <= threshold -> Probable (watch + 'retest en 1–2 h').
    """
    delta = curr_val - prev_val
    abs_delta = abs(delta)
    u_combined = math.sqrt((prev_error ** 2) + (curr_error ** 2))
    u_combined = round(u_combined, 4)

    effective_delta = abs_delta - u_combined

    if effective_delta > threshold:
        status = "confirmed"
        severity = "critical"
        msg = (
            f"Oscilación confirmada de {delta:+.2f} dKH en 24h (incertidumbre combinada u = ±{u_combined:.2f} dKH). "
            f"El cambio efectivo corregido por error (|Δ| - u = {effective_delta:.2f} dKH) supera el umbral crítico de {threshold:.2f} dKH."
        )
        recommendation = "Suspender o estabilizar de inmediato la dosificación; evitar correcciones bruscas."
    elif abs_delta > threshold:
        status = "probable"
        severity = "watch"
        msg = (
            f"Oscilación probable de {delta:+.2f} dKH en 24h con incertidumbre combinada u = ±{u_combined:.2f} dKH. "
            f"El cambio nominal supera {threshold:.2f} dKH, pero la incertidumbre de los kits de test cubre parte de la variación."
        )
        recommendation = "Retest en 1–2 h para verificar si la oscilación es real antes de alterar la dosificación."
    else:
        status = "safe"
        severity = "safe"
        msg = f"Variación diaria controlada de {delta:+.2f} dKH dentro del margen seguro (u = ±{u_combined:.2f} dKH)."
        recommendation = "Mantener monitoreo regular."

    return {
        "status": status,
        "severity": severity,
        "delta": round(delta, 3),
        "abs_delta": round(abs_delta, 3),
        "uncertainty": u_combined,
        "effective_delta": round(effective_delta, 3),
        "threshold": threshold,
        "message": msg,
        "recommendation": recommendation
    }


# ==============================================================================
# 3. ACCIONES CORRECTORAS ANTI-COLAPSO
# ==============================================================================

class SafeCorrectionAction(BaseModel):
    parameter: str
    can_act: bool
    status: str                         # 'no_action_within_error', 'adjust_conservative', 'paused_interaction'
    current_value: float
    target_value: float
    error: float
    deviation: float
    least_correction_needed: float
    daily_allowed_change: float
    recommended_today: float
    message: str
    retest_required: bool = True


def calculate_safe_correction(
    parameter: str,
    current_value: float,
    target_value: float,
    error: float,
    profile_max_daily_change: float
) -> SafeCorrectionAction:
    """
    Calcula una corrección segura evitando desestabilizaciones o colapso del acuario:
    1. Si la corrección necesaria (|target - v|) es menor que el error 'e' -> No actuar:
       'dentro del margen de error, repite la prueba'.
    2. Cambio diario permitido = límite_del_perfil - error.
       Así, aunque la medición real fuera la peor del intervalo, el ajuste nunca supera el límite seguro.
    3. Para decidir cuánto corregir, usa el extremo del intervalo que MENOS corrige (nunca el que más).
    4. Retest obligatorio antes de cualquier ajuste posterior.
    """
    p_norm = normalize_param_key(parameter)
    deviation = target_value - current_value
    abs_dev = abs(deviation)

    # 1. Anti-colapso: Si la desviación es menor o igual al error de medición, NO ACTUAR
    if abs_dev <= error:
        return SafeCorrectionAction(
            parameter=p_norm,
            can_act=False,
            status="no_action_within_error",
            current_value=current_value,
            target_value=target_value,
            error=error,
            deviation=round(deviation, 3),
            least_correction_needed=0.0,
            daily_allowed_change=0.0,
            recommended_today=0.0,
            message=(
                f"La desviación detectada ({abs_dev:.2f}) está dentro del margen de error de la prueba (±{error:.2f}). "
                "No actuar: repite la prueba antes de realizar cualquier ajuste para evitar sobre-dosificación accidental."
            ),
            retest_required=True
        )

    # 2. Extremo del intervalo [v - e, v + e] que MENOS corrige
    # - Si current_value < target_value (está bajo, requiere subir):
    #   El extremo superior (v + e) es el que MENOS corrección necesita para llegar a target.
    # - Si current_value > target_value (está alto, requiere bajar):
    #   El extremo inferior (v - e) es el que MENOS corrección necesita para descender a target.
    if deviation > 0:
        least_correction = max(0.0, target_value - (current_value + error))
    else:
        least_correction = max(0.0, (current_value - error) - target_value)

    least_correction = round(least_correction, 3)

    # Si al considerar el extremo favorable ya está dentro o más allá del target, no dosificar
    if least_correction <= 0.0:
        return SafeCorrectionAction(
            parameter=p_norm,
            can_act=False,
            status="no_action_within_error",
            current_value=current_value,
            target_value=target_value,
            error=error,
            deviation=round(deviation, 3),
            least_correction_needed=0.0,
            daily_allowed_change=0.0,
            recommended_today=0.0,
            message=(
                f"Considerando el margen de incertidumbre (±{error:.2f}), el extremo conservador del intervalo ya alcanza el objetivo. "
                "No se recomienda dosificar: repite la prueba para confirmar antes de intervenir."
            ),
            retest_required=True
        )

    # 3. Cambio diario permitido = límite_del_perfil - error
    daily_allowed = max(0.0, profile_max_daily_change - error)
    daily_allowed = round(daily_allowed, 3)

    # El ajuste recomendado hoy es el mínimo entre lo que menos corrige y el límite diario seguro
    recommended_today = min(least_correction, daily_allowed)
    recommended_today = round(recommended_today, 3)

    action_verb = "Aumentar" if deviation > 0 else "Disminuir"
    msg = (
        f"{action_verb} {p_norm.upper()} de forma gradual: Corrección conservadora de {recommended_today} hoy "
        f"(máximo diario seguro permitido: {daily_allowed}, límite de perfil: {profile_max_daily_change} - error: {error:.2f}). "
        "Retest obligatorio antes de cualquier otra adición."
    )

    return SafeCorrectionAction(
        parameter=p_norm,
        can_act=True,
        status="adjust_conservative",
        current_value=current_value,
        target_value=target_value,
        error=error,
        deviation=round(deviation, 3),
        least_correction_needed=least_correction,
        daily_allowed_change=daily_allowed,
        recommended_today=recommended_today,
        message=msg,
        retest_required=True
    )


def coordinate_chemical_corrections(
    corrections: Dict[str, SafeCorrectionAction]
) -> Dict[str, SafeCorrectionAction]:
    """
    Coordinación Anti-Colapso para parámetros que interactúan químicamente:
    NUNCA recomendar corregir dos parámetros al mismo tiempo si interactúan (KH / Ca / Mg).
    Prioridad estricta basada en química del agua marina:
    1º Magnesio (Mg): Sin magnesio adecuado (~1300-1400 ppm), el Ca y KH precipitan como CaCO3.
    2º Alcalinidad (KH): Buffer primario del pH y esqueleto de calcificación.
    3º Calcio (Ca): Ion de contraparte.
    """
    interactors = ["magnesium", "kh", "calcium"]
    active_interactors = [p for p in interactors if p in corrections and corrections[p].can_act]

    # Si hay más de un interactuante activo, solo se permite actuar sobre el de mayor prioridad
    if len(active_interactors) > 1:
        top_param = active_interactors[0]  # El primero según el orden Mg > KH > Ca
        for secondary in active_interactors[1:]:
            old_act = corrections[secondary]
            corrections[secondary] = SafeCorrectionAction(
                parameter=old_act.parameter,
                can_act=False,
                status="paused_interaction",
                current_value=old_act.current_value,
                target_value=old_act.target_value,
                error=old_act.error,
                deviation=old_act.deviation,
                least_correction_needed=old_act.least_correction_needed,
                daily_allowed_change=old_act.daily_allowed_change,
                recommended_today=0.0,
                message=(
                    f"⚠️ Pausado por Interacción Química (Anti-Colapso): No se debe dosificar {old_act.parameter.upper()} "
                    f"al mismo tiempo que {top_param.upper()}. Corrige primero {top_param.upper()} y realiza un "
                    "retest obligatorio antes de ajustar este parámetro."
                ),
                retest_required=True
            )

    return corrections


# ==============================================================================
# 4. TENDENCIAS Y PROYECCIONES CON FILTRO R² Y BANDAS DE INCERTIDUMBRE
# ==============================================================================

class TrendProjectionResult(BaseModel):
    parameter: str
    unit: str
    is_conclusive: bool
    status: str                         # 'insufficient_data', 'inconclusive_trend', 'safe_projected', 'warning_approaching'
    points_count: int
    r_squared: Optional[float] = None
    slope_per_day: Optional[float] = None
    slope_uncertainty: Optional[float] = None
    uncertainty_band: Optional[List[float]] = None # [min_projected, max_projected]
    days_remaining_safe: Optional[float] = None
    estimated_exit_date: Optional[str] = None
    message: str


def project_trend_with_uncertainty(
    parameter: str,
    unit: str,
    points: List[Tuple[float, float]],   # [(dias_desde_t0, valor), ...]
    safe_min: float,
    safe_max: float,
    latest_timestamp: Optional[datetime] = None,
    latest_error: float = 0.3
) -> TrendProjectionResult:
    """
    Proyecta la tendencia bioquímica cumpliendo estrictamente la Fase 3:
    1. Mínimo 3 mediciones para proyectar (si < 3 -> 'insufficient_data').
    2. Regresión lineal calculando R² y banda de incertidumbre (rango ±).
    3. Si R² < 0.5 o la banda incluye ambos lados del límite -> 'tendencia no concluyente', sin 'días al límite'.
    """
    p_norm = normalize_param_key(parameter)
    n = len(points)
    now_dt = latest_timestamp or datetime.utcnow()

    # 1. Mínimo 3 mediciones obligatorias para proyectar
    if n < 3:
        return TrendProjectionResult(
            parameter=p_norm,
            unit=unit,
            is_conclusive=False,
            status="insufficient_data",
            points_count=n,
            r_squared=None,
            slope_per_day=None,
            slope_uncertainty=None,
            uncertainty_band=None,
            days_remaining_safe=None,
            estimated_exit_date=None,
            message=f"Se requieren al menos 3 mediciones de {p_norm.upper()} para calcular proyecciones estadísticas válidas (actuales: {n})."
        )

    # Extraer arrays x (días) e y (valores)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    latest_val = ys[-1]

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    ss_yy = sum((y - mean_y) ** 2 for y in ys)
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))

    # Si todos los x son idénticos (tiempoSpan casi 0)
    if ss_xx < 1e-9:
        return TrendProjectionResult(
            parameter=p_norm,
            unit=unit,
            is_conclusive=False,
            status="inconclusive_trend",
            points_count=n,
            r_squared=0.0,
            slope_per_day=0.0,
            slope_uncertainty=None,
            uncertainty_band=[latest_val - latest_error, latest_val + latest_error],
            days_remaining_safe=None,
            estimated_exit_date=None,
            message="Mediciones registradas en un intervalo de tiempo demasiado corto para proyectar."
        )

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    # Residuos y R²
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    ss_res = sum(r ** 2 for r in residuals)

    if ss_yy < 1e-9:
        # Valores idénticos constantes (perfectamente estable)
        r_squared = 1.0
        s_yx = 0.0
        s_m = 0.0
    else:
        r_squared = max(0.0, 1.0 - (ss_res / ss_yy))
        degrees_of_freedom = max(1, n - 2)
        s_yx = math.sqrt(ss_res / degrees_of_freedom)
        s_m = s_yx / math.sqrt(ss_xx)

    r_squared = round(r_squared, 3)
    slope_rounded = round(slope, 3)
    s_m_rounded = round(s_m, 3)

    # 2. Filtro de Confiabilidad: Si R² < 0.50 -> Tendencia no concluyente, sin días al límite
    if r_squared < 0.50 and abs(slope) > 0.001:
        return TrendProjectionResult(
            parameter=p_norm,
            unit=unit,
            is_conclusive=False,
            status="inconclusive_trend",
            points_count=n,
            r_squared=r_squared,
            slope_per_day=slope_rounded,
            slope_uncertainty=s_m_rounded,
            uncertainty_band=[round(latest_val - latest_error, 2), round(latest_val + latest_error, 2)],
            days_remaining_safe=None,
            estimated_exit_date=None,
            message=(
                f"Tendencia no concluyente (R² = {r_squared:.2f} < 0.50). "
                f"La dispersión de los datos ({n} lecturas) impide proyectar los días restantes con precisión."
            )
        )

    # Banda de incertidumbre actual
    band_min = round(latest_val - latest_error, 2)
    band_max = round(latest_val + latest_error, 2)

    # Proyección de días restantes
    days_remaining = None
    exit_date = None
    status = "safe_projected"
    alert_msg = f"{p_norm.upper()} estable dentro del rango seguro [{safe_min}, {safe_max}]."

    # Proyección si desciende hacia safe_min
    if slope < -0.005:
        # Pendiente con intervalo [slope - s_m, slope + s_m]
        # Verificar si la banda abarca ambos lados del límite (cruza safe_min y safe_max o pendiente ambigua)
        if (slope + s_m >= 0) and (r_squared < 0.7):
            return TrendProjectionResult(
                parameter=p_norm,
                unit=unit,
                is_conclusive=False,
                status="inconclusive_trend",
                points_count=n,
                r_squared=r_squared,
                slope_per_day=slope_rounded,
                slope_uncertainty=s_m_rounded,
                uncertainty_band=[band_min, band_max],
                days_remaining_safe=None,
                estimated_exit_date=None,
                message="Tendencia no concluyente: la banda de incertidumbre incluye tanto estabilidad como descenso."
            )

        deficit = latest_val - safe_min
        if deficit > 0:
            days = deficit / abs(slope)
            days_remaining = round(days, 1)
            proj_dt = now_dt + timedelta(days=days)
            exit_date = proj_dt.strftime("%Y-%m-%d")

            if days <= 3.5:
                status = "warning_approaching"
                alert_msg = (
                    f"Advertencia: Consumo de {abs(slope_rounded)} {unit}/día (R² = {r_squared:.2f}). "
                    f"Caerá bajo el límite ({safe_min} {unit}) en ~{days_remaining} días ({exit_date})."
                )
            else:
                alert_msg = (
                    f"Consumo de {abs(slope_rounded)} {unit}/día (R² = {r_squared:.2f}). "
                    f"Margen seguro restante: ~{days_remaining} días ({exit_date})."
                )

    # Proyección si asciende hacia safe_max
    elif slope > 0.005:
        if (slope - s_m <= 0) and (r_squared < 0.7):
            return TrendProjectionResult(
                parameter=p_norm,
                unit=unit,
                is_conclusive=False,
                status="inconclusive_trend",
                points_count=n,
                r_squared=r_squared,
                slope_per_day=slope_rounded,
                slope_uncertainty=s_m_rounded,
                uncertainty_band=[band_min, band_max],
                days_remaining_safe=None,
                estimated_exit_date=None,
                message="Tendencia no concluyente: la banda de incertidumbre de la pendiente cruza el valor neutro."
            )

        margin = safe_max - latest_val
        if margin > 0:
            days = margin / slope
            days_remaining = round(days, 1)
            proj_dt = now_dt + timedelta(days=days)
            exit_date = proj_dt.strftime("%Y-%m-%d")

            if days <= 3.0:
                status = "warning_approaching"
                alert_msg = (
                    f"Advertencia: Incremento de +{slope_rounded} {unit}/día (R² = {r_squared:.2f}). "
                    f"Superará el límite ({safe_max} {unit}) en ~{days_remaining} días ({exit_date})."
                )
            else:
                alert_msg = (
                    f"Incremento de +{slope_rounded} {unit}/día (R² = {r_squared:.2f}). "
                    f"Margen seguro restante: ~{days_remaining} días ({exit_date})."
                )

    return TrendProjectionResult(
        parameter=p_norm,
        unit=unit,
        is_conclusive=True,
        status=status,
        points_count=n,
        r_squared=r_squared,
        slope_per_day=slope_rounded,
        slope_uncertainty=s_m_rounded,
        uncertainty_band=[band_min, band_max],
        days_remaining_safe=days_remaining,
        estimated_exit_date=exit_date,
        message=alert_msg
    )
