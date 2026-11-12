import os
import re
import json
import base64
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

logger = logging.getLogger("aquapulse.vision")

# Prompt especializado en kits analíticos de acuariofilia (Hanna Checkers, Salifert, Red Sea, etc.)
AQUARIUM_VISION_SYSTEM_PROMPT = """
Eres un asistente experto en análisis químico de acuarios de arrecife marino y agua dulce plantada.
Tu misión es inspeccionar la fotografía adjunta tomada por el acuarista y extraer con precisión quirúrgica el valor numérico medido y el parámetro correspondiente.

La imagen puede ser:
1. Un fotómetro digital Hanna Checker (pantalla LCD de 7 segmentos mostrando números como 8.3, 142, 420, etc.).
2. Un kit de titulación Salifert (jeringa de 1ml con lectura de émbolo o tarjeta de comparación de colores).
3. Un kit colorimétrico de gotas (Red Sea, Salifert, Colombo, Tropic Marin, API) con vial de prueba junto a la escala cromática.
4. Un refractómetro óptico o digital mostrando salinidad (ej: 35 ppt o 1.025 SG).

DEBES devolver ÚNICAMENTE un objeto JSON válido con los siguientes campos:
{
  "parameter": string o null,
  "value": number o null,
  "confidence": number,
  "kit_detected": string,
  "notes": string,
  "raw_reading": string
}

Reglas estrictas de extracción:
1. "parameter": Debe ser EXACTAMENTE uno de los siguientes nombres de campo si se detecta con claridad:
   - "alkalinity_dkh" : Si es alcalinidad / dKH / Carbonate Hardness / KH.
   - "calcium_ppm"    : Si es Calcio (Ca) en ppm / mg/L.
   - "magnesium_ppm"  : Si es Magnesio (Mg) en ppm / mg/L.
   - "nitrate_ppm"    : Si es Nitrato (NO3) en ppm / mg/L.
   - "phosphate_ppm"  : Si es Fosfato (PO4) en ppm / mg/L.
   - "salinity_ppt"   : Si es Salinidad (ppt o Gravedad Específica como 1.025).
   Si no se puede identificar el parámetro, asigna null.

2. "value": El valor numérico decimal o entero correspondiente.
   - Si es un Hanna HI736 (Phosphorus ULR en ppb), convierte ppb a ppm de PO4: PO4 = (ppb * 3.066) / 1000. Redondea a 3 decimales.
   - Si es Hanna HI772 (dKH), extrae el valor directo de la pantalla.
   - Si es Salifert Titulación: lee la marca exacta del émbolo de la jeringa o el valor deducido de la tabla.
   - Si no hay ningún número legible, asigna null.

3. "confidence": Un número flotante entre 0.0 y 1.0 reflejando tu nivel de certeza de la lectura.

4. "kit_detected": Nombre descriptivo del kit identificado (ej: "Hanna Checker HI772 Alcalinidad dKH", "Salifert Nitrato NO3", "Refractómetro Óptico 35ppt", "Vial Colorimétrico Red Sea").

5. "notes": Breve nota con detalles observados (ej: "Lectura digital clara en pantalla: 8.3 dKH").

6. "raw_reading": Texto exacto detectado en la pantalla o escala (ej: "8.3", "0.14 ml", "35 ppt").
"""

class ScanMeasurementRequest(BaseModel):
    image_base64: str = Field(..., description="Imagen en Base64 (incluyendo o no data:image/...)")
    preferred_parameter: Optional[str] = Field(None, description="Parámetro sugerido si el usuario preseleccionó uno")
    demo_fallback: bool = Field(True, description="Si no hay API key configurada, simular lectura de muestra para pruebas de UI")

class ScanMeasurementResponse(BaseModel):
    success: bool
    api_key_configured: bool
    parameter: Optional[str] = None
    value: Optional[float] = None
    confidence: float = 0.0
    kit_detected: Optional[str] = None
    notes: Optional[str] = None
    raw_reading: Optional[str] = None
    message: str


def extract_image_bytes(image_data: str) -> tuple[bytes, str]:
    """Extrae los bytes binarios y el tipo MIME de una cadena Base64."""
    mime_type = "image/webp"
    clean_b64 = image_data.strip()

    if clean_b64.startswith("data:"):
        match = re.match(r"data:([^;]+);base64,(.+)", clean_b64, re.DOTALL)
        if match:
            mime_type = match.group(1)
            clean_b64 = match.group(2)

    image_bytes = base64.b64decode(clean_b64)
    return image_bytes, mime_type


def analyze_test_image(
    image_data: str,
    preferred_parameter: Optional[str] = None,
    allow_demo_fallback: bool = True
) -> ScanMeasurementResponse:
    """
    Analiza una fotografía de test de acuario usando la librería oficial Google GenAI (Gemini).
    Si la API Key no está configurada, devuelve un mensaje claro o una respuesta simulada para pruebas.
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

    # 1. Si no hay API Key configurada
    if is_dummy_key:
        if allow_demo_fallback:
            logger.warning("⚠️ GEMINI_API_KEY no configurada. Generando detección demostrativa para pruebas de UI.")
            # Si el usuario eligió un parámetro preferido, usamos ese, sino Alcalinidad
            param = preferred_parameter if preferred_parameter in [
                "alkalinity_dkh", "calcium_ppm", "magnesium_ppm",
                "nitrate_ppm", "phosphate_ppm", "salinity_ppt"
            ] else "alkalinity_dkh"

            demo_values = {
                "alkalinity_dkh": (8.25, "Hanna Checker HI772 dKH", "Lectura digital detectada: 8.25 dKH"),
                "calcium_ppm": (425.0, "Hanna Checker HI758 Calcio", "Lectura digital detectada: 425 ppm"),
                "magnesium_ppm": (1350.0, "Salifert Magnesio", "Titulación jeringa detectada: 1350 ppm"),
                "nitrate_ppm": (7.5, "Salifert Nitrato NO3", "Comparación cromática detectada: ~7.5 ppm"),
                "phosphate_ppm": (0.035, "Hanna Checker HI736 Fósforo ULR", "11 ppb detectado -> 0.035 ppm PO4"),
                "salinity_ppt": (35.0, "Refractómetro Óptico", "Línea de contraste en 35 ppt / 1.026 SG")
            }

            val, kit, note = demo_values.get(param, (8.3, "Test Demo", "Lectura de muestra"))

            return ScanMeasurementResponse(
                success=True,
                api_key_configured=False,
                parameter=param,
                value=val,
                confidence=0.92,
                kit_detected=kit,
                notes=f"{note} (Modo Demo: Configura GEMINI_API_KEY en backend/.env para reconocimiento con IA real)",
                raw_reading=str(val),
                message="Detección en modo demostración. Inserta tu GEMINI_API_KEY en backend/.env para activar el modelo de visión en vivo."
            )
        else:
            return ScanMeasurementResponse(
                success=False,
                api_key_configured=False,
                message="API Key no configurada. Por favor define GEMINI_API_KEY en el archivo backend/.env."
            )

    # 2. Conexión con la librería oficial Google GenAI
    try:
        from google import genai
        from google.genai import types

        image_bytes, mime_type = extract_image_bytes(image_data)
        primary_model = os.environ.get("VISION_MODEL", "gemini-3.1-flash-lite")
        fallback_models = [primary_model, "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash-lite"]
        # Eliminar duplicados manteniendo orden
        candidate_models = list(dict.fromkeys(fallback_models))

        client = genai.Client(api_key=api_key)

        prompt_context = AQUARIUM_VISION_SYSTEM_PROMPT
        if preferred_parameter:
            prompt_context += f"\nNota adicional: El acuarista sospecha que este test corresponde al parámetro: '{preferred_parameter}'."

        last_error = None
        response = None

        for model_cand in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_cand,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        prompt_context
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                if response and response.text:
                    break
            except Exception as model_err:
                logger.warning(f"Error con modelo {model_cand}: {model_err}. Probando siguiente modelo...")
                last_error = model_err

        if not response or not response.text:
            raise RuntimeError(f"No se pudo obtener respuesta de visión: {last_error}")

        response_text = response.text.strip()
        data = json.loads(response_text)

        param = data.get("parameter")
        val = data.get("value")
        confidence = float(data.get("confidence", 0.8))
        kit_detected = data.get("kit_detected", "Test kit identificado")
        notes = data.get("notes", "")
        raw_reading = data.get("raw_reading", str(val) if val is not None else "")

        if val is not None:
            val = float(val)

        return ScanMeasurementResponse(
            success=True,
            api_key_configured=True,
            parameter=param,
            value=val,
            confidence=confidence,
            kit_detected=kit_detected,
            notes=notes,
            raw_reading=raw_reading,
            message="Lectura extraída exitosamente con Google Gemini Vision."
        )

    except Exception as e:
        logger.error(f"Error procesando imagen con Gemini Vision: {e}")
        return ScanMeasurementResponse(
            success=False,
            api_key_configured=True,
            message=f"Error al analizar la imagen con el modelo de visión: {str(e)}"
        )
