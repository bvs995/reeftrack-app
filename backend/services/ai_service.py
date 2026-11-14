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
    MedicionAcuario
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
    # Definir el umbral de tiempo (hace exactamente 48 horas)
    hace_48_horas = datetime.utcnow() - timedelta(hours=48)

    # Consulta en SQLAlchemy ordenada de la más antigua a la más reciente
    registros = (
        db.query(MedicionAcuario)
        .filter(MedicionAcuario.acuario_id == acuario_id)
        .filter(MedicionAcuario.fecha_registro >= hace_48_horas)
        .order_by(MedicionAcuario.fecha_registro.asc())
        .all()
    )

    if not registros:
        # Fallback a tabla legacy measurements si aplica
        try:
            from backend.models import Measurement
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

    # Convertir los registros en un texto estructurado para que la IA entienda la tendencia
    resumen_historial = []
    for reg in registros:
        fecha_str = reg.fecha_registro.strftime("%Y-%m-%d %H:%M")
        resumen_historial.append(
            f"[{fecha_str}] pH: {reg.ph}, KH: {reg.kh} dKH, Calcio: {reg.calcio} ppm, Fosfato: {reg.fosfato} ppm"
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
    tendencia: str
) -> AnalisisAcuarioResponse:
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
    Devuelve un modelo Pydantic AnalisisAcuarioResponse (alias de AnalisisAcuarioSchema) directamente parseado.
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
    tendencia = datos_acuario.get("tendencia_reciente", "Estable")

    # Si no hay API key disponible en entorno local, devolver diagnóstico clínico inteligente estructurado de respaldo
    if is_dummy_key:
        logger.warning("⚠️ GEMINI_API_KEY no detectada. Generando diagnóstico clínico estructurado de respaldo (demo fallback).")
        return _generar_analisis_fallback(nombre, volumen, ph, kh, calcio, magnesio, nitrato, fosfato, tendencia)

    try:
        from google import genai
        from google.genai import types

        # Inicializa cliente con api_key explícita si existe
        client = genai.Client(api_key=api_key) if api_key else genai.Client()

        system_instruction = (
            "Eres AquaPulse AI, un biólogo marino experto en química del agua de arrecife. "
            "Analiza los parámetros de entrada y genera una respuesta puramente técnica, predictiva y estructurada."
        )

        user_prompt = f"""
    Analiza los datos del acuario '{nombre}':
    - pH: {ph if ph is not None else 'No registrado'}
    - KH: {kh if kh is not None else 'No registrado'} dKH
    - Calcio: {calcio if calcio is not None else 'No registrado'} ppm
    - Magnesio: {magnesio if magnesio is not None else 'No registrado'} ppm
    - Nitrato: {nitrato if nitrato is not None else 'No registrado'} ppm
    - Fosfato: {fosfato if fosfato is not None else 'No registrado'} ppm
    - Historial: {tendencia}
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
                        temperature=0.1,  # Temperatura ultra baja para precisión en esquemas
                        response_mime_type="application/json",
                        response_schema=AnalisisAcuarioResponse,  # ¡Aquí ocurre la magia!
                    ),
                )
                if response:
                    # Si el SDK soporta response.parsed directamente, devolverlo
                    if hasattr(response, "parsed") and response.parsed is not None:
                        return response.parsed

                    # Si devuelve texto JSON estructurado, validarlo contra el esquema
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
            return _generar_analisis_fallback(nombre, volumen, ph, kh, calcio, magnesio, nitrato, fosfato, tendencia)
        raise e


# Alias de compatibilidad
analizar_parametros_acuario = analizar_parametros_estructurado
analizar_acuario_estructurado = analizar_parametros_estructurado
