# utils_subflujos.py
# Last modified: 2025-11-05 by Andrés Bermúdez

import ast
import json
import os
import random
import logging
from typing import Any, Dict
import re
from utils_registration import validate_direction_first_time

# --- IMPORTS INTERNOS --- #
from utils import (
    marcar_estemporal_true_en_pedidos,
    actualizar_medio_pago,
    obtener_direccion,
    actualizar_costos_y_tiempos_pedido,
    actualizar_total_productos,
    eliminar_pedido,
    guardar_intencion_futura,
    guardar_pedido_completo,
    log_message,
    marcar_intencion_como_resuelta,
    marcar_pedido_como_definitivo,
    match_item_to_menu,
    normalizar_entities_items,
    obtener_datos_cliente_por_telefono,
    obtener_datos_promocion,
    obtener_estado_pedido_por_codigo,
    obtener_intencion_futura_mensaje_chatbot,
    obtener_intencion_futura_mensaje_usuario,
    obtener_intencion_futura_observaciones,
    obtener_menu,
    obtener_pedido_por_codigo,
    obtener_pedido_por_codigo_orignal,
    obtener_promociones_activas,
    send_pdf_response,
    send_text_response,
    obtener_intencion_futura,
    borrar_intencion_futura,
)
from utils_chatgpt import actualizar_pedido_con_mensaje, actualizar_pedido_con_mensaje_modificacion, clasificar_pregunta_menu_chatgpt, enviar_menu_digital, generar_mensaje_cancelacion, generar_mensaje_confirmacion_modificacion_pedido, generar_mensaje_invitar_pago, generar_mensaje_recogida_invitar_pago, generar_mensaje_seleccion_sede, interpretar_eleccion_promocion, mapear_pedido_al_menu, mapear_sede_cliente, pedido_incompleto_dynamic, pedido_incompleto_dynamic_promocion, responder_pregunta_menu_chatgpt, responder_sobre_pedido, responder_sobre_promociones, respuesta_quejas_graves_ia, respuesta_quejas_ia, saludo_dynamic, sin_intencion_respuesta_variable, solicitar_medio_pago, solicitar_metodo_recogida,direccion_bd,mapear_modo_pago,corregir_direccion
from utils_database import execute_query, execute_query_columns
from utils_google import calcular_tiempo_pedido, formatear_tiempo_entrega, orquestador_tiempo_y_valor_envio, set_direccion_cliente, set_lat_lon, set_sede_cliente
from utils_pagos import generar_link_pago, guardar_id_pago_en_db, validar_pago

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

def subflujo_solicitud_pedido(sender: str, pregunta_usuario: str, entidades_text: str, id_ultima_intencion: str) -> None:
    """Genera un mensaje para solicitar la ubicación del usuario o pedir más detalles si el pedido no está completo."""
    try:
        bandera_promocion: bool = False
        bandera_revision: bool = False
        log_message(f'Iniciando función <SubflujoSolicitudPedido> para {sender}.', 'INFO')
        items_menu: list = obtener_menu()
        pedido_dict: dict = {}
        if obtener_intencion_futura(sender) == "continuacion_pedido":
            log_message(f"Continuando pedido previo para {sender}.", "INFO")
            observaciones_pedido = obtener_intencion_futura_observaciones(sender)
            mensaje_chatbot_intencion_futura: str = obtener_intencion_futura_mensaje_chatbot(sender)
            mensaje_usuario_intencion_futura: str = obtener_intencion_futura_mensaje_usuario(sender)
            pedido_dict = actualizar_pedido_con_mensaje(observaciones_pedido, pregunta_usuario, items_menu, mensaje_chatbot_intencion_futura, mensaje_usuario_intencion_futura)
            bandera_revision = True
        if not bandera_revision:
            log_message(f"Nuevo pedido para {sender}.", "INFO")
            entidades_text = normalizar_entities_items(entidades_text)
            pedido_dict = mapear_pedido_al_menu(entidades_text, items_menu)

        # --- Intento rápido: si el usuario respondió con "cantidad + producto"
        # y el pedido sigue incompleto, intentar un match directo para no quedar en loop.
        if not pedido_dict.get("order_complete", False):
            log_message(f"Intentando quick-match para {sender}.", "INFO")
            try:
                m = re.match(r'^\s*(\d+)\s+(.+)$', pregunta_usuario.strip(), flags=re.I)
                if m:
                    log_message(f"Quick-match detectado: {pregunta_usuario} -> qty={m.group(1)}, producto={m.group(2)}", "INFO")
                    qty = int(m.group(1))
                    prod_text = m.group(2).strip()
                    # usar match_item_to_menu para localizar producto
                    match = match_item_to_menu(prod_text, items_menu)
                    if match.get("found"):
                        # construir pedido mínimo aceptable
                        single_item = {
                            "requested": {"producto": prod_text},
                            "status": "found",
                            "matched": {"name": match["name"], "price": match["price"], "id": None},
                            "candidates": [],
                            "modifiers_applied": [],
                        }
                        pedido_dict = {
                            "order_complete": True,
                            "items": [{**single_item, "cantidad": qty}],
                            "total_price": round(match["price"] * qty, 2)
                        }
                        log_message(f"[SubflujoSolicitudPedido] Quick-match aplicado: {qty}x {match['name']} -> pedido auto-completado", "INFO")
            except Exception:
                logging.exception("Quick-match fallo; continúa flujo normal")
        
        if not pedido_dict.get("order_complete", False):
            log_message(f"153Pedido incompleto para {sender}.", "INFO")
            no_completo: dict = pedido_incompleto_dynamic(pregunta_usuario, items_menu, str(pedido_dict))
            send_text_response(sender, no_completo.get("mensaje"))
            guardar_intencion_futura(sender, "continuacion_pedido", str(pedido_dict), no_completo.get("mensaje"), pregunta_usuario)
            return
        pedido_info = guardar_pedido_completo(sender, pedido_dict, es_temporal=True)
        if not pedido_info or not isinstance(pedido_info, dict) or "idpedido" not in pedido_info:
            log_message(f'No se pudo crear el pedido para {sender}. pedido_info={pedido_info}', 'ERROR')
            send_text_response(sender, "Lo siento, no pude guardar tu pedido. Por favor inténtalo de nuevo más tarde.")
            return
        #items_info = guardar_ordenes(pedido_info["idpedido"], pedido_dict, sender)
        info_promociones = None
        eleccion_promocion = None
        if obtener_intencion_futura(sender) == "continuacion_promocion":
            info_promociones = obtener_intencion_futura_observaciones(sender)
            respuesta_previa_promocion = obtener_intencion_futura_mensaje_chatbot(sender)
            eleccion_promocion = interpretar_eleccion_promocion(pregunta_usuario, info_promociones, respuesta_previa_promocion, pedido_dict)
            if eleccion_promocion.get("valida_promocion"):
                actualizar_total_productos(sender, pedido_info['codigo_unico'], float(eleccion_promocion.get("total_final", pedido_info.get("total_productos", 0.0))))
                bandera_promocion = True
            else:
                no_completo: dict = pedido_incompleto_dynamic_promocion(pregunta_usuario, items_menu, str(pedido_dict))
                send_text_response(sender, no_completo.get("mensaje"))
                return
        confirmacion_modificacion_pedido: dict = generar_mensaje_confirmacion_modificacion_pedido(pedido_dict, bandera_promocion, info_promociones, eleccion_promocion)
        send_text_response(sender, confirmacion_modificacion_pedido.get("mensaje"))
        #confirmacion_pedido: dict = generar_mensaje_confirmacion_pedido(pedido_dict, bandera_promocion, info_promociones, eleccion_promocion)
        #send_text_response(sender, confirmacion_pedido.get("mensaje"))
        datos_promocion = {
            "info_promociones": info_promociones,
            "eleccion_promocion": eleccion_promocion,
            "bandera_promocion": bandera_promocion
        }
        guardar_intencion_futura(sender, "confirmacion_modificacion_pedido", pedido_info['codigo_unico'], str(pedido_dict), pregunta_usuario, datos_promocion)
        if id_ultima_intencion is None:
            log_message(f"No hay intención previa para marcar como resuelta para {sender}.", "INFO")
        else:
            log_message(f"Marcar intención como resuelta {id_ultima_intencion}.", "INFO")
            marcar_intencion_como_resuelta(id_ultima_intencion)
    except Exception as e:
        logging.error(f"Error en <SubflujoSolicitudPedido>: {e}")
        log_message(f'Error en <SubflujoSolicitudPedido>: {e}.', 'ERROR')
        send_text_response(sender, "Lo siento, hubo un error al procesar tu pedido. ¿Podrías intentarlo de nuevo?")

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

def subflujo_negacion_general(sender: str, respuesta_cliente: str, nombre_cliente: str) -> Dict[str, Any]:
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
        if anterior_intencion == "confirmar_pedido":
            codigo_unico_temp: str = obtener_intencion_futura_observaciones(sender)
            dict_temp_cancelacion: dict = generar_mensaje_cancelacion(sender, codigo_unico_temp, nombre_cliente)
            #datos_eliminar: dict = eliminar_pedido(sender, codigo_unico_temp)
            send_text_response(sender, dict_temp_cancelacion.get("mensaje"))
            borrar_intencion_futura(sender)
        elif anterior_intencion == "confirmacion_modificacion_pedido":
            datos_promocion: dict = obtener_datos_promocion(sender)
            codigo_unico_temp: str = obtener_intencion_futura_observaciones(sender)
            pedido_dict: str = obtener_intencion_futura_mensaje_chatbot(sender)
            send_text_response(sender, "Listo, entonces, ¿confirmas el pedido que te envié?")
            guardar_intencion_futura(sender, "confirmar_pedido", codigo_unico_temp, pedido_dict, "", datos_promocion)
        else:
            send_text_response(sender, "Entendido. Si necesitas algo más, no dudes en escribirme. ¡Estoy aquí para ayudarte!")
            borrar_intencion_futura(sender)
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
            items: list[dict[str, Any]] = obtener_menu()
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

def subflujo_quejas(sender: str, nombre_cliente: str, contenido_usuario: str) -> None:
    """Maneja quejas de menor nivel."""
    try:
        log_message(f'Iniciando función <SubflujoQuejas> para {sender}.', 'INFO')
        respuesta_quejas: dict = respuesta_quejas_ia(contenido_usuario, nombre_cliente, "Sierra Nevada")
        query = """
            INSERT INTO quejas (
                sender,
                queja_original,
                entidades,
                respuesta_agente,
                fecha_hora
            ) VALUES (%s, %s, %s, %s, NOW());
        """
        params = (
            sender,
            contenido_usuario,
            json.dumps({"resumen_queja": respuesta_quejas.get("resumen_queja")}),
            respuesta_quejas.get("respuesta_cordial")
        )
        execute_query(query, params)
        send_text_response(sender, respuesta_quejas.get("respuesta_cordial"))
        log_message('Registro de queja leve guardado correctamente.', 'INFO')
    except Exception as e:
        logging.error(f"Error en <SubflujoQuejas>: {e}")
        log_message(f'Error en <SubflujoQuejas>: {e}.', 'ERROR')
        raise e

def subflujo_transferencia(sender: str, nombre_cliente: str, contenido_usuario: str) -> None:
    try:
        """Maneja la transferencia a un agente humano."""
        log_message(f'Iniciando función <SubflujoTransferencia> para {sender}.', 'INFO')
        respuesta_grave: dict = respuesta_quejas_graves_ia(contenido_usuario, nombre_cliente, "Sierra Nevada")
        query: str = """
            INSERT INTO quejas_graves (
                sender,
                queja_original,
                entidades,
                respuesta_agente,
                accion_recomendada,
                resumen_ejecutivo
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            );
        """
        params = (
            sender,
            contenido_usuario,
            json.dumps({"resumen_queja": respuesta_grave.get("resumen_queja")}),
            respuesta_grave.get("respuesta_cordial"),
            respuesta_grave.get("accion_recomendada"),
            respuesta_grave.get("resumen_ejecutivo")
        )
        execute_query(query, params)
        send_text_response(sender, respuesta_grave.get("respuesta_cordial"))
        numero_admin: str = os.getenv("NUMERO_ADMIN")
        send_text_response(numero_admin, f"Nuevo caso de queja grave de {nombre_cliente} ({sender}): {contenido_usuario}")
        send_text_response(numero_admin, f"Resumen ejecutivo: {respuesta_grave.get('resumen_ejecutivo')}")
        log_message('Registro de queja grave guardado correctamente.', 'INFO')
    except Exception as e:
        log_message(f'Error en <SubflujoTransferencia>: {e}.', 'ERROR')
        raise e

def subflujo_confirmacion_pedido(sender: str, nombre_cliente: str) -> Dict[str, Any]:
    try:
        """Maneja la confirmación del pedido por parte del usuario."""
        log_message(f'Iniciando función <SubflujoConfirmacionPedido> para {sender}.', 'INFO')
        codigo_unico: str = obtener_intencion_futura_observaciones(sender)
        confirmar_dict: dict = marcar_pedido_como_definitivo(sender, codigo_unico)
        pedido_temp: dict = obtener_pedido_por_codigo_orignal(sender, codigo_unico)
        total_pedido: float = confirmar_dict.get("total_productos", 0.0)
        if total_pedido > 200000:
            numero_admin: str = os.getenv("NUMERO_ADMIN")
            send_text_response(numero_admin, f"Atención: Pedido grande confirmado por {nombre_cliente} ({sender}) por un total de {total_pedido}. Código único: {codigo_unico}.")
            send_text_response(sender, "Un asesor se comunicará contigo muy pronto.")
        mensaje_metodo_recogida: dict = solicitar_metodo_recogida(nombre_cliente, codigo_unico, "Sierra Nevada", pedido_temp.get("producto", ""))
        # Normalizar respuesta: aceptar dict {"mensaje": "..."} o str
        
        if isinstance(mensaje_metodo_recogida, dict):
            texto_a_enviar = mensaje_metodo_recogida.get("mensaje") or ""
        elif isinstance(mensaje_metodo_recogida, str):
            texto_a_enviar = mensaje_metodo_recogida
        else:
            log_message(f"subflujo_confirmacion_pedido: respuesta inesperada de solicitar_metodo_recogida: {type(mensaje_metodo_recogida)}", "WARN")
            texto_a_enviar = f"{nombre_cliente}, tu pedido ({codigo_unico}) quedó delicioso! ¿Domicilio o recoges en el local?"
        send_text_response(sender, texto_a_enviar)
        guardar_intencion_futura(sender, "metodo_recogida", codigo_unico)
        log_message(f'Pedido {confirmar_dict.get("codigo_unico")} confirmado correctamente para {sender}.', 'INFO')
    except Exception as e:
        log_message(f'Error en <SubflujoConfirmacionPedido>: {e}.', 'ERROR')
        raise e

def subflujo_consulta_menu(sender: str, nombre_cliente: str) -> None:
    """Maneja la consulta del menú por parte del usuario."""
    try:
        log_message(f'Iniciando función <SubflujoConsultaMenu> para {sender}.', 'INFO')
        menu = obtener_menu()
        promociones_list: list = obtener_promociones_activas()
        mensaje_menu: dict = enviar_menu_digital(nombre_cliente, "Sierra Nevada", menu, promociones_list)
        send_text_response(sender, mensaje_menu.get("mensaje"))
        send_pdf_response(sender)
        log_message(f'Menú enviado correctamente a {sender}.', 'INFO')
    except Exception as e:
        log_message(f'Error en <SubflujoConsultaMenu>: {e}.', 'ERROR')
        raise e

def subflujo_consulta_pedido(sender: str, nombre_cliente: str, entidades: str, pregunta_usuario: str) -> None:
    try:
        """Maneja la consulta del estado del pedido por parte del usuario."""
        log_message(f'Iniciando función <SubflujoConsultaPedido> para {sender}.', 'INFO')
        if isinstance(entidades, dict):
            entidades_dict = entidades
        else:
            try:
                entidades_dict = json.loads(entidades)
            except:  # noqa: E722
                entidades_dict = ast.literal_eval(str(entidades))
        pedido_id: str = entidades_dict.get("pedido_id", "")
        pedido_info: dict = obtener_estado_pedido_por_codigo(sender, pedido_id)
        respuesta_consulta_pedido: dict = responder_sobre_pedido(nombre_cliente, "Sierra Nevada", pedido_info, pregunta_usuario)
        send_text_response(sender, respuesta_consulta_pedido.get("mensaje"))
        guardar_intencion_futura(sender, respuesta_consulta_pedido.get("futura_intencion", "consulta_menu"))
        log_message(f'Consulta de pedido respondida correctamente para {sender}.', 'INFO')
    except Exception as e:
        log_message(f'Error en <SubflujoConsultaPedido>: {e}.', 'ERROR')
        raise e

def subflujo_promociones(sender: str, nombre_cliente: str, pregunta_usuario: str) -> None:
    """Maneja la consulta de promociones por parte del usuario."""
    try:
        log_message(f'Iniciando función <SubflujoPromociones> para {sender}.', 'INFO')
        promociones_info: list = obtener_promociones_activas()
        respuesta = responder_sobre_promociones(
            nombre=nombre_cliente,
            nombre_local="Sierra Nevada",
            promociones_info=promociones_info,
            pregunta_usuario=pregunta_usuario
        )
        send_text_response(sender, respuesta["mensaje"])
        guardar_intencion_futura(sender, respuesta.get("futura_intencion", "continuacion_promocion"), str(promociones_info), respuesta["mensaje"], pregunta_usuario)
        log_message(f'Promociones enviadas correctamente a {sender}.', 'INFO')
    except Exception as e:
        log_message(f'Error en <SubflujoPromociones>: {e}.', 'ERROR')
        raise e

def subflujo_medio_pago(sender: str, nombre_cliente: str, respuesta_usuario: str) -> None:
    try:
        """Maneja la selección del modo de pago por parte del usuario."""
        log_message(f'Iniciando función <SubflujoMedioPago> para {sender}.', 'INFO')
        codigo_unico: str = obtener_intencion_futura_observaciones(sender)
        medio_pago_real: str = mapear_modo_pago(respuesta_usuario)
        datos_actualizados: dict = actualizar_medio_pago(sender, codigo_unico, medio_pago_real)
        if medio_pago_real =="efectivo":
            mensaje_pago: str = f"¡Perfecto {nombre_cliente}! Has seleccionado pagar en efectivo al momento de la entrega o recogida de tu pedido ({codigo_unico}). Por favor, ten el monto exacto listo para facilitar la transacción. ¡Gracias por tu preferencia!"
            send_text_response(sender, mensaje_pago)
            borrar_intencion_futura(sender)
            marcar_estemporal_true_en_pedidos(sender,codigo_unico)
            return
        elif medio_pago_real == "tarjeta":
            try:
                query = """
                    SELECT total_productos
                    FROM public.pedidos
                    WHERE codigo_unico = %s;"""
                params = (codigo_unico,)
                # Pedimos también las columnas para mapear filas a dicts si es necesario
                result = execute_query_columns(query, params, fetchone=False, return_columns=True)
                if isinstance(result, tuple) and len(result) == 2:
                    data, cols = result
                else:
                    data = result
                    cols = None

                if not data:
                    send_text_response(sender, "Lo siento nuestra plataforma de pagos esta fallando, por favor intenta más tarde o elige otro medio de pago.")
                    return

                first_row = data[0]
                if isinstance(first_row, dict):
                    monto_raw = first_row.get('total_productos')
                elif cols:
                    row = dict(zip(cols, first_row))
                    monto_raw = row.get('total_productos')
                else:
                    # fallback: tomar la primera columna
                    monto_raw = first_row[0] if isinstance(first_row, (list, tuple)) and len(first_row) > 0 else first_row

                try:
                    monto = int(round(float(monto_raw))) if monto_raw is not None else 0
                except Exception:
                    monto = 0

                log_message(f"[SubflujoMedioPago] Generando link de pago para {sender} por monto {monto}.", "INFO")
                monto = float(monto_raw)            # por ejemplo 31900.0
                monto_cents = int(round(monto * 100))  # 3190000
                pago = generar_link_pago(monto_cents,sender)
                if pago is None:
                    send_text_response(sender, "No fue posible generar el link de pago ahora mismo. Intenta más tarde o elige otro medio.")
                    return
                form_url, order_id = pago
                # Guardar referencia del pago en la BD (si falla, informar pero continuar)
                try:
                    guardar_id_pago_en_db(order_id, codigo_unico)
                except Exception as e:
                    log_message(f"Advertencia: no se pudo guardar id_pago en DB: {e}", "WARN")
                # Enviar link al cliente con instrucciones claras
                mensaje_pago = (
                    f"¡Perfecto {nombre_cliente}! Para completar tu pedido ({codigo_unico}) puedes pagar aquí:\n{form_url}\n\n"
                    "Una vez realices el pago, por favor envíame el comprobante o espera la confirmación automática."
                )
                send_text_response(sender, mensaje_pago)
                guardar_intencion_futura(sender, "esperando_confirmacion_pago", codigo_unico)
                return
            except Exception as e:
                log_message(f"Error generando/enviando link de pago: {e}", "ERROR")
                send_text_response(sender, "Hubo un problema generando el link de pago. Puedes intentar pagar en el local o probar otro método.")
                return
        else:
            numero_admin: str = os.getenv("NUMERO_ADMIN")
            send_text_response(numero_admin, f"Atención: Medio de pago no reconocido '{respuesta_usuario}' seleccionado por {nombre_cliente} ({sender}) para el pedido {codigo_unico}.")
            send_text_response(sender, f"Te transferire a un asesor para que te ayude con el medio de pago. en breves momentos te escribira desde {numero_admin}")
            marcar_estemporal_true_en_pedidos(sender,codigo_unico)
    except Exception as e:
        log_message(f'Error en <SubflujoMedioPago>: {e}.', 'ERROR')
        raise e

def subflujo_modificacion_pedido(sender: str, nombre_cliente: str, pregunta_usuario: str) -> dict:
    """Maneja la modificación del pedido por parte del usuario."""
    try:
        log_message(f'Iniciando función <SubflujoModificacionPedido> para {sender}.', 'INFO')
        bandera_promocion: bool = False
        items_menu: list = obtener_menu()
        pedido_dict: dict = {}
        pedido_anterior = obtener_intencion_futura_mensaje_chatbot(sender)
        nuevos_elementos: str = pregunta_usuario
        codigo_unico_anterior: str = obtener_intencion_futura_observaciones(sender)
        eliminar_pedido(sender, codigo_unico_anterior)
        pedido_dict = actualizar_pedido_con_mensaje_modificacion(pedido_anterior, items_menu, nuevos_elementos)
        if not pedido_dict.get("order_complete", False):
            no_completo: dict = pedido_incompleto_dynamic(pregunta_usuario, items_menu, str(pedido_dict))
            send_text_response(sender, no_completo.get("mensaje"))
            guardar_intencion_futura(sender, "continuacion_pedido", str(pedido_dict), no_completo.get("mensaje"), pregunta_usuario)
            return
        pedido_info = guardar_pedido_completo(sender, pedido_dict, es_temporal=True)
        if not pedido_info or not isinstance(pedido_info, dict) or "idpedido" not in pedido_info:
            log_message(f'No se pudo crear el pedido para {sender}. pedido_info={pedido_info}', 'ERROR')
            send_text_response(sender, "Lo siento, no pude guardar tu pedido. Por favor inténtalo de nuevo más tarde.")
            return
        #items_info = guardar_ordenes(pedido_info["idpedido"], pedido_dict, sender)
        info_promociones = None
        eleccion_promocion = None
        if obtener_intencion_futura(sender) == "continuacion_promocion":
            info_promociones = obtener_intencion_futura_observaciones(sender)
            respuesta_previa_promocion = obtener_intencion_futura_mensaje_chatbot(sender)
            eleccion_promocion = interpretar_eleccion_promocion(pregunta_usuario, info_promociones, respuesta_previa_promocion, pedido_dict)
            send_text_response(sender, f"Elección de promoción interpretada: {str(eleccion_promocion)}")
            if eleccion_promocion.get("valida_promocion"):
                actualizar_total_productos(sender, pedido_info['codigo_unico'], float(eleccion_promocion.get("total_final", pedido_info.get("total_productos", 0.0))))
                bandera_promocion = True
            else:
                no_completo: dict = pedido_incompleto_dynamic_promocion(pregunta_usuario, items_menu, str(pedido_dict))
                send_text_response(sender, no_completo.get("mensaje"))
                return
        confirmacion_modificacion_pedido: dict = generar_mensaje_confirmacion_modificacion_pedido(pedido_dict, bandera_promocion, info_promociones, eleccion_promocion)
        send_text_response(sender, confirmacion_modificacion_pedido.get("mensaje"))
        #confirmacion_pedido: dict = generar_mensaje_confirmacion_pedido(pedido_dict, bandera_promocion, info_promociones, eleccion_promocion)
        #send_text_response(sender, confirmacion_pedido.get("mensaje"))
        datos_promocion = {
            "info_promociones": info_promociones,
            "eleccion_promocion": eleccion_promocion,
            "bandera_promocion": bandera_promocion
        }
        guardar_intencion_futura(sender, "confirmacion_modificacion_pedido", pedido_info['codigo_unico'], str(pedido_dict), pregunta_usuario, datos_promocion)
    except Exception as e:
        log_message(f'Error en <SubflujoModificacionPedido>: {e}.', 'ERROR')
        raise e

def subflujo_confirmar_direccion(sender: str, nombre_cliente: str) -> None:
    try:
        """Maneja la recepción de la dirección para el domicilio."""
        log_message(f'Iniciando función <SubflujoConfirmarDireccion> para {sender}.', 'INFO')
        id_restaurante = os.environ.get("ID_RESTAURANTE", "5")
        datos_cliente_temp: dict = obtener_datos_cliente_por_telefono(sender, id_restaurante)
        latitud_cliente: float = datos_cliente_temp.get("latitud", 0.0)
        longitud_cliente: float = datos_cliente_temp.get("longitud", 0.0)
        id_sede: str = datos_cliente_temp.get("id_sede", "")
        codigo_unico: str = obtener_intencion_futura_observaciones(sender)
        # Cálculo del tiempo y valor de envío
        resultado = orquestador_tiempo_y_valor_envio(
            latitud_cliente,
            longitud_cliente,
            id_sede,
            sender,
            id_restaurante
        )
        if not resultado:
            send_text_response(
                sender,
                f"Puedes volver a enviar tu dirección {nombre_cliente}, no pude calcular el valor y tiempo de envío para tu dirección. ¿Podrías verificarla o enviarme otra?"
            )
            return
        valor, duracion, distancia, direccion_envio = resultado
        # Actualizar los costos y tiempos del pedido
        datos_actualizados: dict = actualizar_costos_y_tiempos_pedido(
            sender,
            codigo_unico,
            valor,
            duracion,
            distancia
        )
        if not datos_actualizados.get("actualizado"):
            send_text_response(sender, f"Lo siento, no pude confirmar tu dirección {direccion_envio}")
            return
        mensaje_pagar: dict = solicitar_medio_pago(
            nombre_cliente,
            codigo_unico,
            "Sierra Nevada",
            datos_actualizados.get("total_final")
        )
        # Enviar solo mensaje como en versión 1
        send_text_response(sender, mensaje_pagar.get("mensaje"))
        # Actualizar intención futura
        guardar_intencion_futura(sender, "medio_pago", codigo_unico)
        log_message(f'Valor y tiempo de envío calculados correctamente para {sender}.', 'INFO')

    except Exception as e:
        log_message(f'Error en <SubflujoConfirmarDireccion>: {e}.', 'ERROR')
        raise e

    except Exception as e:
        log_message(f'Error en <SubflujoDomicilioValor>: {e}.', 'ERROR')
        raise e

def generar_pago_domicilio(sender: str, nombre_cliente: str, codigo_unico: str, datos_actualizados: dict) -> None:
            # Intentar generar link de pago inmediato usando total_final; si falla,
        # caemos al comportamiento anterior (guardar intención para invitar a pagar).
        total_final = datos_actualizados.get("total_final")
        if total_final is None:
            try:
                pedido_tmp = obtener_pedido_por_codigo(sender, codigo_unico)
                total_final = pedido_tmp.get("total_final") if isinstance(pedido_tmp, dict) else None
            except Exception:
                total_final = None

        try:
            monto_val = float(total_final) 
            monto_cents = int(round(monto_val * 100))
            pago = generar_link_pago(monto_cents,sender)
            if pago:
                form_url, order_id = pago
                try:
                    guardar_id_pago_en_db(order_id, codigo_unico)
                except Exception as e:
                    log_message(f"Advertencia: no se pudo guardar id_pago en DB: {e}", "WARN")
                mensaje_link = (
                    f"¡Perfecto {nombre_cliente}! Puedes completar tu pago aquí:\n{form_url}\n\n"
                    "Una vez realices el pago, por favor envíame el comprobante o espera la confirmación automática."
                )
                send_text_response(sender, mensaje_link)
                guardar_intencion_futura(sender, "esperando_confirmacion_pago", codigo_unico)
                log_message(f'Valor y tiempo de envío calculados correctamente y link enviado a {sender}.', 'INFO')
                return
            else:
                log_message(f"Generación de link de pago fallida para {sender}.", "WARN")
                logging.warning(f"Generación de link de pago fallida para {sender}.")
                send_text_response(sender, f"No hemos podido generar el link de pago ahora mismo. Por favor, te comunicare con un asesor que te escribira desde: {os.getenv('NUMERO_ADMIN')}.")
                send_text_response(os.getenv("NUMERO_ADMIN"), f"No se pudo generar link de pago para {nombre_cliente} ({sender}) por un total de {total_final}. Código único: {codigo_unico}.")
        except Exception as e:
            log_message(f"Advertencia: no se pudo generar link de pago inmediato: {e}", "WARN")
def subflujo_recoger_restaurante(sender: str, nombre_cliente: str):
    try:
        log_message("Empieza subflujo recoger restaurante", "INFO")
        mensaje_sede: str = generar_mensaje_seleccion_sede(nombre_cliente)
        send_text_response(sender, mensaje_sede)
        codigo_unico = obtener_intencion_futura_observaciones(sender)
        guardar_intencion_futura(sender, "eleccion_sede", codigo_unico)
    except Exception as e:
        log_message(f"Error en subflujo recoger restaurante {e}", "ERROR") 
        raise e

def subflujo_eleccion_sede(sender: str, nombre_cliente: str, texto_cliente):
    try:
        log_message("Empieza subflujo eleccion sede", "INFO")
        codigo_unico: str = obtener_intencion_futura_observaciones(sender)
        datos_mapeo_sede: dict = mapear_sede_cliente(texto_cliente)
        if datos_mapeo_sede.get("error"):
            send_text_response(sender, "Disculpa, la sede que escribiste no existe, ¿puedes volver a escribir con mayor claridad?")
            return
        id_sede = datos_mapeo_sede.get("id_sede")
        id_restaurante = os.environ.get("ID_RESTAURANTE", "5")
        latitud_cliente = datos_mapeo_sede.get("latitud_sede")
        longitud_cliente = datos_mapeo_sede.get("longitud_sede")
        direccion_cliente = datos_mapeo_sede.get("direccion_sede")
        if not set_sede_cliente(id_sede, sender, id_restaurante) or not set_lat_lon(sender, latitud_cliente, longitud_cliente, id_restaurante) or not set_direccion_cliente(sender, direccion_cliente, id_restaurante):
            send_text_response(sender, "Hubo un error, escribe Hola y vuelve a intentarlo.")
            return None
        nombre_sede = datos_mapeo_sede.get("nombre_sede")
        duracion = calcular_tiempo_pedido("0 min", id_sede)
        tiempo_pedido: str = formatear_tiempo_entrega(duracion)
        datos_actualizados: dict = actualizar_costos_y_tiempos_pedido(sender, codigo_unico, 0, tiempo_pedido, 0)
        if not datos_actualizados.get("actualizado"):
            send_text_response(sender, "Lo siento, no pude confirmar tu pedido")
            return
        valor_ultimo = datos_actualizados.get("total_final")
        mensaje = generar_mensaje_recogida_invitar_pago(
            nombre_cliente=nombre_cliente,
            nombre_sede=nombre_sede,
            direccion_sede=direccion_cliente,
            valor_total_pedido=valor_ultimo,
            tiempo_pedido=tiempo_pedido,
            codigo_pedido=codigo_unico
        )
        send_text_response(sender, mensaje)
        log_message("Termina subflujo eleccion sede", "INFO")
    except Exception as e:
        log_message(f"Error en subflujo eleccion sede {e}", "ERROR")
        raise e

def subflujo_verificación_pago(sender: str, nombre_cliente: str, respuesta_usuario: str) -> None:
    try:
        log_message(f'Iniciando función <SubflujoVerificacionPago> para {sender}.', 'INFO')
        codigo_unico: str = obtener_intencion_futura_observaciones(sender)
        query="""
            SELECT id_pago
            FROM public.pedidos
            WHERE codigo_unico = %s;"""
        params=(codigo_unico,)
        order_row = execute_query(query, params, fetchone=True)
        log_message(f"[SubflujoVerificacionPago] Resultado consulta id_pago para codigo_unico {codigo_unico}: {order_row}", "INFO")
        logging.info(f"[SubflujoVerificacionPago] Resultado consulta id_pago para codigo_unico {codigo_unico}: {order_row}")
        # execute_query devuelve una tupla/row; extraer el valor si es necesario
        order_id = None
        if order_row is None:
            order_id = None
        elif isinstance(order_row, (list, tuple)):
            order_id = order_row[0]
        else:
            order_id = order_row

        if not order_id:
            send_text_response(sender, f"Hola {nombre_cliente}, no encontramos un un pago asociado a tu pedido {codigo_unico}.")
            return
        logging.info(f"[SubflujoVerificacionPago] ID de pago extraído: {order_id}")
        log_message(f"[SubflujoVerificacionPago] ID de pago extraído: {order_id}", "INFO")
        resultado_validacion = validar_pago(order_id)
        logging.info(f"[SubflujoVerificacionPago] Resultado de validar_pago: {resultado_validacion}")
        log_message(f"[SubflujoVerificacionPago] Resultado de validar_pago: {resultado_validacion}", "INFO")
        # `validar_pago` devuelve un dict con 'resultado' ('aprobado'|'pendiente'|'rechazado')
        if isinstance(resultado_validacion, dict) and resultado_validacion.get("resultado") == "aprobado":
            send_text_response(sender, f"¡Gracias {nombre_cliente}! Hemos confirmado el pago de tu pedido {codigo_unico}. Estamos preparando todo para ti.")
            borrar_intencion_futura(sender)
            marcar_estemporal_true_en_pedidos(sender,codigo_unico)
        else:
            send_text_response(sender, f"Hola {nombre_cliente}, aún no hemos recibido la confirmación de tu pago para el pedido {codigo_unico}. Por favor, verifica tu pago o intenta nuevamente.")
    except Exception as e:
        log_message(f'Error en <SubflujoVerificacionPago>: {e}.', 'ERROR')
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
        elif (clasificacion_mensaje == "solicitud_pedido" or clasificacion_mensaje == "continuacion_promocion") and obtener_intencion_futura(sender) != "confirmacion_modificacion_pedido":
            subflujo_solicitud_pedido(sender, pregunta_usuario, entidades_text, id_ultima_intencion)
        elif clasificacion_mensaje == "confirmacion_general":
            return subflujo_confirmacion_general(sender, pregunta_usuario)
        elif clasificacion_mensaje == "negacion_general":
            subflujo_negacion_general(sender, pregunta_usuario, nombre_cliente)
        elif clasificacion_mensaje == "consulta_promociones":
            subflujo_promociones(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "consulta_menu" and type_text != "pregunta" and obtener_intencion_futura(sender) != "eleccion_sede":
            subflujo_consulta_menu(sender, nombre_cliente)
            borrar_intencion_futura(sender)
        elif clasificacion_mensaje == "preguntas_generales" or (clasificacion_mensaje == "consulta_menu" and (type_text == "pregunta" or type_text == "preguntas_generales")):
            subflujo_preguntas_generales(sender, pregunta_usuario, nombre_cliente)
        elif clasificacion_mensaje == "sin_intencion":
            subflujo_sin_intencion(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "quejas":
            subflujo_quejas(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "transferencia":
            subflujo_transferencia(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "confirmar_pedido":
            subflujo_confirmacion_pedido(sender, nombre_cliente)
        elif clasificacion_mensaje == "consulta_pedido":
            subflujo_consulta_pedido(sender, nombre_cliente, entidades_text, pregunta_usuario)
        elif clasificacion_mensaje == "validacion_pago":
            intent_futura = obtener_intencion_futura(sender)
            # Si estamos en el paso de elegir medio de pago, procesar selección
            if intent_futura == "medio_pago":
                subflujo_medio_pago(sender, nombre_cliente, pregunta_usuario)
            # Si ya se generó un link y estamos esperando confirmación, verificar pago
            elif intent_futura in ("esperando_confirmacion_pago", "pagar_pedido"):
                subflujo_verificación_pago(sender, nombre_cliente, pregunta_usuario)
            else:
                # Fallback: intentar verificar el pago por si el usuario envió comprobante
                subflujo_verificación_pago(sender, nombre_cliente, pregunta_usuario)
        elif (clasificacion_mensaje == "modificacion_pedido" or clasificacion_mensaje == "continuacion_pedido" or clasificacion_mensaje == "solicitud_pedido" or clasificacion_mensaje == "solicitud_pedido") and obtener_intencion_futura(sender) == "confirmacion_modificacion_pedido":
            subflujo_modificacion_pedido(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "confirmacion_modificacion_pedido":
            send_text_response(sender, "Escribe lo que quieras modificar de tu pedido de manera clara y específica.")
        elif clasificacion_mensaje == "domicilio":
            id_restaurante = os.environ.get("ID_RESTAURANTE", "5")
            # Si ya tiene dirección registrada, recuperarla y mostrarla
            if validate_direction_first_time(sender, id_restaurante=id_restaurante):
                direccion = obtener_direccion(sender, id_restaurante)
                if direccion:
                    mensaje = direccion_bd(nombre_cliente, direccion)
                    send_text_response(sender, mensaje)
                    guardar_intencion_futura(sender, "confirmar_direccion", obtener_intencion_futura_observaciones(sender))
                else:
                    # caso raro: flag indica primera vez pero no hay dirección en BD
                    send_text_response(sender, "Gracias. Por favor, proporciona tu dirección completa para el domicilio.")
                    guardar_intencion_futura(sender, "primera_direccion_domicilio", obtener_intencion_futura_observaciones(sender))
            else:
                # No tiene dirección: solicitarla al usuario
                send_text_response(sender, "Por favor, proporciona tu dirección completa para el domicilio. No olvides incluir detalles como calle, número, ciudad y cualquier referencia adicional. También puedes enviarme tu ubicación si lo prefieres.")
                codigo_unico: str = obtener_intencion_futura_observaciones(sender)
                guardar_intencion_futura(sender, "primera_direccion_domicilio", codigo_unico)
        elif clasificacion_mensaje == "confirmar_direccion":
            subflujo_confirmar_direccion(sender, nombre_cliente)
        elif clasificacion_mensaje == "recoger_restaurante":
            subflujo_recoger_restaurante(sender, nombre_cliente)
        elif (clasificacion_mensaje == "direccion" or clasificacion_mensaje == "consulta_menu") and obtener_intencion_futura(sender) == "eleccion_sede":
            subflujo_eleccion_sede(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "esperando_confirmacion_pago":
            subflujo_verificación_pago(sender, nombre_cliente, pregunta_usuario)
        elif (clasificacion_mensaje == "direccion") and obtener_intencion_futura(sender) == "primera_direccion_domicilio":
            subflujo_confirmar_direccion(sender, nombre_cliente)
        elif (clasificacion_mensaje == "continuacion_pedido") and obtener_intencion_futura(sender) == "eleccion_sede":
            subflujo_eleccion_sede(sender, nombre_cliente, pregunta_usuario)
        elif (clasificacion_mensaje == "continuacion_pedido"):
            send_text_response(sender, "Por favor, especifica claramente qué deseas agregar o modificar en tu pedido.")
        elif (clasificacion_mensaje == "direccion") and obtener_intencion_futura(sender) == "confirmar direccion":
            try:
                direccion = obtener_direccion(sender, os.environ.get("ID_RESTAURANTE", "5"))
                log_message(f"Dirección antes de corrección: {direccion}", "INFO")
                direccion = corregir_direccion(direccion,pregunta_usuario)
                log_message(f"Dirección después de corrección: {direccion}", "INFO")
                mensaje = direccion_bd(nombre_cliente, direccion)
                send_text_response(sender, mensaje)
                guardar_intencion_futura(sender, "confirmar_direccion", obtener_intencion_futura_observaciones(sender))
                execute_query("""
                            UPDATE clientes_whatsapp
                            SET direccion_google = %s
                            WHERE telefono = %s AND id_restaurante = %s;
                                """, (direccion, sender, os.environ.get("ID_RESTAURANTE", "5")))
                log_message(f"Dirección corregida guardada en BD para {sender}", "INFO")
            except Exception as e:
                log_message(f"Error al corregir dirección: {e}", "ERROR")
                send_text_response(sender, "Hubo un error al procesar tu dirección. Por favor, intenta nuevamente.")
        elif clasificacion_mensaje == "mas_datos_direccion":
            try:
                direccion = obtener_direccion(sender, os.environ.get("ID_RESTAURANTE", "5"))
                log_message(f"Dirección antes de corrección: {direccion}", "INFO")
                direccion = corregir_direccion(direccion,pregunta_usuario)
                log_message(f"Dirección después de corrección: {direccion}", "INFO")
                mensaje = direccion_bd(nombre_cliente, direccion)
                send_text_response(sender, mensaje)
                guardar_intencion_futura(sender, "confirmar_direccion", obtener_intencion_futura_observaciones(sender))
                execute_query("""
                            UPDATE clientes_whatsapp
                            SET direccion_google = %s
                            WHERE telefono = %s AND id_restaurante = %s;
                                """, (direccion, sender, os.environ.get("ID_RESTAURANTE", "5")))
                log_message(f"Dirección corregida guardada en BD para {sender}", "INFO")
            except Exception as e:
                log_message(f"Error al corregir dirección: {e}", "ERROR")
                send_text_response(sender, "Hubo un error al procesar tu dirección. Por favor, intenta nuevamente.")
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
