# Last modified: 2025-21-12 Juan Agudelo
import contextvars
from typing import Optional
from utils_database import execute_query
from psycopg2.extras import Json
import os
# from utils import es_menor_24h
from datetime import datetime, timedelta    
from zoneinfo import ZoneInfo   

_sender_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("sender", default=None)
_id_cliente_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("id_cliente", default=None)

def set_sender(sender: str) -> None:
    _sender_var.set(sender)

def get_sender() -> Optional[str]:
    return _sender_var.get()

def set_id_sede(sender: str) -> None:
    try:
        query = """SELECT id_sede FROM clientes_whatsapp WHERE telefono = %s LIMIT 1"""
        result = execute_query(query, (sender,))
        id_sede = result[0][0] if result else None
        print(f'ID sede obtenido: {id_sede}', 'INFO')
        _id_cliente_var.set(id_sede)
    except Exception as e:
        print(f'Error al obtener ID cliente: {e}', 'ERROR')
        _id_cliente_var.set(None)

def get_id_sede() -> Optional[str]:
    print(f'ID sede recuperado: {_id_cliente_var.get()}', 'INFO')
    return _id_cliente_var.get()

def crear_conversacion(mensaje) -> str:
    json_mensaje = Json({
        "mensajes": [
            {
                "rol": "usuario",
                "texto": mensaje,
                "fecha": str(datetime.now())
            }
        ]
    })
    execute_query("""INSERT INTO conversaciones (telefono,conversacion,fecha_mensaje,id_cliente) VALUES (%s, %s, NOW(), %s)""", (get_sender(), json_mensaje, os.environ.get("ID_RESTAURANTE", "5")))
    execute_query("""INSERT INTO historico_conversaciones (telefono,primer_mensaje,id_cliente) VALUES (%s, NOW(),%s)""", (get_sender(), os.environ.get("ID_RESTAURANTE", "5")))
    return str(json_mensaje)

def actualizar_conversacion(mensaje, telefono,rol) -> str:
    
    query = """
    UPDATE conversaciones
    SET conversacion = jsonb_set(
        conversacion,
        '{mensajes}',
        COALESCE(conversacion->'mensajes', '[]'::jsonb) ||
        jsonb_build_array(
            jsonb_build_object(
                'rol', %s,
                'texto', %s,
                'fecha', NOW()
            )
        ),
        true
    )
    WHERE telefono = %s
    """
    execute_query(query, (rol, mensaje, telefono))
    json_mensaje = Json({"rol": rol, "text": mensaje })
    return str(json_mensaje)    

def obtener_contexto_conversacion(telefono: str) -> list:

    query = """
    WITH ultimos_mensajes AS (
        SELECT mensaje, idx
        FROM conversaciones,
             jsonb_array_elements(conversacion->'mensajes') 
             WITH ORDINALITY AS m(mensaje, idx)
        WHERE telefono = %s
        ORDER BY idx DESC
        LIMIT 3
    )
    SELECT 
        (SELECT fecha_mensaje 
         FROM conversaciones 
         WHERE telefono = %s
         ORDER BY id_conversaciones DESC
         LIMIT 1),
        mensaje
    FROM ultimos_mensajes
    ORDER BY idx ASC;
    """

    resultado = execute_query(query, (telefono, telefono))

    if not resultado:
        return []

    ultima_hora = resultado[0][0]
    mensajes = [(row[1],) for row in resultado]  # mantiene lista de tuplas

    ahora = datetime.now(tz=ZoneInfo("America/Bogota"))
    diferencia = ahora - ultima_hora

    if diferencia >= timedelta(hours=24):
        update_query = """
        UPDATE conversaciones 
        SET fecha_mensaje = NOW()
        WHERE telefono = %s;

        UPDATE historico_conversaciones 
        SET ultimo_mensaje = NOW(), cantidad_mensajes = 1
        WHERE ultimo_mensaje IS NULL 
        AND telefono = %s;

        INSERT INTO historico_conversaciones 
        (telefono, primer_mensaje, id_cliente) 
        VALUES (%s, NOW(), 5);
        """

        execute_query(update_query, (telefono, telefono, telefono))

    return mensajes


 
def obtener_x_respuestas(telefono: str, limite: int) -> str:
    query = """
    SELECT mensaje
    FROM conversaciones,
         jsonb_array_elements(conversacion->'mensajes') WITH ORDINALITY AS m(mensaje, idx)
    WHERE telefono = %s
    ORDER BY idx DESC
    LIMIT %s;
    """

    mensajes  = execute_query(query, (telefono, limite))
    mensajes = list(reversed(mensajes))

    return mensajes
  