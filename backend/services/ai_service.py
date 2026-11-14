import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger("aquapulse.ai_service")

# Modelos recomendados con fallback resiliente
PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
FALLBACK_MODELS = [PRIMARY_MODEL, "gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash"]

def analizar_parametros_acuario(datos_acuario: Dict[str, Any]) -> str:
    """
    Analiza los parámetros químicos actuales de un acuario y genera un diagnóstico predictivo
    y clínico utilizando Google GenAI (Gemini SDK oficial).
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
    volumen = datos_acuario.get("volumen_litros", 0)
    ph = datos_acuario.get("ph")
    kh = datos_acuario.get("kh")
    calcio = datos_acuario.get("calcio")
    magnesio = datos_acuario.get("magnesio")
    nitrato = datos_acuario.get("nitrato")
    fosfato = datos_acuario.get("fosfato")
    tendencia = datos_acuario.get("tendencia_reciente", "Estable en las últimas 24h")

    # Si no hay API key disponible en entorno local, devolver diagnóstico clínico inteligente simulado
    if is_dummy_key:
        logger.warning("⚠️ GEMINI_API_KEY no detectada. Generando diagnóstico clínico de respaldo (demo fallback).")
        return (
            f"Soy **AquaPulse AI** (Modo Demostración). Análisis de telemetría de '{nombre}' ({volumen} L):\n\n"
            f"### 1. Diagnóstico de Estado\n"
            f"• Alcalinidad (KH): {kh} dKH — Nivel dentro de rango seguro, pero con tendencia a vigilar.\n"
            f"• Calcio: {calcio} ppm | Magnesio: {magnesio} ppm — Balance iónico en equilibrio relativo.\n"
            f"• Nutrientes: Nitrato a {nitrato} ppm y Fosfato a {fosfato} ppm.\n\n"
            f"### 2. Riesgo Potencial (Predictivo)\n"
            f"• Si la tasa de consumo de KH continúa en descenso sin dosificación de soporte, "
            f"el sistema podría caer por debajo de 7.5 dKH en 4 días provocando estrés en puntas de crecimiento de corales SPS.\n\n"
            f"### 3. Acción correctora exacta\n"
            f"1. Monitorear alcalinidad en 48 horas con fotómetro digital.\n"
            f"2. Ajustar bomba dosificadora de carbonatos en +1.5 ml/día si el KH desciende de 7.8 dKH.\n"
            f"3. Realizar un cambio de agua del 10% ({round(float(volumen)*0.1, 1)} L) si los nitratos superan 15 ppm."
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # System Prompt: Define el rol clínico y preventivo
        system_instruction = (
            "Eres AquaPulse AI, un biólogo marino experto en química del agua y sistemas de arrecife cerrado. "
            "Tu objetivo es analizar los parámetros actuales de un acuario, detectar desviaciones y prever colapsos químicos "
            "(como caídas de KH o picos de fosfatos) antes de que ocurran. "
            "Sé directo, clínico y técnico. Estructura tu respuesta siempre en:\n"
            "1. Diagnóstico de Estado\n"
            "2. Riesgo Potencial (Predictivo)\n"
            "3. Acción correctora exacta"
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

Genera el análisis predictivo y las recomendaciones de dosificación.
"""

        # Intentar con modelo primario y fallback si Google devuelve que el modelo se ha actualizado
        candidate_models = list(dict.fromkeys(FALLBACK_MODELS))
        last_error = None

        for model_cand in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_cand,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2,  # Evita alucinaciones y mantiene respuestas técnicas deterministas
                        max_output_tokens=700,
                    )
                )
                if response and response.text:
                    return response.text
            except Exception as model_err:
                last_error = model_err
                logger.warning(f"Aviso con modelo {model_cand}: {model_err}. Intentando fallback...")
                continue

        if last_error:
            raise last_error

        raise RuntimeError("No se obtuvo respuesta del modelo de IA.")

    except Exception as e:
        logger.error(f"Error generando análisis de parámetros con Gemini: {e}")
        raise e
