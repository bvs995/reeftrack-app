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

# Modelos de Gemini oficiales vigentes y catálogo de obsolescencia (P2.14)
SUPPORTED_GEMINI_MODELS = {
    "gemini-3.8-flash": {"status": "active", "recommended": True},
    "gemini-3.6-flash": {"status": "active", "recommended": False},
    "gemini-3.5-flash-lite": {"status": "active", "recommended": True, "light": True},
    "gemini-3.1-flash-lite": {"status": "active", "recommended": True, "light": True},
}

DEPRECATED_MODELS = {
    "gemini-2.5-flash": "Deprecado oficialmente (reemplazado por gemini-3.5-flash-lite / gemini-3.8-flash, retiro 1 dic 2026)",
    "gemini-2.5-pro": "Deprecado oficialmente (reemplazado por gemini-3.8-flash, retiro 1 dic 2026)",
    "gemini-1.5-flash": "Retirado de servicio",
    "gemini-1.5-pro": "Retirado de servicio",
}

AI_GENERATION_MAX_OUTPUT_TOKENS = 4096
AI_GENERATION_THINKING_BUDGET = 0

def validate_gemini_model(model_name: Optional[str]) -> str:
    """
    Verifica que el modelo de Gemini sea obligatorio por variable de entorno
    y exista dentro del catálogo oficial vigente (P2.14).
    """
    if not model_name or not str(model_name).strip():
        raise ValueError(
            "La variable de entorno 'GEMINI_MODEL' es obligatoria. "
            f"Modelos oficiales vigentes: {list(SUPPORTED_GEMINI_MODELS.keys())}."
        )
    clean_model = str(model_name).strip()
    if clean_model.startswith("gemini-mock"):
        return clean_model

    if clean_model in DEPRECATED_MODELS:
        raise ValueError(
            f"El modelo '{clean_model}' está obsoleto/deprecado: {DEPRECATED_MODELS[clean_model]}. "
            f"Por favor actualiza a uno vigente: {list(SUPPORTED_GEMINI_MODELS.keys())}."
        )
    if clean_model not in SUPPORTED_GEMINI_MODELS:
        raise ValueError(
            f"El modelo '{clean_model}' no existe o no es un modelo oficial soportado. "
            f"Modelos oficiales vigentes: {list(SUPPORTED_GEMINI_MODELS.keys())}."
        )
    return clean_model

RAW_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
PRIMARY_MODEL = validate_gemini_model(RAW_GEMINI_MODEL)
FALLBACK_MODELS = [PRIMARY_MODEL, "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]


def first_not_none(*vals):
    """
    Retorna el primer valor que no sea None (P0.5).
    Preserva estrictamente el valor numérico 0 y 0.0 para evitar descartar mediciones válidas.
    """
    for v in vals:
        if v is not None:
            return v
    return None


def sanitize_prompt_text(text: Optional[str], max_len: int = 500) -> str:
    """
    Sanea textos libres (nombres de tanques, notas de usuario, texto de imágenes)
    antes de incluirlos en prompts dirigidos a Gemini (P1.10).
    Neutraliza intentos de inyección de prompt, elimina caracteres de control
    y bloques delimitadores de markdown/JSON.
    """
    if not text:
        return ""
    val = str(text).strip()
    # Eliminar bloques de código markdown y delimitadores que puedan confundir el parser JSON
    val = re.sub(r"```+", "", val)
    # Neutralizar caracteres de control preservando espacios comunes
    val = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", val)
    # Patrones comunes de prompt injection
    injection_patterns = [
        r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"(?i)system\s+prompt",
        r"(?i)system\s*:",
        r"(?i)human\s*:",
        r"(?i)assistant\s*:",
        r"(?i)override\s+rules",
        r"(?i)disregard\s+rules"
    ]
    for pattern in injection_patterns:
        val = re.sub(pattern, "[UNTRUSTED_DATA]", val)
    # Acotar longitud
    if len(val) > max_len:
        val = val[:max_len]
    return val


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
        db.query(Measurement)
        .filter(Measurement.tank_id == acuario_id)
        .filter(Measurement.timestamp >= hace_48_horas)
        .order_by(Measurement.timestamp.asc())
        .all()
    )

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

        safe_nombre = sanitize_prompt_text(nombre, max_len=80)
        safe_tendencia = sanitize_prompt_text(tendencia, max_len=500)

        user_prompt = f"""
        EVALUACIÓN CLÍNICA DETERMINÍSTICA PRE-COMPUTADA (INAPELABLE):
        - Acuario: '{safe_nombre}' ({volumen} L)
        - Biotipo / Perfil de Arrecife: {profile_info['name']} ({profile_info['id']})
        - Método de dosificación: {DOSING_METHOD_LABELS.get(dosing_method, dosing_method or 'No especificado')}
        - Mediciones con Intervalos de Incertidumbre [v - e, v + e]: {json.dumps(intervals_summary, ensure_ascii=False)}
        - Alertas Determinísticas Pre-evaluadas (Inapelables): {json.dumps(all_rules_alerts, ensure_ascii=False)}
        - Severidad máxima calculada por reglas: {rules_max_severity.upper()}
        - Antigüedad del último test: {f'{days_since_last:.1f} días' if days_since_last is not None else 'Sin fecha exacta'}
        - Correlación de mantenimiento y equipo: {json.dumps(maintenance_tasks, ensure_ascii=False) if maintenance_tasks else 'Al día'}
        - Tendencia reciente: {safe_tendencia}

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
                        max_output_tokens=AI_GENERATION_MAX_OUTPUT_TOKENS,
                        thinking_config=types.ThinkingConfig(thinking_budget=AI_GENERATION_THINKING_BUDGET),
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
                    max_output_tokens=AI_GENERATION_MAX_OUTPUT_TOKENS,
                    thinking_config=types.ThinkingConfig(thinking_budget=AI_GENERATION_THINKING_BUDGET),
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
