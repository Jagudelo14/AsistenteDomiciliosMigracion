# utils_subflujos.py
# Last modified: 2025-11-05 by Andrés Bermúdez

import random
import logging
from typing import Any, Dict

# --- IMPORTS INTERNOS --- #
from utils import (
    guardar_intencion_futura,
    log_message,
    marcar_intencion_como_resuelta,
    send_text_response,
    guardar_clasificacion_intencion,
    obtener_intencion_futura,
    borrar_intencion_futura
)
from utils_chatgpt import clasificar_pregunta_menu_chatgpt, responder_pregunta_menu_chatgpt, saludo_dynamic, sin_intencion_respuesta_variable
from utils_database import execute_query

# --- BANCOS DE MENSAJES PREDETERMINADOS --- #
respuestas_no_relacionadas = [
    {
        "mensaje": "Lo siento {nombre} 😅, no tengo información sobre eso. Pero si quieres, puedo mostrarte nuestro menú para que veas todas las opciones disponibles.",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "Ups 😬, esa información no la tengo a la mano ahora mismo {nombre}. ¿Te gustaría que te muestre el menú para que elijas algo delicioso?",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "Disculpame {nombre} 🙈, no tengo respuesta para esa pregunta, pero puedo ayudarte a hacer tu pedido si ya sabes qué quieres.",
        "intencion": "solicitud_pedido"
    },
    {
        "mensaje": "Hmm 🤔, no tengo información sobre eso. Pero si quieres, {nombre}, te muestro el menú y así eliges lo que más te antoje.",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "Perdón {nombre}, no cuento con esa información. Aunque si lo prefieres, puedo ayudarte a hacer un pedido ahora mismo 🍔. Escribe lo que quieras pedir...",
        "intencion": "solicitud_pedido"
    },
    {
        "mensaje": "Lo siento {nombre}, no tengo datos sobre ese tema 😕. ¿Te gustaría que te envíe nuestro menú para que veas las opciones disponibles?",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "No tengo información sobre eso 😅, pero puedo ayudarte a pedir algo delicioso en un momento. ¿Quieres hacerlo ahora {nombre}? Escribe lo que quieras pedir...",
        "intencion": "solicitud_pedido"
    },
    {
        "mensaje": "Lamento no poder responder a eso {nombre} 😔. Pero si quieres, puedo enseñarte nuestro menú para que explores las hamburguesas disponibles.",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "Esa pregunta se sale un poco de mi menú 😅, pero puedo ayudarte a hacer tu pedido o mostrarte nuestras promociones. ¿Te parece {nombre}? Escribe lo que quieras pedir...",
        "intencion": "solicitud_pedido"
    },
]

# --- SUBFLUJOS INDIVIDUALES --- #
def subflujo_saludo_bienvenida(nombre: str, nombre_local: str, sender: str, mensaje_usuario: str) -> str:
    """Genera un mensaje de bienvenida personalizado."""
    try:
        logging.info(f"Generando mensaje de bienvenida para {nombre} en {nombre_local}.")
        log_message(f'Iniciando función <SubflujoSaludoBienvenida> para {nombre}.', 'INFO')
        respuesta_gpt: dict = saludo_dynamic(mensaje_usuario, nombre, nombre_local)
        mensaje = respuesta_gpt.get("mensaje")
        intencion = respuesta_gpt.get("intencion", "consulta_menu")
        guardar_intencion_futura(sender, intencion)
        return mensaje
    except Exception as e:
        logging.error(f"Error al generar mensaje de bienvenida: {e}")
        log_message(f'Error en <SubflujoSaludoBienvenida>: {e}.', 'ERROR')
        raise e

def subflujo_solicitud_pedido(sender: str, respuesta_bot: str, entidades_text: str, id_ultima_intencion: str) -> None:
    """Genera un mensaje para solicitar la ubicación del usuario."""
    try:
        send_text_response(sender, "Perfecto, estoy listo para ayudarte con tu pedido.")
        guardar_intencion_futura(sender, "direccion")
        marcar_intencion_como_resuelta(id_ultima_intencion)
        
    except Exception as e:
        logging.error(f"Error en <SubflujoSolicitudPedido>: {e}")
        log_message(f'Error en <SubflujoSolicitudPedido>: {e}.', 'ERROR')
        raise e

def subflujo_confirmacion_general(sender: str, respuesta_cliente: str) -> Dict[str, Any]:
    """Maneja el caso en que no se detecta una intención específica, con ayuda de IA."""
    try:
        log_message(f"Iniciando función <SubflujoConfirmacionGeneral> para {sender}.", "INFO")
        anterior_intencion = obtener_intencion_futura(sender)
        if anterior_intencion is None:
            send_text_response(sender, "No tengo una acción pendiente. ¿En qué más puedo ayudarte?")
            return {
                "intencion_respuesta": "SinIntencion",
                "continuidad": False,
                "observaciones": respuesta_cliente
            }
        analisis: dict = {
            "intencion_respuesta": anterior_intencion,
            "continuidad": True,
            "observaciones": respuesta_cliente
        }
        log_message(f'Respuesta analizada: {analisis}', 'INFO')
        return analisis
    except Exception as e:
        logging.error(f"Error en <SubflujoConfirmacionGeneral>: {e}")
        log_message(f'Error en <SubflujoConfirmacionGeneral>: {e}.', 'ERROR')
        raise e

def subflujo_negacion_general(sender: str, respuesta_cliente: str) -> Dict[str, Any]:
    """Maneja el caso en que no se detecta una intención específica, con ayuda de IA."""
    try:
        log_message(f"Iniciando función <SubflujoNegacionGeneral> para {sender}.", "INFO")
        anterior_intencion = obtener_intencion_futura(sender)
        if anterior_intencion is None:
            send_text_response(sender, "No tengo una acción pendiente. ¿En qué más puedo ayudarte?")
            return {
                "intencion_respuesta": "SinIntencion",
                "continuidad": False,
                "observaciones": respuesta_cliente
            }
        analisis: dict = {
            "intencion_respuesta": anterior_intencion,
            "continuidad": False,
            "observaciones": respuesta_cliente
        }
        log_message(f'Respuesta analizada: {analisis}', 'INFO')
        borrar_intencion_futura(sender)
        send_text_response(sender, "Entendido. Si necesitas algo más, no dudes en escribirme. ¡Estoy aquí para ayudarte!")
        return analisis
    except Exception as e:
        logging.error(f"Error en <SubflujoNegacionGeneral>: {e}")
        log_message(f'Error en <SubflujoNegacionGeneral>: {e}.', 'ERROR')
        raise e

def subflujo_preguntas_generales(sender: str, pregunta_usuario: str, nombre_cliente: str) -> None:
    """Maneja preguntas generales del usuario."""
    try:
        log_message(f'Iniciando función <SubflujoPreguntasGenerales> para {sender}.', 'INFO')
        clasificacion: dict = clasificar_pregunta_menu_chatgpt(pregunta_usuario)
        clasificacion_tipo = clasificacion.get("clasificacion", "no_relacionada")

        if clasificacion_tipo == "relacionada":
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
            respuesta_llm: dict = responder_pregunta_menu_chatgpt(pregunta_usuario, items)
            send_text_response(sender, respuesta_llm.get("respuesta"))
            send_text_response(sender, respuesta_llm.get("productos", ""))
            if respuesta_llm.get("recomendacion"):
                guardar_intencion_futura(sender, "solicitud_pedido")
        else:
            seleccion = random.choice(respuestas_no_relacionadas)
            mensaje = seleccion["mensaje"].format(nombre=nombre_cliente)
            intencion = seleccion["intencion"]
            send_text_response(sender, mensaje)
            guardar_intencion_futura(sender, intencion)
        log_message(f'Pregunta general clasificada y respondida: {clasificacion}', 'INFO')
    except Exception as e:
        logging.error(f"Error en <SubflujoPreguntasGenerales>: {e}")
        log_message(f'Error en <SubflujoPreguntasGenerales>: {e}.', 'ERROR')
        raise e

def subflujo_sin_intencion(sender: str, nombre_cliente: str, contenido_usuario: str) -> None:
    """Maneja el caso en que no se detecta una intención específica usando GPT-3.5-turbo."""
    try:
        log_message(f'Iniciando función <SubflujoSinIntencion> para {sender}.', 'INFO')
        mensaje: str = sin_intencion_respuesta_variable(contenido_usuario, nombre_cliente)
        send_text_response(sender, mensaje)

    except Exception as e:
        logging.error(f"Error en <SubflujoSinIntencion>: {e}")
        log_message(f'Error en <SubflujoSinIntencion>: {e}.', 'ERROR')
        raise e


# --- ORQUESTADOR DE SUBFLUJOS --- #
def orquestador_subflujos(
    sender: str,
    clasificacion_mensaje: str,
    nombre_cliente: str,
    entidades_text: str,
    pregunta_usuario: str,
    bandera_externo: bool,
    id_ultima_intencion: str,
    nombre_local: str = "Sierra Nevada",
    type_text: str = "text"
) -> Any:
    """Activa el subflujo correspondiente según la intención detectada."""
    try:
        log_message(f"Empieza <OrquestadorSubflujos> con sender {sender} y tipo {clasificacion_mensaje}", "INFO")
        clasificacion_mensaje = clasificacion_mensaje.strip().lower()
        if clasificacion_mensaje == "saludo":
            respuesta_bot = subflujo_saludo_bienvenida(nombre_cliente, nombre_local, sender, pregunta_usuario)
            send_text_response(sender, respuesta_bot)
        elif clasificacion_mensaje == "solicitud_pedido":
            respuesta_bot = (
                f"Gracias por tu ayuda {nombre_cliente}, retomemos con tu pedido anterior. "
                "Por favor envíame tu ubicación exacta."
                if bandera_externo else
                f"¡Perfecto, {nombre_cliente}! Para continuar con tu pedido, por favor envíame tu ubicación exacta."
            )
            subflujo_solicitud_pedido(sender, respuesta_bot, entidades_text, id_ultima_intencion)
            #borrar_intencion_futura(sender)
        elif clasificacion_mensaje == "confirmacion_general":
            return subflujo_confirmacion_general(sender, pregunta_usuario)
        elif clasificacion_mensaje == "negacion_general":
            subflujo_negacion_general(sender, pregunta_usuario)
        elif clasificacion_mensaje == "consulta_promociones":
            send_text_response(sender, "Claro, aquí tienes nuestras promociones actuales...")
            borrar_intencion_futura(sender)
        elif clasificacion_mensaje == "consulta_menu" and type_text != "pregunta" and type_text != "preguntas_generales":
            send_text_response(sender, "Por supuesto, este es nuestro menú digital...")
            borrar_intencion_futura(sender)
        elif clasificacion_mensaje == "preguntas_generales" or (clasificacion_mensaje == "consulta_menu" and (type_text == "pregunta" or type_text == "preguntas_generales")):
            subflujo_preguntas_generales(sender, pregunta_usuario, nombre_cliente)
        elif clasificacion_mensaje == "sin_intencion":
            subflujo_sin_intencion(sender, nombre_cliente, pregunta_usuario)
        return None
    except Exception as e:
        log_message(f"Ocurrió un problema en <OrquestadorSubflujos>: {e}", "ERROR")
        raise e
# --- MANEJADOR PRINCIPAL DE DIÁLOGO (ITERATIVO, NO RECURSIVO) --- #
def manejar_dialogo(
    sender: str,
    clasificacion_mensaje: str,
    nombre_cliente: str,
    entidades_text: str,
    pregunta_usuario: str,
    bandera_externo: bool,
    id_ultima_intencion: str,
    nombre_local: str = "Sierra Nevada",
    type_text: str = "text"
) -> None:
    """
    Controla el flujo completo de conversación de forma iterativa.
    Evalúa continuidad y decide cuándo volver a llamar al orquestador.
    """
    try:
        continuar = True
        contexto = {
            "sender": sender,
            "clasificacion_mensaje": clasificacion_mensaje,
            "nombre_cliente": nombre_cliente,
            "entidades_text": entidades_text,
            "pregunta_usuario": pregunta_usuario,
            "bandera_externo": bandera_externo,
            "id_ultima_intencion": id_ultima_intencion,
            "nombre_local": nombre_local,
            "type_text": type_text
        }

        while continuar:
            resultado = orquestador_subflujos(**contexto)

            if resultado and isinstance(resultado, dict):
                continuar = resultado.get("continuidad", False)
                if continuar:
                    contexto["clasificacion_mensaje"] = resultado.get("intencion_respuesta", "SinIntencion")
                    contexto["pregunta_usuario"] = resultado.get("observaciones", "")
                    log_message(f"Actualizando contexto para nueva iteración: {contexto}", "INFO")
                    log_message(f"Continuando flujo con intención {contexto['clasificacion_mensaje']}", "INFO")
                else:
                    log_message("No hay continuidad, fin del diálogo.", "INFO")
                    continuar = False
            else:
                continuar = False

    except Exception as e:
        log_message(f"Error en <ManejarDialogo>: {e}", "ERROR")
        raise e
