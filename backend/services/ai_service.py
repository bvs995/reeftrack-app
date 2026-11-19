import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.models import (
    AnalisisAcuarioSchema,
    AnalisisAcuarioResponse,
    DosisRecomendada,
    MedicionAcuario,
    Measurement
)
from backend.marine_profiles import (
    get_marine_profile,
    evaluate_marine_alerts,
    DOSING_METHOD_LABELS,
    FLOW_PROFILE_LABELS
)

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger("aquapulse.ai_service")

# Modelos recomendados: usuario solicita gemini-2.5-flash, con fallback a gemini-3.1-flash-lite y 3.8-flash
PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODELS = [PRIMARY_MODEL, "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]


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
    
    profile_info = get_marine_profile(reef_profile or ("fish_only" if tipo_normalizado in ["marine_fish", "peces_marinos", "fowlr", "fish_only"] else "lps_reef"))
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


def analizar_parametros_estructurado(datos_acuario: dict, allow_fallback: bool = True) -> AnalisisAcuarioResponse:
    """
    Analiza los parámetros químicos actuales de un acuario y genera un diagnóstico predictivo
    y clínico puramente técnico y estructurado utilizando Google GenAI (Gemini SDK oficial) con Structured Outputs.
    Soporta los perfiles marinos fish_only, soft_reef, lps_reef, mixed_reef y sps_reef con alertas dinámicas.
    """
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

    ph = datos_acuario.get("ph")
    kh = datos_acuario.get("kh") or datos_acuario.get("alkalinity_dkh")
    calcio = datos_acuario.get("calcio") or datos_acuario.get("calcium") or datos_acuario.get("calcium_ppm")
    magnesio = datos_acuario.get("magnesio") or datos_acuario.get("magnesium") or datos_acuario.get("magnesium_ppm")
    nitrato = datos_acuario.get("nitrato") or datos_acuario.get("nitrate") or datos_acuario.get("nitrate_ppm")
    fosfato = datos_acuario.get("fosfato") or datos_acuario.get("phosphate") or datos_acuario.get("phosphate_ppm")
    temperatura = datos_acuario.get("temperatura") or datos_acuario.get("temperature")
    salinity = datos_acuario.get("salinity") or datos_acuario.get("salinity_ppt")
    ammonia = datos_acuario.get("ammonia") or datos_acuario.get("ammonia_ppm")
    nitrite = datos_acuario.get("nitrite") or datos_acuario.get("nitrite_ppm")
    trace_elements = datos_acuario.get("trace_elements") or {}
    test_methods = datos_acuario.get("test_methods") or {}
    tendencia = datos_acuario.get("tendencia_reciente", "Estable")
    history_measurements = datos_acuario.get("history_measurements") or []
    maintenance_tasks = datos_acuario.get("maintenance_tasks_summary") or datos_acuario.get("maintenance_tasks") or []

    # Evaluación de alertas dinámicas especializadas
    dynamic_alerts = evaluate_marine_alerts(
        reef_profile=reef_profile,
        current_data=datos_acuario,
        history_measurements=history_measurements,
        dosing_method=dosing_method
    )

    profile_info = get_marine_profile(reef_profile)

    if is_dummy_key:
        logger.warning("⚠️ GEMINI_API_KEY no detectada. Generando diagnóstico estructurado inteligente con reglas marinas locales.")
        return _generar_analisis_fallback(
            nombre=nombre,
            volumen=volumen,
            ph=ph,
            kh=kh,
            calcio=calcio,
            magnesio=magnesio,
            nitrato=nitrato,
            fosfato=fosfato,
            tendencia=tendencia,
            temperatura=temperatura,
            tipo=tipo,
            reef_profile=reef_profile,
            dosing_method=dosing_method,
            lighting_par=lighting_par,
            flow_profile=flow_profile,
            salinity=salinity,
            ammonia=ammonia,
            nitrite=nitrite,
            trace_elements=trace_elements,
            test_methods=test_methods,
            dynamic_alerts=dynamic_alerts,
            maintenance_tasks=maintenance_tasks
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key) if api_key else genai.Client()

        system_instruction = (
            "Eres AquaPulse AI, biólogo marino sénior experto en química de acuarios de arrecife y marinos.\n"
            f"ADAPTA ESTRICTAMENTE tus consejos al perfil marino '{profile_info['name']}' ({profile_info['id']}):\n"
            "1. En 'fish_only' (Solo Peces / FOWLR): NUNCA des recomendaciones ni ajustes sobre corales, calcio, magnesio, elementos traza ni calcificación. Tolera NO3 hasta 30-40 ppm y PO4 hasta 0.25 ppm. Solo enfócate en salinidad, temperatura, pH, amoníaco, nitrito y nitratos para peces.\n"
            "2. En 'soft_reef' (Corales Blandos): Tolera nutrientes moderados (NO3 5-15 ppm, PO4 0.05-0.15 ppm). No exijas fotómetros ULR ni dosificación estricta de trazas.\n"
            "3. En 'lps_reef' (Arrecife LPS): Requieren nutrientes detectables (NO3 5-10, PO4 0.03-0.08 ppm, ideal 0.05). NUNCA exijas nutrientes ultra-bajos; nutrientes en cero causan inanición y encogimiento de tejido. Recomienda flujo moderado e indirecto.\n"
            "4. En 'mixed_reef' (Arrecife Mixto): Equilibrio entre estabilidad de KH (8.0-8.5, delta máx 0.4) y nutrientes detectables (NO3 3-8 ppm, PO4 0.03-0.06 ppm) para no matar de hambre los LPS ni blanquear SPS.\n"
            "5. En 'sps_reef' (Arrecife SPS): Altísima exigencia de estabilidad de KH (7.5-8.5, delta máx 0.3 dKH diario por riesgo crítico de RTN/STN) y nutrientes bajos controlados (NO3 1-5 ppm, PO4 0.01-0.04 ppm, advertencia de dinoflagelados si llegan a cero).\n"
            "\n"
            "CORRELACIÓN CON EQUIPO Y MANTENIMIENTO MECÁNICO:\n"
            "1. Si hay picos de NO3 o PO4 y 'mechanical_filter' o 'skimmer_cup' llevan > 7 días sin completarse o están vencidos ('overdue'), señala la acumulación de detrito en la filtración mecánica como posible causa raíz prioritaria antes de recomendar químicos, resinas o cambios drásticos.\n"
            "2. Si el perfil es 'sps_reef', 'mixed_reef' o 'lps_reef' y 'pumps_cleaning' está vencido, advierte sobre pérdida de flujo real por calcificación/sarro y riesgo de acumulación de detrito o cianobacteria.\n"
            "3. Si hay oscilaciones de KH (delta > 0.3 dKH) y 'doser_probes' está vencido, sugiere revisar calibración de dosificadora, mangueras o sondas antes de ajustar dosificación.\n"
            "Genera un diagnóstico en JSON puro cumpliendo estrictamente con el esquema Pydantic."
        )

        user_prompt = f"""
        Analiza los datos del acuario '{nombre}':
        - Biotipo general: {tipo}
        - Perfil de Arrecife: {profile_info['name']} ({profile_info['id']})
        - Método de dosificación: {DOSING_METHOD_LABELS.get(dosing_method, dosing_method or 'No especificado')}
        - Iluminación PAR: {lighting_par if lighting_par is not None else 'No especificado'}
        - Perfil de flujo: {FLOW_PROFILE_LABELS.get(flow_profile, flow_profile or 'No especificado')}
        - Salinidad: {salinity if salinity is not None else 'No registrado'} SG
        - Temperatura: {temperatura if temperatura is not None else 'No registrado'} °C
        - pH: {ph if ph is not None else 'No registrado'}
        - KH / Alcalinidad: {kh if kh is not None else 'No registrado'} dKH
        - Calcio: {calcio if calcio is not None else 'No registrado'} ppm
        - Magnesio: {magnesio if magnesio is not None else 'No registrado'} ppm
        - Nitrato (NO3): {nitrato if nitrato is not None else 'No registrado'} ppm
        - Fosfato (PO4): {fosfato if fosfato is not None else 'No registrado'} ppm
        - Amoníaco (NH3): {ammonia if ammonia is not None else '0.00'} ppm
        - Nitrito (NO2): {nitrite if nitrite is not None else '0.00'} ppm
        - Elementos Traza: {json.dumps(trace_elements) if trace_elements else 'No registrados'}
        - Métodos de Test: {json.dumps(test_methods) if test_methods else 'No especificados'}
        - Tareas de Mantenimiento y Filtración Activas: {json.dumps(maintenance_tasks, ensure_ascii=False) if maintenance_tasks else 'No registradas'}
        - Historial / Tendencia: {tendencia}
        - Alertas Dinámicas Pre-evaluadas: {json.dumps(dynamic_alerts, ensure_ascii=False) if dynamic_alerts else 'Ninguna detectada'}
        """

        candidate_models = list(dict.fromkeys(FALLBACK_MODELS))
        last_error = None

        for model_cand in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_cand,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=AnalisisAcuarioResponse,
                    ),
                )
                if response:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        return response.parsed

                    if response.text:
                        clean_text = response.text.strip()
                        if clean_text.startswith("```"):
                            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                            clean_text = re.sub(r"\s*```$", "", clean_text)
                        return AnalisisAcuarioResponse.model_validate_json(clean_text)
            except Exception as model_err:
                last_error = model_err
                logger.warning(f"Aviso con modelo {model_cand}: {model_err}. Intentando modelo alternativo...")
                continue

        if last_error:
            raise last_error

        raise RuntimeError("No se obtuvo respuesta estructurada del modelo de IA.")

    except Exception as e:
        logger.error(f"Error generando análisis de parámetros con Gemini: {e}")
        if allow_fallback:
            logger.info("Activando fallback estructurado de emergencia para garantizar disponibilidad.")
            return _generar_analisis_fallback(
                nombre=nombre,
                volumen=volumen,
                ph=ph,
                kh=kh,
                calcio=calcio,
                magnesio=magnesio,
                nitrato=nitrato,
                fosfato=fosfato,
                tendencia=tendencia,
                temperatura=temperatura,
                tipo=tipo,
                reef_profile=reef_profile,
                dosing_method=dosing_method,
                lighting_par=lighting_par,
                flow_profile=flow_profile,
                salinity=salinity,
                ammonia=ammonia,
                nitrite=nitrite,
                trace_elements=trace_elements,
                test_methods=test_methods,
                dynamic_alerts=dynamic_alerts
            )
        raise e


# Alias de compatibilidad
analizar_parametros_acuario = analizar_parametros_estructurado
analizar_acuario_estructurado = analizar_parametros_estructurado
