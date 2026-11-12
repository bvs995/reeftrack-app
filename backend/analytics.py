"""
Motor de Análisis Predictivo Bioquímico para Acuarios.
Calcula tasas de consumo mediante regresión lineal sobre las últimas 3 a 5 lecturas,
estima fechas de salida del rango seguro (dKH 7.5 - 9.0) y proyecta acumulación de nitratos.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from backend.models import (
    Measurement,
    ParameterConsumption,
    WaterChangePrediction,
    PredictionResponse
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
    max_readings: int = 5
) -> Tuple[List[Tuple[float, float]], Optional[float], Optional[datetime]]:
    """
    Extrae las últimas 3 a 5 lecturas válidas de un parámetro dado.
    Retorna: (puntos_dias_valor, ultimo_valor, fecha_ultima_lectura)
    """
    valid = [
        m for m in measurements 
        if getattr(m, attribute_name) is not None
    ]
    if not valid:
        return [], None, None
    
    # Orden cronológico ascendente
    valid.sort(key=lambda m: m.timestamp)
    recent = valid[-max_readings:]
    
    t0 = recent[0].timestamp
    points = []
    for m in recent:
        delta_days = (m.timestamp - t0).total_seconds() / 86400.0
        val = float(getattr(m, attribute_name))
        points.append((delta_days, val))
        
    latest_val = float(getattr(recent[-1], attribute_name))
    latest_time = recent[-1].timestamp
    return points, latest_val, latest_time

def analyze_parameter_consumption(
    measurements: List[Measurement],
    attr: str,
    name: str,
    unit: str,
    safe_min: float,
    safe_max: float
) -> Tuple[ParameterConsumption, Optional[str]]:
    """
    Calcula la tasa de consumo diario y días restantes antes de salir del rango seguro.
    """
    points, latest_val, latest_time = extract_recent_time_series(measurements, attr, max_readings=5)
    safe_range = [safe_min, safe_max]
    
    if latest_val is None or len(points) < 2:
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
            alert_message=f"Se requieren al menos 2 mediciones de {name} para estimar la tasa de consumo."
        ), None

    slope = compute_linear_regression(points)
    if slope is None:
        slope = 0.0

    # Tasa de consumo: positiva cuando el buffer desciende
    daily_consumption = round(-slope, 3) if slope < 0 else 0.0
    slope_rounded = round(slope, 3)
    
    days_remaining = None
    exit_date = None
    status = "safe"
    alert = None

    # Evaluación respecto a rango seguro
    if latest_val < safe_min:
        status = "critical_below_safe"
        days_remaining = 0.0
        alert_msg = f"{name} en nivel crítico ({latest_val} {unit}), por debajo del mínimo seguro ({safe_min} {unit})."
        alert = alert_msg
    elif latest_val > safe_max:
        status = "critical_above_safe"
        days_remaining = 0.0
        alert_msg = f"{name} alto ({latest_val} {unit}), por encima del máximo seguro ({safe_max} {unit})."
        alert = alert_msg
    else:
        # Está dentro del rango seguro; proyectar cuándo saldrá
        if slope < -0.005:  # Bajando (consumo activo)
            deficit_to_min = latest_val - safe_min
            days = deficit_to_min / abs(slope)
            days_remaining = round(days, 1)
            projected_dt = latest_time + timedelta(days=days)
            exit_date = projected_dt.strftime("%Y-%m-%d")

            if days <= 3.5:
                status = "warning_approaching"
                alert_msg = (
                    f"Advertencia de Estabilización: Consumo de {abs(slope_rounded)} {unit}/día. "
                    f"Caerá bajo el límite ({safe_min} {unit}) en ~{days_remaining} días ({exit_date}). Se requiere calibrar dosificación."
                )
                alert = alert_msg
            else:
                status = "safe"
                alert_msg = (
                    f"Tasa de consumo: {abs(slope_rounded)} {unit}/día. "
                    f"Margen seguro restante: ~{days_remaining} días ({exit_date})."
                )
        elif slope > 0.005:  # Subiendo (dosificación excede consumo)
            margin_to_max = safe_max - latest_val
            days = margin_to_max / slope
            days_remaining = round(days, 1)
            projected_dt = latest_time + timedelta(days=days)
            exit_date = projected_dt.strftime("%Y-%m-%d")

            if days <= 3.0:
                status = "warning_approaching"
                alert_msg = (
                    f"Incremento de +{slope_rounded} {unit}/día. "
                    f"Alcanzará el límite ({safe_max} {unit}) en ~{days_remaining} días ({exit_date})."
                )
                alert = alert_msg
            else:
                status = "safe"
                alert_msg = (
                    f"Nivel incrementando +{slope_rounded} {unit}/día. "
                    f"Margen restante antes de {safe_max} {unit}: ~{days_remaining} días."
                )
        else:
            status = "safe"
            alert_msg = f"{name} estable a {latest_val} {unit} dentro del rango óptimo."

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
        alert_message=alert_msg
    )
    return param_result, alert

def analyze_nitrate_accumulation(
    measurements: List[Measurement],
    threshold_ppm: float = 20.0
) -> Tuple[WaterChangePrediction, Optional[str]]:
    """
    Proyecta acumulación de nitratos y calcula fecha estimada para sugerir cambio de agua.
    """
    points, latest_val, latest_time = extract_recent_time_series(measurements, "nitrate_ppm", max_readings=5)
    
    if latest_val is None:
        return WaterChangePrediction(
            current_nitrate_ppm=None,
            daily_accumulation_rate=None,
            threshold_ppm=threshold_ppm,
            days_until_threshold=None,
            suggested_water_change_date=None,
            suggested_percentage=20,
            urgency="safe",
            message="No hay mediciones de nitrato registradas."
        ), None

    if len(points) < 2:
        return WaterChangePrediction(
            current_nitrate_ppm=latest_val,
            daily_accumulation_rate=None,
            threshold_ppm=threshold_ppm,
            days_until_threshold=None,
            suggested_water_change_date=None,
            suggested_percentage=20,
            urgency="safe" if latest_val < threshold_ppm else "immediate",
            message=f"Última lectura: {latest_val} ppm. Se requieren al menos 2 mediciones para calcular la tasa de acumulación."
        ), None

    slope = compute_linear_regression(points)
    slope_rounded = round(slope if slope is not None else 0.0, 3)

    alert = None

    if latest_val >= threshold_ppm:
        urgency = "immediate"
        days_until = 0.0
        sugg_date = "Inmediato (Hoy)"
        pct = 25
        msg = (
            f"Nitrato actual ({latest_val} ppm) supera el umbral seguro de {threshold_ppm} ppm. "
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
                f"Alerta: Nitratos subiendo a +{slope_rounded} ppm/día. "
                f"Alcanzará el límite de {threshold_ppm} ppm en ~{days_until} días ({sugg_date}). "
                f"Programar cambio de agua del {pct}%."
            )
            alert = msg
        else:
            urgency = "approaching"
            pct = 15
            msg = (
                f"Tasa de acumulación de +{slope_rounded} ppm/día. "
                f"Fecha estimada para cambio de agua al superar {threshold_ppm} ppm: {sugg_date} (~{days_until} días)."
            )
    else:
        urgency = "safe"
        days_until = None
        sugg_date = "Rutina en 14 días"
        pct = 15
        msg = f"Nivel de nitratos controlado ({latest_val} ppm). Pendiente estable ({slope_rounded:+.2f} ppm/día)."

    pred = WaterChangePrediction(
        current_nitrate_ppm=latest_val,
        daily_accumulation_rate=slope_rounded,
        threshold_ppm=threshold_ppm,
        days_until_threshold=days_until,
        suggested_water_change_date=sugg_date,
        suggested_percentage=pct,
        urgency=urgency,
        message=msg
    )
    return pred, alert

def calculate_predictions(measurements: List[Measurement]) -> PredictionResponse:
    """
    Función principal del motor predictivo:
    - Evalúa nivel de confianza estadística basado en lecturas de los últimos 14 días.
    - Calcula consumo diario y días restantes de Alcalinidad dKH (rango 7.5 - 9.0).
    - Calcula consumo diario y días restantes de Calcio Ca (rango 400 - 450 ppm).
    - Proyecta acumulación de nitratos y fecha estimada para cambio de agua.
    - Consolida alertas biológicas activas.
    """
    now = datetime.utcnow()
    fourteen_days_ago = now - timedelta(days=14)
    
    # Conteo de mediciones en la ventana de 14 días
    recent_14_days = [m for m in measurements if m.timestamp >= fourteen_days_ago]
    count_14d = len(recent_14_days)
    total_count = len(measurements)

    # Nivel de confianza según requerimiento:
    # "si hay menos de 3 mediciones en los últimos 14 días, indicar que se necesitan más datos antes de predecir con exactitud"
    if count_14d < 3:
        confidence = "low"
        conf_msg = f"Nivel de confianza bajo ({count_14d} mediciones en los últimos 14 días). Se necesitan al menos 3 mediciones recientes para predecir con exactitud."
    elif count_14d < 5:
        confidence = "medium"
        conf_msg = f"Nivel de confianza moderado ({count_14d} mediciones en los últimos 14 días). Predicciones funcionales."
    else:
        confidence = "high"
        conf_msg = f"Nivel de confianza alto ({count_14d} mediciones en los últimos 14 días). Alta significancia estadística."

    active_alerts = []

    # 1. Alcalinidad (dKH) - Rango seguro requerido: 7.5 - 9.0 dKH
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

    # Si la confianza es baja, agregar alerta informativa
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
