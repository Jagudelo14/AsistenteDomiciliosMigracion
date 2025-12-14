# utils.py
# Last modified: 2025-09-30 by Andrés Bermúdez

from decimal import Decimal
import logging
import os
import unicodedata
from heyoo import WhatsApp
import re
import ast
from utils_database import execute_query, execute_query_columns
import inspect
import traceback
from typing import Dict, Any, List
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import json
import requests
import difflib
from utils_contexto import get_sender,actualizar_conversacion

REPLACE_PHRASES = [
    "cambia todo", "borra lo que había", "solo quiero esto", "quita lo anterior",
    "nuevo pedido", "empezar de cero", "anula pedido", "cancelar pedido", "resetear pedido",
    "empezar from cero", "empezar de 0"
]

def register_log(mensaje: str, tipo: str, ambiente: str = "Whatsapp", idusuario: int = 1, archivoPy: str = "", function_name: str = "",line_number: int = 0) -> None:
    try:
        """Registra un log en la base de datos."""
        query: str = """
        INSERT INTO logs (ambiente, tipo, mensaje, fecha, idusuario, "archivoPy", function, "lineNumber", telefono)
        VALUES (%s, %s, %s, (NOW() AT TIME ZONE 'America/Bogota'), %s, %s, %s, %s, %s)
        """
        telefono = get_sender()
        params: tuple = (ambiente, tipo, mensaje, idusuario, archivoPy, function_name, line_number, telefono)
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
        conversacion = actualizar_conversacion(message,to,"asistente")
        log_message(f"Conversación actualizada: {conversacion}", "INFO")
        """Envía un mensaje de texto por WhatsApp Business API."""
        log_message('Iniciando función <SendTextResponse>.', 'INFO')
        logging.info('Enviando respuesta a WhatsApp')
        token: str = api_whatsapp()
        PHONE_ID: str = os.environ["PHONE_NUMBER_ID"]
        whatsapp: WhatsApp = WhatsApp(token, PHONE_ID)
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
        """Verifica si un cliente existe en la base de datos por su número de celular y no es temporal."""
        log_message('Iniciando función <get_client_database>.', 'INFO')
        logging.info('Iniciando función <get_client_database>.')
        query = """
            SELECT 1
            FROM clientes_whatsapp
            WHERE telefono = %s
              AND id_restaurante = %s
            LIMIT 1;
        """
        log_message(f'Consulta SQL: {query} con parámetros ({numero_celular}, {id_restaurante})', 'INFO')
        resultado = execute_query(query, (numero_celular, id_restaurante))
        logging.info(f"Resultado de la consulta: {resultado}")
        log_message(f"Resultado de la consulta: {resultado}", "INFO")
        log_message('Finalizando función <get_client_database>.', 'INFO')

        # Devolver booleano seguro (maneja None y colecciones vacías)
        return bool(resultado) and len(resultado) > 0

    except Exception as e:
        log_message(f'Error al hacer uso de función <get_client_database>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <get_client_database>: {e}.')
        return False

def handle_create_client(sender: str, datos: str, id_restaurante: str, es_temporal: bool) -> str:
    try:
        log_message('Iniciando función <handleCreateClient>.', 'INFO')
        logging.info('Iniciando función <handleCreateClient>.')
        log_message(f'Datos recibidos para crear/actualizar cliente: {datos}', 'INFO')
        nombre = "Desconocido"
        id_sede = 21
        if datos is not None:
            nombre = datos
        logging.info(f'Nombre del cliente: {nombre}')
        logging.info(f'Teléfono (sender): {sender}')
        log_message(f'Nombre del cliente: {nombre}', 'INFO')
        log_message(f'Teléfono (sender): {sender}', 'INFO')
        execute_query("""
            INSERT INTO clientes_whatsapp (nombre, telefono, id_restaurante, es_temporal,id_sede)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (telefono)
            DO UPDATE SET 
                nombre = EXCLUDED.nombre,
                es_temporal = EXCLUDED.es_temporal,
                id_restaurante = EXCLUDED.id_restaurante,
                id_sede = EXCLUDED.id_sede;
        """, (nombre, sender, id_restaurante, es_temporal,id_sede))

        logging.info('Cliente creado o actualizado exitosamente.')
        log_message('Finalizando función <handleCreateClient>.', 'INFO')
        log_message(f'Cliente creado o actualizado exitosamente.{nombre}', 'INFO')
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
            INSERT INTO conversaciones_whatsapp (telefono, mensaje_usuario, clasificacion, tipo_clasificacion, entidades, fecha, tipo_mensaje, idcliente)
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

def guardar_clasificacion_intencion(
    telefono: str,
    clasificacion: str,
    estado: str,
    emisor: str,
    pregunta: str,
    respuesta: str,
    tipo_mensaje: str,
    entitites: str
) -> int | None:
    """
    Guarda la clasificación de intención en la base de datos y devuelve el ID insertado.
    """
    try:
        if isinstance(entitites, dict):
            entitites = json.dumps(entitites)
        query = """
            INSERT INTO public.clasificacion_intenciones
                (telefono, clasificacion, estado, emisor, pregunta, respuesta, tipo_mensaje, entitites)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        values = (telefono, clasificacion, estado, emisor, pregunta, respuesta, tipo_mensaje, entitites)
        result = execute_query(query, values, fetchone=True)
        inserted_id = result[0] if result else None
        if inserted_id:
            logging.info(f"✅ Clasificación guardada con éxito. ID: {inserted_id}")
            log_message(f"Clasificación de intención guardada exitosamente. ID: {inserted_id}", "INFO")
            return inserted_id
        else:
            raise Exception("No se devolvió ningún ID después del INSERT.")
    except Exception as e:
        logging.error(f"Error al guardar la clasificación: {e}")
        log_message(f"Error al guardar la clasificación de intención: {e}", "ERROR")
        return None

def obtener_ultima_intencion_no_resuelta(telefono: str) -> dict[str, Any] | None:
    """
    Retorna la última intención con estado 'no_resuelto' asociada al teléfono dado.
    Devuelve un diccionario con los campos principales o None si no hay resultados.
    """
    try:
        query = """
            SELECT id, telefono, clasificacion, estado, emisor, pregunta, respuesta, tipo_mensaje, entitites
            FROM public.clasificacion_intenciones
            WHERE telefono = %s AND estado = 'sin_resolver'
            ORDER BY id DESC
            LIMIT 1;
        """
        result = execute_query(query, (telefono,), fetchone=True)
        if result:
            columnas = ["id", "telefono", "clasificacion", "estado", "emisor", "pregunta", "respuesta", "tipo_mensaje", "entitites"]
            data = dict(zip(columnas, result))
            logging.info(f"Última intención no resuelta encontrada para {telefono}: {data['id']}")
            log_message(f"Última intención no resuelta encontrada para {telefono}: {data['id']}", "INFO")
            return data
        else:
            logging.info(f"No hay intenciones no resueltas para {telefono}.")
            log_message(f"No hay intenciones no resueltas para {telefono}.", "INFO")
            return None
    except Exception as e:
        logging.error(f"Error al obtener la última intención no resuelta: {e}")
        return None

def marcar_intencion_como_resuelta(id_intencion: int) -> bool:
    """
    Actualiza el estado de una intención a 'resuelto' según su ID.
    Retorna True si la actualización fue exitosa, False si falló.
    """
    try:
        # Validar entrada
        if id_intencion is None or str(id_intencion).strip() == "":
            log_message(f"marcar_intencion_como_resuelta: id_intencion inválido: {id_intencion!r}", "ERROR")
            return False
        try:
            id_int = int(id_intencion)
        except (ValueError, TypeError):
            log_message(f"marcar_intencion_como_resuelta: no se pudo convertir id a int: {id_intencion!r}", "ERROR")
            return False

        query = """
            UPDATE public.clasificacion_intenciones
            SET estado = 'resuelta'
            WHERE id = %s;
        """
        execute_query(query, (id_int,))
        log_message(f"Intención {id_int} marcada como resuelta.", "INFO")
        return True
    except Exception as e:
        log_message(f"Error al actualizar la intención {id_intencion} a 'resuelta': {e}", "ERROR")
        return False

def guardar_intencion_futura(telefono: str, intencion_futura: str, observaciones: str = "", mensaje_chatbot: str = "", mensaje_usuario: str = "", datos_promocion: dict = None) -> None:
    """
    Inserta o actualiza la intención futura de un cliente según su número de teléfono.
    Si no existe el registro, lo crea. Si ya existe, actualiza la intención.
    """
    try:
        log_message('Iniciando función <GuardarIntencionFutura>.', 'INFO')
        query = """
            INSERT INTO clasificacion_intenciones_futuras 
            (telefono, intencion_futura, fecha_actualizacion, observaciones, mensaje_chatbot, mensaje_usuario, datos_promocion)
            VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s::jsonb)
            ON CONFLICT (telefono)
            DO UPDATE SET
                intencion_futura = EXCLUDED.intencion_futura,
                fecha_actualizacion = CURRENT_TIMESTAMP,
                observaciones = EXCLUDED.observaciones,
                mensaje_chatbot = EXCLUDED.mensaje_chatbot,
                mensaje_usuario = EXCLUDED.mensaje_usuario,
                datos_promocion = EXCLUDED.datos_promocion;
        """
        execute_query(
            query,
            (
                telefono,
                intencion_futura,
                observaciones,
                mensaje_chatbot,
                mensaje_usuario,
                json.dumps(datos_promocion, ensure_ascii=False)
            )
        )
        log_message(f"Intención futura guardada/actualizada para {telefono}: {intencion_futura}", "INFO")
    except Exception as e:
        log_message(f"Error al guardar la intención futura: {e}", "ERROR")

def obtener_intencion_futura(telefono: str) -> str:
    """
    Retorna el valor de intencion_futura para un teléfono específico
    desde la tabla public.clasificacion_intenciones_futuras.
    """
    try:
        query = """
            SELECT intencion_futura
            FROM public.clasificacion_intenciones_futuras
            WHERE telefono = %s
            ORDER BY telefono ASC
            LIMIT 1;
        """
        resultado = execute_query(query, (telefono,), fetchone=True)
        log_message(f"Intención futura obtenida para {telefono}: {resultado}", "INFO")
        if resultado:
            return resultado[0]
        else:
            return None
    except Exception as e:
        log_message(f"Error al consultar la base de datos: {e}")
        return None
    
def borrar_intencion_futura(telefono: str) -> bool:
    """
    Elimina el registro asociado a un teléfono específico
    en la tabla public.clasificacion_intenciones_futuras.

    Retorna True si se eliminó algún registro, False si no existía o hubo error.
    """
    try:
        query = """
            DELETE FROM public.clasificacion_intenciones_futuras
            WHERE telefono = %s;
        """
        filas_afectadas = execute_query(query, (telefono,))
        log_message(f"Registro eliminado para {telefono}, filas afectadas: {filas_afectadas}", "INFO")
        return bool(filas_afectadas)
    except Exception as e:
        log_message(f"Error al eliminar registro para {telefono}: {e}", "ERROR")
        return False

def obtener_menu() -> list[dict[str, Any]]:
    try:
        log_message("Iniciando función <ObtenerMenu>.", "INFO")
        query = """
                SELECT
                    iditem,
                    nombre, 
                    tipo_comida, 
                    descripcion, 
                    observaciones, 
                    precio
                FROM public.items
                WHERE estado = true
                ORDER BY tipo_comida, nombre;
                """
        items_data = execute_query(query)
        items = [
            {   
                "iditem": row[0],
                "nombre": row[1],
                "tipo_comida": row[2],
                "descripcion": row[3],
                "observaciones": row[4],
                "precio": float(row[5]) if row[5] is not None else 0.0
            }
            for row in items_data
            ]
        log_message("Menú obtenido exitosamente.", "INFO")
        return items
    except Exception as e:
        log_message(f"Error al obtener el menú: {e}", "ERROR")
        return []

def normalizar_entities_items(entities: dict) -> dict:
    try:
        log_message('Iniciando función <NormalizarEntitiesItems>.', 'INFO')
        items = entities.get("items", [])
        resultado = {}
        for item in items:
            producto = item.get("producto", "").strip().lower()
            modalidad = item.get("modalidad", "")
            especificaciones = tuple(sorted(item.get("especificaciones", [])))
            cantidad = item.get("cantidad", 1)
            key = (producto, especificaciones, modalidad)
            if key in resultado: # si ya existía, sumamos cantidad
                resultado[key]["cantidad"] += cantidad
            else:
                resultado[key] = {
                    "producto": producto,
                    "modalidad": modalidad,
                    "especificaciones": list(especificaciones),
                    "cantidad": cantidad }
        entities["items"] = list(resultado.values())
        log_message(f'Entities normalizadas: {entities}', 'INFO')
        log_message('Finalizando función <NormalizarEntitiesItems>.', 'INFO')
        return entities
    except Exception as e:
        log_message(f"Error en función <NormalizarEntitiesItems>: {e}", "ERROR")
        return entities

def guardar_pedido_completo(sender: str, pedido_dict: dict, es_temporal: bool = False) -> dict:
    try:
        """ Guarda un pedido completo en la BD y retorna: { "idpedido": X, "codigo_unico": "P-00015" } """
        log_message('Iniciando función <GuardarPedidoCompleto>.', 'INFO')
        # ------------------------------- # 1. Obtener id_whatsapp # -------------------------------
        q_idw = "SELECT * FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        log_message(f"[GuardarPedidoCompleto] Resultado consulta id_whatsapp: {res_idw}", "INFO")
        id_whatsapp = res_idw[0] if res_idw else None
        idsede = res_idw[11] if res_idw else 17
        direccion = res_idw[5] if res_idw else None
        logging.info(f"[GuardarPedidoCompleto] id_whatsapp para {sender}: {id_whatsapp}")
        # ------------------------------- # 2. Determinar si es persona nueva # -------------------------------
        q_prev = "SELECT COUNT(*) FROM pedidos WHERE id_whatsapp = %s"
        res_prev = execute_query(q_prev, (id_whatsapp,), fetchone=True)
        persona_nuevo = (res_prev[0] == 0)
        # ------------------------------- # 3. Obtener último código único # -------------------------------
        q_last_code = "SELECT codigo_unico FROM pedidos ORDER BY idpedido DESC LIMIT 1"
        res_last_code = execute_query(q_last_code, fetchone=True)
        if res_last_code: 
            last_code = res_last_code[0] # Ej: "P-00042"
            num = int(last_code.split("-")[1])
            new_num = num + 1
        else:
            new_num = 1
        codigo_unico = f"P-{new_num:05d}" 
        # ------------------------------- # 4. Preparar productos y total # ------------------------------- 
# ...existing code...
        productos = []
        for item in pedido_dict.get("items", []):
            matched = item.get("matched") or {}
            nombre = matched.get("name")

            # determinar cantidad: prioridad campos explícitos -> note -> fallback 1
            cantidad = item.get("cantidad") or item.get("quantity") or item.get("qty")
            if cantidad is None:
                note = str(item.get("note") or "")
                m = re.search(r'(?:cantidad|cant)\s*[:=]?\s*(\d+)', note, flags=re.I)
                if m:
                    try:
                        cantidad = int(m.group(1))
                    except Exception:
                        cantidad = 1
            try:
                cantidad = int(cantidad) if cantidad is not None else 1
            except Exception:
                cantidad = 1
            # if nombre:
            #     # añadir el nombre repetido según la cantidad
            #     for _ in range(max(1, cantidad)):
            #         productos.append(nombre)
            # else:
            #     log_message(f"[WARN] Item sin matched en <GuardarPedidoCompleto>: {item}", "WARN")
            #     for _ in range(max(1, cantidad)):
            #         productos.append("SIN_MATCH")
        #productos_str = " | ".join(productos)
        total_price = float(pedido_dict.get("total_price", 0))
        # ------------------------------- # 5. Hora y fecha Bogotá # -------------------------------
        now = datetime.now(ZoneInfo("America/Bogota"))
        fecha = now.strftime("%Y-%m-%d %H:%M:%S")
        hora = now.strftime("%H:%M")
        # ------------------------------- # 6. Campos fijos # ------------------------------- 
        idcliente = os.getenv("ID_RESTAURANTE", "5")
        idsede = idsede
        estado = "pendiente"
        metodo_pago = "efectivo"
        # ------------------------------- # 7. Query con RETURNING # -------------------------------
        query = """ INSERT INTO pedidos ( total_productos, fecha, hora, idcliente, idsede, estado, persona_nuevo, id_whatsapp, metodo_pago, codigo_unico, es_temporal,direccion ) VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING idpedido, codigo_unico """
        params = (total_price, fecha, hora, idcliente, idsede, estado, persona_nuevo, id_whatsapp, metodo_pago, codigo_unico, es_temporal, direccion )
        # ------------------------------- # 8. Ejecutar y retornar el id # -------------------------------
        logging.info(f"[GuardarPedidoCompleto] Ejecutando INSERT pedidos. params={params}")
        res = execute_query(query, params, fetchone=True)
        logging.info(f"[GuardarPedidoCompleto] Resultado INSERT (res) = {res}")
        # Verificación defensiva: si la consulta no devolvió fila, registrar y retornar None
        if not res:
            log_message('La inserción de pedido no devolvió resultados (res is None).', 'ERROR')
            logging.error('La inserción de pedido no devolvió resultados. Query o DB pueden haber fallado. params=%s', params)
            return None
        log_message(f'Pedido guardado con ID {res[0]} y código único {res[1]}', 'INFO')
        # Guardar detalle de los productos
        for item in pedido_dict.get("items", []):
            especificaciones_txt = normalizar_especificaciones(item)
            query = """ INSERT INTO detalle_pedido ( id_producto,id_pedido, cantidad, total, especificaciones) VALUES (%s, %s, %s, %s, %s)"""
            params = (item.get("matched").get("id"), res[0], item.get("cantidad"), (item.get("matched").get("price") * item.get("cantidad", 1)), especificaciones_txt )
            res_detalle = execute_query(query, params)
        log_message(f'Detalle de pedido guardado para pedido ID {res[0]}', 'INFO')  
        return {
            "idpedido": res[0],
            "codigo_unico": res[1]
        }
    except Exception as e:
        tb = traceback.format_exc()
        log_message(f'Error al hacer uso de función <GuardarPedidoCompleto>: {e}.\nTRACEBACK:\n{tb}', 'ERROR')
        logging.error(f'Error al hacer uso de función <GuardarPedidoCompleto>: {e}.\n{tb}')
        return {}
    
def normalizar_especificaciones(item):
    specs = []

    requested_specs = item.get("requested", {}).get("especificaciones")
    if isinstance(requested_specs, list):
        specs.extend(requested_specs)

    modifiers = item.get("modifiers_applied")
    if isinstance(modifiers, list):
        specs.extend(modifiers)

    if not specs:
        return None

    # Eliminar duplicados manteniendo el orden
    specs_unicos = list(dict.fromkeys(str(s).strip().lower() for s in specs))

    # Capitalizar o normalizar presentación
    specs_final = [s.capitalize() for s in specs_unicos]

    return " | ".join(specs_final)


def guardar_ordenes(idpedido: int, pedido_json: dict, sender: str) -> dict:
    """
    Guarda cada item del pedido en la tabla 'ordenes'.
    Estructura esperada de pedido_json:
    {
        "order_complete": true/false,
        "items": [
            {
                "requested": {
                    "producto": "string",
                    "modalidad": "",
                    "especificaciones": []
                },
                "matched": {
                    "name": "string",
                    "id": "",
                    "price": float
                },
                ...
            }
        ],
        "total_price": float
    }
    """
    try:
        log_message('Iniciando función <GuardarOrdenes>.', 'INFO')
        items = pedido_json.get("items", [])
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None
        if not items:
            raise ValueError("El JSON no contiene items para guardar en ordenes.")
        inserted_ids = []
        for item in items:
            matched = item.get("matched", {})
            requested = item.get("requested", {})
            nombre_producto = matched.get("name", requested.get("producto"))
            precio_producto = matched.get("price", 0)
            especificaciones_list = requested.get("especificaciones", [])
            especificaciones_texto = ", ".join(especificaciones_list) if especificaciones_list else ""
            query = """
                INSERT INTO ordenes (
                    desglose_productos,
                    desglose_precio,
                    id_whatsapp,
                    idpedidos,
                    especificaciones
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING idorden;
            """
            params = (
                nombre_producto,
                precio_producto,
                id_whatsapp,
                idpedido,
                especificaciones_texto
                )
            result = execute_query(query, params, fetchone=True)
            inserted_ids.append(result[0])
        log_message(f'Ordenes guardadas con IDs: {inserted_ids}', 'INFO')
        return {
            "status": "success",
            "mensaje": f"{len(inserted_ids)} registros insertados en ordenes.",
            "ordenes_ids": inserted_ids
        }
    except Exception as e:
        log_message(f'Error al hacer uso de función <GuardarOrdenes>: {e}.', 'ERROR')
        return {
            "status": "error",
            "mensaje": str(e)
        }

def obtener_intencion_futura_observaciones(telefono: str) -> str:
    """
    Retorna el valor de intencion_futura para un teléfono específico
    desde la tabla public.clasificacion_intenciones_futuras.
    """
    try:
        query = """
            SELECT observaciones
            FROM public.clasificacion_intenciones_futuras
            WHERE telefono = %s
            ORDER BY telefono ASC
            LIMIT 1;
        """
        resultado = execute_query(query, (telefono,), fetchone=True)
        log_message(f"Intención futura - observaciones obtenida para {telefono}: {resultado}", "INFO")
        if resultado:
            return resultado[0]
        else:
            return None
    except Exception as e:
        log_message(f"Error al consultar la base de datos: {e}")
        return None

def obtener_intencion_futura_mensaje_chatbot(telefono: str) -> str:
    """
    Retorna el valor de intencion_futura para un teléfono específico
    desde la tabla public.clasificacion_intenciones_futuras.
    """
    try:
        query = """
            SELECT mensaje_chatbot
            FROM public.clasificacion_intenciones_futuras
            WHERE telefono = %s
            ORDER BY telefono ASC
            LIMIT 1;
        """
        resultado = execute_query(query, (telefono,), fetchone=True)
        log_message(f"Intención futura - mensaje_chatbot obtenida para {telefono}: {resultado}", "INFO")
        if resultado:
            return resultado[0]
        else:
            return None
    except Exception as e:
        log_message(f"Error al consultar la base de datos: {e}")
        return None

def obtener_intencion_futura_mensaje_usuario(telefono: str) -> str:
    """
    Retorna el valor de intencion_futura para un teléfono específico
    desde la tabla public.clasificacion_intenciones_futuras.
    """
    try:
        query = """
            SELECT mensaje_usuario
            FROM public.clasificacion_intenciones_futuras
            WHERE telefono = %s
            ORDER BY telefono ASC
            LIMIT 1;
        """
        resultado = execute_query(query, (telefono,), fetchone=True)
        log_message(f"Intención futura - mensaje_usuario obtenida para {telefono}: {resultado}", "INFO")
        if resultado:
            return resultado[0]
        else:
            return None
    except Exception as e:
        log_message(f"Error al consultar la base de datos: {e}")
        return None

def _safe_parse_order(pedido_actual: Any) -> Dict:
    """Convierte pedido_actual a dict incluso si viene como repr de python (comillas simples)."""
    if isinstance(pedido_actual, dict):
        return pedido_actual
    if isinstance(pedido_actual, str):
        try:
            return json.loads(pedido_actual)
        except Exception:
            pass
        try:
            parsed = ast.literal_eval(pedido_actual)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {"order_complete": False, "items": [], "total_price": 0}

def _normalize_name(item: Dict) -> str:
    """Extrae un nombre normalizado para detectar duplicados."""
    name = ""
    if isinstance(item, dict):
        matched = item.get("matched") or {}
        name = matched.get("name") or item.get("requested", {}).get("producto") or item.get("name") or ""
    return re.sub(r'\s+', ' ', str(name or "")).strip().lower()

def _price_of_item(it: Dict) -> float:
    """Extrae el precio multiplicado por cantidad de un item de forma segura."""
    if not isinstance(it, dict):
        return 0.0
    matched = it.get("matched") or {}
    price = matched.get("price") or it.get("price") or 0
    qty = it.get("quantity") or it.get("qty") or it.get("cantidad") or 1
    try:
        qty_num = float(qty)
    except Exception:
        try:
            qty_num = float(str(qty).strip()) if str(qty).strip() else 1.0
        except Exception:
            qty_num = 1.0
    try:
        price_num = float(price)
    except Exception:
        price_num = 0.0
    return round(price_num * qty_num, 2)

def _merge_items(base_items: List[Dict], new_items: List[Dict], replace_all: bool = False) -> List[Dict]:
    """Fusiona base_items y new_items evitando duplicados. Si replace_all=True, devuelve solo new_items."""
    if replace_all:
        seen = set()
        out = []
        for it in new_items:
            key = _normalize_name(it)
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out
    merged = {}
    for it in base_items or []:
        key = _normalize_name(it)
        if key:
            merged[key] = it
    for it in new_items or []:
        key = _normalize_name(it)
        if not key:
            key = f"_unknown_{len(merged)}"
        merged[key] = it
    return list(merged.values())

def marcar_estemporal_true_en_pedidos(sender,codigo_unico) -> dict:
    """Marca es_temporal = TRUE en el pedido del cliente."""
    try:
        log_message('Iniciando función <MarcarTrue>.', 'INFO')
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None

        if id_whatsapp is None:
            return {
                "actualizado": False,
                "msg": "No existe id_whatsapp para este número."
            }
        query = """
            UPDATE pedidos
            SET es_temporal = TRUE
            WHERE codigo_unico = %s
              AND id_whatsapp = %s
            RETURNING idpedido;
        """
        params = (codigo_unico, id_whatsapp)
        res = execute_query(query, params, fetchone=True)
        
        if res:
            log_message(f'Pedido actualizado con código único {codigo_unico}', 'INFO')
            return {
                "actualizado": True,
                "idpedido": res[0],
                "codigo_unico": codigo_unico
            }
        else:
            log_message(f'No se encontró un pedido temporal con código único {codigo_unico}', 'INFO')
            return {
                "actualizado": False,
                "msg": "No se encontró un pedido temporal con ese código y ese id_whatsapp."
            }
    except Exception as e:
        log_message(f'Error en <MarcarPedidoComoDefinitivo>: {e}', 'ERROR')
        logging.error(f'Error en marcar_pedido_como_definitivo: {e}')
        return {"actualizado": False, "error": str(e)}
    
def marcar_pedido_como_definitivo(sender: str, codigo_unico: str) -> dict:
    """MARCA UN PEDIDO COMO FALSE EN ES_TEMPORAL Y RETORNA INFO DEL PEDIDO ACTUALIZADO."""
    try:
        log_message('Iniciando función <MarcarPedidoComoDefinitivo>.', 'INFO')
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None

        if id_whatsapp is None:
            return {
                "actualizado": False,
                "msg": "No existe id_whatsapp para este número."
            }
        query = """
            UPDATE pedidos
            SET es_temporal = TRUE
            WHERE codigo_unico = %s
              AND id_whatsapp = %s
            RETURNING idpedido;
        """
        params = (codigo_unico, id_whatsapp)
        res = execute_query(query, params, fetchone=True)
        if res:
            return {
                "actualizado": True,
                "idpedido": res[0],
                "codigo_unico": codigo_unico
            }
        else:
            return {
                "actualizado": False,
                "msg": "No se encontró un pedido temporal con ese código y ese id_whatsapp."
            }
    except Exception as e:
        log_message(f'Error en <MarcarPedidoComoDefinitivo>: {e}', 'ERROR')
        logging.error(f'Error en marcar_pedido_como_definitivo: {e}')
        return {"actualizado": False, "error": str(e)}

def eliminar_pedido(sender: str, codigo_unico: str) -> dict:
    try:
        log_message('Iniciando función <EliminarPedido>.', 'INFO')
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None

        if id_whatsapp is None:
            return {
                "eliminado": False,
                "msg": "No existe id_whatsapp para este número."
            }
        query = """
            DELETE FROM ordenes
            WHERE idpedidos = (
                SELECT idpedido
                FROM pedidos
                WHERE codigo_unico = %s
                AND id_whatsapp = %s
            );
        """
        params = (codigo_unico, id_whatsapp)
        execute_query(query, params)
        query_2 = """
            DELETE FROM pedidos
            WHERE codigo_unico = %s
            AND id_whatsapp = %s
            RETURNING idpedido;
        """
        res = execute_query(query_2, params, fetchone=True)
        log_message(f'Pedido eliminado con código único {codigo_unico}', 'INFO')
        if res:
            return {
                "eliminado": True,
                "idpedido": res[0],
                "codigo_unico": codigo_unico
            }
        else:
            return {
                "eliminado": False,
                "msg": "No se encontró un pedido con ese código y ese id_whatsapp."
            }
    except Exception as e:
        log_message(f'Error en <EliminarPedido>: {e}', 'ERROR')
        logging.error(f'Error en eliminar_pedido: {e}')
        return {"eliminado": False, "error": str(e)}
    
def obtener_pedido_por_codigo_orignal(sender: str, codigo_unico: str) -> dict:
    try:
        log_message('Iniciando función <ObtenerPedidoPorCodigo>.', 'INFO')
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None

        if id_whatsapp is None:
            return {
                "exito": False,
                "msg": "No existe id_whatsapp para este número."
            }
        query = """
            SELECT total_productos, codigo_unico
            FROM pedidos
            WHERE codigo_unico = %s
              AND id_whatsapp = %s;
        """
        params = (codigo_unico, id_whatsapp)
        res = execute_query(query, params, fetchone=True)
        log_message(f'Pedido obtenido con código único {codigo_unico}', 'INFO')
        if res:
            return {
                "exito": True,
                "total_productos": res[0],
                "codigo_unico": res[1]
            }
        else:
            return {
                "exito": False,
                "msg": "No se encontró un pedido con ese código y ese id_whatsapp."
            }
    except Exception as e:
        log_message(f'Error en <ObtenerPedidoPorCodigo>: {e}', 'ERROR')
        logging.error(f'Error en obtener_pedido_por_codigo: {e}')
        return {"exito": False, "error": str(e)}

def send_pdf_response(sender: str):
    try:
        """
        Envía un PDF al usuario vía WhatsApp Cloud API usando una URL con SAS.
        """
        log_message('Iniciando función <SendPDFResponse>.', 'INFO')
        ACCESS_TOKEN = os.environ["WABA_TOKEN"]
        PHONE_ID = os.environ["PHONE_NUMBER_ID"]
        url = f"https://graph.facebook.com/v20.0/{PHONE_ID}/messages"
        PDF_URL: str = os.environ["PDF_SAS_URL"]
        FILE_NAME: str = "menu-sierra-nevada.pdf"
        payload = {
            "messaging_product": "whatsapp",
            "to": sender,
            "type": "document",
            "document": {
                "link": PDF_URL,
                "filename": FILE_NAME
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ACCESS_TOKEN}"
        }
        res = requests.post(url, json=payload, headers=headers)
        log_message(f'PDF enviado al usuario {sender} con estado {res.status_code}.', 'INFO')
        return res.status_code, res.text
    except Exception as e:
        log_message(f'Error en <SendPDFResponse>: {e}', 'ERROR')
        logging.error(f'Error en send_pdf_response: {e}')
        return None, str(e)

def obtener_estado_pedido_por_codigo(sender: str, codigo_unico: str) -> dict:
    try:
        log_message('Iniciando función <ObtenerPedidoPorCodigo>.', 'INFO')
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s;"
        res_idw = execute_query_columns(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None
        if id_whatsapp is None:
            return {"exito": False, "msg": "No existe id_whatsapp para este número."}
        query_pedido = """
            SELECT *
            FROM pedidos
            WHERE codigo_unico = %s
              AND id_whatsapp = %s;
        """
        pedido_row, pedido_cols = execute_query_columns(
            query_pedido, (codigo_unico, id_whatsapp),
            fetchone=True, return_columns=True
        )
        if not pedido_row:
            return {"exito": False, "msg": "No se encontró un pedido con ese código."}
        pedido_info_serializable = {
            col: to_json_safe(val)
            for col, val in zip(pedido_cols, pedido_row)
        }
        idsede = pedido_info_serializable.get("idsede")
        sede_dict = None
        if idsede:
            query_sede = "SELECT * FROM sedes WHERE id_sede = %s;"
            sede_row, sede_cols = execute_query_columns(
                query_sede, (idsede,), fetchone=True, return_columns=True
            )
            if sede_row:
                sede_dict = {
                    col: to_json_safe(val)
                    for col, val in zip(sede_cols, sede_row)
                }
        return {
            "exito": True,
            "pedido": pedido_info_serializable,
            "sede": sede_dict
        }
    except Exception as e:
        log_message(f'Error en <ObtenerPedidoPorCodigo>: {e}', 'ERROR')
        logging.error(f'Error en obtener_pedido_por_codigo: {e}')
        return {"exito": False, "error": str(e)}


def convert_decimals(obj):
    try:
        """Convierte objetos Decimal en float dentro de estructuras anidadas."""
        log_message('Iniciando función <ConvertDecimals>.', 'INFO')
        if isinstance(obj, dict):
            log_message('Convirtiendo diccionario en <ConvertDecimals>.', 'INFO')
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            log_message('Convirtiendo lista en <ConvertDecimals>.', 'INFO')
            return [convert_decimals(i) for i in obj]
        elif isinstance(obj, Decimal):
            log_message('Convirtiendo Decimal en <ConvertDecimals>.', 'INFO')
            return float(obj)  # o str(obj) si prefieres exactitud
        else:
            log_message('No se requiere conversión en <ConvertDecimals>.', 'INFO')
            return obj
    except Exception as e:
        log_message(f'Error en <ConvertDecimals>: {e}', 'ERROR')
        logging.error(f'Error en convert_decimals: {e}')
        return obj

def to_json_safe(value):
    if isinstance(value, Decimal):
        return float(value)  # o str(value) si prefieres exactitud
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return value

def actualizar_total_productos(sender: str, codigo_unico: str, nuevo_total: float):
    """
    Actualiza total_productos e id_promocion del pedido según codigo_unico y sender.
    Retorna el idpedido y los valores actualizados.
    """
    try:
        log_message("Iniciando <actualizar_total_productos>", "INFO")
        query = """
            UPDATE pedidos
            SET es_promocion = true,
            WHERE codigo_unico = %s
              AND id_whatsapp = (
                    SELECT id_whatsapp
                    FROM clientes_whatsapp
                    WHERE telefono = %s
                )
            RETURNING idpedido, total_productos, id_promocion;
        """
        params = (nuevo_total, codigo_unico, sender)
        #res_promo = execute_query(query, params, fetchone=True)
        query = """
            UPDATE pedidos
            SET total_productos = %s,
            WHERE codigo_unico = %s
              AND id_whatsapp = (
                    SELECT id_whatsapp
                    FROM clientes_whatsapp
                    WHERE telefono = %s
                )
            RETURNING idpedido, total_productos, id_promocion;
        """
        params = (nuevo_total, codigo_unico, sender)
        res = execute_query(query, params, fetchone=True)
        if not res:
            return {
                "success": False,
                "mensaje": "No encontré un pedido con ese código para este usuario."
            }
        idpedido, total_actualizado, promo_actualizada = res
        log_message(f"Total actualizado para pedido {idpedido}: {total_actualizado}, promoción: {promo_actualizada}", "INFO")
        return {
            "success": True,
            "idpedido": idpedido,
            "total_productos": float(total_actualizado),
            "id_promocion": promo_actualizada
        }
    except Exception as e:
        log_message(f"Error en <actualizar_total_productos>: {e}", "ERROR")
        return {
            "success": False,
            "mensaje": f"Error: {e}"
        }

def actualizar_medio_pago(sender: str, codigo_unico: str, metodo_pago: str) -> dict:
    try:
        log_message('Iniciando función <MarcarPedidoComoDefinitivo>.', 'INFO')
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None

        if id_whatsapp is None:
            return {
                "actualizado": False,
                "msg": "No existe id_whatsapp para este número."
            }
        query = """
            UPDATE pedidos
            SET metodo_pago = %s
            WHERE codigo_unico = %s
              AND id_whatsapp = %s
            RETURNING idpedido, producto;
        """
        params = (metodo_pago, codigo_unico, id_whatsapp)
        res = execute_query(query, params, fetchone=True)
        if res:
            return {
                "actualizado": True,
                "idpedido": res[0],
                "producto": res[1],
                "codigo_unico": codigo_unico
            }
        else:
            return {
                "actualizado": False,
                "msg": "No se encontró un pedido temporal con ese código y ese id_whatsapp."
            }
    except Exception as e:
        log_message(f'Error en <MarcarPedidoComoDefinitivo>: {e}', 'ERROR')
        logging.error(f'Error en marcar_pedido_como_definitivo: {e}')
        return {"actualizado": False, "error": str(e)}

def obtener_pedido_por_codigo(codigo_unico: str) -> dict:
    q = "SELECT idpedido, producto, total_productos, fecha, hora, id_whatsapp, es_temporal,total_final,tiempo_estimado FROM pedidos WHERE codigo_unico = %s"
    res = execute_query(q, (codigo_unico,), fetchone=True)
    if not res:
        return {}
    return {
        "idpedido": res[0],
        "producto": res[1],
        "total_productos": float(res[2]) if res[2] is not None else 0.0,
        "fecha": res[3],
        "hora": res[4],
        "id_whatsapp": res[5],
        "es_temporal": res[6],
        "total_final": float(res[7]) if res[7] is not None else 0.0,
        "tiempo_estimado": res[8]
    }

# Helper: obtener ordenes existentes por idpedido (cada fila representa un item)
def obtener_ordenes_por_idpedido(idpedido: int) -> List[dict]:
    q = """
        SELECT idorden, desglose_productos, desglose_precio, especificaciones
        FROM ordenes
        WHERE idpedidos = %s
        ORDER BY idorden
    """
    rows = execute_query(q, (idpedido,), fetchall=True)
    ordenes = []
    for r in rows:
        ordenes.append({
            "idorden": r[0],
            "producto": r[1],
            "precio": float(r[2]) if r[2] is not None else 0.0,
            "especificaciones": r[3] or ""
        })
    return ordenes

# Helper: insertar una orden (retorna idorden)
def insertar_orden(id_whatsapp: int, idpedido: int, nombre_producto: str, precio: float, especificaciones_texto: str = "") -> int:
    q = """
        INSERT INTO ordenes (desglose_productos, desglose_precio, id_whatsapp, idpedidos, especificaciones)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING idorden;
    """
    res = execute_query(q, (nombre_producto, precio, id_whatsapp, idpedido, especificaciones_texto), fetchone=True)
    return res[0]

# Helper: eliminar una orden por idorden
def eliminar_orden_por_idorden(idorden: int) -> None:
    q = "DELETE FROM ordenes WHERE idorden = %s"
    execute_query(q, (idorden,))

# Helper: eliminar una orden por nombre (elimina una instancia que más se parezca)
def eliminar_una_instancia_orden_por_nombre(idpedido: int, nombre_producto: str, especificaciones_texto: str = "") -> bool:
    ordenes = obtener_ordenes_por_idpedido(idpedido)
    # buscar coincidencia exacta primero, si no fuzzy match
    for o in ordenes:
        if o["producto"].lower() == nombre_producto.lower() and (not especificaciones_texto or o["especificaciones"] == especificaciones_texto):
            eliminar_orden_por_idorden(o["idorden"])
            return True
    # fuzzy match por nombre
    productos = [o["producto"] for o in ordenes]
    if productos:
        match = difflib.get_close_matches(nombre_producto, productos, n=1, cutoff=0.6)
        if match:
            # eliminar la primera coincidencia que tenga ese nombre
            for o in ordenes:
                if o["producto"] == match[0]:
                    eliminar_orden_por_idorden(o["idorden"])
                    return True
    return False

# Helper: recalcular totales y actualizar tabla pedidos
def recalcular_y_actualizar_pedido(idpedido: int) -> dict:
    q = "SELECT desglose_productos, desglose_precio FROM ordenes WHERE idpedidos = %s"
    rows = execute_query(q, (idpedido,), fetchall=True)
    productos = [r[0] for r in rows] if rows else []
    total = sum([float(r[1]) for r in rows]) if rows else 0.0
    productos_str = " | ".join(productos) if productos else ""
    q_upd = "UPDATE pedidos SET producto = %s, total_productos = %s WHERE idpedido = %s RETURNING idpedido, codigo_unico, total_productos"
    res = execute_query(q_upd, (productos_str, total, idpedido), fetchone=True)
    return {
        "idpedido": res[0],
        "codigo_unico": res[1],
        "total_productos": float(res[2])
    }

# Helper: buscar producto en el menu (obtiene nombre oficial y precio)
def match_item_to_menu(product_name: str, items_menu: List[dict]) -> dict:
    # items_menu: lista de dicts; intentamos buscar por keys comunes 'name','price' o 'nombre','precio'
    nombres = []
    mapping = {}
    for it in items_menu:
        name = it.get("name") or it.get("nombre") or it.get("producto") or ""
        price = it.get("price") or it.get("precio") or 0.0
        nombres.append(name)
        mapping[name] = price
    # buscar coincidencia exacta (case-insensitive)
    for n in nombres:
        if n.lower() == product_name.lower():
            return {"name": n, "price": float(mapping[n]), "found": True}
    # fuzzy match
    match = difflib.get_close_matches(product_name, nombres, n=1, cutoff=0.6)
    if match:
        n = match[0]
        return {"name": n, "price": float(mapping[n]), "found": True}
    # no encontrado
    return {"name": product_name, "price": 0.0, "found": False}

def obtener_datos_promocion(telefono: str) -> dict | None:
    """
    Retorna un diccionario con:
      - bandera_promocion (bool)
      - info_promociones (list)
      - eleccion_promocion (dict)
    
    Consultado desde la columna JSONB `datos_promocion` de la tabla
    public.clasificacion_intenciones_futuras.

    Si no existe el registro o la columna está vacía, retorna None.
    """

    try:
        query = """
            SELECT datos_promocion
            FROM public.clasificacion_intenciones_futuras
            WHERE telefono = %s
            LIMIT 1;
        """

        resultado = execute_query(query, (telefono,), fetchone=True)
        log_message(f"Datos de promoción obtenidos para {telefono}: {resultado}", "INFO")

        if not resultado:
            return None  # No existe el registro

        datos_json = resultado[0]

        if not datos_json:
            return None  # La columna está vacía o null

        # PostgreSQL → Python: dict automático
        # Si tu driver ya devuelve JSON como dict (psycopg2 lo hace), puedes usarlo directo.
        # Si lo devuelve como string JSON, lo parseamos.
        if isinstance(datos_json, str):
            datos_json = json.loads(datos_json)

        # Garantizar que retorna las 3 claves aunque falten
        return {
            "bandera_promocion": datos_json.get("bandera_promocion"),
            "info_promociones": datos_json.get("info_promociones"),
            "eleccion_promocion": datos_json.get("eleccion_promocion"),
        }

    except Exception as e:
        log_message(f"Error al consultar datos de promoción: {e}", "ERROR")
        return None

def _normalize_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # dejar solo letras/números/espacios
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _apply_direct_selection_from_text(pedido: dict, mensaje_usuario: str, fuzzy_cutoff: float = 0.78) -> dict:
    """
    Busca en cada item con status 'multiple_matches' si el mensaje del usuario
    menciona claramente alguna candidate. Si la encuentra, actualiza el item en sitio:
    - matched -> candidate
    - status -> 'found'
    - candidates -> []
    - añade nota explicativa
    """
    if not mensaje_usuario:
        return pedido
    mensaje_norm = _normalize_text(mensaje_usuario)

    for it in pedido.get("items", []):
        try:
            if not it or it.get("status") != "multiple_matches":
                continue
            candidates = it.get("candidates") or []
            # construir lista de nombres normalizados
            for cand in candidates:
                # el nombre preferido puede estar en 'name' o 'id'
                cand_name = str(cand.get("name") or cand.get("id") or "")
                cand_norm = _normalize_text(cand_name)
                if not cand_norm:
                    continue
                # 1) substring directo (más seguro)
                if cand_norm in mensaje_norm.split():
                    # si el usuario solo escribió la palabra clave suelta
                    it["matched"] = cand
                    it["status"] = "found"
                    it["candidates"] = []
                    it["modifiers_applied"] = it.get("modifiers_applied", [])
                    it["note"] = f"Seleccionado automáticamente por mención del cliente: '{cand_name}'."
                    break
                if cand_norm in mensaje_norm:  # permite 'quiero una sierra clasica'
                    it["matched"] = cand
                    it["status"] = "found"
                    it["candidates"] = []
                    it["modifiers_applied"] = it.get("modifiers_applied", [])
                    it["note"] = f"Seleccionado automáticamente por mención del cliente: '{cand_name}'."
                    break
                # 2) comparación fuzzy: medir similitud con todo el mensaje
                # usamos difflib comparando el nombre candidato frente al mensaje normalizado
                close = difflib.get_close_matches(cand_norm, [mensaje_norm], n=1, cutoff=fuzzy_cutoff)
                if close:
                    it["matched"] = cand
                    it["status"] = "found"
                    it["candidates"] = []
                    it["modifiers_applied"] = it.get("modifiers_applied", [])
                    it["note"] = f"Seleccionado por coincidencia fuzzy con el mensaje del cliente: '{cand_name}'."
                    break
        except Exception:
            # no romper el flujo por un error en un item
            logging.exception("Error aplicando selección directa en item del pedido")
            continue
    return pedido

def obtener_datos_cliente_por_telefono(telefono: str, id_restaurante: str):
    """
    Retorna latitud, longitud e id_sede del cliente según su teléfono.
    Si no existe devuelve None.
    """
    try:
        query = """
            SELECT latitud, longitud, id_sede
            FROM clientes_whatsapp
            WHERE telefono = %s AND id_restaurante = %s;
        """
        
        resultado = execute_query(query, (telefono, id_restaurante), fetchone=True)
        log_message(f"Datos del cliente obtenidos para {telefono}: {resultado}", "INFO")
        if not resultado:
            log_message(f"No se encontró cliente con teléfono {telefono}", "INFO")
            return None

        latitud, longitud, id_sede = resultado
        return {
            "latitud": latitud,
            "longitud": longitud,
            "id_sede": id_sede
        }
    except Exception as e:
        log_message(f"Error en obtener_datos_cliente_por_telefono: {e}", "ERROR")
        return None

def obtener_pedido_pendiente_reciente(sender: str) -> dict:
    """
    Retorna el pedido más reciente (última hora) cuyo:
    - es_temporal = FALSE
    - estado = 'Pendiente'
    - asociado al sender
    """
    try:
        log_message('Iniciando función <ObtenerPedidoPendienteReciente>.', 'INFO')

        # 1. Obtener id_whatsapp
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None

        if id_whatsapp is None:
            return {
                "existe": False,
                "msg": "No existe id_whatsapp para este número."
            }

        # 2. Buscar pedido dentro de la última hora, no temporal, estado pendiente
        query = """
            SELECT idpedido, codigo_unico, fecha
            FROM pedidos
            WHERE id_whatsapp = %s
              AND es_temporal = FALSE
              AND estado = 'Pendiente'
              AND fecha >= NOW() - INTERVAL '1 hour'
            ORDER BY fecha DESC
            LIMIT 1;
        """

        res = execute_query(query, (id_whatsapp,), fetchone=True)

        if not res:
            return {
                "existe": False,
                "msg": "No hay pedidos pendientes recientes."
            }
        log_message("Finaliza obtener pedido pendiente reciente sin lios", "INFO")
        return {
            "existe": True,
            "idpedido": res[0],
            "codigo_unico": res[1],
            "fecha_creado": str(res[2])
        }

    except Exception as e:
        log_message(f'Error en <ObtenerPedidoPendienteReciente>: {e}', 'ERROR')
        logging.error(f'Error en obtener_pedido_pendiente_reciente: {e}')
        return {"existe": False, "error": str(e)}

def actualizar_costos_y_tiempos_pedido(
        sender: str,
        codigo_unico: str,
        valor: float,
        duracion: str,
        distancia: float
    ) -> dict:
    """
    Actualiza total_domicilio, tiempo_estimado, distancia, direccion_envio
    y total_final = total_productos + total_domicilio.
    """
    try:
        log_message("Iniciando función <ActualizarCostosYTiempoPedido>.", "INFO")

        # 1. Obtener id_whatsapp
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None

        if id_whatsapp is None:
            return {
                "actualizado": False,
                "msg": "No existe id_whatsapp para este número."
            }

        # 2. Actualizar los valores + recalcular total_final
        query = """
            UPDATE pedidos
            SET 
                total_domicilio = %s,
                tiempo_estimado = %s,
                distancia = %s,
                total_final = total_productos + %s
            WHERE codigo_unico = %s
              AND id_whatsapp = %s
            RETURNING idpedido, total_final;
        """

        params = (
            valor,
            duracion,
            distancia,
            valor,            # total_final = total_productos + valor
            codigo_unico,
            id_whatsapp
        )

        res = execute_query(query, params, fetchone=True)

        if not res:
            return {
                "actualizado": False,
                "msg": "No se encontró un pedido con ese código y ese id_whatsapp."
            }

        return {
            "actualizado": True,
            "idpedido": res[0],
            "total_final": float(res[1])
        }

    except Exception as e:
        log_message(f"Error en <ActualizarCostosYTiempoPedido>: {e}", "ERROR")
        logging.error(f"Error en actualizar_costos_y_tiempos_pedido: {e}")
        return {
            "actualizado": False,
            "error": str(e)
        }

def obtener_promociones_activas() -> list:
    try:
        log_message("Inicia obtener promociones activas", "INFO")
        promos_rows, promo_cols = execute_query_columns(
            """
            SELECT *
            FROM promociones
            WHERE fecha_inicio <= NOW()
              AND fecha_fin > NOW()
              AND estado = 'true';
            """,
            fetchone=False,
            return_columns=True
        )
        promociones_info = [
            {col: to_json_safe(val) for col, val in zip(promo_cols, row)}
            for row in promos_rows
        ]
        log_message(f"Termina obtener promociones activas {str(promociones_info)}", "INFO")
        return promociones_info
    except Exception as e:
        log_message(f"Error al obtener promociones activas {e}", "ERROR")
        return 

def verify_hour_atettion(sender: str, ID_RESTAURANTE: int) -> bool:
    """Verifica si el mensaje fue enviado dentro del horario de atención."""
    try:
        query = """
            SELECT hora_apertura, hora_cierre
            FROM public.clientes
            WHERE idcliente = %s;
        """
        params = (ID_RESTAURANTE,)
        res = execute_query(query, params, fetchone=True)
        log_message("Iniciando verificación de horario de atención", "INFO")

        # corregir la lógica y usar valores por defecto si vienen como NULL
        hora_inicio = int(res[0]) if res and res[0] is not None else 11
        hora_fin = int(res[1]) if res and res[1] is not None else 22

        ahora = datetime.now(ZoneInfo("America/Bogota"))
        hora_actual = ahora.hour

        # soportar horario que no cruza medianoche (ej: 11-22) y que sí lo cruza (ej: 22-6)
        if hora_inicio <= hora_fin:
            dentro = (hora_inicio <= hora_actual < hora_fin)
        else:
            # abre por la tarde/noche y cierra al día siguiente
            dentro = (hora_actual >= hora_inicio) or (hora_actual < hora_fin)

        if dentro:
            return True
        else:
            send_text_response(
                sender,
                f"¡Hola! 👋✨Por ahora estamos fuera de horario 🕐, pero abrimos de nuevo a las {hora_inicio} AM ⏰¡Te esperamos pronto!"
            )
            return False
    except Exception as e:
        log_message(f"Error al verificar horario de atención: {e}", "ERROR")
        return True


def obtener_direccion(sender: str, id_restaurante: str) -> bool:
    try:
        query = """
            SELECT direccion_google
            FROM public.clientes_whatsapp
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (sender, id_restaurante)
        result = execute_query(query, params)
        if result and result[0]:
            direccion_google = result[0][0]
            return direccion_google
        return False
    except Exception as e:
        log_message(f"validate_personal_data error: {e}", "ERROR")
        logging.error(f"validate_personal_data error: {e}")
        return False

def actualizar_order_complete_en_observaciones(sender: str) -> dict:
    """
    Lee la columna `observaciones` (json/jsonb) de public.clasificacion_intenciones_futuras
    para el telefono=sender, fuerza order_complete = True, recalcula total_price desde
    los items y actualiza la fila en la base. Retorna dict con el resultado y la nueva observación.
    """
    try:
        log_message("Iniciando <actualizar_order_complete_en_observaciones>", "INFO")
        query_sel = """
            SELECT observaciones
            FROM public.clasificacion_intenciones_futuras
            WHERE telefono = %s
            LIMIT 1;
        """
        res = execute_query(query_sel, (sender,), fetchone=True)
        if not res or res[0] is None:
            log_message(f"No se encontró observaciones para {sender}", "INFO")
            return {"success": False, "msg": "No existe registro o observaciones vacías."}

        observaciones_raw = res[0]

        # Normalizar a dict
        if isinstance(observaciones_raw, str):
            try:
                observaciones = json.loads(observaciones_raw)
            except Exception:
                try:
                    observaciones = ast.literal_eval(observaciones_raw)
                except Exception:
                    observaciones = {"order_complete": False, "items": [], "total_price": 0.0}
        elif isinstance(observaciones_raw, dict):
            observaciones = observaciones_raw
        else:
            # tipo inesperado -> intentar convertir a str then parse
            try:
                observaciones = json.loads(str(observaciones_raw))
            except Exception:
                observaciones = {"order_complete": False, "items": [], "total_price": 0.0}

        # Usar estructura segura
        pedido = _safe_parse_order(observaciones)

        # Forzar order_complete True
        pedido["order_complete"] = True

        # Recalcular total_price sumando total_price de cada item o unit_price*cantidad
        total = 0.0
        for it in pedido.get("items", []) or []:
            if not isinstance(it, dict):
                continue
            tp = None
            # preferir total_price
            if "total_price" in it and it.get("total_price") is not None:
                try:
                    tp = float(it.get("total_price"))
                except Exception:
                    tp = None
            # si no, intentar unit_price * quantity
            if tp is None:
                qty = it.get("quantity") or it.get("cantidad") or it.get("qty") or 1
                unit = it.get("unit_price") or it.get("price") or it.get("matched", {}).get("price") if isinstance(it.get("matched"), dict) else 0
                try:
                    tp = float(unit) * float(qty)
                except Exception:
                    tp = 0.0
            try:
                total += float(tp or 0.0)
            except Exception:
                continue

        pedido["total_price"] = round(total, 2)

        # Serializar y actualizar DB (usar jsonb cast)
        observaciones_db = json.dumps(pedido, ensure_ascii=False)
        query_upd = """
            UPDATE public.clasificacion_intenciones_futuras
            SET observaciones = %s::jsonb,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE telefono = %s
            RETURNING telefono;
        """
        upd_res = execute_query(query_upd, (observaciones_db, sender), fetchone=True)
        if not upd_res:
            log_message(f"No se pudo actualizar observaciones para {sender}", "ERROR")
            return {"success": False, "msg": "Fallo al actualizar la base de datos."}

        log_message(f"Observaciones actualizadas para {sender}", "INFO")
        return {"success": True, "telefono": sender, "observaciones": pedido}
    except Exception as e:
        log_message(f"Error en <actualizar_order_complete_en_observaciones>: {e}", "ERROR")
        logging.error(f"Error actualizar_order_complete_en_observaciones: {e}")
        return {"success": False, "error": str(e)}
    

def corregir_total_price_en_result(result: Dict) -> Dict:
    """
    Recalcula y corrige únicamente el campo 'total_price' en el dict `result`.
    - No modifica ninguna otra clave ni estructura del JSON.
    - Intenta usar _price_of_item (si existe) para respetar reglas internas.
    - Si falla, hace fallback usando matched.price y buscando 'Cantidad: N' en note
      o posibles campos de cantidad en requested.
    - Retorna el mismo dict con result['total_price'] actualizado (float, 2 decimales).
    """
    log_message("Iniciando corregir_total_price_en_result", "INFO")
    try:
        if not isinstance(result, dict):
            return result

        items = result.get("items") or []
        total = 0.0

        for it in items:
            # 1) intentar usar la función interna si está disponible y no lanza error
            try:
                price_item = _price_of_item(it)
                total += float(price_item or 0)
                continue
            except Exception:
                # si falla, caer al cálculo manual
                pass

            # 2) cálculo manual: precio unitario desde matched.price
            matched = it.get("matched") or {}
            unit_price = 0.0
            try:
                unit_price = float(matched.get("price") or 0)
            except Exception:
                unit_price = 0.0

            # 3) detectar cantidad: prioridad note -> requested.cantidad / qty
            qty = 1
            note = str(it.get("note") or "")
            m = re.search(r'cantidad\s*[:=]?\s*(\d+)', note, flags=re.I)
            if m:
                try:
                    qty = int(m.group(1))
                except Exception:
                    qty = 1
            else:
                requested = it.get("requested") or {}
                if isinstance(requested, dict):
                    q = requested.get("cantidad") or requested.get("qty") or requested.get("cantidad_total")
                    if isinstance(q, (int, float)) and q > 0:
                        qty = int(q)
                    elif isinstance(q, str) and q.isdigit():
                        qty = int(q)

            total += unit_price * qty

        total = round(float(total), 2)
        
        # Actualizar únicamente el campo total_price
        result["total_price"] = total
        log_message(f"total_price corregido: {total}", "DEBUG")
        return result

    except Exception as e:
        log_message(f"Error en corregir_total_price_en_result: {e}", "ERROR")
        return result

def extraer_ultimo_mensaje(mensaje: str) -> str:
    """
    Extrae el último mensaje del usuario de una cadena que puede contener
    múltiples mensajes concatenados (por ejemplo, en chats largos).
    Asume que los mensajes están separados por saltos de línea.
    Retorna el último mensaje limpio.
    """
    try:
        log_message("Iniciando extraer_ultimo_mensaje", "INFO")
        if not mensaje:
            return ""

        # Si la entrada es una representación de una lista/tupla de tuplas/dicts
        # intentar parsearla con ast.literal_eval y buscar el último texto del rol 'usuario'.
        try:
            import ast
            parsed = None
            if isinstance(mensaje, str) and (mensaje.strip().startswith("[") or "'rol'" in mensaje or '"rol"' in mensaje):
                try:
                    parsed = ast.literal_eval(mensaje)
                except Exception:
                    parsed = None

            if parsed and isinstance(parsed, (list, tuple)):
                # recorrer de atrás hacia adelante buscando rol usuario
                for elem in reversed(parsed):
                    # elem puede ser un tuple que contiene dicts
                    candidates = []
                    if isinstance(elem, dict):
                        candidates = [elem]
                    elif isinstance(elem, (list, tuple)):
                        # a veces viene como ((dict,),)
                        for sub in elem:
                            if isinstance(sub, dict):
                                candidates.append(sub)
                            elif isinstance(sub, (list, tuple)):
                                for sub2 in sub:
                                    if isinstance(sub2, dict):
                                        candidates.append(sub2)
                    # revisar candidatos
                    for c in candidates:
                        if not isinstance(c, dict):
                            continue
                        role = (c.get('rol') or c.get('role') or c.get('sender') or '').strip().lower()
                        text_field = c.get('texto') or c.get('text') or c.get('mensaje') or c.get('message')
                        if role in ('usuario', 'user', 'cliente') and text_field:
                            if isinstance(text_field, (list, tuple)):
                                # tomar el último elemento si es lista
                                ultimo_text = str(text_field[-1]).strip()
                            else:
                                ultimo_text = str(text_field).strip()
                            log_message(f"Último mensaje extraído (desde estructura): {ultimo_text}", "DEBUG")
                            return ultimo_text
                # si no encontramos rol usuario, extraer el último 'texto' disponible
                for elem in reversed(parsed):
                    # buscar el primer dict con clave 'texto' o 'text'
                    if isinstance(elem, dict):
                        text_field = elem.get('texto') or elem.get('text')
                        if text_field:
                            return str(text_field if not isinstance(text_field, (list, tuple)) else text_field[-1]).strip()
                    elif isinstance(elem, (list, tuple)):
                        for sub in reversed(elem):
                            if isinstance(sub, dict):
                                text_field = sub.get('texto') or sub.get('text')
                                if text_field:
                                    return str(text_field if not isinstance(text_field, (list, tuple)) else text_field[-1]).strip()
        except Exception:
            # fallthrough al parsing por líneas
            pass

        # Fallback: Dividir por líneas y tomar la última no vacía
        lineas = [line.strip() for line in mensaje.splitlines() if line.strip()]
        if lineas:
            ultimo = lineas[-1]
            log_message(f"Último mensaje extraído (por líneas): {ultimo}", "DEBUG")
            return ultimo

        # Último recurso: buscar con regex la última ocurrencia de texto dentro de comillas después de 'texto' o 'message'
        try:
            m = re.findall(r"(?:'texto'|\"texto\"|\'message\'|\"message\")\s*:\s*(?:\[)?\s*([\'\"])(.*?)\1", mensaje, flags=re.I | re.S)
            if m:
                ultimo = m[-1][1].strip()
                log_message(f"Último mensaje extraído (por regex): {ultimo}", "DEBUG")
                return ultimo
        except Exception:
            pass

        return ""
    except Exception as e:
        log_message(f"Error en extraer_ultimo_mensaje: {e}", "ERROR")
        return ""