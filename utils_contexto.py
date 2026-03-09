# Last modified: 2025-21-12 Juan Agudelo
import contextvars
from typing import Optional
from utils_database import execute_query
from psycopg2.extras import Json
import os
# from utils import es_menor_24h
from datetime import datetime, timedelta    
from zoneinfo import ZoneInfo   
import json

ID_RESTAURANTE: str = os.getenv("ID_RESTAURANTE", "9")

_sender_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("sender", default=None)
_id_cliente_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("id_cliente", default=None)

def set_sender(sender: str) -> None:
    _sender_var.set(sender)

def get_sender() -> Optional[str]:
    return _sender_var.get()

def set_id_sede(sender: str) -> None:
    try:
        query = """SELECT id_sede FROM clientes_whatsapp WHERE telefono = %s and id_restaurante = %s LIMIT 1"""
        result = execute_query(query, (sender, ID_RESTAURANTE))
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
    execute_query("""INSERT INTO conversaciones (telefono,conversacion,fecha_mensaje,id_cliente) VALUES (%s, %s, NOW(), %s)""", (get_sender(), json_mensaje, ID_RESTAURANTE))
    execute_query("""INSERT INTO historico_conversaciones (telefono,primer_mensaje,id_cliente) VALUES (%s, NOW(),%s)""", (get_sender(), ID_RESTAURANTE))
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
    AND id_cliente = %s
    """
    execute_query(query, (rol, mensaje, telefono, ID_RESTAURANTE,))
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
        AND id_cliente = %s
        ORDER BY idx DESC
        LIMIT 5
    )
    SELECT 
        (SELECT fecha_mensaje 
        FROM conversaciones 
        WHERE telefono = %s
        AND id_cliente = %s
        ORDER BY id_conversaciones DESC
        LIMIT 1),
        mensaje
    FROM ultimos_mensajes
    ORDER BY idx ASC;
    """

    resultado = execute_query(query, (telefono,ID_RESTAURANTE, telefono, ID_RESTAURANTE))

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
        WHERE telefono = %s
        AND id_restaurante = %s;

        UPDATE historico_conversaciones 
        SET ultimo_mensaje = NOW(), cantidad_mensajes = 1
        WHERE ultimo_mensaje IS NULL 
        AND telefono = %s
        AND id_restaurante = %s;

        INSERT INTO historico_conversaciones 
        (telefono, primer_mensaje, id_cliente) 
        VALUES (%s, NOW(), %s);
        """

        execute_query(update_query, (telefono, ID_RESTAURANTE, telefono, ID_RESTAURANTE, telefono, ID_RESTAURANTE))
        query = """
        UPDATE clientes_whatsapp
        SET resumen = %s::jsonb
        WHERE telefono = %s
        AND id_restaurante = %s;
        """

        resumen_base = {
            "pedido_en_proceso": "",
            "metodo_pago_seleccionado": "",
            "direccion_confirmada": False,
            "resumen_contextual": "",
            "Importante": "",
            "gusta": [],
            "no_le_gusta": []
        }

        execute_query(
            query,
            (json.dumps(resumen_base), telefono, ID_RESTAURANTE)
        )
    return mensajes


 
def obtener_x_respuestas(telefono: str, limite: int) -> str:
    query = """
    SELECT mensaje
    FROM conversaciones,
         jsonb_array_elements(conversacion->'mensajes') WITH ORDINALITY AS m(mensaje, idx)
    WHERE telefono = %s
      AND id_cliente = %s
    ORDER BY idx DESC
    LIMIT %s;
    """

    mensajes  = execute_query(query, (telefono, ID_RESTAURANTE, limite))
    mensajes = list(reversed(mensajes))

    return mensajes
  
def obtener_estado_pedido(telefono: str, id_restaurante: int):
    try:
        query = """
            SELECT estado_actual, num_pedido
            FROM estado_pedido
            WHERE telefono = %s
            AND id_restaurante = %s
            LIMIT 1;
        """

        result = execute_query(query, (telefono, id_restaurante), fetchone=True)

        if not result:
            return None

        return {
            "estado_actual": result[0],
            "num_pedido": result[1]
        }

    except Exception as e:
        return None
    

def crear_estado_inicial(telefono: str, id_restaurante: int, estado: str ,num_pedido: str ):
    try:
        query = """
            INSERT INTO estado_pedido (telefono, id_restaurante, estado_actual, num_pedido)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telefono, id_restaurante)
            DO NOTHING;
        """

        execute_query(query, (telefono, id_restaurante, estado, num_pedido))

    except Exception as e:
        return None

def actualizar_estado_pedido(
    telefono: str,
    id_restaurante: int,
    estado: str,
    num_pedido: str = None
):
    try:
        query = """
            INSERT INTO estado_pedido (telefono, id_restaurante, estado_actual, num_pedido)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telefono, id_restaurante)
            DO UPDATE SET
                estado_actual = EXCLUDED.estado_actual,
                num_pedido = COALESCE(EXCLUDED.num_pedido, estado_pedido.num_pedido),
                fecha_actualizacion = NOW();
        """

        execute_query(query, (telefono, id_restaurante, estado, num_pedido))

    except Exception as e:
        raise e

def borrar_estado_pedido(telefono: str, id_restaurante: int):
    try:
        query = """
            DELETE FROM estado_pedido
            WHERE telefono = %s
            AND id_restaurante = %s;
        """

        execute_query(query, (telefono, id_restaurante))

    except Exception as e:
        return None

def tiene_estado_activo(telefono: str, id_restaurante: int) -> bool:
    try:
        query = """
            SELECT 1
            FROM estado_pedido
            WHERE telefono = %s
            AND id_restaurante = %s
            LIMIT 1;
        """

        result = execute_query(query, (telefono, id_restaurante), fetchone=True)
        return result is not None

    except Exception as e:
        return False
    
def obtener_codigo(telefono: str, id_restaurante: int):
    try:
        query = """
            SELECT num_pedido
            FROM estado_pedido
            WHERE telefono = %s
            AND id_restaurante = %s
            LIMIT 1;
        """

        result = execute_query(query, (telefono, id_restaurante), fetchone=True)

        if not result:
            return None

        return result[0]

    except Exception as e:
        return None

def actualizar_resumen_parcial(id_cliente: int, telefono: str, cambios: dict) -> bool:
    """
    Actualiza solo las llaves enviadas en 'cambios'
    dentro del jsonb 'resumen' en clientes_whatsapp
    usando execute_query().
    """

    if not cambios:
        return False

    try:
        update_expr = "resumen"
        valores = []

        # Construimos jsonb_set encadenado
        for clave, valor in cambios.items():
            update_expr = f"jsonb_set({update_expr}, %s, %s::jsonb, true)"
            valores.append(f"{{{clave}}}")
            valores.append(json.dumps(valor))

        query = f"""
            UPDATE clientes_whatsapp
            SET resumen = {update_expr}
            WHERE id_cliente = %s
            AND telefono = %s;
        """

        valores.append(id_cliente)
        valores.append(telefono)

        execute_query(query, tuple(valores))

        return True

    except Exception as e:
        print("Error actualizando resumen:", e)
        return False
    
def obtener_resumen(id_cliente: int, telefono: str):
    query = """
        SELECT resumen
        FROM clientes_whatsapp
        WHERE id_cliente = %s
        AND telefono = %s
        LIMIT 1;
    """

    result = execute_query(query, (id_cliente, telefono), fetchone=True)

    return result["resumen"] if result else None