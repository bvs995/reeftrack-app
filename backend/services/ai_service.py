import os
import re
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Set
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models import (
    AnalisisAcuarioSchema,
    AnalisisAcuarioResponse,
    DosisRecomendada,
    MedicionAcuario,
    Measurement,
    DiagnosticAudit
)
from backend.marine_profiles import (
    get_marine_profile,
    evaluate_marine_alerts,
    DOSING_METHOD_LABELS,
    FLOW_PROFILE_LABELS
)
from backend.uncertainty import (
    calculate_measurement_uncertainty,
    evaluate_parameter_with_interval,
    evaluate_delta_24h_uncertainty
)
from backend.ai_validator import (
    AIDiagnosisOutput,
    DiagnosticFinding,
    AllowedAction,
    ALLOWED_ACTIONS,
    SEVERITY_HIERARCHY,
    load_versioned_system_prompt,
    validate_and_sanitize_ai_diagnosis,
    execute_double_pass_verification,
    generate_rules_deterministic_diagnosis
)

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger("aquapulse.ai_service")

# Modelos recomendados: usuario solicita gemini-2.5-flash, con fallback a gemini-3.1-flash-lite y 3.8-flash
PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODELS = [PRIMARY_MODEL, "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]


def first_not_none(*vals):
    """
    Retorna el primer valor que no sea None (P0.5).
    Preserva estrictamente el valor numérico 0 y 0.0 para evitar descartar mediciones válidas.
    """
    for v in vals:
        if v is not None:
            return v
    return None


def get_current_month_ai_spend(db: Optional[Session]) -> float:
    """Calcula el gasto acumulado en USD en llamadas a Gemini en el mes en curso (Fase 7)."""
    if not db:
        return 0.0
    try:
        now = datetime.utcnow()
        first_day_of_month = datetime(now.year, now.month, 1)
        total = db.query(func.coalesce(func.sum(DiagnosticAudit.cost_usd), 0.0)).filter(
            DiagnosticAudit.created_at >= first_day_of_month
        ).scalar()
        return round(float(total or 0.0), 4)
    except Exception as e:
        logger.debug(f"Aviso consultando gasto de IA: {e}")
        return 0.0


def record_diagnostic_audit(
    db: Optional[Session],
    user_id: Optional[int],
    tank_id: Optional[int],
    prompt_version: str,
    inputs: Dict[str, Any],
    rules_alerts: List[Dict[str, Any]],
    raw_ai_output: Optional[str],
    status: str,
    rejection_reason: Optional[str] = None,
    cost_usd: float = 0.0,
    token_count: int = 0,
    latency_ms: float = 0.0
) -> Optional[DiagnosticAudit]:
    """Registra una traza de auditoría operativa del diagnóstico en la base de datos (Fase 7)."""
    if not db:
        return None
    try:
        safe_inputs = {}
        for k, v in inputs.items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                safe_inputs[k] = v
            else:
                safe_inputs[k] = str(v)

        audit_entry = DiagnosticAudit(
            user_id=user_id,
            tank_id=tank_id,
            prompt_version=prompt_version,
            inputs=safe_inputs,
            rules_alerts=rules_alerts,
            raw_ai_output=raw_ai_output[:4000] if raw_ai_output else None,
            status=status,
            rejection_reason=rejection_reason,
            cost_usd=round(cost_usd, 6),
            token_count=int(token_count),
            latency_ms=round(latency_ms, 2)
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)

        # Monitorear tasa de descarte y alertar si sube (> 25%)
        check_discard_rate_alert(db)
        return audit_entry
    except Exception as e:
        logger.warning(f"Aviso guardando auditoría de diagnóstico: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def check_discard_rate_alert(db: Session, sample_size: int = 50, threshold: float = 0.25) -> bool:
    """Evalúa si la tasa de descarte de la IA en los últimos N diagnósticos supera el umbral crítico (Fase 7)."""
    try:
        recent = db.query(DiagnosticAudit.status).order_by(DiagnosticAudit.created_at.desc()).limit(sample_size).all()
        if len(recent) < 5:
            return False
        total = len(recent)
        discarded = sum(1 for (st,) in recent if st == "discarded")
        rate = discarded / total
        if rate > threshold:
            logger.warning(
                f"🚨 ALERTA OPERATIVA FASE 7: Tasa de descarte de IA anormalmente alta: "
                f"{rate * 100:.1f}% ({discarded}/{total} descartados en últimas evaluaciones). "
                f"Posible deriva del modelo Gemini o inconsistencia de prompt."
            )
            return True
        return False
    except Exception as e:
        logger.debug(f"Aviso comprobando tasa de descarte: {e}")
        return False


def get_ai_audit_statistics(db: Session, sample_size: int = 100) -> Dict[str, Any]:
    """Retorna métricas consolidadas de auditoría operativa para /api/admin y monitor /api/health (Fase 7)."""
    try:
        budget_limit = float(os.getenv("GEMINI_MONTHLY_BUDGET_USD", "25.0"))
        now = datetime.utcnow()
        first_day_of_month = datetime(now.year, now.month, 1)

        month_spend = db.query(func.coalesce(func.sum(DiagnosticAudit.cost_usd), 0.0)).filter(
            DiagnosticAudit.created_at >= first_day_of_month
        ).scalar() or 0.0

        recent = db.query(DiagnosticAudit.status).order_by(DiagnosticAudit.created_at.desc()).limit(sample_size).all()
        total = len(recent)
        discarded = sum(1 for (st,) in recent if st == "discarded")
        accepted = sum(1 for (st,) in recent if st == "accepted")
        sanitized = sum(1 for (st,) in recent if st == "sanitized")
        fallback = sum(1 for (st,) in recent if st in ["fallback", "budget_exceeded"])
        rate = (discarded / total) if total > 0 else 0.0
        alert = rate > 0.25 and total >= 5

        budget_status = "exceeded" if month_spend >= budget_limit else ("warning" if month_spend >= budget_limit * 0.8 else "ok")

        return {
            "total_evaluations": total,
            "discarded_count": discarded,
            "accepted_count": accepted,
            "sanitized_count": sanitized,
            "fallback_count": fallback,
            "discard_rate": round(rate, 3),
            "discard_rate_alert": alert,
            "total_cost_usd": round(float(month_spend), 4),
            "budget_limit_usd": budget_limit,
            "budget_status": budget_status
        }
    except Exception as e:
        logger.error(f"Error generando estadísticas de auditoría IA: {e}")
        return {
            "total_evaluations": 0,
            "discarded_count": 0,
            "accepted_count": 0,
            "sanitized_count": 0,
            "fallback_count": 0,
            "discard_rate": 0.0,
            "discard_rate_alert": False,
            "total_cost_usd": 0.0,
            "budget_limit_usd": 25.0,
            "budget_status": "ok"
        }


def obtener_tendencia_ultimas_48h(db: Session, acuario_id: int) -> str:
    """
    Obtiene el historial cronológico de mediciones de un acuario en las últimas 48 horas
    y lo resume en texto estructurado comprensible para la IA de AquaPulse.
    """
    hace_48_horas = datetime.utcnow() - timedelta(hours=48)

    registros = (
        db.query(MedicionAcuario)
        .filter(MedicionAcuario.acuario_id == acuario_id)
        .filter(MedicionAcuario.fecha_registro >= hace_48_horas)
        .order_by(MedicionAcuario.fecha_registro.asc())
        .all()
    )

    if not registros:
        try:
            registros = (
                db.query(Measurement)
                .filter(Measurement.tank_id == acuario_id)
                .filter(Measurement.timestamp >= hace_48_horas)
                .order_by(Measurement.timestamp.asc())
                .all()
            )
        except Exception:
            pass

    if not registros:
        return "No hay registros en las últimas 48 horas. Estado inicial o estable."

    resumen_historial = []
    for reg in registros:
        fecha_str = getattr(reg, "fecha_registro", None) or getattr(reg, "timestamp", None)
        fecha_display = fecha_str.strftime("%Y-%m-%d %H:%M") if hasattr(fecha_str, "strftime") else str(fecha_str)
        temp_val = getattr(reg, "temperature", None) or getattr(reg, "temperatura", None)
        kh_val = getattr(reg, "kh", None) or getattr(reg, "alkalinity_dkh", None)
        ca_val = getattr(reg, "calcium", None) or getattr(reg, "calcium_ppm", None) or getattr(reg, "calcio", None)
        po4_val = getattr(reg, "phosphate", None) or getattr(reg, "phosphate_ppm", None) or getattr(reg, "fosfato", None)
        sal_val = getattr(reg, "salinity", None) or getattr(reg, "salinity_ppt", None)

        extra = []
        if temp_val is not None:
            extra.append(f"Temp: {temp_val} °C")
        if sal_val is not None:
            extra.append(f"Salinidad: {sal_val}")

        extra_str = f", {', '.join(extra)}" if extra else ""
        resumen_historial.append(
            f"[{fecha_display}] pH: {reg.ph}, KH: {kh_val} dKH, Ca: {ca_val} ppm, PO4: {po4_val} ppm{extra_str}"
        )

    return "\n".join(resumen_historial)


def _generar_analisis_fallback(
    nombre: str,
    volumen: float,
    ph: Optional[float],
    kh: Optional[float],
    calcio: Optional[float],
    magnesio: Optional[float],
    nitrato: Optional[float],
    fosfato: Optional[float],
    tendencia: str,
    temperatura: Optional[float] = None,
    tipo: str = "mixto",
    reef_profile: Optional[str] = None,
    dosing_method: Optional[str] = None,
    lighting_par: Optional[int] = None,
    flow_profile: Optional[str] = None,
    salinity: Optional[float] = None,
    ammonia: Optional[float] = None,
    nitrite: Optional[float] = None,
    trace_elements: Optional[Dict[str, Any]] = None,
    test_methods: Optional[Dict[str, Any]] = None,
    delta_kh_24h: Optional[float] = None,
    dynamic_alerts: Optional[List[Dict[str, Any]]] = None,
    maintenance_tasks: Optional[List[Dict[str, Any]]] = None
) -> AnalisisAcuarioResponse:
    """Genera un análisis clínico estructurado inteligente de respaldo respetando las reglas de biotipo y perfiles marinos."""
    risk = "Bajo"
    tipo_normalizado = (tipo or "mixto").strip().lower()
    es_marino = tipo_normalizado in ["arrecife", "reef", "mixed", "mixto", "marine_fish", "peces_marinos", "fowlr", "fish_only", "soft_reef", "mixed_reef", "sps_reef", "lps_reef"]
    
    profile_info = get_marine_profile(reef_profile or tipo_normalizado)
    profile_id = profile_info["id"]

    alert = f"Parámetros dentro de umbrales operativos estables para '{profile_info['name']}'. Mantener rutina regular de filtración."
    acciones: List[DosisRecomendada] = []

    # 0. Correlación con Equipo y Mantenimiento Mecánico
    if maintenance_tasks:
        # A. Picos de NO3 o PO4 + filtración mecánica/skimmer vencida o > 7 días
        mech_or_skimmer_overdue = [
            t for t in maintenance_tasks
            if t.get("task_key") in ["mechanical_filter", "skimmer_cup"]
            and (t.get("status") == "overdue" or (t.get("days_since_last") is not None and t.get("days_since_last") > 7))
        ]
        has_high_nutrients = (
            (nitrato is not None and nitrato > (profile_info["targets"]["nitrate"]["max"] if es_marino else 25.0)) or
            (fosfato is not None and fosfato > (profile_info["targets"]["phosphate"]["max"] if es_marino else 0.10))
        )
        if mech_or_skimmer_overdue and has_high_nutrients:
            task_names = ", ".join(t.get("title", "") for t in mech_or_skimmer_overdue)
            acciones.append(
                DosisRecomendada(
                    parametro="Filtración Mecánica / Skimmer",
                    producto=f"Limpieza prioritaria de filtración ({task_names})",
                    cantidad_sugerida="La acumulación de detrito orgánico en calcetines/esponjas o copa de skimmer es la causa raíz primaria de NO3/PO4. Lavar o sustituir antes de añadir resinas o químicos."
                )
            )

        # B. SPS / Mixto / LPS + bombas de recirculación vencidas
        if es_marino and profile_id in ["sps_reef", "mixed_reef", "lps_reef"]:
            pumps_overdue = [t for t in maintenance_tasks if t.get("task_key") == "pumps_cleaning" and t.get("status") == "overdue"]
            if pumps_overdue:
                acciones.append(
                    DosisRecomendada(
                        parametro="Flujo / Bombas de recirculación",
                        producto="Limpieza profunda y descalcificación con ácido cítrico",
                        cantidad_sugerida="Limpieza de bombas vencida. La precipitación de sarro reduce hasta 40% el flujo real, propiciando zonas muertas y acumulación de cianobacteria."
                    )
                )

        # C. Oscilación de KH + dosificadoras/sondas vencidas
        has_kh_issue = any("KH" in d.get("title", "") for d in (dynamic_alerts or [])) or (delta_kh_24h is not None and delta_kh_24h > 0.3)
        if has_kh_issue:
            doser_overdue = [t for t in maintenance_tasks if t.get("task_key") == "doser_probes" and t.get("status") == "overdue"]
            if doser_overdue:
                acciones.append(
                    DosisRecomendada(
                        parametro="Dosificadoras / Sondas",
                        producto="Calibración volumétrica de cabezales y sondas",
                        cantidad_sugerida="Inestabilidad de KH detectada con calibración de dosificadoras vencida. Verifica mangueras y calibra la dosificación antes de ajustar dosis diarias."
                    )
                )

    # 1. Integración de alertas dinámicas prioritarias
    if dynamic_alerts:
        for d_alert in dynamic_alerts:
            sev = d_alert.get("severity")
            if sev == "critical":
                risk = "Crítico"
                alert = d_alert["message"]
            elif sev == "warning" and risk != "Crítico":
                risk = "Moderado"
                alert = d_alert["message"]
            
            acciones.append(
                DosisRecomendada(
                    parametro=d_alert.get("title", "Alerta Dinámica"),
                    producto=d_alert.get("recommendation", "Acción preventiva"),
                    cantidad_sugerida=d_alert.get("message", "")
                )
            )

    # 2. Monitoreo de Temperatura
    if temperatura is not None:
        if temperatura > 27.5:
            risk = "Crítico" if temperatura >= 28.5 else ("Moderado" if risk == "Bajo" else risk)
            acciones.append(
                DosisRecomendada(
                    parametro="Temperatura",
                    producto="Enfriador (Chiller) o ventiladores de superficie",
                    cantidad_sugerida=f"Temperatura a {temperatura} °C excede el rango óptimo. Aumentar disipación térmica."
                )
            )
        elif temperatura < 23.5:
            risk = "Moderado" if risk == "Bajo" else risk
            acciones.append(
                DosisRecomendada(
                    parametro="Temperatura",
                    producto="Calentador termostático",
                    cantidad_sugerida=f"Temperatura a {temperatura} °C por debajo del rango seguro. Calibrar calentador a 25.0 °C."
                )
            )

    # 3. Monitoreo de Salinidad
    if salinity is not None and es_marino:
        targets = profile_info["targets"]["salinity"]
        if salinity < targets["min"]:
            risk = "Moderado" if risk == "Bajo" else risk
            acciones.append(
                DosisRecomendada(
                    parametro="Salinidad",
                    producto="Agua salada concentrada en reposición",
                    cantidad_sugerida=f"Salinidad a {salinity} SG por debajo del mínimo ({targets['min']} SG). Rellenar evaporación con agua salada suavemente."
                )
            )
        elif salinity > targets["max"]:
            risk = "Moderado" if risk == "Bajo" else risk
            acciones.append(
                DosisRecomendada(
                    parametro="Salinidad",
                    producto="Agua pura de osmosis (RO/DI)",
                    cantidad_sugerida=f"Salinidad a {salinity} SG por encima del máximo ({targets['max']} SG). Retirar agua salada y agregar RO/DI."
                )
            )

    # 4. Amoníaco y Nitrito
    if ammonia is not None and ammonia > 0.05:
        risk = "Crítico"
        alert = f"Amoníaco detectable a {ammonia} ppm. Riesgo inminente de toxicidad branquial en peces e invertebrados."
        acciones.append(
            DosisRecomendada(
                parametro="Amoníaco (NH3)",
                producto="Acondicionador neutralizador de amonio (ej. Seachem Prime) y bacterias vivas nitrificantes",
                cantidad_sugerida="Dosis de emergencia y suspender alimentación."
            )
        )
    if nitrite is not None and nitrite > 0.1:
        risk = "Crítico" if risk != "Crítico" else risk
        acciones.append(
            DosisRecomendada(
                parametro="Nitrito (NO2)",
                producto="Bacterias nitrificantes y cambio de agua parcial",
                cantidad_sugerida=f"Nitrito a {nitrite} ppm. Añadir ampolletas de bacterias heterótrofas/autótrofas."
            )
        )

    # 5. KH y Balance de Nutrientes (Solo para perfiles con corales)
    if kh is not None and es_marino and profile_id != "fish_only":
        kh_targets = profile_info["targets"]["kh"]
        if kh < kh_targets["min"]:
            risk = "Crítico" if kh < 6.8 else ("Moderado" if risk == "Bajo" else risk)
            acciones.append(
                DosisRecomendada(
                    parametro="Alcalinidad (KH)",
                    producto="Solución tampón de carbonatos / Bicarbonato sódico",
                    cantidad_sugerida=f"{round(float(volumen or 280) * 0.04, 1)} ml/g diluido en zona de alto flujo. Incrementar máx 0.5 dKH/día."
                )
            )
        elif kh > kh_targets["max"]:
            risk = "Moderado" if risk == "Bajo" else risk
            acciones.append(
                DosisRecomendada(
                    parametro="Alcalinidad (KH)",
                    producto="Ajuste de dosificadora",
                    cantidad_sugerida=f"KH a {kh} dKH por encima del rango de {profile_info['name']} ({kh_targets['min']}-{kh_targets['max']} dKH). Suspender dosificación 24h."
                )
            )

    # 6. Nutrientes NO3 y PO4
    if es_marino:
        no3_targets = profile_info["targets"]["nitrate"]
        po4_targets = profile_info["targets"]["phosphate"]
        if nitrato is not None:
            if nitrato > no3_targets["max"]:
                risk = "Moderado" if risk == "Bajo" else risk
                acciones.append(
                    DosisRecomendada(
                        parametro="Nitrato (NO3)",
                        producto="Cambio parcial de agua y ajuste de skimmer",
                        cantidad_sugerida=f"{round(float(volumen or 280) * 0.15, 1)} L (15%) con agua RO/DI y sal marina de calidad."
                    )
                )
        if fosfato is not None and profile_id != "fish_only":
            if fosfato > po4_targets["max"]:
                risk = "Moderado" if risk == "Bajo" else risk
                acciones.append(
                    DosisRecomendada(
                        parametro="Fosfato (PO4)",
                        producto="Resina de óxido férrico (GFO) o eliminador de PO4 a base de lantano",
                        cantidad_sugerida="Añadir en reactor de lecho fluido con flujo lento para evitar precipitación."
                    )
                )

    if not acciones:
        acciones = [
            DosisRecomendada(
                parametro="Rutina de Mantenimiento",
                producto="Cambio de agua regular y monitoreo semanal",
                cantidad_sugerida=f"{round(float(volumen or 280) * 0.1, 1)} litros (10%) para reposición de oligoelementos y dilución de compuestos orgánicos."
            )
        ]

    diagnostico = (
        f"Diagnóstico técnico AquaPulse para '{nombre}' ({volumen} L, biotipo '{tipo}', perfil '{profile_info['name']}'): "
        f"pH={ph if ph is not None else '8.2'}, "
        f"KH={kh if kh is not None else '8.2'} dKH, "
        f"{f'Ca={calcio} ppm, Mg={magnesio} ppm, ' if profile_id != 'fish_only' else ''}"
        f"NO3={nitrato if nitrato is not None else '5.0'} ppm, "
        f"PO4={fosfato if fosfato is not None else '0.04'} ppm"
        f"{f', Temp={temperatura} °C' if temperatura is not None else ''}"
        f"{f', Salinidad={salinity} SG' if salinity is not None else ''}. "
        f"Tendencia: '{tendencia}'."
    )

    return AnalisisAcuarioResponse(
        diagnostico_general=diagnostico,
        nivel_riesgo=risk,
        alerta_predictiva=alert,
        acciones_correctoras=acciones
    )


def analizar_parametros_estructurado(
    datos_acuario: dict,
    allow_fallback: bool = True,
    db: Optional[Session] = None,
    user_id: Optional[int] = None,
    tank_id: Optional[int] = None
) -> AIDiagnosisOutput:
    """
    Arquitectura Fase 4 & 7 (Operación y Auditoría):
    1. Reglas determinísticas (con intervalos de incertidumbre)
    2. Control de presupuesto de gasto en Gemini (GEMINI_MONTHLY_BUDGET_USD)
    3. Gemini con System Prompt versionado (explica, no decide, temp <= 0.2)
    4. Validador estricto anti-alucinación, Doble Pasada y registro de auditoría en BD
    5. Monitoreo de tasa de descarte y Fallback heurístico por reglas (nunca 500)
    """
    start_time = time.time()
    effective_user_id = user_id or datos_acuario.get("user_id")
    effective_tank_id = tank_id or datos_acuario.get("tank_id") or datos_acuario.get("acuario_id")

    # Fase 2 & 6: Lectura de cámara sin confirmar -> no entra al diagnóstico
    if datos_acuario.get("is_draft") or datos_acuario.get("status") == "draft":
        raise ValueError(
            "Lectura de cámara en estado borrador (sin confirmar): toda lectura por visión es un borrador "
            "que el usuario debe confirmar o corregir antes de guardarse o usarse en un diagnóstico."
        )
    api_key = (
        os.environ.get("GEMINI_API_KEY") or
        os.environ.get("GOOGLE_API_KEY") or
        ""
    ).strip()

    is_dummy_key = (
        not api_key or
        api_key == "tu_gemini_api_key_aqui" or
        api_key.startswith("inserta_")
    )

    nombre = datos_acuario.get("nombre_acuario", "Principal")
    volumen = float(datos_acuario.get("volumen_litros") or 280.0)
    tipo = (
        datos_acuario.get("tipo") or
        datos_acuario.get("tank_type") or
        datos_acuario.get("type") or
        "mixto"
    )
    reef_profile = datos_acuario.get("reef_profile")
    dosing_method = datos_acuario.get("dosing_method")
    lighting_par = datos_acuario.get("lighting_par")
    flow_profile = datos_acuario.get("flow_profile")

    ph = first_not_none(datos_acuario.get("ph"))
    kh = first_not_none(datos_acuario.get("kh"), datos_acuario.get("alkalinity_dkh"))
    calcio = first_not_none(datos_acuario.get("calcio"), datos_acuario.get("calcium"), datos_acuario.get("calcium_ppm"))
    magnesio = first_not_none(datos_acuario.get("magnesio"), datos_acuario.get("magnesium"), datos_acuario.get("magnesium_ppm"))
    nitrato = first_not_none(datos_acuario.get("nitrato"), datos_acuario.get("nitrate"), datos_acuario.get("nitrate_ppm"))
    fosfato = first_not_none(datos_acuario.get("fosfato"), datos_acuario.get("phosphate"), datos_acuario.get("phosphate_ppm"))
    temperatura = first_not_none(datos_acuario.get("temperatura"), datos_acuario.get("temperature"))
    salinity = first_not_none(datos_acuario.get("salinity"), datos_acuario.get("salinity_ppt"))
    ammonia = first_not_none(datos_acuario.get("ammonia"), datos_acuario.get("ammonia_ppm"))
    nitrite = first_not_none(datos_acuario.get("nitrite"), datos_acuario.get("nitrite_ppm"))
    trace_elements = datos_acuario.get("trace_elements") or {}
    test_methods = datos_acuario.get("test_methods") or {}
    tendencia = datos_acuario.get("tendencia_reciente", "Estable")
    history_measurements = datos_acuario.get("history_measurements") or []
    maintenance_tasks = datos_acuario.get("maintenance_tasks_summary") or datos_acuario.get("maintenance_tasks") or []
    kit_name = datos_acuario.get("kit")
    is_cam = bool(datos_acuario.get("is_camera_scan", False))

    profile_info = get_marine_profile(reef_profile or tipo)
    targets = profile_info.get("targets", {})

    # ==========================================================================
    # PASO 1: REGLAS DETERMINÍSTICAS CON INTERVALOS METROLÓGICOS
    # ==========================================================================
    raw_params = {
        "kh": kh,
        "calcium": calcio,
        "magnesium": magnesio,
        "salinity": salinity,
        "temperature": temperatura,
        "ph": ph,
        "nitrate": nitrato,
        "phosphate": fosfato,
        "ammonia": ammonia,
        "nitrite": nitrite
    }

    intervals_dict: Dict[str, Any] = {}
    allowed_intervals: List[Tuple[float, float]] = []
    allowed_constants: Set[float] = {volumen}

    for p_k, p_val in raw_params.items():
        if p_val is not None:
            try:
                flt_val = float(p_val)
                u_int = calculate_measurement_uncertainty(p_k, flt_val, kit=kit_name, is_camera_scan=is_cam)
                intervals_dict[p_k] = u_int
                allowed_intervals.append((u_int.min_val, u_int.max_val))
                allowed_constants.add(round(flt_val, 2))
                allowed_constants.add(round(u_int.error, 2))
            except Exception as e:
                logger.debug(f"Aviso calculando intervalo para {p_k}: {e}")

    # Agregar límites de targets oficiales del perfil a constantes permitidas
    for t_spec in targets.values():
        if isinstance(t_spec, dict):
            if t_spec.get("min") is not None:
                allowed_constants.add(float(t_spec["min"]))
            if t_spec.get("max") is not None:
                allowed_constants.add(float(t_spec["max"]))

    # Evaluación de alertas dinámicas pre-existentes (Fases 1, 2 y 3)
    dynamic_alerts = evaluate_marine_alerts(
        reef_profile=reef_profile or tipo,
        current_data=datos_acuario,
        history_measurements=history_measurements,
        dosing_method=dosing_method
    )

    # Evaluación con intervalos de cada parámetro contra los rangos seguros del biotipo
    interval_alerts: List[Dict[str, Any]] = []
    for p_k, p_val in raw_params.items():
        if p_val is not None and p_k in targets and p_k in intervals_dict:
            t_spec = targets[p_k]
            t_min = t_spec.get("min")
            t_max = t_spec.get("max")
            eval_res = evaluate_parameter_with_interval(
                param=p_k,
                interval=intervals_dict[p_k],
                safe_min=t_min,
                safe_max=t_max,
                profile_name=profile_info["name"]
            )
            if eval_res.is_alert:
                interval_alerts.append({
                    "parameter": p_k,
                    "status": eval_res.status,
                    "severity": eval_res.severity,
                    "title": eval_res.title,
                    "message": eval_res.message,
                    "recommendation": eval_res.recommendation
                })

    all_rules_alerts = list(dynamic_alerts) + interval_alerts

    # Calcular severidad máxima de las reglas determinísticas
    max_rule_rank = 0
    for a in all_rules_alerts:
        sev = str(a.get("severity", "ok")).lower()
        stat = str(a.get("status", "")).lower()
        rank = max(SEVERITY_HIERARCHY.get(sev, 0), SEVERITY_HIERARCHY.get(stat, 0))
        if rank > max_rule_rank:
            max_rule_rank = rank

    rules_max_severity = ["ok", "watch", "warning", "critical"][min(max_rule_rank, 3)]

    # Determinar antigüedad de mediciones
    days_since_last: Optional[float] = None
    if history_measurements:
        try:
            m_0 = history_measurements[0]
            raw_ts = m_0.get("timestamp") or m_0.get("fecha_registro")
            if raw_ts:
                dt_meas = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")).replace(tzinfo=None)
                days_since_last = (datetime.utcnow() - dt_meas).total_seconds() / 86400.0
        except Exception:
            pass

    # Si no hay API key o es dummy, retornar directamente fallback por reglas
    if is_dummy_key:
        logger.warning("⚠️ GEMINI_API_KEY no detectada. Activando fallback determinístico de seguridad por reglas.")
        record_diagnostic_audit(
            db=db,
            user_id=effective_user_id,
            tank_id=effective_tank_id,
            prompt_version="v1",
            inputs=raw_params,
            rules_alerts=all_rules_alerts,
            raw_ai_output=None,
            status="fallback",
            rejection_reason="Modo determinístico por reglas de seguridad (GEMINI_API_KEY no detectada)",
            cost_usd=0.0,
            token_count=0,
            latency_ms=round((time.time() - start_time) * 1000, 2)
        )
        return generate_rules_deterministic_diagnosis(
            aquarium_name=nombre,
            biotope=profile_info["name"],
            rules_alerts=all_rules_alerts,
            measured_intervals=list(intervals_dict.values()),
            days_since_last_measurement=days_since_last
        )

    # Control de Presupuesto Operativo Gemini (Fase 7)
    budget_limit_usd = float(os.getenv("GEMINI_MONTHLY_BUDGET_USD", "25.0"))
    current_spend_usd = get_current_month_ai_spend(db)
    if current_spend_usd >= budget_limit_usd:
        budget_msg = f"Límite mensual de gasto en IA alcanzado (${current_spend_usd:.2f} >= ${budget_limit_usd:.2f}). Activando modo determinístico por reglas."
        logger.warning(budget_msg)
        record_diagnostic_audit(
            db=db,
            user_id=effective_user_id,
            tank_id=effective_tank_id,
            prompt_version="v1",
            inputs=raw_params,
            rules_alerts=all_rules_alerts,
            raw_ai_output=None,
            status="budget_exceeded",
            rejection_reason=budget_msg,
            cost_usd=0.0,
            token_count=0,
            latency_ms=round((time.time() - start_time) * 1000, 2)
        )
        return generate_rules_deterministic_diagnosis(
            aquarium_name=nombre,
            biotope=profile_info["name"],
            rules_alerts=all_rules_alerts,
            measured_intervals=list(intervals_dict.values()),
            days_since_last_measurement=days_since_last
        )

    # ==========================================================================
    # PASO 2: GEMINI (EXPLICA, NO DECIDE) CON SYSTEM PROMPT VERSIONADO
    # ==========================================================================
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key) if api_key else genai.Client()
        system_instruction = load_versioned_system_prompt("v1")

        # Serializar intervalos para Gemini
        intervals_summary = {
            k: {
                "valor_nominal": v.value,
                "error_metrologico": v.error,
                "intervalo_seguro": [v.min_val, v.max_val],
                "display": v.display_value,
                "por_debajo_limite_deteccion": v.is_below_detection_limit
            }
            for k, v in intervals_dict.items()
        }

        user_prompt = f"""
        EVALUACIÓN CLÍNICA DETERMINÍSTICA PRE-COMPUTADA (INAPELABLE):
        - Acuario: '{nombre}' ({volumen} L)
        - Biotipo / Perfil de Arrecife: {profile_info['name']} ({profile_info['id']})
        - Método de dosificación: {DOSING_METHOD_LABELS.get(dosing_method, dosing_method or 'No especificado')}
        - Mediciones con Intervalos de Incertidumbre [v - e, v + e]: {json.dumps(intervals_summary, ensure_ascii=False)}
        - Alertas Determinísticas Pre-evaluadas (Inapelables): {json.dumps(all_rules_alerts, ensure_ascii=False)}
        - Severidad máxima calculada por reglas: {rules_max_severity.upper()}
        - Antigüedad del último test: {f'{days_since_last:.1f} días' if days_since_last is not None else 'Sin fecha exacta'}
        - Correlación de mantenimiento y equipo: {json.dumps(maintenance_tasks, ensure_ascii=False) if maintenance_tasks else 'Al día'}
        - Tendencia reciente: {tendencia}

        REGLAS DE RESPUESTA:
        1. Eres una IA: explica el contexto biológico de los datos anteriores, NO decidas nuevos límites ni anules alertas.
        2. Si la severidad máxima de las reglas es '{rules_max_severity}', tu severidad DEBE ser al menos '{rules_max_severity}'. NUNCA digas 'ok' si hay alertas activas.
        3. En 'recommended_actions', selecciona ÚNICAMENTE del catálogo cerrado: ["retest_parameter", "monitor_24h", "pause_dosing", "water_change_small", "check_equipment", "consult_expert"].
        4. NUNCA prescribas dosis, cantidades ni gramos/ml de productos.
        5. Cita únicamente los números reales contenidos en las mediciones y sus intervalos. No inventes números.
        6. Responde solo con el JSON del esquema AIDiagnosisOutput.
        """

        pass1_output: Optional[AIDiagnosisOutput] = None
        candidate_models = list(dict.fromkeys(FALLBACK_MODELS))
        last_error = None

        for model_cand in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_cand,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1,  # temperature <= 0.2
                        max_output_tokens=1024,
                        response_mime_type="application/json",
                        response_schema=AIDiagnosisOutput,
                    ),
                )
                if response:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        pass1_output = response.parsed
                        break
                    if response.text:
                        clean_text = response.text.strip()
                        if clean_text.startswith("```"):
                            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                            clean_text = re.sub(r"\s*```$", "", clean_text)
                        pass1_output = AIDiagnosisOutput.model_validate_json(clean_text)
                        break
            except Exception as model_err:
                last_error = model_err
                logger.warning(f"Aviso en Pasada 1 con modelo {model_cand}: {model_err}. Intentando alternativa...")
                continue

        if not pass1_output:
            raise RuntimeError(f"Falla en generación con modelos Gemini: {last_error}")

        # ======================================================================
        # PASO 3: DOBLE PASADA (SEGUNDA REVISIÓN INDEPENDIENTE)
        # ======================================================================
        pass2_output: Optional[AIDiagnosisOutput] = None
        try:
            auditor_prompt = (
                f"Audita críticamente la siguiente evaluación preliminar del acuario '{nombre}' con perfil '{profile_info['name']}':\n"
                f"Severidad preliminar: {pass1_output.severity}, Acciones: {pass1_output.recommended_actions}\n"
                f"Alertas determinísticas inapelables: {json.dumps(all_rules_alerts, ensure_ascii=False)}\n"
                "Emite una segunda evaluación independiente de máxima prudencia biológica respetando estrictamente el catálogo cerrado de acciones."
            )
            resp_audit = client.models.generate_content(
                model=PRIMARY_MODEL,
                contents=auditor_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,
                    max_output_tokens=1024,
                    response_mime_type="application/json",
                    response_schema=AIDiagnosisOutput,
                ),
            )
            if resp_audit:
                if hasattr(resp_audit, "parsed") and resp_audit.parsed is not None:
                    pass2_output = resp_audit.parsed
                elif resp_audit.text:
                    c_txt = resp_audit.text.strip()
                    if c_txt.startswith("```"):
                        c_txt = re.sub(r"^```(?:json)?\s*", "", c_txt)
                        c_txt = re.sub(r"\s*```$", "", c_txt)
                    pass2_output = AIDiagnosisOutput.model_validate_json(c_txt)
        except Exception as audit_err:
            logger.debug(f"Aviso en segunda pasada de auditoría: {audit_err}. Procediendo con verificación estricta de Pasada 1.")

        # Consolidar doble pasada si está disponible
        if pass2_output:
            candidate_output = execute_double_pass_verification(pass1_output, pass2_output)
        else:
            candidate_output = pass1_output

        # ======================================================================
        # PASO 4: VALIDADOR ESTRICTO ANTES DE MOSTRAR (4.4) Y AUDITORÍA (FASE 7)
        # ======================================================================
        latency_ms = round((time.time() - start_time) * 1000, 2)
        tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0) if (hasattr(response, "usage_metadata") and response.usage_metadata) else 450
        tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0) if (hasattr(response, "usage_metadata") and response.usage_metadata) else 220
        total_tokens = int(tokens_in + tokens_out)
        cost_usd = round((tokens_in * 0.075 + tokens_out * 0.30) / 1_000_000, 6)
        raw_text_record = getattr(response, "text", "") or ""

        is_valid, sanitized_output, discrepancies = validate_and_sanitize_ai_diagnosis(
            ai_output=candidate_output,
            rules_max_severity=rules_max_severity,
            rules_alerts=all_rules_alerts,
            allowed_intervals=allowed_intervals,
            allowed_constants=allowed_constants,
            days_since_last_measurement=days_since_last
        )

        if not is_valid:
            logger.warning(
                "La salida de Gemini fue descartada por el validador estricto. "
                "Activando fallback determinístico por reglas para proteger la vida del acuario."
            )
            record_diagnostic_audit(
                db=db,
                user_id=effective_user_id,
                tank_id=effective_tank_id,
                prompt_version="v1",
                inputs=raw_params,
                rules_alerts=all_rules_alerts,
                raw_ai_output=raw_text_record,
                status="discarded",
                rejection_reason="; ".join(discrepancies) if discrepancies else "Rechazado por validador estricto",
                cost_usd=cost_usd,
                token_count=total_tokens,
                latency_ms=latency_ms
            )
            return generate_rules_deterministic_diagnosis(
                aquarium_name=nombre,
                biotope=profile_info["name"],
                rules_alerts=all_rules_alerts,
                measured_intervals=list(intervals_dict.values()),
                days_since_last_measurement=days_since_last
            )

        audit_status = "sanitized" if discrepancies else "accepted"
        record_diagnostic_audit(
            db=db,
            user_id=effective_user_id,
            tank_id=effective_tank_id,
            prompt_version="v1",
            inputs=raw_params,
            rules_alerts=all_rules_alerts,
            raw_ai_output=raw_text_record,
            status=audit_status,
            rejection_reason="; ".join(discrepancies) if discrepancies else None,
            cost_usd=cost_usd,
            token_count=total_tokens,
            latency_ms=latency_ms
        )

        return sanitized_output

    except Exception as e:
        logger.error(f"Excepción en pipeline de IA: {e}. Activando fallback determinístico por reglas (sin error 500).")
        record_diagnostic_audit(
            db=db,
            user_id=effective_user_id,
            tank_id=effective_tank_id,
            prompt_version="v1",
            inputs=raw_params,
            rules_alerts=all_rules_alerts,
            raw_ai_output=None,
            status="fallback",
            rejection_reason=str(e),
            cost_usd=0.0,
            token_count=0,
            latency_ms=round((time.time() - start_time) * 1000, 2)
        )
        if allow_fallback:
            return generate_rules_deterministic_diagnosis(
                aquarium_name=nombre,
                biotope=profile_info["name"],
                rules_alerts=all_rules_alerts,
                measured_intervals=list(intervals_dict.values()),
                days_since_last_measurement=days_since_last
            )
        raise e


# Alias de compatibilidad
analizar_parametros_acuario = analizar_parametros_estructurado
analizar_acuario_estructurado = analizar_parametros_estructurado


# Alias de compatibilidad
analizar_parametros_acuario = analizar_parametros_estructurado
analizar_acuario_estructurado = analizar_parametros_estructurado
