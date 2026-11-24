"""
Motor de Análisis Predictivo Bioquímico para Acuarios.
AquaPulse - Fase 3:
- Exige mínimo 3 mediciones para proyectar.
- Regresión lineal con cálculo de R² y bandas de incertidumbre ±.
- Si R² < 0.50 o banda incluye ambos lados del límite -> 'tendencia no concluyente', sin 'días al límite'.
- Nutrientes NO3/PO4 en cero se muestran como '< e' (por debajo del límite de detección).
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Any
from backend.models import (
    Measurement,
    ParameterConsumption,
    WaterChangePrediction,
    PredictionResponse
)
from backend.uncertainty import (
    calculate_measurement_uncertainty,
    project_trend_with_uncertainty
)

def compute_linear_regression(points: List[Tuple[float, float]]) -> Optional[float]:
    """
    Calcula la pendiente (m) de una regresión lineal simple:
    y = m * x + b
    points: Lista de tuplas (x_dias, y_valor)
    Retorna m (unidades por día) o None si no hay suficientes puntos.
    """
    n = len(points)
    if n < 2:
        return None

    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_x2 = sum(p[0] ** 2 for p in points)

    denominator = (n * sum_x2 - (sum_x ** 2))
    if abs(denominator) < 1e-9:
        return 0.0

    slope = (n * sum_xy - (sum_x * sum_y)) / denominator
    return slope

def extract_recent_time_series(
    measurements: List[Measurement],
    attribute_name: str,
    max_readings: int = 10
) -> Tuple[List[Tuple[float, float]], Optional[float], Optional[datetime], Optional[Any]]:
    """
    Extrae las lecturas válidas recientes de un parámetro dado.
    Retorna: (puntos_dias_valor, ultimo_valor, fecha_ultima_lectura, ultima_medicion)
    """
    valid = [
        m for m in measurements 
        if getattr(m, attribute_name) is not None
    ]
    if not valid:
        return [], None, None, None

    # Orden cronológico ascendente
    valid.sort(key=lambda m: m.timestamp)
    recent = valid[-max_readings:]

    t0 = recent[0].timestamp
    points = []
    for m in recent:
        delta_days = (m.timestamp - t0).total_seconds() / 86400.0
        val = float(getattr(m, attribute_name))
        points.append((delta_days, val))

    latest_m = recent[-1]
    latest_val = float(getattr(latest_m, attribute_name))
    latest_time = latest_m.timestamp
    return points, latest_val, latest_time, latest_m

def analyze_parameter_consumption(
    measurements: List[Measurement],
    attr: str,
    name: str,
    unit: str,
    safe_min: float,
    safe_max: float
) -> Tuple[ParameterConsumption, Optional[str]]:
    """
    Calcula la tasa de consumo diario, días restantes y banda de incertidumbre.
    Fase 3:
    - Mínimo 3 mediciones para proyectar.
    - Si R² < 0.50 -> status='inconclusive_trend', days_remaining_safe=None.
    - Incorpora error metrológico e intervalo [v - e, v + e].
    """
    points, latest_val, latest_time, latest_m = extract_recent_time_series(measurements, attr, max_readings=10)
    safe_range = [safe_min, safe_max]

    if latest_val is None:
        return ParameterConsumption(
            parameter=name,
            unit=unit,
            latest_value=None,
            daily_consumption_rate=None,
            daily_slope=None,
            safe_range=safe_range,
            days_remaining_safe=None,
            estimated_exit_date=None,
            status="insufficient_data",
            alert_message=f"No hay mediciones registradas de {name}.",
            uncertainty=None,
            uncertainty_band=None,
            r_squared=None,
            is_conclusive=False,
            display_value=None
        ), None

    kit = getattr(latest_m, "kit", None) if latest_m else None
    is_cam = bool(getattr(latest_m, "is_camera_scan", False)) if latest_m else False
    u_int = calculate_measurement_uncertainty(attr, latest_val, kit=kit, is_camera_scan=is_cam)

    # 1. Regla Fase 3: Mínimo 3 mediciones para proyectar
    if len(points) < 3:
        return ParameterConsumption(
            parameter=name,
            unit=unit,
            latest_value=latest_val,
            daily_consumption_rate=None,
            daily_slope=None,
            safe_range=safe_range,
            days_remaining_safe=None,
            estimated_exit_date=None,
            status="insufficient_data",
            alert_message=f"Se requieren al menos 3 mediciones de {name} para estimar la tasa de consumo con validez estadística (actuales: {len(points)}).",
            uncertainty=u_int.error,
            uncertainty_band=[u_int.min_val, u_int.max_val],
            r_squared=None,
            is_conclusive=False,
            display_value=u_int.display_value
        ), None

    # 2. Proyección con regresión lineal y filtro R²
    trend = project_trend_with_uncertainty(
        parameter=attr,
        unit=unit,
        points=points,
        safe_min=safe_min,
        safe_max=safe_max,
        latest_timestamp=latest_time,
        latest_error=u_int.error
    )

    slope_rounded = trend.slope_per_day
    daily_consumption = round(-slope_rounded, 3) if (slope_rounded is not None and slope_rounded < 0) else 0.0

    # 3. Evaluación del estado actual frente a límites de seguridad
    alert = None

    if latest_val < safe_min:
        if u_int.max_val < safe_min:
            status = "critical_below_safe"
            alert_msg = f"{name} en nivel crítico confirmado ({latest_val} ± {u_int.error:.2f} {unit}), por debajo del mínimo seguro ({safe_min} {unit})."
        else:
            status = "warning_approaching"
            alert_msg = f"{name} en nivel probable bajo ({latest_val} ± {u_int.error:.2f} {unit}). Retest en 1–2 h para verificar."
        days_remaining = 0.0
        exit_date = None
        alert = alert_msg
    elif latest_val > safe_max:
        if u_int.min_val > safe_max:
            status = "critical_above_safe"
            alert_msg = f"{name} en nivel alto confirmado ({latest_val} ± {u_int.error:.2f} {unit}), por encima del máximo seguro ({safe_max} {unit})."
        else:
            status = "warning_approaching"
            alert_msg = f"{name} en nivel probable alto ({latest_val} ± {u_int.error:.2f} {unit}). Retest en 1–2 h para verificar."
        days_remaining = 0.0
        exit_date = None
        alert = alert_msg
    else:
        # Está dentro del rango seguro
        if not trend.is_conclusive:
            status = trend.status  # 'inconclusive_trend'
            days_remaining = None
            exit_date = None
            alert_msg = trend.message
        else:
            status = trend.status
            days_remaining = trend.days_remaining_safe
            exit_date = trend.estimated_exit_date
            alert_msg = trend.message
            if status == "warning_approaching":
                alert = alert_msg

    param_result = ParameterConsumption(
        parameter=name,
        unit=unit,
        latest_value=latest_val,
        daily_consumption_rate=daily_consumption,
        daily_slope=slope_rounded,
        safe_range=safe_range,
        days_remaining_safe=days_remaining,
        estimated_exit_date=exit_date,
        status=status,
        alert_message=alert_msg,
        uncertainty=u_int.error,
        uncertainty_band=[u_int.min_val, u_int.max_val],
        r_squared=trend.r_squared,
        is_conclusive=trend.is_conclusive,
        display_value=u_int.display_value
    )
    return param_result, alert

def analyze_nitrate_accumulation(
    measurements: List[Measurement],
    threshold_ppm: float = 20.0
) -> Tuple[WaterChangePrediction, Optional[str]]:
    """
    Proyecta acumulación de nitratos y calcula fecha estimada para sugerir cambio de agua.
    Fase 3:
    - Mínimo 3 mediciones para proyectar.
    - Si R² < 0.50 -> 'inconclusive_trend', sin días al límite.
    - Nitrato en cero se muestra como '< e' (por debajo del límite de detección).
    """
    points, latest_val, latest_time, latest_m = extract_recent_time_series(measurements, "nitrate_ppm", max_readings=10)

    if latest_val is None:
        return WaterChangePrediction(
            current_nitrate_ppm=None,
            daily_accumulation_rate=None,
            threshold_ppm=threshold_ppm,
            days_until_threshold=None,
            suggested_water_change_date=None,
            suggested_percentage=20,
            urgency="safe",
            message="No hay mediciones de nitrato registradas.",
            uncertainty=None,
            uncertainty_band=None,
            r_squared=None,
            is_conclusive=False,
            display_value=None
        ), None

    kit = getattr(latest_m, "kit", None) if latest_m else None
    is_cam = bool(getattr(latest_m, "is_camera_scan", False)) if latest_m else False
    u_int = calculate_measurement_uncertainty("nitrate", latest_val, kit=kit, is_camera_scan=is_cam)

    # 1. Regla Fase 3: Mínimo 3 mediciones
    if len(points) < 3:
        return WaterChangePrediction(
            current_nitrate_ppm=latest_val,
            daily_accumulation_rate=None,
            threshold_ppm=threshold_ppm,
            days_until_threshold=None,
            suggested_water_change_date=None,
            suggested_percentage=20,
            urgency="insufficient_data",
            message=f"Se requieren al menos 3 mediciones de nitrato para calcular proyecciones (actuales: {len(points)}).",
            uncertainty=u_int.error,
            uncertainty_band=[u_int.min_val, u_int.max_val],
            r_squared=None,
            is_conclusive=False,
            display_value=u_int.display_value
        ), None

    # 2. Regresión lineal y cálculo de R²
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(points)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    ss_yy = sum((y - mean_y) ** 2 for y in ys)
    ss_xy = sum((x - mean_x) * (y - mean_y) for x in xs)

    if ss_xx < 1e-9:
        slope = 0.0
        r_squared = 0.0
    else:
        slope = ss_xy / ss_xx
        if ss_yy < 1e-9:
            r_squared = 1.0
        else:
            residuals = [y - (slope * (x - mean_x) + mean_y) for x, y in zip(xs, ys)]
            ss_res = sum(r ** 2 for r in residuals)
            r_squared = max(0.0, 1.0 - (ss_res / ss_yy))

    slope_rounded = round(slope, 3)
    r_squared = round(r_squared, 3)
    alert = None

    # 3. Filtro R² < 0.50
    if r_squared < 0.50 and abs(slope_rounded) > 0.02 and latest_val < threshold_ppm:
        return WaterChangePrediction(
            current_nitrate_ppm=latest_val,
            daily_accumulation_rate=slope_rounded,
            threshold_ppm=threshold_ppm,
            days_until_threshold=None,
            suggested_water_change_date=None,
            suggested_percentage=15,
            urgency="inconclusive_trend",
            message=f"Tendencia de nitratos no concluyente (R² = {r_squared:.2f} < 0.50). Dispersión elevada en las mediciones.",
            uncertainty=u_int.error,
            uncertainty_band=[u_int.min_val, u_int.max_val],
            r_squared=r_squared,
            is_conclusive=False,
            display_value=u_int.display_value
        ), None

    if latest_val >= threshold_ppm:
        urgency = "immediate"
        days_until = 0.0
        sugg_date = "Inmediato (Hoy)"
        pct = 25
        msg = (
            f"Nitrato actual ({u_int.display_value} ppm ± {u_int.error:.2f}) supera el umbral seguro de {threshold_ppm} ppm. "
            f"Se sugiere cambio de agua urgente del {pct}% para restablecer parámetros."
        )
        alert = msg
    elif slope_rounded > 0.05:  # Acumulando nitratos
        margin = threshold_ppm - latest_val
        days = margin / slope_rounded
        days_until = round(days, 1)
        est_dt = latest_time + timedelta(days=days)
        sugg_date = est_dt.strftime("%Y-%m-%d")

        if days_until <= 3.0:
            urgency = "immediate"
            pct = 20
            msg = (
                f"Alerta: Nitratos subiendo a +{slope_rounded} ppm/día (R² = {r_squared:.2f}). "
                f"Alcanzará el límite de {threshold_ppm} ppm en ~{days_until} días ({sugg_date}). "
                f"Programar cambio de agua del {pct}%."
            )
            alert = msg
        else:
            urgency = "approaching"
            pct = 15
            msg = (
                f"Tasa de acumulación de +{slope_rounded} ppm/día (R² = {r_squared:.2f}). "
                f"Fecha estimada para cambio de agua al superar {threshold_ppm} ppm: {sugg_date} (~{days_until} días)."
            )
    else:
        urgency = "safe"
        days_until = None
        sugg_date = "Rutina en 14 días"
        pct = 15
        msg = f"Nivel de nitratos controlado ({u_int.display_value} ppm). Pendiente estable ({slope_rounded:+.2f} ppm/día)."

    pred = WaterChangePrediction(
        current_nitrate_ppm=latest_val,
        daily_accumulation_rate=slope_rounded,
        threshold_ppm=threshold_ppm,
        days_until_threshold=days_until,
        suggested_water_change_date=sugg_date,
        suggested_percentage=pct,
        urgency=urgency,
        message=msg,
        uncertainty=u_int.error,
        uncertainty_band=[u_int.min_val, u_int.max_val],
        r_squared=r_squared,
        is_conclusive=True,
        display_value=u_int.display_value
    )
    return pred, alert

def calculate_predictions(measurements: List[Measurement]) -> PredictionResponse:
    """
    Función principal del motor predictivo con metrología de incertidumbre:
    - Evalúa nivel de confianza estadística basado en lecturas de los últimos 14 días.
    - Proyecta consumo de Alcalinidad dKH con intervalos y filtro R² >= 0.50.
    - Proyecta consumo de Calcio Ca con intervalos y filtro R² >= 0.50.
    - Proyecta acumulación de nitratos y fecha estimada para cambio de agua.
    - Consolida alertas biológicas activas.
    """
    now = datetime.utcnow()
    fourteen_days_ago = now - timedelta(days=14)

    recent_14_days = [m for m in measurements if m.timestamp >= fourteen_days_ago]
    count_14d = len(recent_14_days)
    total_count = len(measurements)

    if count_14d < 3:
        confidence = "low"
        conf_msg = f"Nivel de confianza bajo ({count_14d} mediciones en los últimos 14 días). Se necesitan al menos 3 mediciones recientes para predecir con exactitud."
    elif count_14d < 5:
        confidence = "medium"
        conf_msg = f"Nivel de confianza moderado ({count_14d} mediciones en los últimos 14 días). Predicciones funcionales con margen de incertidumbre."
    else:
        confidence = "high"
        conf_msg = f"Nivel de confianza alto ({count_14d} mediciones en los últimos 14 días). Alta significancia estadística."

    active_alerts = []

    # 1. Alcalinidad (dKH) - Rango seguro estándar arrecifal: 7.5 - 9.0 dKH
    alk_result, alk_alert = analyze_parameter_consumption(
        measurements,
        attr="alkalinity_dkh",
        name="Alcalinidad (dKH)",
        unit="dKH",
        safe_min=7.5,
        safe_max=9.0
    )
    if alk_alert:
        active_alerts.append(alk_alert)

    # 2. Calcio (ppm) - Rango seguro estándar arrecifal: 400 - 450 ppm
    ca_result, ca_alert = analyze_parameter_consumption(
        measurements,
        attr="calcium_ppm",
        name="Calcio (ppm)",
        unit="ppm",
        safe_min=400.0,
        safe_max=450.0
    )
    if ca_alert:
        active_alerts.append(ca_alert)

    # 3. Predicción de acumulación de nitratos (límite 20 ppm)
    wc_result, no3_alert = analyze_nitrate_accumulation(
        measurements,
        threshold_ppm=20.0
    )
    if no3_alert:
        active_alerts.append(no3_alert)

    # Si la confianza es baja, agregar advertencia informativa
    if confidence == "low" and total_count > 0:
        active_alerts.insert(0, f"Advertencia de Confiabilidad: {conf_msg}")

    return PredictionResponse(
        confidence_level=confidence,
        confidence_message=conf_msg,
        measurements_count_last_14_days=count_14d,
        total_measurements=total_count,
        alkalinity=alk_result,
        calcium=ca_result,
        water_change_prediction=wc_result,
        active_alerts=active_alerts
    )
