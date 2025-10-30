# utils.py
# Last modified: 2025-09-30 by Andrés Bermúdez

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
        query: str = """
        INSERT INTO logs (ambiente, tipo, mensaje, fecha, idusuario, "archivoPy", function, "lineNumber")
        VALUES (%s, %s, %s, (NOW() AT TIME ZONE 'America/Bogota'), %s, %s, %s, %s)
        """
        params: tuple = (ambiente, tipo, mensaje, idusuario, archivoPy, function_name, line_number)
        execute_query(query, params)
    except Exception as e:
        logging.error(f'Error al hacer uso de función <RegisterLog>: {e}.')

def log_message(message: str, tipo: str) -> None:
    try:
        """Registra un mensaje en el log con nivel INFO."""
        caller_frame = inspect.stack()[1]
        filename = os.path.basename(caller_frame.filename)
        function_name = caller_frame.function
        line_no = caller_frame.lineno
        tb_str = traceback.format_exc()
        if tb_str and "NoneType: None" not in tb_str:
            message += f"\nTRACEBACK:\n{tb_str.strip()}"
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

def get_client_database(numero_celular: str, id_restaurante: str) -> bool:
    try:
        """Verifica si un cliente existe en la base de datos por su número de celular."""
        log_message('Iniciando función <get_client_database>.', 'INFO')
        logging.info('Iniciando función <get_client_database>.')
        resultado = execute_query(
            "SELECT 1 FROM clientes_whatsapp WHERE telefono = %s AND id_restaurante = %s LIMIT 1;",
            (numero_celular, id_restaurante)
        )
        logging.info(f"Resultado de la consulta: {resultado}")
        log_message('Finalizando función <get_client_database>.', 'INFO')
        return len(resultado) > 0
    except Exception as e:
        log_message(f'Error al hacer uso de función <get_client_database>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <get_client_database>: {e}.')
        return False

def handle_create_client(sender, datos, id_restaurante) -> str:
    try:
        """Crea un nuevo cliente en la base de datos."""
        log_message('Iniciando función <handleCreateClient>.', 'INFO')
        logging.info('Iniciando función <handleCreateClient>.')
        nombre = datos.get("nombre", "Desconocido")
        logging.info(f'Nombre del cliente: {nombre}')
        logging.info(f'Teléfono (sender): {sender}')
        execute_query("""
            INSERT INTO clientes_whatsapp (nombre, telefono, id_restaurante)
            VALUES (%s, %s, %s);
        """, (nombre, sender, id_restaurante))
        logging.info('Cliente creado exitosamente.')
        log_message('Finalizando función <handleCreateClient>.', 'INFO')
        return nombre.split()[0]  # Retorna el primer nombre
    except Exception as e:
        log_message(f'Error al hacer uso de función <handleCreateClient>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <handleCreateClient>: {e}.')
        raise e

def save_message_to_db(sender: str, message: str, classification: str, tipo_clasificacion: str, entidades: str, tipo_mensaje: str, id_restaurante: str) -> None:
    try:
        """Guarda el mensaje recibido y su clasificación en la base de datos."""
        log_message('Iniciando función <SaveMessageToDB>.', 'INFO')
        logging.info('Iniciando función <SaveMessageToDB>.')
        execute_query("""
            INSERT INTO conversaciones_whatsapp (telefono, mensaje_usuario, clasificacion, tipo_clasificacion, entidades, fecha, tipo_mensaje, id_restaurante)
            VALUES (%s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'America/Bogota'), %s, %s);
        """, (sender, message, classification, tipo_clasificacion, entidades, tipo_mensaje, id_restaurante))
        logging.info('Mensaje guardado exitosamente.')
        log_message('Finalizando función <SaveMessageToDB>.', 'INFO')
    except Exception as e:
        log_message(f'Error al hacer uso de función <SaveMessageToDB>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <SaveMessageToDB>: {e}.')

def get_client_name_database(sender: str, id_restaurante: str) -> str:
    try:
        """Obtiene el nombre del cliente en la base de datos"""
        logging.info(f'Buscando cliente con teléfono: {sender}')
        log_message(f"Busca nombre de cliente con {sender}", "INFO")
        resultado = execute_query(
            "SELECT nombre FROM clientes_whatsapp WHERE telefono = %s AND id_restaurante = %s LIMIT 1;",
            (sender,id_restaurante),
            fetchone=True
        )
        if resultado:
            nombre = resultado[0].split()[0]
        else:
            logging.info('No se encontró ningún cliente con ese número.', "INFO")
            log_message(f"No se encontró cliente con {sender}", "INFO")
            return None
        logging.info(f"Nombre del cliente encontrado: {nombre}")
        log_message(f"Nombre de cliente encontrado: {nombre}", "INFO")
        return nombre
    except Exception as e:
        logging.error(f'Error en get_client_name_database: {e}')
        log_message(f"Error al obtener nombre de cliente en la bbdd {e}", "ERROR")
        return None

def _to_float(v):
    try:
        return float(v)
    except Exception:
        raise TypeError(f"Valor no numérico en coordenada: {v!r}")

def point_on_segment(x, y, xi, yi, xj, yj, eps=1e-9):
    # comprobar si (x,y) está en el segmento (xi,yi)-(xj,yj)
    # usando la distancia perpendicular y la caja delimitadora
    # primero, colinealidad por área (cross product)
    cross = (y - yi) * (xj - xi) - (x - xi) * (yj - yi)
    if abs(cross) > eps:
        return False
    # luego comprobar si x está entre xi,xj y y entre yi,yj (con tolerancia)
    if min(xi, xj) - eps <= x <= max(xi, xj) + eps and min(yi, yj) - eps <= y <= max(yi, yj) + eps:
        return True
    return False

def point_in_polygon(lat, lng, poly):
    """
    Robust ray-casting algorithm.
    - lat, lng: punto a probar
    - poly: lista de puntos {'lat':..., 'lng':...} OR puede ser una lista anidada [[{...},...]]
    Devuelve True si el punto está dentro o sobre el borde.
    """
    if not isinstance(poly, (list, tuple)):
        raise TypeError("poly debe ser una lista o tupla de puntos con 'lat' y 'lng'")

    # Manejar caso donde valor es [ [ {lat,lng}, ... ] ] (polígonos anidados)
    if len(poly) == 0:
        return False
    if isinstance(poly[0], (list, tuple)):
        # tomar el primer anidado - si quieres soportar multi-polígono, adapta aquí
        poly = poly[0]
        if not poly:
            return False

    # construir listas de coordenadas fiables
    pts = []
    for idx, p in enumerate(poly):
        if not isinstance(p, dict):
            raise TypeError(f"Elemento del polígono no es dict en índice {idx}: {p!r}")
        # soportar claves 'lng' o 'lon'
        if 'lat' not in p or ('lng' not in p and 'lon' not in p):
            raise KeyError(f"Punto del polígono debe tener 'lat' y 'lng'/'lon'. Recibido: {p}")
        lat_i = _to_float(p.get('lat'))
        lng_i = _to_float(p.get('lng') if 'lng' in p else p.get('lon'))
        pts.append((lng_i, lat_i))  # trabajamos con (x=lng, y=lat)

    n = len(pts)
    if n < 3:
        return False  # no es polígono válido

    x = _to_float(lng)
    y = _to_float(lat)

    # Caja rápida (bounding box)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if x < min(xs) or x > max(xs) or y < min(ys) or y > max(ys):
        return False

    inside = False
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[(i - 1) % n]

        # si está sobre el segmento -> True
        try:
            if point_on_segment(x, y, xi, yi, xj, yj):
                return True
        except Exception:
            # no queremos que esto rompa todo; seguir con el algoritmo
            logging.debug(f"point_on_segment fallo con puntos {(xi, yi)} {(xj, yj)} y punto {(x, y)}")

        # ignora horizontales exactas evitando división por cero
        if ((yi > y) != (yj > y)):
            # calcular intersección en X de la arista con la horizontal y
            x_intersect = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_intersect:
                inside = not inside

    return inside