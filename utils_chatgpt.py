# utils_chatgpt.py
# Last modified: 2025-11-05 by Andrés Bermúdez

from openai import OpenAI
import logging
from typing import Any, Optional, Tuple, Dict
import os
import json
from utils import send_text_response, limpiar_respuesta_json, log_message

def get_openai_key() -> str:
    try:
        """Obtiene la clave API de OpenAI desde variables de entorno."""
        log_message('Iniciando función <GetOpenAIKey>.', 'INFO')
        logging.info('Obteniendo clave de OpenAI')
        api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("No se encontró la clave OPENAI_API_KEY en las variables de entorno.")
        logging.info('Clave de OpenAI obtenida')
        log_message('Finalizando función <GetOpenAIKey>.', 'INFO')
        return api_key
    except Exception as e:
        log_message(f"Error al obtener la clave de OpenAI: {e}", 'ERROR')
        logging.error(f"Error al obtener la clave de OpenAI: {e}")
        raise
    
def get_classifier(msj: str, sender: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    try:
        """Clasifica un mensaje de WhatsApp usando un modelo fine-tuned de OpenAI."""
        log_message('Iniciando función <GetClassifier>.', 'INFO')
        logging.info('Clasificando mensaje')
        classificationPrompt: str = """
        Eres un clasificador de mensajes para un asistente de WhatsApp de un restaurante.
        Responde **únicamente** en formato JSON válido con la siguiente estructura:
        {
          "intent": "<la intención detectada>",
          "type": "<el tipo de mensaje>",
          "entities": { }
        }
        No incluyas explicaciones ni texto fuera del JSON.
        """
        messages = [
            {"role": "system", "content": classificationPrompt},
            {"role": "user", "content": msj}
        ]
        client: OpenAI = OpenAI(api_key=get_openai_key())
        respuesta: Any = client.chat.completions.create(
            model="ft:gpt-3.5-turbo-0125:net-applications:domicilios:CJRSZZ2S",
            messages=messages,
            max_tokens=500,
            temperature=0.1
        )
        raw_response: str = respuesta.choices[0].message.content.strip()
        logging.info(f"[Clasificador RAW] {raw_response!r}")
        json_str: str = limpiar_respuesta_json(raw_response)
        result: Dict[str, Any] = json.loads(json_str)
        intent: Optional[str] = result.get("intent")
        type_: Optional[str] = result.get("type")
        entities: Dict[str, Any] = result.get("entities", {})
        if not intent or not type_:
            raise ValueError(f"Respuesta inválida, faltan claves: {result}")
        logging.info(f"Respuesta del clasificador: {result}")
        logging.info(f"Intent: {intent}, Type: {type_}, Entities: {entities}")
        log_message('Finalizando función <GetClassifier>.', 'INFO')
        return intent, type_, entities
    except Exception as e:
        log_message(f'Error al hacer uso de función <GetClassifier>: {e}.', 'ERROR')
        logging.error(f"Error al clasificar el mensaje: {e}")
        send_text_response(sender, "Lo siento, hubo un error al procesar tu mensaje. ¿Podrías repetirlo?")
        return None, None, {}

def analizar_respuesta_usuario_sin_intencion(respuesta_cliente: str, intencion_anterior: str, model: str = "gpt-3.5-turbo") -> dict:
    """
    Analiza si la respuesta del usuario tiene continuidad con la intención anterior.
    
    Parámetros:
        respuesta_cliente (str): Respuesta dada por el usuario (e.g., "sí", "no", "no entiendo").
        intencion_anterior (str): Intención previa detectada en el flujo conversacional.
        model (str): Modelo de OpenAI a utilizar.
    
    Retorna:
        dict: JSON con la estructura solicitada.
    """
    client: OpenAI = OpenAI()
    prompt = f"""
        Eres un asistente que analiza si la respuesta de un usuario mantiene continuidad con la intención anterior.
        Tu salida debe ser un JSON EXACTO con la forma:
        {{
        "intencion_respuesta": "nombre_intencion",
        "continuidad": bool,
        "observaciones": "texto opcional si hay duda o ruptura de flujo"
        }}

        Ejemplos:

        1️⃣
        intencion_anterior: "consulta_promociones"
        respuesta_cliente: "sí"
        →
        {{
        "intencion_respuesta": "consulta_promociones",
        "continuidad": true,
        "observaciones": ""
        }}

        2️⃣
        intencion_anterior: "consulta_promociones"
        respuesta_cliente: "no"
        →
        {{
        "intencion_respuesta": "consulta_promociones",
        "continuidad": false,
        "observaciones": "El usuario rechazó la continuidad de la promoción"
        }}

        3️⃣
        intencion_anterior: "consulta_productos"
        respuesta_cliente: "no entiendo"
        →
        {{
        "intencion_respuesta": "consulta_productos",
        "continuidad": false,
        "observaciones": "El usuario parece confundido o necesita aclaración"
        }}

        4️⃣
        intencion_anterior: "reclamo_servicio"
        respuesta_cliente: "ya lo solucionaron"
        →
        {{
        "intencion_respuesta": "reclamo_servicio",
        "continuidad": false,
        "observaciones": "El usuario indica que el problema ya se resolvió"
        }}

        5️⃣
        intencion_anterior: "consulta_horarios"
        respuesta_cliente: "perfecto, gracias"
        →
        {{
        "intencion_respuesta": "consulta_horarios",
        "continuidad": true,
        "observaciones": "El usuario confirma que recibió la información"
        }}

        Ahora analiza:
        intencion_anterior: "{intencion_anterior}"
        respuesta_cliente: "{respuesta_cliente}"

        Devuelve SOLO el JSON, sin explicación.
    """ 
    response = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.3
    )
    text_output = response.output[0].content[0].text.strip()
    try:
        result = json.loads(text_output)
    except json.JSONDecodeError:
        result = {
            "intencion_respuesta": intencion_anterior,
            "continuidad": False,
            "observaciones": "Error al interpretar la respuesta del modelo"
        }
    log_message('Finalizando función <AnalizarRespuestaUsuarioSinIntencion>.', 'INFO')
    log_message(f'Respuesta analizada: {result}', 'INFO')
    return result