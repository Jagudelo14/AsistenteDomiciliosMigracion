# utils_subflujos.py
# Last modified: 2025-09-30 by Andrés Bermúdez

import random
import logging
from utils import log_message, send_text_response
from typing import Any, Dict
mensajes_bienvenida = [
    "¡Hola {nombre}! 🍔 Bienvenido a {nombre_local}, ¿ya sabes con qué hamburguesa te quieres deleitar hoy?",
    "¡Qué gusto tenerte por aquí, {nombre}! 😃 En {nombre_local} tenemos hamburguesas irresistibles, ¿quieres ver nuestro menú?",
    "¡Hola {nombre}! 👋 Nada mejor que una burger jugosa para alegrar el día, ¿te muestro nuestras opciones en {nombre_local}?",
    "¡Hey {nombre}! 🤗 Gracias por escribirnos. En {nombre_local} te esperan las hamburguesas más sabrosas, ¿quieres conocer nuestras promociones?",
    "¡Hola {nombre}! 👨‍🍳 Estamos listos en {nombre_local} para preparar tu hamburguesa favorita, ¿te comparto el menú?",
    "¡Qué alegría saludarte, {nombre}! 🥳 En {nombre_local} tenemos combos perfectos para ti, ¿quieres que te enseñe cuál te puede gustar más?",
    "¡Bienvenido a {nombre_local}, {nombre}! 🍔✨ ¿Se te antoja empezar con una clásica o prefieres algo más especial?",
    "¡Hola {nombre}! 😋 Te está esperando la hamburguesa más jugosa de la ciudad en {nombre_local}, ¿quieres que te muestre las recomendaciones del chef?",
    "¡Qué bueno verte por aquí, {nombre}! 🤝 En {nombre_local} siempre tenemos algo para cada gusto, ¿quieres ver los combos de hoy?",
    "¡Hola {nombre}! 🌟 Gracias por escribirnos a {nombre_local}. ¿Listo para pedir tu hamburguesa favorita o prefieres que te sugiera algo?",
    "¡Bienvenido {nombre}! 🥓🍔 En {nombre_local} tenemos burgers con todo el sabor que buscas, ¿quieres que te mande el menú digital?",
    "¡Hola {nombre}! 😍 Ya huele a hamburguesa recién hecha en {nombre_local}, ¿quieres ver nuestras especialidades del día?",
    "¡Hey {nombre}, qué tal! 👋 En {nombre_local} nos encanta consentirte con buenas burgers, ¿quieres empezar con tu pedido?",
    "¡Hola {nombre}! 🤩 En {nombre_local} tenemos hamburguesas para todos los gustos, ¿quieres probar las opciones de pollo, res o veggie?",
    "¡Bienvenido a {nombre_local}, {nombre}! 🍟 Además de burgers deliciosas, tenemos acompañamientos que no te puedes perder, ¿quieres pedirlos?"
]

def subflujo_saludo_bienvenida(nombre: str, nombre_local: str) -> str:
    try:
        """Genera un mensaje de bienvenida personalizado."""
        logging.info(f"Generando mensaje de bienvenida para {nombre} en {nombre_local}.")
        log_message(f'Iniciando función <SubflujoSaludoBienvenida> para {nombre}.', 'INFO')
        mensaje = random.choice(mensajes_bienvenida).format(nombre=nombre, nombre_local=nombre_local)
    except Exception as e:
        logging.error(f"Error al generar mensaje de bienvenida: {e}")
        log_message(f'Error al hacer uso de función <SubflujoSaludoBienvenida>: {e}.', 'ERROR')
        raise e
    finally:
        log_message(f'Finalizando función <SubflujoSaludoBienvenida> para {nombre}.', 'INFO')
        return mensaje

def orquestador_subflujos(sender: str, clasificacion_mensaje: str, nombre_cliente: str, entidades_dic: Dict[str, Any], nombre_local = "Sierra Nevada") -> None:
    try:
        """Clasifica y activa los subflujos necesarios dependiendo del mensaje"""
        log_message(f"Empieza orquestador_subflujos con sender {sender} y tipo {clasificacion_mensaje}", "INFO")
        if clasificacion_mensaje == "saludo":
            send_text_response(sender, subflujo_saludo_bienvenida(nombre_cliente, nombre_local))
        log_message("Termina orquestador sin problemas", "INFO")
    except Exception as e:
        log_message(f"Ocurrió un problema al ejecutar orquestador, revisar {e}", "ERROR")
        raise e