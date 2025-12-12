# function_app.py
# Last modified: 2025-09-30 by Andrés Bermúdez
#CAMBIOS 10 DICIEMBRE 2:00 AM
import azure.functions as func
from datetime import datetime
import logging
import os
import json
from utils import obtener_datos_cliente_por_telefono, obtener_intencion_futura_observaciones, send_text_response,  log_message, get_client_database, handle_create_client, save_message_to_db, get_client_name_database, guardar_clasificacion_intencion, obtener_ultima_intencion_no_resuelta, marcar_intencion_como_resuelta,verify_hour_atettion, guardar_intencion_futura,validate_duplicated_message
from utils_chatgpt import get_classifier, get_openai_key,extraer_info_personal,get_direction,Extraer_Nombre
from utils_subflujos import manejar_dialogo
from utils_google import orquestador_ubicacion_exacta,calcular_distancia_entre_sede_y_cliente,geocode_and_assign
from utils_registration import  update_datos_personales, update_dir_primera_vez, update_tratamiento_datos, validate_personal_data, validate_data_treatment, validate_direction_first_time, save_personal_data_partial, check_and_mark_datos_personales
from utils_database import execute_query
from typing import Any, Dict, Optional, List
import requests
from openai import OpenAI
import io
import re

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
        log_message(f"Cuerpo recibido: {json.dumps(req_body, indent=2)}", "INFO")
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
        log_message(f"Mensaje extraído: {json.dumps(message, indent=2)}", "INFO")
        tipo_general = message["type"]
        logging.info(f"Tipo de mensaje recibido: {tipo_general}")
        message_id = message["id"]
        #Validación mensaje duplicado
        #if validate_duplicated_message(message_id):
        #    logging.info(f"Mensaje duplicado: {message_id}")
        #    return func.HttpResponse("Mensaje duplicado", status_code=200)
        sender: str = message["from"]
        nombre_cliente: str
        respuesta_bot : str
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
            send_text_response(sender,"¡Hola! necesitamos tu aprobación para el tratamiento de tus datos personales según la Ley 1581 de 2012.Por favor, responde NO para rechazar, si continuas la conversación entendemos que aceptas el tratamiento de tus datos. ")
            send_text_response(sender, "Entoces para continuar ,Por favor envia los siguientes datos:\nNombre, Tipo de documento, Número de documento, Correo electrónico.\nEjemplo:Juan Perez, C.C, 123456789, juan14@gmail.com")
            log_message("Empieza a clasificar cliente nuevo", "INFO")
            return func.HttpResponse("Cliente no registrado, esperando datos", status_code=200)
        ####################################
        ########### CLIENTE EXISTENTE ##########  
        ####################################
        else:
            log_message("Cliente existente detectado", "INFO")
            nombre_cliente = get_client_name_database(sender, ID_RESTAURANTE)
            if tipo_general == "text":
                text: str = message.get("text", {}).get("body", "")
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
                    logging.info(f"Transcripción recibida: {text}")
                    log_message(f"Mensaje transcrito {text}", "INFO")
            #############
            #validar ubicación primera vez
            #############
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
                save_message_to_db(sender, "[imagen recibida]", "validacion_pago", "image", "{}", tipo_general, ID_RESTAURANTE)
                guardar_clasificacion_intencion(sender, "validacion_pago", "sin_resolver", "usuario", "[imagen recibida]", "", "image", "{}")
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
                send_text_response(sender, "Por el momento solo puedo procesar mensajes de texto.")
                return func.HttpResponse("Tipo de mensaje no soportado", status_code=200)
                # Clasificación con modelo OpenAI
            log_message(f"Empieza a clasificar con text {text}", "INFO")
            pattern = re.compile(r'\bno\b', re.IGNORECASE)
            def contiene_no(texto: str) -> bool:
                return bool(pattern.search(texto))
            if validate_data_treatment(sender, ID_RESTAURANTE) is False:
                if contiene_no(text):
                    log_message("Usuario negó el tratamiento de datos", "INFO")
                    update_tratamiento_datos(sender, ID_RESTAURANTE, False)
                    update_datos_personales(sender, ID_RESTAURANTE,  False)
                    update_dir_primera_vez(sender, ID_RESTAURANTE, True)
                    update_tratamiento_datos(sender, ID_RESTAURANTE, False)
                    save_personal_data_partial(sender, ID_RESTAURANTE, None, None, None)
                    send_text_response(sender, f"Entendido {nombre_cliente}, no procesaremos tus datos personales. Si cambias de opinión, no dudes en contactarnos nuevamente.")
                    logging.info(f"Usuario {sender} negó el tratamiento de datos.")
                    log_message(f"Usuario {sender} negó el tratamiento de datos.", "INFO")
                    return func.HttpResponse("EVENT_RECEIVED", status_code=200)
                else:
                    log_message("Usuario aceptó el tratamiento de datos", "INFO")
                    update_tratamiento_datos(sender, ID_RESTAURANTE, True)
                    logging.info(f"Usuario {sender} aceptó el tratamiento de datos.")
                    log_message(f"Usuario {sender} aceptó el tratamiento de datos.", "INFO")
                    #######################################
                    #validación datos personales
                    #######################################
                    if validate_personal_data(sender, ID_RESTAURANTE) is False:
                        datos = extraer_info_personal(text)
                        # datos es dict con keys: tipo_documento, numero_documento, email
                        tipo_doc = datos.get("tipo_documento")
                        n_doc = datos.get("numero_documento")
                        email = datos.get("email")
                        nombre = datos.get("nombre")
                        # Guardar solo los campos que traigan información útil
                        try:
                            save_personal_data_partial(sender, ID_RESTAURANTE, tipo_doc, n_doc, email,nombre)
                        except Exception as e:
                            logging.error(f"Error guardando datos parciales: {e}")
                            log_message(f"Error guardando datos parciales: {e}", "ERROR")
                            send_text_response(sender, f"{nombre_cliente}, ocurrió un error al guardar tus datos. Intenta de nuevo.")
                            return func.HttpResponse("EVENT_RECEIVED", status_code=200)

                        # Verificar si ahora la fila tiene los 4 campos completos
                        missing = check_and_mark_datos_personales(sender, ID_RESTAURANTE)
                        if not missing:
                            logging.info(f"Datos personales de {sender} completos y marcados.")
                            log_message(f"Datos personales de {sender} completos y marcados.", "INFO")
                            send_text_response(sender, "Gracias. Ahora por ultimo ¿puedes proporcionarme tu dirección para validar que estes en nuestra area de cobertura?")
                            return func.HttpResponse("EVENT_RECEIVED", status_code=200)
                        else:
                            # mapear nombres amigables
                            friendly = {"Tipo_Doc": "tipo de documento", "N_Doc": "número de documento", "email": "correo electrónico", "nombre": "nombre completo"}
                            faltantes = ", ".join(friendly.get(m, m) for m in missing)
                            send_text_response(sender, f"aún faltan los siguientes datos: {faltantes}. Por favor envíalos para continuar.")
                            return func.HttpResponse("EVENT_RECEIVED", status_code=200)     
            #######################################
            #validación datos personales
            #######################################
            if validate_personal_data(sender, ID_RESTAURANTE) is False:
                datos = extraer_info_personal(text)
                # datos es dict con keys: tipo_documento, numero_documento, email
                tipo_doc = datos.get("tipo_documento")
                n_doc = datos.get("numero_documento")
                email = datos.get("email")
                nombre = datos.get("nombre")
                # Guardar solo los campos que traigan información útil
                try:
                    save_personal_data_partial(sender, ID_RESTAURANTE, tipo_doc, n_doc, email,nombre)
                except Exception as e:
                    logging.error(f"Error guardando datos parciales: {e}")
                    log_message(f"Error guardando datos parciales: {e}", "ERROR")
                    send_text_response(sender, ", ocurrió un error al guardar tus datos. Intenta de nuevo.")
                    return func.HttpResponse("EVENT_RECEIVED", status_code=200)

                # Verificar si ahora la fila tiene los 4 campos completos
                missing = check_and_mark_datos_personales(sender, ID_RESTAURANTE)
                if not missing:
                    logging.info(f"Datos personales de {sender} completos y marcados.")
                    log_message(f"Datos personales de {sender} completos y marcados.", "INFO")
                    send_text_response(sender, "Gracias. Ahora por ultimo ¿puedes proporcionarme tu dirección para validar que estes en nuestra area de cobertura?")
                    return func.HttpResponse("EVENT_RECEIVED", status_code=200)
                else:
                    # mapear nombres amigables
                    friendly = {"Tipo_Doc": "tipo de documento", "N_Doc": "número de documento", "email": "correo electrónico", "nombre": "nombre completo"}
                    faltantes = ", ".join(friendly.get(m, m) for m in missing)
                    send_text_response(sender, "aún faltan los siguientes datos: {faltantes}. Por favor envíalos para continuar.")
                    return func.HttpResponse("EVENT_RECEIVED", status_code=200)            
            #######################################
            #validación dirección primera vez
            #######################################
            if validate_direction_first_time(sender, ID_RESTAURANTE) is False:
                classification: str
                type_text: str
                entities_text: str
                classification, type_text, entities_text = get_classifier(text, sender)
                # revision de si es direccion
                if classification == "direccion" or classification =="mas_datos_direccion":
                    send_text_response(sender, "Gracias, voy a validar que estes en nuestra cobertura dame un par de minutos.")
                    direccion=get_direction(text)
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
                        return func.HttpResponse("EVENT_RECEIVED", status_code=200)
                    logging.info(f"Usuario {sender} proporcionó una dirección.")
                    log_message(f"Usuario {sender} proporcionó una dirección.", "INFO")

                    return func.HttpResponse("EVENT_RECEIVED", status_code=200)
                else:
                    send_text_response(sender, f"{nombre_cliente}, para continuar con tu pedido, por favor envíanos tu ubicación actual o tu dirección.")
                    logging.info(f"Usuario {sender} no proporcionó una dirección válida.")
                    log_message(f"Usuario {sender} no proporcionó una dirección válida.", "INFO")
                return func.HttpResponse("EVENT_RECEIVED", status_code=200)

            if text:
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

