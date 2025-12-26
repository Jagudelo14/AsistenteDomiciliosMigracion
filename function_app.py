# function_app.py
# Last modified: 2025-21-12 Juan Agudelo
# ajsute efectivo
import azure.functions as func
from datetime import datetime
import logging
import os
import json
from utils import obtener_datos_cliente_por_telefono, send_pdf_response, send_text_response,  log_message, get_client_database, handle_create_client, get_client_name_database,verify_hour_atettion,validate_duplicated_message
from utils_chatgpt import get_classifier, get_openai_key,get_direction,get_name
from utils_subflujos import manejar_dialogo
from utils_google import orquestador_ubicacion_exacta,calcular_distancia_entre_sede_y_cliente,geocode_and_assign
from utils_registration import  update_dir_primera_vez, update_nombre_bool, validate_nombre_bool,  validate_direction_first_time
from utils_database import execute_query
from typing import Any, Dict, Optional, List
import requests
from openai import OpenAI
import io
from utils_contexto import set_sender,crear_conversacion, actualizar_conversacion,obtener_contexto_conversacion
import random

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
        #Validación mensaje duplicado###################################
        if validate_duplicated_message(message_id):
            logging.info(f"Mensaje duplicado: {message_id}")
            return func.HttpResponse("Mensaje duplicado", status_code=200)
        sender: str = message["from"]
        set_sender(sender)
        nombre_cliente: str
        if not verify_hour_atettion(sender, ID_RESTAURANTE):
            return func.HttpResponse("Fuera de horario de atención", status_code=200)
        ####################################
        ############ CLIENTE NUEVO  ############
        ####################################
        if not get_client_database(sender, ID_RESTAURANTE):
            log_message("Cliente nuevo detectado", "INFO")
            datos: str = None
            nombre_temp: str = handle_create_client(sender, datos, ID_RESTAURANTE, False)
            log_message(f"Cliente creado en base de datos: {nombre_temp}", "INFO")
            if tipo_general == "text":
                text: str = message.get("text", {}).get("body", "")
                conversacion = crear_conversacion(text)
                log_message(f"Conversación iniciada: {conversacion}", "INFO")  
                if not text:
                    logging.warning("⚠️ Mensaje recibido sin texto.")
                    return func.HttpResponse("Mensaje vacío", status_code=200)
            elif message["type"] == "audio":
                audio_id = message["audio"]["id"]
                mime_type = message["audio"]["mime_type"]
                logging.info(f"Audio recibido de {sender}: ID {audio_id}, Tipo {mime_type}")
                log_message("Llega mensaje de audio", "INFO")
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
                conversacion = crear_conversacion(text)
                log_message(f"Conversación iniciada: {conversacion}", "INFO")          
            send_text_response(sender,"¡Hola! al continuar la conversación entendemos que aceptas el tratamiento de tus datos. \nPuedes saber mas de la política de aqui: https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981")
            send_text_response(sender, "Recuerda que hablas con un asistente virtual 😊 Durante toda la conversación, procura enviar tus solicitudes en un solo mensaje para poder ayudarte mejor.\nPara continuar, envíame:\n• Tu nombre\n• Tu dirección")
            return func.HttpResponse("Cliente no registrado, esperando datos", status_code=200)
        ####################################
        ########### CLIENTE EXISTENTE ######
        ####################################
        else:
            log_message("Cliente existente detectado", "INFO")
            nombre_cliente = get_client_name_database(sender, ID_RESTAURANTE)
            if tipo_general == "text":
                text: str = message.get("text", {}).get("body", "")
                conversacion = actualizar_conversacion(text,sender,"usuario")
                if not text:
                    logging.warning("⚠️ Mensaje recibido sin texto.")
                    return func.HttpResponse("Mensaje vacío", status_code=200)
            elif message["type"] == "audio":
                    log_message("Llega mensaje de audio", "INFO")
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
                    conversacion = actualizar_conversacion(text,sender,"usuario")
                    logging.info(f"Transcripción recibida: {text}")
                    log_message(f"Mensaje transcrito {text}", "INFO")
            elif tipo_general == "location" and validate_direction_first_time(sender, ID_RESTAURANTE) is False:
                latitude_temp = message["location"]["latitude"]
                longitude_temp = message["location"]["longitude"]
                log_message(f"Ubicación recibida: lat {latitude_temp}, lon {longitude_temp}", "INFO")
                calcular_distancia_entre_sede_y_cliente(sender, latitude_temp, longitude_temp, ID_RESTAURANTE, nombre_cliente)
                update_dir_primera_vez(sender, ID_RESTAURANTE, True)
                return func.HttpResponse("EVENT_RECEIVED", status_code=200)
            elif tipo_general == "location" and validate_direction_first_time(sender, ID_RESTAURANTE) is True:
                latitude_temp = message["location"]["latitude"]
                longitude_temp = message["location"]["longitude"]
                log_message(f"Ubicación recibida: lat {latitude_temp}, lon {longitude_temp}", "INFO")
                orquestador_ubicacion_exacta(sender, latitude_temp, longitude_temp, ID_RESTAURANTE, nombre_cliente)    
            elif tipo_general == "image":
                # No procesamos el contenido de la imagen; la tratamos como comprobante
                image_id = message["image"].get("id")
                mime_type = message["image"].get("mime_type", "")
                log_message(f"Imagen recibida de {sender}: ID {image_id}, Tipo {mime_type}", "INFO")
                # Guardar un registro sencillo en la base y clasificar como "validacion_pago"
                # Llamar al manejador de diálogo como si el usuario pidiera validar pago
                manejar_dialogo(
                    sender=sender,
                    clasificacion_mensaje="validacion_pago",
                    nombre_cliente=nombre_cliente,
                    entidades_text={},
                    pregunta_usuario="[imagen_pago]",
                    bandera_externo=False,
                    id_ultima_intencion="",
                    nombre_local="Sierra Nevada",
                    type_text = "image"
                )
                return func.HttpResponse("EVENT_RECEIVED", status_code=200)
            else:
                logging.warning(f"⚠️ Tipo de mensaje no soportado: {tipo_general}")
                send_text_response(sender, "Por el momento solo puedo procesar mensajes de texto.Intenta de nuevo con un mensaje escrito o de voz.")
                return func.HttpResponse("Tipo de mensaje no soportado", status_code=200)
                # Clasificación con modelo OpenAI
            log_message(f"Empieza a clasificar con text {text}", "INFO")
            if text:
                if not validate_direction_first_time(sender, ID_RESTAURANTE) or not validate_nombre_bool(sender, ID_RESTAURANTE):
                    direccion=get_direction(text)
                    nombre=get_name(text)
                    booleano_dir: bool = True
                    if direccion and not validate_direction_first_time(sender, ID_RESTAURANTE):
                        #send_text_response(sender, "Gracias , voy a validar que estes en nuestra cobertura dame un par de minutos.")
                        logging.info(f"Usuario {sender} proporcionó una dirección.")
                        log_message(f"Usuario {sender} proporcionó una dirección.", "INFO")
                        geocode_and_assign(sender, direccion, ID_RESTAURANTE)
                        datos_cliente_temp: dict = obtener_datos_cliente_por_telefono(sender, ID_RESTAURANTE)
                        latitud_cliente: float = datos_cliente_temp.get("latitud", 0.0)
                        longitud_cliente: float = datos_cliente_temp.get("longitud", 0.0)
                        resultado=calcular_distancia_entre_sede_y_cliente(sender,latitud_cliente, longitud_cliente,ID_RESTAURANTE, nombre_cliente)
                        update_dir_primera_vez(sender, ID_RESTAURANTE, True)
                        if resultado is None:
                            execute_query("""
                                            UPDATE clientes_whatsapp
                                            SET direccion_google = %s
                                            WHERE telefono = %s AND id_restaurante = %s;
                                            """, (None, sender, ID_RESTAURANTE))
                            booleano_dir = False
                    if nombre and not validate_nombre_bool(sender, ID_RESTAURANTE):
                        execute_query("""
                                        UPDATE clientes_whatsapp
                                        SET nombre = %s
                                        WHERE telefono = %s AND id_restaurante = %s;
                        """, (nombre,sender, ID_RESTAURANTE))
                        log_message(f'Cliente creado o actualizado exitosamente.{nombre}', 'INFO')
                        update_nombre_bool(sender, ID_RESTAURANTE, True)
                    if not validate_direction_first_time(sender, ID_RESTAURANTE):
                        send_text_response(sender, "Por favor, comparteme tu ubicación para continuar con el pedido.")
                    if not validate_nombre_bool(sender, ID_RESTAURANTE):
                        send_text_response(sender, "Por favor, indícame tu nombre para continuar con el pedido.")
                    if booleano_dir is False:
                        send_text_response(sender, "No estas dentro de nuestra area de operación, puedes hacer tu pedido para recoger en tienda")
                    if validate_direction_first_time(sender, ID_RESTAURANTE) and validate_nombre_bool(sender, ID_RESTAURANTE):
                        send_text_response(sender,"¡Gracias por la información! 😊 Bienvenido a sierra nevada la cima del sabor")
                        send_pdf_response(sender)                 
                    return func.HttpResponse("EVENT_RECEIVED", status_code=200)
                mensajes= obtener_contexto_conversacion(sender)
                text = str(mensajes)
                if len(mensajes) > 2:
                    ultimo = mensajes[-1][0]["rol"]
                    penultimo = mensajes[-2][0]["rol"]

                    if ultimo == "usuario" and penultimo == "usuario":
                        mensajes = [
                            "Recuerda enviar tus solicitudes en un único mensaje.",
                            "Por favor, envía todas tus solicitudes en un solo mensaje.",
                            "Ten presente que debes enviar tus solicitudes en un único mensaje.",
                            "Recuerda enviar tus solicitudes juntas en un solo mensaje.",
                            "Importante: envía tus solicitudes en un único mensaje."
                            ]

                        mensaje = random.choice(mensajes)
                        send_text_response(sender, mensaje)   
                        return func.HttpResponse("EVENT_RECEIVED", status_code=200)
                log_message(f"Contexto de conversación obtenido: {text}", "INFO")
                classification: str
                type_text: str
                entities_text: Dict[str, Any]
                classification, type_text, entities_text = get_classifier(text, sender)
                logging.info(
                    f"Clasificación: {classification}, Tipo: {type_text}, Entidades: {entities_text}"
                )
                # Guardar mensaje en base de datos
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

