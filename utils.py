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
from typing import Tuple, Dict, Any, List
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import json
import requests
import unidecode
import difflib

REPLACE_PHRASES = [
    "cambia todo", "borra lo que había", "solo quiero esto", "quita lo anterior",
    "nuevo pedido", "empezar de cero", "anula pedido", "cancelar pedido", "resetear pedido",
    "empezar from cero", "empezar de 0"
]

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
              AND (es_temporal = FALSE OR es_temporal IS NULL)
            LIMIT 1;
        """
        resultado = execute_query(query, (numero_celular, id_restaurante))
        logging.info(f"Resultado de la consulta: {resultado}")
        log_message('Finalizando función <get_client_database>.', 'INFO')
        return len(resultado) > 0
    except Exception as e:
        log_message(f'Error al hacer uso de función <get_client_database>: {e}.', 'ERROR')
        logging.error(f'Error al hacer uso de función <get_client_database>: {e}.')
        return False

def handle_create_client(sender: str, datos: dict, id_restaurante: str, es_temporal: bool) -> str:
    try:
        log_message('Iniciando función <handleCreateClient>.', 'INFO')
        logging.info('Iniciando función <handleCreateClient>.')
        nombre = "Desconocido"
        if isinstance(datos, dict):
            nombre = datos.get("nombre", "Desconocido")
        logging.info(f'Nombre del cliente: {nombre}')
        logging.info(f'Teléfono (sender): {sender}')
        execute_query("""
            INSERT INTO clientes_whatsapp (nombre, telefono, id_restaurante, es_temporal)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telefono)
            DO UPDATE SET 
                nombre = EXCLUDED.nombre,
                es_temporal = EXCLUDED.es_temporal,
                id_restaurante = EXCLUDED.id_restaurante;
        """, (nombre, sender, id_restaurante, es_temporal))

        logging.info('Cliente creado o actualizado exitosamente.')
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
        query = """
            UPDATE public.clasificacion_intenciones
            SET estado = 'resuelta'
            WHERE id = %s;
        """
        execute_query(query, (id_intencion,))
        log_message(f"Intención {id_intencion} marcada como resuelta.", "INFO")
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
                "nombre": row[0],
                "tipo_comida": row[1],
                "descripcion": row[2],
                "observaciones": row[3],
                "precio": float(row[4]) if row[4] is not None else 0.0
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
        q_idw = "SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s"
        res_idw = execute_query(q_idw, (sender,), fetchone=True)
        id_whatsapp = res_idw[0] if res_idw else None
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
        productos = []
        for item in pedido_dict.get("items", []):
            matched = item.get("matched")

            if matched and matched.get("name"):
                productos.append(matched["name"])
            else:
                # Registrar el ítem que llegó sin match
                log_message(f"[WARN] Item sin matched en <GuardarPedidoCompleto>: {item}", "WARN")

                # Evitas romper la función, pero registras algo legible
                productos.append("SIN_MATCH")
        productos_str = " | ".join(productos)
        total_price = float(pedido_dict.get("total_price", 0))
        # ------------------------------- # 5. Hora y fecha Bogotá # -------------------------------
        now = datetime.now(ZoneInfo("America/Bogota"))
        fecha = now.strftime("%Y-%m-%d %H:%M:%S")
        hora = now.strftime("%H:%M")
        # ------------------------------- # 6. Campos fijos # ------------------------------- 
        idcliente = 5
        idsede = 15
        estado = "pendiente"
        metodo_pago = "efectivo"
        # ------------------------------- # 7. Query con RETURNING # -------------------------------
        query = """ INSERT INTO pedidos ( producto, total_productos, fecha, hora, idcliente, idsede, estado, persona_nuevo, id_whatsapp, metodo_pago, codigo_unico, es_temporal ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING idpedido, codigo_unico """
        params = ( productos_str, total_price, fecha, hora, idcliente, idsede, estado, persona_nuevo, id_whatsapp, metodo_pago, codigo_unico, es_temporal )
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
        return {
            "idpedido": res[0],
            "codigo_unico": res[1]
        }
    except Exception as e:
        tb = traceback.format_exc()
        log_message(f'Error al hacer uso de función <GuardarPedidoCompleto>: {e}.\nTRACEBACK:\n{tb}', 'ERROR')
        logging.error(f'Error al hacer uso de función <GuardarPedidoCompleto>: {e}.\n{tb}')
        return {}

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

def marcar_pedido_como_definitivo(sender: str, codigo_unico: str) -> dict:
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
            SET es_temporal = FALSE
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
            SELECT producto, total_productos, codigo_unico
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
                "producto": res[0],
                "total_productos": res[1],
                "codigo_unico": res[2]
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
        res_promo = execute_query(query, params, fetchone=True)
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
    q = "SELECT idpedido, producto, total_productos, fecha, hora, id_whatsapp, es_temporal FROM pedidos WHERE codigo_unico = %s"
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
        "es_temporal": res[6]
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