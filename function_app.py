# function_app.py
# Last modified: 2025-09-30 by Andrés Bermúdez

import azure.functions as func
from datetime import datetime
import logging
import os
import json
from utils import obtener_intencion_futura_observaciones, send_text_response, validate_duplicated_message, log_message, get_client_database, handle_create_client, save_message_to_db, get_client_name_database, guardar_clasificacion_intencion, obtener_ultima_intencion_no_resuelta, marcar_intencion_como_resuelta
from utils_chatgpt import get_classifier, get_openai_key
from utils_subflujos import manejar_dialogo
from utils_google import orquestador_ubicacion_exacta
from typing import Any, Dict, Optional, List
import requests
from openai import OpenAI
import io

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Constantes desde variables de entorno
VERIFY_TOKEN: str = os.environ["META_VERIFY_TOKEN"] 
ACCESS_TOKEN: str = os.environ["WABA_TOKEN"]
ID_RESTAURANTE: str = os.environ.get("ID_RESTAURANTE", "5")
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
        client = OpenAI(api_key=get_openai_key())
        if not messages:
            logging.info("No hay mensajes en el evento. Puede ser una notificación de estado.")
            return func.HttpResponse("Sin mensajes para procesar", status_code=200)
        message: Dict[str, Any] = messages[0]
        tipo_general = message["type"]
        logging.info(f"Tipo de mensaje recibido: {tipo_general}")
        message_id = message["id"]
        # Validación mensaje duplicado
        if validate_duplicated_message(message_id):
            logging.info(f"Mensaje duplicado: {message_id}")
            return func.HttpResponse("Mensaje duplicado", status_code=200)
        sender: str = message["from"]
        nombre_cliente: str
        respuesta_bot : str
        if not get_client_database(sender, ID_RESTAURANTE):
            dict_vacio: dict = {}
            nombre_temp: str = handle_create_client(sender, dict_vacio, ID_RESTAURANTE, True)
            if tipo_general == "text":
                text: str = message.get("text", {}).get("body", "")
                if not text:
                    logging.warning("⚠️ Mensaje recibido sin texto.")
                    return func.HttpResponse("Mensaje vacío", status_code=200)
            elif message["type"] == "audio":
                audio_id = message["audio"]["id"]
                mime_type = message["audio"]["mime_type"]
                logging.info(f"Audio recibido de {sender}: ID {audio_id}, Tipo {mime_type}")
                log_message(f"Llega mensaje de audio", "INFO")
                headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
                media_url = f"https://graph.facebook.com/v17.0/{audio_id}?fields=url"
                response = requests.get(media_url, headers=headers)
                media_info = response.json()
                if "url" not in media_info:
                    logging.error(f"No se encontró la URL del audio: {media_info}")
                    return func.HttpResponse("No se pudo obtener el audio", status_code=500)
                file_url = media_info["url"]
                audio_response = requests.get(file_url, headers=headers)
                audio_data = io.BytesIO(audio_response.content)
                files = {"file": ("audio.ogg", audio_data, mime_type)}
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=files["file"]
                )
                text = transcript.text
                logging.info(f"Transcripción recibida: {text}")
                log_message(f"Mensaje transcrito {text}", "INFO")
            else:
                send_text_response(sender,"¡Hola! Parece que eres un nuevo cliente. Por favor, envíame tu *nombre completo* para poder atenderte mejor.\nEjemplo: *Juan Pérez*")
                return func.HttpResponse("Cliente no registrado, esperando datos", status_code=200)
            log_message(f"Empieza a clasificar cliente nuevo", "INFO")
            if text:
                # Clasificación con modelo OpenAI
                classification: str
                type_text: str
                entities_text: str
                classification, type_text, entities_text = get_classifier(text, sender)
                # implementar guardado de intention
                if classification == "info_personal":
                    nombre_temp: str = handle_create_client(sender, entities_text, ID_RESTAURANTE, False)
                    respuesta_bot = f"¡Gracias por registrarte {nombre_temp}! Bienvenido a Sierra Nevada."
                    send_text_response(sender, respuesta_bot)
                    id_temp: str = guardar_clasificacion_intencion(sender, classification, "sin_resolver", "usuario", text, "", type_text, entities_text)
                    marcar_intencion_como_resuelta(id_temp)
                    data_temp = obtener_ultima_intencion_no_resuelta(sender)
                    if data_temp:
                        manejar_dialogo(
                            sender=sender,
                            clasificacion_mensaje=classification,
                            nombre_cliente=nombre_cliente,
                            entidades_text=entities_text,
                            pregunta_usuario=text,
                            bandera_externo=False,
                            id_ultima_intencion="",
                            nombre_local="Sierra Nevada",
                            type_text = type_text
                        )
                else:
                    respuesta_bot = "¡Hola! Parece que eres un nuevo cliente. Por favor, envíame tu *nombre completo* para poder atenderte mejor.\nEjemplo: *Juan Pérez*"
                    guardar_clasificacion_intencion(sender, classification, "sin_resolver", "usuario", text, "", type_text, entities_text)
                    send_text_response(sender, respuesta_bot)
        else:
            nombre_cliente = get_client_name_database(sender, ID_RESTAURANTE)
            if tipo_general == "text":
                text: str = message.get("text", {}).get("body", "")
                if not text:
                    logging.warning("⚠️ Mensaje recibido sin texto.")
                    return func.HttpResponse("Mensaje vacío", status_code=200)
                elif message["type"] == "audio":
                    log_message(f"Llega mensaje de audio", "INFO")
                    audio_id = message["audio"]["id"]
                    mime_type = message["audio"]["mime_type"]
                    logging.info(f"Audio recibido de {sender}: ID {audio_id}, Tipo {mime_type}")
                    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
                    media_url = f"https://graph.facebook.com/v17.0/{audio_id}?fields=url"
                    response = requests.get(media_url, headers=headers)
                    media_info = response.json()
                    if "url" not in media_info:
                        logging.error(f"No se encontró la URL del audio: {media_info}")
                        return func.HttpResponse("No se pudo obtener el audio", status_code=500)
                    file_url = media_info["url"]
                    audio_response = requests.get(file_url, headers=headers)
                    audio_data = io.BytesIO(audio_response.content)
                    files = {"file": ("audio.ogg", audio_data, mime_type)}
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=files["file"]
                    )
                    text = transcript.text
                    logging.info(f"Transcripción recibida: {text}")
                    log_message(f"Mensaje transcrito {text}", "INFO")
                elif tipo_general == "location":
                    latitude_temp = message["location"]["latitude"]
                    longitude_temp = message["location"]["longitude"]
                    log_message(f"Ubicación recibida: lat {latitude_temp}, lon {longitude_temp}", "INFO")
                    orquestador_ubicacion_exacta(sender, latitude_temp, longitude_temp, ID_RESTAURANTE, nombre_cliente)
                else:
                    logging.warning(f"⚠️ Tipo de mensaje no soportado: {tipo_general}")
                    send_text_response(sender, "Por el momento solo puedo procesar mensajes de texto.")
                    return func.HttpResponse("Tipo de mensaje no soportado", status_code=200)
                # Clasificación con modelo OpenAI
                classification: str
                type_text: str
                entities_text: Dict[str, Any]
                classification, type_text, entities_text = get_classifier(text, sender)
                logging.info(
                    f"Clasificación: {classification}, Tipo: {type_text}, Entidades: {entities_text}"
                )
                # Guardar mensaje en base de datos
                save_message_to_db(sender, text, classification, type_text, str(entities_text), tipo_general, ID_RESTAURANTE)
                manejar_dialogo(
                    sender=sender,
                    clasificacion_mensaje=classification,
                    nombre_cliente=nombre_cliente,
                    entidades_text=entities_text,
                    pregunta_usuario=text,
                    bandera_externo=False,
                    id_ultima_intencion="",
                    nombre_local="Sierra Nevada",
                    type_text = type_text
                )
                log_message('Finalizando función <ProcessMessage>.', 'INFO')
                return func.HttpResponse("EVENT_RECEIVED", status_code=200)
    except Exception as e:
        log_message(f'Error al hacer uso de función <ProcessMessage>: {e}.', 'ERROR')
        logging.error(f"⚠️ Error procesando POST: {e}")
        return func.HttpResponse("Error", status_code=400)

@app.function_name(name="health_check")
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET", "POST"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint simple para probar disponibilidad desde Postman.
    - GET  → responde con una página HTML sencilla que dice "Todo OK" y la hora.
    - POST → devuelve una página HTML que dice "Todo OK" y muestra el JSON/texto recibido.
    """
    try:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        if req.method == "GET":
            html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Health Check</title>
</head>
<body>
  <h1>Todo OK</h1>
  <p>Servicio activo — {now}</p>
</body>
</html>"""
            return func.HttpResponse(
                html,
                status_code=200,
                mimetype="text/html"
            )

        if req.method == "POST":
            body_raw = req.get_body().decode("utf-8")
            # intentamos parsear JSON para mostrarlo bonito, si no, mostramos el texto plano
            try:
                body = json.loads(body_raw)
                pretty_body = json.dumps(body, ensure_ascii=False, indent=2)
            except Exception:
                pretty_body = body_raw

            html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Health Check - POST</title>
</head>
<body>
  <h1>Todo OK</h1>
  <p>Servicio activo — {now}</p>
  <h2>Contenido recibido:</h2>
  <pre>{func.HtmlEscape(pretty_body)}</pre>
</body>
</html>"""
            # Si tu versión de azure.functions no tiene HtmlEscape, reemplaza por: pretty_body.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            return func.HttpResponse(
                html,
                status_code=200,
                mimetype="text/html"
            )

    except Exception as e:
        logging.error(f"Error en /health: {e}")
        error_html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Error</title></head>
<body>
  <h1>ERROR</h1>
  <p>{str(e)}</p>
</body>
</html>"""
        return func.HttpResponse(
            error_html,
            status_code=500,
            mimetype="text/html"
        )