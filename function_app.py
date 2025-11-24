# function_app.py
# Last modified: 2025-09-30 by Andrés Bermúdez

import azure.functions as func
import logging
import os
import json
from utils import send_text_response, validate_duplicated_message, log_message, get_client_database, handle_create_client, save_message_to_db, get_client_name_database, guardar_clasificacion_intencion, obtener_ultima_intencion_no_resuelta, marcar_intencion_como_resuelta
from utils_chatgpt import get_classifier
from utils_subflujos import manejar_dialogo
from utils_google import orquestador_ubicacion_exacta
from typing import Any, Dict, Optional, List

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Constantes desde variables de entorno
VERIFY_TOKEN: str = os.environ["META_VERIFY_TOKEN"] 
ACCESS_TOKEN: str = os.environ["WABA_TOKEN"]
ID_RESTAURANTE: str = os.environ.get("ID_RESTAURANTE", "1")
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
                    #todo mirar intenciones faltantes
                    
                    # Falta envio de menú
                else:
                    respuesta_bot = "¡Hola! Parece que eres un nuevo cliente. Por favor, envíame tu *nombre completo* para poder atenderte mejor.\nEjemplo: *Juan Pérez*"
                    guardar_clasificacion_intencion(sender, classification, "sin_resolver", "usuario", text, "", type_text, entities_text)
                    send_text_response(sender, respuesta_bot)
            else:
                    send_text_response(sender,"¡Hola! Parece que eres un nuevo cliente. Por favor, envíame tu *nombre completo* para poder atenderte mejor.\nEjemplo: *Juan Pérez*")
            return func.HttpResponse("Cliente no registrado, esperando datos", status_code=200)
        else:
            nombre_cliente = get_client_name_database(sender, ID_RESTAURANTE)
            if tipo_general == "text":
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
                send_text_response(sender, f"Clasificación: {classification}, Tipo: {type_text}, Entidades: {entities_text}")
                # Guardar mensaje en base de datos
                save_message_to_db(sender, text, classification, type_text, str(entities_text), tipo_general, ID_RESTAURANTE)
                # Verificar si el usuario ya existe en la base de datos
                # Responder al usuario
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
                send_text_response(sender, classification or "Sin clasificación")
                log_message('Finalizando función <ProcessMessage>.', 'INFO')
                return func.HttpResponse("EVENT_RECEIVED", status_code=200)
            elif tipo_general == "location":
                latitude_temp = message["location"]["latitude"]
                longitude_temp = message["location"]["longitude"]
                log_message(f"Ubicación recibida: lat {latitude_temp}, lon {longitude_temp}", "INFO")
                sedes_cercanas = orquestador_ubicacion_exacta(sender, latitude_temp, longitude_temp, ID_RESTAURANTE)
                if sedes_cercanas:
                    # Sede principal (la más cercana)
                    sede_principal = sedes_cercanas
                    mensaje = (
                        f"🏢 La sede más cercana a tu ubicación es:\n"
                        f"➡️ {sede_principal['nombre']} en {sede_principal['ciudad']}, "
                        f"a {sede_principal['distancia_km']} km "
                        f"(~{sede_principal['tiempo_min']} min en carro).\n\n"
                    )
                
                    send_text_response(sender, mensaje)
                else:
                    send_text_response(
                        sender,
                        "📍 Gracias por tu ubicación.\n\nEn este momento no encontramos una sede que pueda atender tu dirección dentro de nuestra zona de cobertura.\n\nEsperamos próximamente en tu barrio. 😊 - Sierra Nevada"
                    )
            else:
                logging.warning(f"⚠️ Tipo de mensaje no soportado: {tipo_general}")
                send_text_response(sender, "Por el momento solo puedo procesar mensajes de texto.")
                return func.HttpResponse("Tipo de mensaje no soportado", status_code=200)
    except Exception as e:
        log_message(f'Error al hacer uso de función <ProcessMessage>: {e}.', 'ERROR')
        logging.error(f"⚠️ Error procesando POST: {e}")
        return func.HttpResponse("Error", status_code=400)

@app.function_name(name="health_check")
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET", "POST"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint simple para probar disponibilidad desde Postman.
    - GET → responde con OK + tiempo
    - POST → devuelve el JSON recibido
    """
    try:
        if req.method == "GET":
            return func.HttpResponse(
                json.dumps({"status": "OK", "message": "Servicio activo"}),
                status_code=200,
                mimetype="application/json"
            )

        if req.method == "POST":
            body_raw = req.get_body().decode("utf-8")
            try:
                body = json.loads(body_raw)
            except:
                body = body_raw  # por si mandas texto plano

            return func.HttpResponse(
                json.dumps({
                    "status": "OK",
                    "received": body
                }),
                status_code=200,
                mimetype="application/json"
            )

    except Exception as e:
        logging.error(f"Error en /health: {e}")
        return func.HttpResponse(
            json.dumps({"status": "ERROR", "detail": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
