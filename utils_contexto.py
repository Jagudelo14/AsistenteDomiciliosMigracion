import contextvars
from typing import Optional
from utils_database import execute_query
from psycopg2.extras import Json

_sender_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("sender", default=None)

def set_sender(sender: str) -> None:
    _sender_var.set(sender)

def get_sender() -> Optional[str]:
    return _sender_var.get()

def crear_conversacion(mensaje) -> str:
    json_mensaje = Json({
        "mensajes": [
            {
                "rol": "usuario",
                "texto": mensaje
            }
        ]
    })
    execute_query("""INSERT INTO conversaciones (telefono,conversacion) VALUES (%s, %s)""", (get_sender(), json_mensaje))
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

    return str(mensajes)

    