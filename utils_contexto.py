# Last modified: 2025-21-12 Juan Agudelo
import contextvars
from typing import Optional
from utils_database import execute_query
from psycopg2.extras import Json
import os
from utils import es_menor_24h

_sender_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("sender", default=None)
_id_cliente_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("id_cliente", default=None)

def set_sender(sender: str) -> None:
    _sender_var.set(sender)

def get_sender() -> Optional[str]:
    return _sender_var.get()

def set_id_cliente(sender: str) -> None:
    query = """SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s LIMIT 1"""
    result = execute_query(query, (sender,))
    id_cliente = result[0][0] if result else None
    print(f'ID cliente obtenido: {id_cliente}', 'INFO')
    _id_cliente_var.set(id_cliente)

def get_id_cliente() -> Optional[str]:
    print(f'ID cliente recuperado: {_id_cliente_var.get()}', 'INFO')
    return _id_cliente_var.get()

def crear_conversacion(mensaje) -> str:
    json_mensaje = Json({
        "mensajes": [
            {
                "rol": "usuario",
                "texto": mensaje
            }
        ]
    })
    execute_query("""INSERT INTO conversaciones (telefono,conversacion,fecha_mensaje,id_cliente) VALUES (%s, %s, NOW(), %s)""", (get_sender(), json_mensaje, os.environ.get("ID_RESTAURANTE", "5")))
    execute_query("""INSERT INTO historico_conversaciones (telefono,primer_mensaje,ultimo_mensaje,cantidad_mensajes,id_cliente) VALUES (%s, NOW(), NOW(), %s,%s)""", (get_sender(), 1, os.environ.get("ID_RESTAURANTE", "5")))
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
                'texto', %s
            )
        ),
        true
    )
    WHERE telefono = %s
    """
    execute_query(query, (rol, mensaje, telefono))
    json_mensaje = Json({"rol": rol, "text": mensaje })
    return str(json_mensaje)    

def obtener_contexto_conversacion(telefono: str) -> str:
    query = """
    SELECT mensaje
    FROM conversaciones,
         jsonb_array_elements(conversacion->'mensajes') WITH ORDINALITY AS m(mensaje, idx)
    WHERE telefono = %s
    ORDER BY idx DESC
    LIMIT %s;
    """

    mensajes  = execute_query(query, (telefono, 3))
    mensajes = list(reversed(mensajes))

    query="""SELECT fecha_mensaje
    FROM conversaciones,
    WHERE telefono = %s
    ORDER BY idx DESC
    LIMIT %s;
    """
    ultima_hora  = execute_query(query, (telefono, 1))

    if ultima_hora and es_menor_24h(ultima_hora[0][0]):
        return mensajes
    else:
        execute_query(
            "UPDATE conversaciones SET fecha_mensaje=NOW() WHERE telefono=%s AND id_cliente=%s",(get_sender(), os.environ.get("ID_RESTAURANTE", "5")))
        execute_query("""INSERT INTO historico_conversaciones (telefono,primer_mensaje,ultimo_mensaje,cantidad_mensajes,id_cliente) VALUES (%s, NOW(), NOW(), %s,%s)""", (get_sender(), 1, os.environ.get("ID_RESTAURANTE", "5")))
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
    