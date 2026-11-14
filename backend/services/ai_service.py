import os
import re
import json
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from backend.models import AnalisisAcuarioSchema, DosisRecomendada

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger("aquapulse.ai_service")

# Modelos recomendados con fallback resiliente
PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
FALLBACK_MODELS = [PRIMARY_MODEL, "gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]


def _generar_analisis_fallback(
    nombre: str,
    volumen: float,
    ph: Optional[float],
    kh: Optional[float],
    calcio: Optional[float],
    magnesio: Optional[float],
    nitrato: Optional[float],
    fosfato: Optional[float],
    tendencia: str
) -> AnalisisAcuarioSchema:
    """Genera un análisis clínico estructurado inteligente de respaldo cuando la API externa no está disponible."""
    risk = "Bajo"
    alert = "Parámetros dentro de umbrales operativos estables. Mantener rutina regular de dosificación y filtración."
    acciones: List[DosisRecomendada] = []

    if kh is not None and kh < 7.5:
        risk = "Crítico" if kh < 6.8 else "Moderado"
        alert = (
            f"Alcalinidad a {kh} dKH por debajo del umbral óptimo (7.5 - 8.5 dKH). "
            f"Riesgo de estrés osmótico y calcificación comprometida en corales SPS en las próximas 48 horas si no se repone."
        )
        acciones.append(
            DosisRecomendada(
                parametro="Alcalinidad (KH)",
                producto="Bicarbonato de sodio grado alimenticio / Buffer comercial de carbonatos",
                cantidad_sugerida=f"{round(float(volumen or 280) * 0.05, 1)} ml en solución diluida en zona de alto flujo"
            )
        )
    elif kh is not None and kh > 9.0:
        risk = "Moderado"
        alert = (
            f"Alcalinidad a {kh} dKH por encima del rango natural seguro (7.5 - 8.5 dKH). "
            f"Riesgo de lisis celular y quemado de puntas de crecimiento (tip burn) en acroporas bajo alta radiación lumínica."
        )
        acciones.append(
            DosisRecomendada(
                parametro="Alcalinidad (KH)",
                producto="Pausa o recalibración de bomba dosificadora",
                cantidad_sugerida="Suspender dosificación de KH durante 24 horas y monitorear caída natural"
            )
        )

    if calcio is not None and calcio < 400:
        risk = "Moderado" if risk == "Bajo" else risk
        acciones.append(
            DosisRecomendada(
                parametro="Calcio (Ca)",
                producto="Cloruro de calcio anhidro o suplemento líquido de calcio",
                cantidad_sugerida="10 ml diarios hasta alcanzar 430 ppm"
            )
        )

    if nitrato is not None and nitrato > 15:
        acciones.append(
            DosisRecomendada(
                parametro="Nitrato (NO3)",
                producto="Cambio parcial de agua con agua desionizada (RO/DI) y sal sintética",
                cantidad_sugerida=f"{round(float(volumen or 280) * 0.15, 1)} litros (15% del volumen total)"
            )
        )

    if fosfato is not None and fosfato > 0.10:
        acciones.append(
            DosisRecomendada(
                parametro="Fosfato (PO4)",
                producto="Resina de óxido de hierro granular (GFO) o reductor de fosfatos base lantano",
                cantidad_sugerida="50 g de resina en reactor pasivo de flujo moderado"
            )
        )

    if not acciones:
        acciones = [
            DosisRecomendada(
                parametro="Alcalinidad / KH",
                producto="Mantenimiento preventivo de tampones",
                cantidad_sugerida="Mantener dosis basal de 5 ml/día"
            ),
            DosisRecomendada(
                parametro="Nutrientes y Elementos Traza",
                producto="Cambio de agua regular con sal de arrecife",
                cantidad_sugerida=f"{round(float(volumen or 280) * 0.1, 1)} litros (10%) semanal"
            )
        ]

    diagnostico = (
        f"Evaluación química del acuario '{nombre}' ({volumen} L): "
        f"pH={ph if ph is not None else '8.2'}, "
        f"KH={kh if kh is not None else '8.2'} dKH, "
        f"Ca={calcio if calcio is not None else '420'} ppm, "
        f"Mg={magnesio if magnesio is not None else '1350'} ppm, "
        f"NO3={nitrato if nitrato is not None else '5.0'} ppm, "
        f"PO4={fosfato if fosfato is not None else '0.04'} ppm. "
        f"Tendencia reportada: '{tendencia}'."
    )

    return AnalisisAcuarioSchema(
        diagnostico_general=diagnostico,
        nivel_riesgo=risk,
        alerta_predictiva=alert,
        acciones_correctoras=acciones
    )


def analizar_parametros_acuario(datos_acuario: Dict[str, Any], allow_fallback: bool = True) -> AnalisisAcuarioSchema:
    """
    Analiza los parámetros químicos actuales de un acuario y genera un diagnóstico predictivo
    y clínico estructurado utilizando Google GenAI (Gemini SDK oficial) con Structured Outputs.
    Devuelve una instancia validada de AnalisisAcuarioSchema.
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
    ph = datos_acuario.get("ph")
    kh = datos_acuario.get("kh")
    calcio = datos_acuario.get("calcio")
    magnesio = datos_acuario.get("magnesio")
    nitrato = datos_acuario.get("nitrato")
    fosfato = datos_acuario.get("fosfato")
    tendencia = datos_acuario.get("tendencia_reciente", "Estable en las últimas 24h")

    # Si no hay API key disponible en entorno local, devolver diagnóstico clínico inteligente estructurado de respaldo
    if is_dummy_key:
        logger.warning("⚠️ GEMINI_API_KEY no detectada. Generando diagnóstico clínico estructurado de respaldo (demo fallback).")
        return _generar_analisis_fallback(nombre, volumen, ph, kh, calcio, magnesio, nitrato, fosfato, tendencia)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # System Prompt: Define el rol clínico y preventivo
        system_instruction = (
            "Eres AquaPulse AI, un biólogo marino experto en química del agua y sistemas de arrecife cerrado. "
            "Tu objetivo es analizar los parámetros actuales de un acuario, detectar desviaciones y prever colapsos químicos "
            "(como caídas de KH o picos de fosfatos) antes de que ocurran. "
            "Sé directo, clínico y técnico. Estructura tu respuesta en formato JSON estrictamente acorde al esquema requerido:\n"
            "- diagnostico_general: Resumen clínico del estado químico actual del tanque.\n"
            "- nivel_riesgo: 'Bajo', 'Moderado', 'Crítico' o 'Colapso Inminente'.\n"
            "- alerta_predictiva: Predicción de lo que ocurrirá en las próximas 48 horas si no se actúa.\n"
            "- acciones_correctoras: Lista de objetos { parametro, producto, cantidad_sugerida } con dosificaciones exactas."
        )

        # User Prompt Dinámico inyectando los datos del acuario
        user_prompt = f"""
Analiza los siguientes datos actuales del acuario '{nombre}':
- Volumen: {volumen} litros
- pH: {ph if ph is not None else 'No registrado'} (Ideal: 8.1 - 8.4)
- Alcalinidad (KH): {kh if kh is not None else 'No registrado'} dKH (Ideal: 7.5 - 8.5 dKH)
- Calcio: {calcio if calcio is not None else 'No registrado'} ppm (Ideal: 420 - 450 ppm)
- Magnesio: {magnesio if magnesio is not None else 'No registrado'} ppm (Ideal: 1300 - 1450 ppm)
- Nitrato: {nitrato if nitrato is not None else 'No registrado'} ppm (Ideal: 5 - 10 ppm)
- Fosfato: {fosfato if fosfato is not None else 'No registrado'} ppm (Ideal: 0.03 - 0.08 ppm)

Historial reciente de cambios:
{tendencia}

Genera el análisis predictivo estructurado y las recomendaciones precisas de dosificación.
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
                        temperature=0.2,  # Evita alucinaciones y mantiene determinismo técnico
                        max_output_tokens=1000,
                        response_mime_type="application/json",
                        response_schema=AnalisisAcuarioSchema,
                    )
                )
                if response and response.text:
                    clean_text = response.text.strip()
                    if clean_text.startswith("```"):
                        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                        clean_text = re.sub(r"\s*```$", "", clean_text)
                    return AnalisisAcuarioSchema.model_validate_json(clean_text)
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
            return _generar_analisis_fallback(nombre, volumen, ph, kh, calcio, magnesio, nitrato, fosfato, tendencia)
        raise e
