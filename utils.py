# utils.py
# Last modified: 2025-09-26 by Andrés Bermúdez

import logging
import os
from heyoo import WhatsApp
import json
import re
import ast
from typing import Any
from utils_database import execute_query
import inspect
import traceback

def register_log(mensaje: str, tipo: str, ambiente: str = "Whatsapp", idusuario: int = 1, archivoPy: str = "", function_name: str = "",line_number: int = 0) -> None:
    try:
        """Registra un log en la base de datos."""
        logging.info('Iniciando función <RegisterLog>.')
        query: str = """
        INSERT INTO logs (ambiente, tipo, mensaje, fecha, idusuario, "archivoPy", function, "lineNumber")
        VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s)
        """
        params: tuple = (ambiente, tipo, mensaje, idusuario, archivoPy, function_name, line_number)
        execute_query(query, params)
        logging.info('Log registrado correctamente.')
    except Exception as e:
        logging.error(f'Error al hacer uso de función <RegisterLog>: {e}.')

def log_message(message: str, tipo: str) -> None:
    try:
        """Registra un mensaje en el log con nivel INFO."""
        logging.info(message)
        caller_frame = inspect.stack()[1]
        filename = os.path.basename(caller_frame.filename)
        function_name = caller_frame.function
        line_no = caller_frame.lineno
        tb_str = traceback.format_exc()
        if tb_str and "NoneType: None" not in tb_str:
            message += f"\nTRACEBACK:\n{tb_str.strip()}"
        logging.info(f"Log details - File: {filename}, Function: {function_name}, Line: {line_no}")
        register_log(message, tipo, ambiente="WhatsApp", idusuario=1, archivoPy=filename, function_name=function_name, line_number=line_no)
    except Exception as e:
        logging.error(f"Error logging message: {e}")

def api_whatsapp() -> str:
    try:
        """Obtiene el token de la API de WhatsApp desde variables de entorno."""
        log_message('Iniciando función <ApiWhatsApp>.', 'INFO')
        logging.info('Obteniendo token de WhatsApp')
        token: str = os.getenv("WABA_TOKEN", "")
        if not token:
            raise ValueError("No se encontró el token WABA_TOKEN en las variables de entorno.")
        logging.info('Token de WhatsApp obtenido')
        log_message('Finalizando función <ApiWhatsApp>.', 'INFO')
        return token
    except Exception as e:
        log_message(f'Error al hacer uso de función <ApiWhatsApp>: {e}.', 'ERROR')
        logging.error(f"Error al obtener el token de WhatsApp: {e}")
        raise

def send_text_response(to: str, message: str) -> str:
    try:
        """Envía un mensaje de texto por WhatsApp Business API."""
        log_message('Iniciando función <SendTextResponse>.', 'INFO')
        logging.info('Enviando respuesta a WhatsApp')
        token: str = api_whatsapp()
        phone_number_id: str = '629019633625906'
        whatsapp: WhatsApp = WhatsApp(token, phone_number_id)
        whatsapp.send_message(message, to)
        logging.info('Respuesta enviada.')
        log_message('Finalizando función <SendTextResponse>.', 'INFO')
        return ("OK")
    except Exception as e:
        log_message(f'Error al hacer uso de función <SendTextResponse>: {e}.', 'ERROR')
        logging.error(f"Error al enviar respuesta a WhatsApp: {e}")
        return (f"Error {e}")

def limpiar_respuesta_json(raw: str) -> str:
    """
    Convierte la respuesta cruda del clasificador en un JSON válido.
    - Soporta respuestas tipo tupla de Python.
    - Limpia bloque triple ```json.
    - Repara estructuras comunes rotas.
    """
    log_message('Iniciando función <LimpiarRespuestaJson>.', 'INFO')
    text: str = raw.strip()
    # Caso: respuesta como tupla Python
    if text.startswith("(") and text.endswith(")"):
        try:
            intent: str
            type_: str
            entities: dict[str, Any]
            intent, type_, entities = ast.literal_eval(text)
            if not isinstance(entities, dict):
                entities = {}
            obj: dict[str, Any] = {"intent": intent, "type": type_, "entities": entities}
            return json.dumps(obj)
        except Exception:
            pass
    # Caso: respuesta con bloque ```json
    s: str = re.sub(r"^```json\s*", "", text)
    s = re.sub(r"\s*```$", "", s)
    # Extraer desde la primera llave
    idx: int = s.find("{")
    if idx != -1:
        s = s[idx:]
    # Reparaciones comunes
    s = re.sub(r',\s*([\]}])', r"\1", s)
    s += "]" * (s.count("[") - s.count("]"))
    s += "}" * (s.count("{") - s.count("}"))
    logging.info(f"JSON limpiado: {s}")
    try:
        json.loads(s)
    except json.JSONDecodeError as e:
        log_message(f"JSON inválido tras limpieza: {e}", 'ERROR')
        logging.error(f"JSON inválido tras limpieza: {e}")
        raise ValueError(f"JSON inválido tras limpieza: {e}")
    log_message('Finalizando función <LimpiarRespuestaJson>.', 'INFO')
    return s

def validate_duplicated_message(message_id: str) -> bool:
    try:
        """Valida si un mensaje de WhatsApp ya fue procesado usando su ID único."""
        log_message("Iniciando función <ValidarMensajeDuplicado>.", 'INFO')
        logging.info('Iniciando función <ValidarMensajeDuplicado>.')
        resultTemp = execute_query("""Select * from id_whatsapp_messages where id_messages = %s;""", (message_id,))
        if len(resultTemp)>0:
            logging.info('Mensaje ya registrado.')
            log_message("Finalizando función <ValidarMensajeDuplicado>.", 'INFO')
            return True
        else:
            logging.info('Mensaje no registrado.')
            execute_query("""Insert into id_whatsapp_messages(id_messages) values (%s);""", (message_id,))
            log_message("Finalizando función <ValidarMensajeDuplicado>.", 'INFO')
            return False
    except Exception as e:
        log_message(f'Error al hacer uso de función <ValidarMensajeDuplicado>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <ValidarMensajeDuplicado>: {e}.')

def get_client_database(numero_celular: str) -> bool:
    try:
        """Verifica si un cliente existe en la base de datos por su número de celular."""
        log_message('Iniciando función <get_client_database>.', 'INFO')
        logging.info('Iniciando función <get_client_database>.')
        resultado = execute_query(
            "SELECT 1 FROM clientes_whatsapp WHERE telefono = %s LIMIT 1;",
            (numero_celular,)
        )
        logging.info(f"Resultado de la consulta: {resultado}")
        log_message('Finalizando función <get_client_database>.', 'INFO')
        return len(resultado) > 0
    except Exception as e:
        log_message(f'Error al hacer uso de función <get_client_database>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <get_client_database>: {e}.')
        return False

def handle_create_client(sender, datos) -> str:
    try:
        """Crea un nuevo cliente en la base de datos."""
        log_message('Iniciando función <handleCreateClient>.', 'INFO')
        logging.info('Iniciando función <handleCreateClient>.')
        nombre = datos.get("nombre", "Desconocido")
        logging.info(f'Nombre del cliente: {nombre}')
        logging.info(f'Teléfono (sender): {sender}')
        execute_query("""
            INSERT INTO clientes_whatsapp (nombre, telefono)
            VALUES (%s, %s);
        """, (nombre, sender))
        logging.info('Cliente creado exitosamente.')
        log_message('Finalizando función <handleCreateClient>.', 'INFO')
        return nombre.split()[0]  # Retorna el primer nombre
    except Exception as e:
        log_message(f'Error al hacer uso de función <handleCreateClient>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <handleCreateClient>: {e}.')
        raise e

def save_message_to_db(sender: str, message: str, classification: str, tipo_clasificacion: str, entidades: str, tipo_mensaje: str) -> None:
    try:
        """Guarda el mensaje recibido y su clasificación en la base de datos."""
        log_message('Iniciando función <SaveMessageToDB>.', 'INFO')
        logging.info('Iniciando función <SaveMessageToDB>.')
        execute_query("""
            INSERT INTO conversaciones_whatsapp (telefono, mensaje_usuario, clasificacion, tipo_clasificacion, entidades, fecha, tipo_mensaje)
            VALUES (%s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'America/Bogota'), %s);
        """, (sender, message, classification, tipo_clasificacion, entidades, tipo_mensaje))
        logging.info('Mensaje guardado exitosamente.')
        log_message('Finalizando función <SaveMessageToDB>.', 'INFO')
    except Exception as e:
        log_message(f'Error al hacer uso de función <SaveMessageToDB>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <SaveMessageToDB>: {e}.')