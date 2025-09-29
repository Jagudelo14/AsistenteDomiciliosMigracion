# function_app.py
# Last modified: 2025-09-26 by Andrés Bermúdez

import azure.functions as func
import logging
import os
import json
from utils import send_text_response, validate_duplicated_message, log_message
from utils_chatgpt import get_classifier
from typing import Any, Dict, Optional, List

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Constantes desde variables de entorno
VERIFY_TOKEN:str = os.environ["META_VERIFY_TOKEN"] 
ACCESS_TOKEN:str = os.environ["WABA_TOKEN"]
#PHONE_ID:str = os.environ["PHONE_NUMBER_ID"] 

@app.function_name(name="wpp_webhook")
@app.route(route="wpp", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET", "POST"])
def wpp(req: func.HttpRequest) -> func.HttpResponse:
    """
    Webhook de WhatsApp Business API:
    - GET → Verificación inicial de Meta.
    - POST → Recepción de mensajes y clasificación con OpenAI.
    """
    logging.info("📩 Webhook WhatsApp recibido.")
    if req.method == "GET":
        return _verify_webhook(req)
    if req.method == "POST":
        return _process_message(req)
    return func.HttpResponse("Método no permitido", status_code=405)

def _verify_webhook(req: func.HttpRequest) -> func.HttpResponse:
    """Maneja la verificación inicial del webhook de Meta."""
    mode: Optional[str] = req.params.get("hub.mode")
    token: Optional[str] = req.params.get("hub.verify_token")
    challenge: Optional[str] = req.params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logging.info("✅ Webhook verificado correctamente.")
        return func.HttpResponse(challenge, status_code=200)
    logging.warning("❌ Verificación fallida.")
    return func.HttpResponse("Error de verificación", status_code=403)

def _process_message(req: func.HttpRequest) -> func.HttpResponse:
    try:
        """Procesa los mensajes recibidos desde WhatsApp Business API."""
        log_message('Iniciando función <ProcessMessage>.', 'INFO')
        req_body: Dict[str, Any] = json.loads(req.get_body().decode("utf-8"))
        logging.info(f"Cuerpo recibido: {json.dumps(req_body, indent=2)}")
        entry: Dict[str, Any] = req_body.get("entry", [{}])[0]
        change: Dict[str, Any] = entry.get("changes", [{}])[0]
        value: Dict[str, Any] = change.get("value", {})
        messages: Optional[List[Dict[str, Any]]] = value.get("messages")
        if not messages:
            logging.info("No hay mensajes en el evento. Puede ser una notificación de estado.")
            return func.HttpResponse("Sin mensajes para procesar", status_code=200)
        message: Dict[str, Any] = messages[0]
        message_id = message["id"]
        if validate_duplicated_message(message_id):
            logging.info(f"Mensaje duplicado: {message_id}")
            return func.HttpResponse("Mensaje duplicado", status_code=200)
        sender: str = message["from"]
        text: str = message.get("text", {}).get("body", "")
        if not text:
            logging.warning("⚠️ Mensaje recibido sin texto.")
            return func.HttpResponse("Mensaje vacío", status_code=200)
        # Clasificación con modelo OpenAI
        classification: str
        type_text: str
        entities_text: Dict[str, Any]
        classification, type_text, entities_text = get_classifier(text, sender)
        logging.info(
            f"Clasificación: {classification}, Tipo: {type_text}, Entidades: {entities_text}"
        )
        # Responder al usuario
        send_text_response(sender, classification or "Sin clasificación")
        log_message('Finalizando función <ProcessMessage>.', 'INFO')
        return func.HttpResponse("EVENT_RECEIVED", status_code=200)
    except Exception as e:
        log_message(f'Error al hacer uso de función <ProcessMessage>: {e}.', 'ERROR')
        logging.error(f"⚠️ Error procesando POST: {e}")
        return func.HttpResponse("Error", status_code=400)