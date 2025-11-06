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
from utils_chatgpt import analizar_respuesta_usuario_sin_intencion

# --- MENSAJES DE BIENVENIDA --- #
mensajes_bienvenida = [
    {
        "mensaje": "¡Qué gusto tenerte por aquí, {nombre}! 😃 En {nombre_local} tenemos hamburguesas irresistibles, ¿quieres ver nuestro menú?",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "¡Hola {nombre}! 👋 Nada mejor que una burger jugosa para alegrar el día, ¿te muestro nuestras opciones en {nombre_local}?",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "¡Hey {nombre}! 🤗 Gracias por escribirnos. En {nombre_local} te esperan las hamburguesas más sabrosas, ¿quieres conocer nuestras promociones?",
        "intencion": "consulta_promociones"
    },
    {
        "mensaje": "¡Hola {nombre}! 👨‍🍳 Estamos listos en {nombre_local} para preparar tu hamburguesa favorita, ¿te comparto el menú?",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "¡Hola {nombre}! 😋 Te está esperando la hamburguesa más jugosa de la ciudad en {nombre_local}, ¿quieres que te muestre las recomendaciones del chef?",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "¡Qué bueno verte por aquí, {nombre}! 🤝 En {nombre_local} siempre tenemos algo para cada gusto, ¿quieres ver los combos de hoy?",
        "intencion": "consulta_promociones"
    },
    {
        "mensaje": "¡Bienvenido {nombre}! 🥓🍔 En {nombre_local} tenemos burgers con todo el sabor que buscas, ¿quieres que te mande el menú digital?",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "¡Hola {nombre}! 😍 Ya huele a hamburguesa recién hecha en {nombre_local}, ¿quieres ver nuestras especialidades del día?",
        "intencion": "consulta_menu"
    },
    {
        "mensaje": "¡Hey {nombre}, qué tal! 👋 En {nombre_local} nos encanta consentirte con buenas burgers, ¿quieres empezar con tu pedido?",
        "intencion": "solicitud_pedido"
    }
]


# --- SUBFLUJOS INDIVIDUALES --- #
def subflujo_saludo_bienvenida(nombre: str, nombre_local: str, sender: str) -> str:
    """Genera un mensaje de bienvenida personalizado."""
    try:
        logging.info(f"Generando mensaje de bienvenida para {nombre} en {nombre_local}.")
        log_message(f'Iniciando función <SubflujoSaludoBienvenida> para {nombre}.', 'INFO')

        seleccion = random.choice(mensajes_bienvenida)
        mensaje = seleccion["mensaje"].format(nombre=nombre, nombre_local=nombre_local)
        intencion = seleccion["intencion"]
        guardar_intencion_futura(sender, intencion)

        return mensaje

    except Exception as e:
        logging.error(f"Error al generar mensaje de bienvenida: {e}")
        log_message(f'Error en <SubflujoSaludoBienvenida>: {e}.', 'ERROR')
        raise e
    finally:
        log_message(f'Finalizando función <SubflujoSaludoBienvenida> para {nombre}.', 'INFO')


def subflujo_solicitud_pedido(sender: str, respuesta_bot: str, entidades_text: str, id_ultima_intencion: str) -> None:
    """Genera un mensaje para solicitar la ubicación del usuario."""
    try:
        send_text_response(sender, respuesta_bot)
        guardar_intencion_futura(sender, "direccion")
        marcar_intencion_como_resuelta(id_ultima_intencion)
    except Exception as e:
        logging.error(f"Error en <SubflujoSolicitudPedido>: {e}")
        log_message(f'Error en <SubflujoSolicitudPedido>: {e}.', 'ERROR')
        raise e


def subflujo_sin_intencion(sender: str, respuesta_cliente: str) -> Dict[str, Any]:
    """Maneja el caso en que no se detecta una intención específica, con ayuda de IA."""
    try:
        log_message(f"Iniciando función <SubflujoSinIntencion> para {sender}.", "INFO")
        anterior_intencion = obtener_intencion_futura(sender)

        if anterior_intencion != "SinIntencion":
            analisis = analizar_respuesta_usuario_sin_intencion(respuesta_cliente, anterior_intencion)
            # analisis = { "intencion_respuesta": str, "continuidad": bool, "observaciones": str }
            #guardar_clasificacion_intencion(sender, analisis["intencion_respuesta"])
            log_message(f'Respuesta analizada: {analisis}', 'INFO')
            
            return analisis
        else:
            send_text_response(sender, "No entendí muy bien, ¿podrías repetirlo?")
            return {"continuidad": False}

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
    nombre_local: str = "Sierra Nevada"
) -> Any:
    """Activa el subflujo correspondiente según la intención detectada."""
    try:
        log_message(f"Empieza <OrquestadorSubflujos> con sender {sender} y tipo {clasificacion_mensaje}", "INFO")

        if clasificacion_mensaje == "saludo":
            respuesta_bot = subflujo_saludo_bienvenida(nombre_cliente, nombre_local, sender)
            send_text_response(sender, respuesta_bot)
        elif clasificacion_mensaje == "solicitud_pedido":
            respuesta_bot = (
                f"Gracias por tu ayuda {nombre_cliente}, retomemos con tu pedido anterior. "
                "Por favor envíame tu ubicación exacta."
                if bandera_externo else
                f"¡Perfecto, {nombre_cliente}! Para continuar con tu pedido, por favor envíame tu ubicación exacta."
            )
            subflujo_solicitud_pedido(sender, respuesta_bot, entidades_text, id_ultima_intencion)
            borrar_intencion_futura(sender)
        elif clasificacion_mensaje == "SinIntencion":
            return subflujo_sin_intencion(sender, pregunta_usuario)
        elif clasificacion_mensaje == "consulta_promociones":
            send_text_response(sender, "Claro, aquí tienes nuestras promociones actuales...")
            borrar_intencion_futura(sender)
        elif clasificacion_mensaje == "consulta_menu":
            send_text_response(sender, "Por supuesto, este es nuestro menú digital...")
            borrar_intencion_futura(sender)
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
    nombre_local: str = "Sierra Nevada"
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
            "nombre_local": nombre_local
        }

        while continuar:
            resultado = orquestador_subflujos(**contexto)

            if resultado and isinstance(resultado, dict):
                continuar = resultado.get("continuidad", False)
                if continuar:
                    contexto["clasificacion_mensaje"] = resultado.get("intencion_respuesta", "SinIntencion")
                    contexto["pregunta_usuario"] = resultado.get("observaciones", "")
                    log_message(f"Continuando flujo con intención {contexto['clasificacion_mensaje']}", "INFO")
                else:
                    log_message("No hay continuidad, fin del diálogo.", "INFO")
                    continuar = False
            else:
                continuar = False

    except Exception as e:
        log_message(f"Error en <ManejarDialogo>: {e}", "ERROR")
        raise e
