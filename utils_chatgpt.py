# utils_chatgpt.py
# Last modified: 2025-09-26 by Andrés Bermúdez

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
