# utils_subflujos.py
# Last modified: 2025-21-12 Juan Agudelo

import json
import os
import random
import logging
from typing import Any, Dict
import re
from utils_contexto import obtener_x_respuestas
from utils_registration import validate_direction_first_time

# --- IMPORTS INTERNOS --- #
from utils import (
    actualizar_medio_entrega,
    actualizar_medio_pago,
    calcular_minutos,
    extraer_ultimo_mensaje,
    marcar_estemporal_true_en_pedidos,
    obtener_direccion,
    actualizar_costos_y_tiempos_pedido,
    actualizar_total_productos,
    guardar_intencion_futura,
    guardar_pedido_completo,
    log_message,
    marcar_intencion_como_resuelta,
    marcar_pedido_como_definitivo,
    match_item_to_menu,
    obtener_datos_cliente_por_telefono,
    obtener_estado_pedido_por_codigo,
    obtener_intencion_futura_mensaje_chatbot,
    obtener_intencion_futura_observaciones,
    obtener_menu,
    obtener_pedido_por_codigo,
    obtener_pedido_por_codigo_orignal,
    obtener_promociones_activas,
    send_pdf_response,
    send_text_response,
    obtener_intencion_futura,
    borrar_intencion_futura,
    normalizar_especificaciones
)
from utils_chatgpt import clasificador_consulta_menu, generar_mensaje_sin_intencion,get_direction, clasificar_pregunta_menu_chatgpt, enviar_menu_digital, generar_mensaje_confirmacion_modificacion_pedido, generar_mensaje_recogida_invitar_pago, interpretar_eleccion_promocion, mapear_pedido_al_menu, mapear_sede_cliente, pedido_incompleto_dynamic, pedido_incompleto_dynamic_promocion, responder_pregunta_menu_chatgpt, responder_sobre_pedido, responder_sobre_promociones, respuesta_quejas_graves_ia, respuesta_quejas_ia, saludo_dynamic, solicitar_medio_pago, solicitar_metodo_recogida,direccion_bd,mapear_modo_pago,extraer_info_personal,clasificar_confirmación_general,get_tiempo_recogida
from utils_database import execute_query
from utils_google import calcular_distancia_entre_sede_y_cliente, calcular_tiempo_pedido, formatear_tiempo_entrega, geocode_and_assign, orquestador_tiempo_y_valor_envio
from utils_pagos import generar_link_pago, guardar_id_pago_en_db, validar_pago
from utils_registration import validate_personal_data,save_personal_data_partial,check_and_mark_datos_personales
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
        items_menu: list = obtener_menu()
        pedido_dict: dict = {}
        if not bandera_revision:
            log_message(f"Nuevo pedido para {sender}.", "INFO")
            pedido_dict = mapear_pedido_al_menu(pregunta_usuario, items_menu)

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
        pedido_info = guardar_pedido_completo(sender, pedido_dict, es_temporal=True)   
        if not pedido_dict.get("order_complete", False):
            log_message(f"153Pedido incompleto para {sender}.", "INFO")
            no_completo: dict = pedido_incompleto_dynamic(pregunta_usuario, items_menu, str(pedido_dict))
            send_text_response(sender, no_completo.get("mensaje"))
            guardar_intencion_futura(sender, "continuacion_pedido", str(pedido_dict), no_completo.get("mensaje"), pregunta_usuario)
            return
        if not pedido_info or not isinstance(pedido_info, dict) or "idpedido" not in pedido_info:
            log_message(f'No se pudo crear el pedido para {sender}. pedido_info={pedido_info}', 'ERROR')
            send_text_response(sender, "Lo siento, no pude guardar tu pedido. Por favor inténtalo de nuevo más tarde.")
            return
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
        confirmacion_modificacion_pedido: dict = generar_mensaje_confirmacion_modificacion_pedido(pedido_dict,items_menu, bandera_promocion, info_promociones, eleccion_promocion)
        send_text_response(sender, confirmacion_modificacion_pedido.get("mensaje"))
        datos_promocion = {
            "info_promociones": info_promociones,
            "eleccion_promocion": eleccion_promocion,
            "bandera_promocion": bandera_promocion
        }
        guardar_intencion_futura(sender, "confirmar_pedido", pedido_info['codigo_unico'], str(pedido_dict), pregunta_usuario, datos_promocion)
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
        items = obtener_menu()
        intencion = clasificar_confirmación_general(respuesta_cliente,items)
        log_message(f'Intención general clasificada: {intencion}', 'INFO')
        if intencion.get("intencion") == "solicitud_pedido":
            return {
                "intencion_respuesta": "solicitud_pedido",
                "continuidad": True,
                "observaciones": respuesta_cliente
            }
        elif intencion.get("intencion") == "confirmar_direccion":
            return {
                "intencion_respuesta": "confirmar_direccion",
                "continuidad": True,
                "observaciones": respuesta_cliente
            }
        elif intencion.get("intencion") == "confirmar_pedido":
            return{
                "intencion_respuesta": "confirmar_pedido",
                "continuidad": True,
                "observaciones": respuesta_cliente
            }
        elif intencion.get("intencion") == "sin_intencion":
            items= obtener_menu()
            mensaje=generar_mensaje_sin_intencion(respuesta_cliente, items)
            send_text_response(sender, mensaje)
            return
        return
    except Exception as e:
        logging.error(f"Error en <SubflujoConfirmacionGeneral>: {e}")
        log_message(f'Error en <SubflujoConfirmacionGeneral>: {e}.', 'ERROR')
        raise e

def subflujo_negacion_general(sender: str, respuesta_cliente: str, nombre_cliente: str) -> Dict[str, Any]:
    """Maneja el caso en que no se detecta una intención específica, con ayuda de IA."""
    try:
        items= obtener_menu()
        mensaje=generar_mensaje_sin_intencion(respuesta_cliente, items)
        send_text_response(sender, mensaje)
        return
    except Exception as e:
        logging.error(f"Error en <SubflujoNegacionGeneral>: {e}")
        log_message(f'Error en <SubflujoNegacionGeneral>: {e}.', 'ERROR')
        raise e

def subflujo_preguntas_generales(sender: str, pregunta_usuario: str, nombre_cliente: str) -> None:
    """Maneja preguntas generales del usuario."""
    try:
        items: list[dict[str, Any]] = obtener_menu()
        clasificacion: dict = clasificar_pregunta_menu_chatgpt(pregunta_usuario,items)
        clasificacion_tipo = clasificacion.get("clasificacion", "no_relacionada")
        if clasificacion_tipo == "relacionada":   
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

def subflujo_quejas(sender: str, nombre_cliente: str, contenido_usuario: str) -> None:
    """Maneja quejas de menor nivel."""
    try:
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
        log_message(f"Notificando al administrador {numero_admin} sobre queja grave de {nombre_cliente} ({sender}).", "INFO")
        send_text_response(numero_admin, f"Nuevo caso de solicitud de transferencia de {nombre_cliente} ({sender}): {contenido_usuario}")
        send_text_response(numero_admin, f"Resumen ejecutivo: {respuesta_grave.get('resumen_ejecutivo')}")
        log_message('Registro de queja grave guardado correctamente.', 'INFO')
    except Exception as e:
        log_message(f'Error en <SubflujoTransferencia>: {e}.', 'ERROR')
        raise e

def subflujo_confirmacion_pedido(sender: str, nombre_cliente: str) -> Dict[str, Any]:
    try:
        """Maneja la confirmación del pedido por parte del usuario."""
        codigo_unico: str = obtener_intencion_futura_observaciones(sender)
        confirmar_dict: dict = marcar_pedido_como_definitivo(sender, codigo_unico)
        pedido_temp: dict = obtener_pedido_por_codigo_orignal(sender, codigo_unico)
        total_pedido: float = pedido_temp.get("total_productos", 0.0)
        if total_pedido > 200000:
            numero_admin: str = os.getenv("NUMERO_ADMIN")
            send_text_response(numero_admin, f"Atención: Pedido grande confirmado por {nombre_cliente} ({sender}) por un total de {total_pedido}. Código único: {codigo_unico}.")
            send_text_response(sender, "El valor de tu pedido es muy alto, Un asesor se comunicará contigo muy pronto.")
        else:
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

def subflujo_consulta_menu(sender: str, nombre_cliente: str, pregunta_usuario: str,entidades: str) -> None:
    """Maneja la consulta del menú por parte del usuario."""
    try:
        menu = obtener_menu()
        promociones_list: list = obtener_promociones_activas()
        clasificacion=clasificador_consulta_menu(pregunta_usuario)
        log_message(f'Clasificación de consulta de menú: {clasificacion}', 'INFO')
        if clasificacion=="consulta_menu":
            mensaje_menu: dict = enviar_menu_digital(nombre_cliente, "Sierra Nevada", menu, promociones_list)
            send_text_response(sender, mensaje_menu.get("mensaje"))
            send_pdf_response(sender)
            log_message(f'Menú enviado correctamente a {sender}.', 'INFO')
        elif clasificacion=="aclaracion_producto":
            mensaje=responder_pregunta_menu_chatgpt(pregunta_usuario, menu)
            log_message(f'Respuesta generada para consulta de producto: {mensaje}', 'INFO')
            send_text_response(sender, mensaje.get("respuesta"))
            log_message(f'Consulta de producto respondida correctamente a {sender}.', 'INFO')
            guardar_intencion_futura(sender, "pregunta_pedido",str(entidades),"",pregunta_usuario,"")
    except Exception as e:
        log_message(f'Error en <SubflujoConsultaMenu>: {e}.', 'ERROR')
        raise e

def subflujo_consulta_pedido(sender: str, nombre_cliente: str, entidades: str, pregunta_usuario: str) -> None:
    try:
        """Maneja la consulta del estado del pedido por parte del usuario."""
        query_pendientes = """
                SELECT d.id_pedido,i.nombre,d.cantidad,i.precio,d.total,d.especificaciones, p.codigo_unico
                    FROM detalle_pedido d
                    INNER JOIN pedidos p 
                        ON d.id_pedido = p.idpedido
                    INNER JOIN items i 
                        ON i.iditem = d.id_producto
                    WHERE p.codigo_unico = (
                        SELECT p2.codigo_unico
                        FROM pedidos p2
                        INNER JOIN clientes_whatsapp cw 
                            ON p2.id_whatsapp = cw.id_whatsapp
                        WHERE cw.telefono = %s and p.estado = 'pendiente' and p.es_temporal = true
                        ORDER BY p2.idpedido DESC
                        LIMIT 1
                    );
        """
        result = execute_query(query_pendientes, (sender,))
        codigo_unico = result[0][6] if result else 0
        pedido_info: dict = obtener_estado_pedido_por_codigo(sender, codigo_unico)
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
        mensaje=extraer_ultimo_mensaje(respuesta_usuario)
        if not validate_personal_data(sender,os.environ.get("ID_RESTAURANTE", "5")):
            datos = extraer_info_personal(mensaje)
            # datos es dict con keys: tipo_documento, numero_documento, email
            tipo_doc = datos.get("tipo_documento")
            n_doc = datos.get("numero_documento")
            email = datos.get("email")
            # Guardar solo los campos que traigan información útil
            try:
                save_personal_data_partial(sender, os.environ.get("ID_RESTAURANTE", "5"), tipo_doc, n_doc, email)
            except Exception as e:
                logging.error(f"Error guardando datos parciales: {e}")
                log_message(f"Error guardando datos parciales: {e}", "ERROR")
                send_text_response(sender, ", ocurrió un error al guardar tus datos. Enviamelos de nuevo escritos de otra manera por favor")
                return 
            # Verificar si ahora la fila tiene los 4 campos completos
            missing = check_and_mark_datos_personales(sender, os.environ.get("ID_RESTAURANTE", "5"))
            if missing:
                # mapear nombres amigables
                friendly = {"Tipo_Doc": "tipo de documento", "N_Doc": "número de documento", "email": "correo electrónico"}
                faltantes = ", ".join(friendly.get(m, m) for m in missing)
                codigo_unico: str = obtener_intencion_futura_observaciones(sender)
                medio_pago_real: str = mapear_modo_pago(mensaje)
                datos_actualizados: dict = actualizar_medio_pago(sender, codigo_unico, medio_pago_real)
                send_text_response(sender, f"aún faltan los siguientes datos: {faltantes}. Por favor envíalos para continuar.")
                return 
        codigo_unico: str = obtener_intencion_futura_observaciones(sender)
        medio_pago_real: str = mapear_modo_pago(mensaje)
        if medio_pago_real == "desconocido":
            query="""SELECT metodo_pago
                    fROM pedidos
                    wHERE codigo_unico=%s;"""
            result= execute_query(query,(codigo_unico,))
            medio_pago_real=result[0][0] if result else "desconocido"
        datos_actualizados: dict = actualizar_medio_pago(sender, codigo_unico, medio_pago_real)  # noqa: F841
        dict_registro_temp: dict = obtener_pedido_por_codigo(codigo_unico)
        tiempo= dict_registro_temp.get("tiempo_estimado", "N/A")
        total_productos = dict_registro_temp.get("total_final", "N/A")
        #total_domicilios = dict_registro_temp.get("total_domicilio", "N/A")
        if medio_pago_real =="efectivo":
            mensaje_pago: str = f"¡Perfecto {nombre_cliente}! Has seleccionado pagar en efectivo al momento de la entrega o recogida de tu pedido ({codigo_unico}). Por favor, el costo de tu domicilio es de {total_productos} y tardara {tiempo}. ¡Gracias por tu preferencia!"
            send_text_response(sender, mensaje_pago)
            borrar_intencion_futura(sender)
            marcar_estemporal_true_en_pedidos(sender,codigo_unico)
            return
        elif medio_pago_real == "datafono":
            mensaje_pago: str = f"¡Perfecto {nombre_cliente}! Has seleccionado pagar con tarjeta (datafono) al momento de la entrega o recogida de tu pedido ({codigo_unico}). Por favor, el costo de tu domicilio es  de {total_productos} y tardara {tiempo}. ¡Gracias por tu preferencia!"
            send_text_response(sender, mensaje_pago)
            borrar_intencion_futura(sender)
            marcar_estemporal_true_en_pedidos(sender,codigo_unico)
            return
        elif medio_pago_real == "tarjeta":
            try:
                monto = float(total_productos)  # por ejemplo 31900.0
                log_message(f"[SubflujoMedioPago] Generando link de pago para {sender} por monto {monto}.", "INFO")
                monto_cents = int(round(monto * 100))  # 3190000
                pago = generar_link_pago(monto_cents,sender)
                if pago is None:
                    send_text_response(sender, "No fue posible generar el link de pago ahora mismo.elige otro medio.")
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
                    "Una vez realices el pago, por favor envíame el pantallazo de la transaccion o avisame que ya pagaste para yo hacer la revisión"
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

def subflujo_modificacion_pedido(sender: str, nombre_cliente: str, pregunta_usuario: str):
    """Maneja la modificación del pedido por parte del usuario."""
    try:
        # Verificar si existen pedidos pendientes
        query_pendientes = """
                SELECT d.id_pedido,i.nombre,d.cantidad,i.precio,d.total,d.especificaciones, p.codigo_unico
                    FROM detalle_pedido d
                    INNER JOIN pedidos p 
                        ON d.id_pedido = p.idpedido
                    INNER JOIN items i 
                        ON i.iditem = d.id_producto
                    WHERE p.codigo_unico = (
                        SELECT p2.codigo_unico
                        FROM pedidos p2
                        INNER JOIN clientes_whatsapp cw 
                            ON p2.id_whatsapp = cw.id_whatsapp
                        WHERE cw.telefono = %s and p.estado = 'pendiente' and p.es_temporal = true
                        ORDER BY p2.idpedido DESC
                        LIMIT 1
                    );
        """
        result = execute_query(query_pendientes, (sender,))
        codigo_unico = result[0][6] if result else 0

        if result is None:
            send_text_response(sender, f"{nombre_cliente}, no tengo un pedido pendiente tuyo para modificar. ¿Quieres hacer un nuevo pedido?")
            return
        if codigo_unico != 0:
            id_pedido = result[0][0] 
            items_menu: list = obtener_menu()
            #txtSolicitud = extraer_ultimo_mensaje(pregunta_usuario)
            txtSolicitud = obtener_x_respuestas(sender, 2)
            productos = mapear_pedido_al_menu(txtSolicitud, items_menu, model="gpt-5.1")
            if productos.get("order_complete", False) is False:
                log_message(f"Modificación de pedido incompleta para {sender}.", "INFO")
                no_completo: dict = pedido_incompleto_dynamic(txtSolicitud, items_menu, str(productos))
                send_text_response(sender, no_completo.get("mensaje"))
                guardar_intencion_futura(sender, "confirmacion_modificacion_pedido", codigo_unico, str(productos), pregunta_usuario)
                return
            else:
                intent = productos["intent"]
                log_message(f'Modificación de pedido detectada: {productos} con la intención {intent}' , 'INFO')
                # Procesar modificaciones según la intención detectada  
                match intent:
                    case "ADD_ITEM":
                        for item in productos.get("items", []):
                            query = """SELECT id_detalle, cantidad
                                        FROM detalle_pedido
                                        WHERE id_pedido = %s AND id_producto = %s"""
                            params = ( id_pedido, item.get("matched").get("id"))
                            res_detalle = execute_query(query, params, fetchone=True)
                            if res_detalle:
                                especificaciones_txt = normalizar_especificaciones(item)
                                id_detalle, cantidad_actual = res_detalle
                                nueva_cantidad = cantidad_actual + item.get("cantidad", 1)
                                query = """ UPDATE detalle_pedido SET cantidad = %s, total = %s ,especificaciones = CASE
                                            WHEN %s IS NULL OR %s = '' THEN especificaciones
                                            ELSE %s 
                                            END
                                            WHERE id_detalle = %s"""
                                params = ( nueva_cantidad, (item.get("matched").get("price") * nueva_cantidad), especificaciones_txt,especificaciones_txt,especificaciones_txt, id_detalle )
                                res_detalle = execute_query(query, params)
                            else:     
                                especificaciones_txt = normalizar_especificaciones(item)           
                                query = """ INSERT INTO detalle_pedido ( id_producto,id_pedido, cantidad, total, especificaciones) VALUES (%s, %s, %s, %s, %s)"""
                                params = (item.get("matched").get("id"), id_pedido, item.get("cantidad"), (item.get("matched").get("price") * item.get("cantidad", 1)), especificaciones_txt )
                                res_detalle = execute_query(query, params)
                    case "REMOVE_ITEM":
                        for item in productos.get("items", []):
                            cambio = item.get("note")
                            if cambio == "delete" or item.get("cantidad") == 0:
                                query = """ DELETE FROM detalle_pedido WHERE id_pedido = %s AND id_producto = %s"""
                                params = ( id_pedido, item.get("matched").get("id"))
                                res_detalle = execute_query(query, params)
                            else:
                                query = """SELECT id_detalle, cantidad
                                            FROM detalle_pedido
                                            WHERE id_pedido = %s AND id_producto = %s"""
                                params = ( id_pedido, item.get("matched").get("id"))
                                res_detalle = execute_query(query, params, fetchone=True)
                                if res_detalle:
                                    id_detalle, cantidad_actual = res_detalle
                                    nueva_cantidad = cantidad_actual - item.get("cantidad", 1)
                                    especificaciones_txt = normalizar_especificaciones(item) 
                                    if nueva_cantidad > 0:
                                        query = """ UPDATE detalle_pedido SET cantidad = %s, total = %s, especificaciones = CASE
                                                    WHEN %s IS NULL OR %s = '' THEN especificaciones
                                                    ELSE %s END
                                                    WHERE id_detalle = %s"""
                                        params = ( nueva_cantidad, (item.get("matched").get("price") * nueva_cantidad),especificaciones_txt,especificaciones_txt,especificaciones_txt, id_detalle)
                                        res_detalle = execute_query(query, params)
                                    else:
                                        query = """ DELETE FROM detalle_pedido WHERE id_pedido = %s AND id_producto = %s"""
                                        params = ( id_pedido, item.get("matched").get("id"))
                                        res_detalle = execute_query(query, params)
                    case "REPLACE_ITEM":
                        for item in productos.get("items", []):            
                            cambio = item.get("note")
                            query = """SELECT id_detalle, cantidad
                                        FROM detalle_pedido
                                        WHERE id_pedido = %s AND id_producto = %s"""
                            params = ( id_pedido, item.get("matched").get("id"))
                            res_detalle = execute_query(query, params, fetchone=True)  
                            if cambio == "Producto de reemplazo":
                                if res_detalle:
                                    especificaciones_txt = normalizar_especificaciones(item)
                                    id_detalle, cantidad_actual = res_detalle
                                    nueva_cantidad = cantidad_actual + item.get("cantidad", 1)
                                    query = """ UPDATE detalle_pedido SET cantidad = %s, total = %s ,especificaciones = CASE
                                                WHEN %s IS NULL OR %s = '' THEN especificaciones
                                                ELSE %s 
                                                END
                                                WHERE id_detalle = %s"""
                                    params = ( nueva_cantidad, (item.get("matched").get("price") * nueva_cantidad), especificaciones_txt,especificaciones_txt,especificaciones_txt, id_detalle )
                                    res_detalle = execute_query(query, params)
                                else:     
                                    especificaciones_txt = normalizar_especificaciones(item)           
                                    query = """ INSERT INTO detalle_pedido ( id_producto,id_pedido, cantidad, total, especificaciones) VALUES (%s, %s, %s, %s, %s)"""
                                    params = (item.get("matched").get("id"), id_pedido, item.get("cantidad"), (item.get("matched").get("price") * item.get("cantidad", 1)), especificaciones_txt )
                                    res_detalle = execute_query(query, params)
                            elif cambio == "Producto a reemplazar":
                                if res_detalle:
                                    id_detalle, cantidad_actual = res_detalle
                                    nueva_cantidad = cantidad_actual - item.get("cantidad", 1)
                                    especificaciones_txt = normalizar_especificaciones(item) 
                                    if nueva_cantidad > 0:
                                        query = """ UPDATE detalle_pedido SET cantidad = %s, total = %s, especificaciones = CASE
                                                    WHEN %s IS NULL OR %s = '' THEN especificaciones
                                                    ELSE %s END
                                                    WHERE id_detalle = %s"""
                                        params = ( nueva_cantidad, (item.get("matched").get("price") * nueva_cantidad),especificaciones_txt,especificaciones_txt,especificaciones_txt, id_detalle)
                                        res_detalle = execute_query(query, params)
                                    else:
                                        query = """ DELETE FROM detalle_pedido WHERE id_pedido = %s AND id_producto = %s"""
                                        params = ( id_pedido, item.get("matched").get("id"))
                                        res_detalle = execute_query(query, params)
                    case "UPDATE_ITEM":
                        for item in productos.get("items", []):
                            if item.get("cantidad") == 0:
                                query = """ DELETE FROM detalle_pedido WHERE id_pedido = %s AND id_producto = %s"""
                                params = ( id_pedido, item.get("matched").get("id"))
                                res_detalle = execute_query(query, params)
                            else:
                                query = """SELECT id_detalle, cantidad
                                            FROM detalle_pedido
                                            WHERE id_pedido = %s AND id_producto = %s"""
                                params = ( id_pedido, item.get("matched").get("id"))
                                res_detalle = execute_query(query, params, fetchone=True)
                                especificaciones_txt = normalizar_especificaciones(item)
                                if res_detalle:
                                    id_detalle, cantidad_actual = res_detalle
                                    query = """ UPDATE detalle_pedido SET cantidad = %s, total = %s, especificaciones = CASE
                                                        WHEN %s IS NULL OR %s = '' THEN especificaciones
                                                        ELSE %s END
                                                        WHERE id_detalle = %s"""
                                    params = ( item.get("cantidad", 1), (item.get("matched").get("price") * item.get("cantidad", 1)),especificaciones_txt,especificaciones_txt,especificaciones_txt, id_detalle)
                                    res_detalle = execute_query(query, params)
                                else:
                                    query = """ INSERT INTO detalle_pedido ( id_producto,id_pedido, cantidad, total, especificaciones) VALUES (%s, %s, %s, %s, %s)"""
                                    params = (item.get("matched").get("id"), id_pedido, item.get("cantidad"), (item.get("matched").get("price") * item.get("cantidad", 1)), especificaciones_txt )
                                    res_detalle = execute_query(query, params)
                    case "ACLARACION":
                        items = obtener_menu()
                        mensaje = generar_mensaje_sin_intencion(pregunta_usuario, items)
                        send_text_response(sender, mensaje)
                        return
                log_message(f'Pedido modificado correctamente: {id_pedido} para {sender}.', 'INFO')
                query_actualizar_total = """update pedidos set total_productos = 
                                            (select sum(total) from detalle_pedido		
                                            where id_pedido = %s)
                                            where idpedido = %s """
                execute_query(query_actualizar_total, (id_pedido, id_pedido))
                result = execute_query(query_pendientes, (sender,))
                items_menu: list = obtener_menu()
                texto = generar_mensaje_confirmacion_modificacion_pedido(result,items_menu)
                guardar_intencion_futura(sender, "confirmar_pedido", codigo_unico)
                send_text_response(sender,texto.get("mensaje"))
                return
        else:
            send_text_response(sender, "los sentimos, Tu pedido ya fue creado, se envía al administrador para que verifique si se puede modificar o no, en un momento el admin se comunicara contigo.")
            numero_admin = os.getenv("NUMERO_ADMIN")
            send_text_response(numero_admin, f"El usuario {nombre_cliente} ({sender}) quiere modificar su pedido el codigo es: {codigo_unico}. Verificar si se puede modificar.")
            return
    except Exception as e:
        log_message(f'Error en <SubflujoModificacionPedido>: {e}.', 'ERROR')
        raise e

def subflujo_confirmar_direccion(sender: str, nombre_cliente: str) -> None:
    try:
        """Maneja la recepción de la dirección para el domicilio."""
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
            datos_actualizados.get("total_final"),
            sender
        )
        # Enviar solo mensaje como en versión 1
        send_text_response(sender, mensaje_pagar.get("mensaje"))
        # Actualizar intención futura
        actualizar_medio_entrega(sender, codigo_unico, "domicilio")
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
                    f"¡Perfecto {nombre_cliente}! Puedes completar tu pago aquí:\n{form_url}\n\nUna vez realices el pago, por favor envíame el pantallazo de la transaccion o avisame que ya pagaste para yo hacer la revisión"
                    ""
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
def     subflujo_recoger_restaurante(sender: str, nombre_cliente: str):
    try:
        log_message("Empieza subflujo recoger restaurante", "INFO")
        #mensaje_sede: str = generar_mensaje_seleccion_sede(nombre_cliente)
        #modificacion temporal solo una sede
        #send_text_response(sender, mensaje_sede)
        codigo_unico = obtener_intencion_futura_observaciones(sender)
        actualizar_medio_entrega(sender, codigo_unico, "recoger")
        guardar_intencion_futura(sender, "eleccion_sede", codigo_unico)
    except Exception as e:
        log_message(f"Error en subflujo recoger restaurante {e}", "ERROR") 
        raise e

def subflujo_eleccion_sede(sender: str, nombre_cliente: str, texto_cliente):
    try:
        log_message("Empieza subflujo eleccion sede", "INFO")
        query_pendientes = """
                    SELECT d.id_pedido,i.nombre,d.cantidad,i.precio,d.total,d.especificaciones, p.codigo_unico
                        FROM detalle_pedido d
                        INNER JOIN pedidos p 
                            ON d.id_pedido = p.idpedido
                        INNER JOIN items i 
                            ON i.iditem = d.id_producto
                        WHERE p.codigo_unico = (
                            SELECT p2.codigo_unico
                            FROM pedidos p2
                            INNER JOIN clientes_whatsapp cw 
                                ON p2.id_whatsapp = cw.id_whatsapp
                            WHERE cw.telefono = %s and p.estado = 'pendiente' and p.es_temporal = true
                            ORDER BY p2.idpedido DESC
                            LIMIT 1
                        );
            """
        result = execute_query(query_pendientes, (sender,))
        codigo_unico = result[0][6] if result else 0
        #MODIFICACION TEMPORAL SOLO UNA SEDE
        datos_mapeo_sede: dict = mapear_sede_cliente("caobos")
        if datos_mapeo_sede.get("error"):
            send_text_response(sender, "Disculpa, la sede que escribiste no existe, ¿puedes volver a escribir con mayor claridad?")
            return
        id_sede = datos_mapeo_sede.get("id_sede")
        #id_restaurante = os.environ.get("ID_RESTAURANTE", "5")
        #latitud_cliente = datos_mapeo_sede.get("latitud_sede")
        #longitud_cliente = datos_mapeo_sede.get("longitud_sede")
        direccion_cliente = datos_mapeo_sede.get("direccion_sede")
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
        marcar_estemporal_true_en_pedidos(sender,codigo_unico)
        log_message("Termina subflujo eleccion sede", "INFO")
    except Exception as e:
        log_message(f"Error en subflujo eleccion sede {e}", "ERROR")
        raise e

def subflujo_verificación_pago(sender: str, nombre_cliente: str, respuesta_usuario: str) -> None:
    try:
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

def subflujo_tiempo_recogida(sender: str, respuesta_usuario: str) -> None:

    try:
        mensaje=extraer_ultimo_mensaje(respuesta_usuario)
        mensaje = get_tiempo_recogida(mensaje)
        tiempo_estimado=calcular_minutos(mensaje)
        if tiempo_estimado == "No presente" or tiempo_estimado is None:
            send_text_response(sender, "Disculpa, no entendí el tiempo de recogida que me diste. ¿Podrías escribirlo de nuevo, por favor?")
            return
        query: str = """
        UPDATE pedidos
        SET tiempo_estimado = %s
        WHERE id_whatsapp = (SELECT id_whatsapp FROM clientes_whatsapp WHERE telefono = %s)
        AND estado = 'pendiente'
        """
        params: tuple = (tiempo_estimado, sender) 

        execute_query(query, params)



    except Exception as e:
        log_message(f'Error en <SubflujoTiempoRecogida>: {e}.', 'ERROR')
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
            send_pdf_response(sender)
        elif (clasificacion_mensaje == "solicitud_pedido" or clasificacion_mensaje == "continuacion_promocion"):
            try:
                # Verificar si existen pedidos pendientes
                query_pendientes = """
                        SELECT d.id_pedido,i.nombre,d.cantidad,i.precio,d.total,d.especificaciones, p.codigo_unico
                            FROM detalle_pedido d
                            INNER JOIN pedidos p 
                                ON d.id_pedido = p.idpedido
                            INNER JOIN items i 
                                ON i.iditem = d.id_producto
                            WHERE p.codigo_unico = (
                                SELECT p2.codigo_unico
                                FROM pedidos p2
                                INNER JOIN clientes_whatsapp cw 
                                    ON p2.id_whatsapp = cw.id_whatsapp
                                WHERE cw.telefono = %s and p.estado = 'pendiente' and p.es_temporal = true
                                ORDER BY p2.idpedido DESC
                                LIMIT 1
                            );
                """
                result = execute_query(query_pendientes, (sender,))
                codigo_unico = result[0][6] if result else 0
                if codigo_unico != 0:
                    subflujo_modificacion_pedido(sender, nombre_cliente, pregunta_usuario)
                else:
                    subflujo_solicitud_pedido(sender, pregunta_usuario, entidades_text, codigo_unico)
            except Exception as e:
                log_message(f'Error en <OrquestadorSubflujos> al manejar continuacion_pedido: {e}.', 'ERROR')
                raise e
        elif clasificacion_mensaje == "confirmacion_general":
            return subflujo_confirmacion_general(sender, pregunta_usuario)
        elif clasificacion_mensaje == "negacion_general":
            subflujo_negacion_general(sender, pregunta_usuario, nombre_cliente)
        elif clasificacion_mensaje == "consulta_promociones":
            subflujo_promociones(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "consulta_menu" and type_text != "pregunta" and obtener_intencion_futura(sender) != "eleccion_sede":
            subflujo_consulta_menu(sender, nombre_cliente, pregunta_usuario, entidades_text)
        elif clasificacion_mensaje == "preguntas_generales" or (clasificacion_mensaje == "consulta_menu" and (type_text == "pregunta" or type_text == "preguntas_generales")):
            subflujo_preguntas_generales(sender, pregunta_usuario, nombre_cliente)
        elif clasificacion_mensaje == "sin_intencion":
            items = obtener_menu()
            mensaje = generar_mensaje_sin_intencion(pregunta_usuario, items)
            send_text_response(sender, mensaje)
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
        elif (clasificacion_mensaje == "modificar_pedido" or clasificacion_mensaje == "continuacion_pedido" or clasificacion_mensaje == "solicitud_pedido" or clasificacion_mensaje == "solicitud_pedido"):
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
                    send_text_response(sender, "Gracias. Te recuerdo que no estas en el area de cobertura, por favor envia una nueva direccion donde te entregaremos este pedido o puedo ofrecerte recogerlo en el restaurante.")
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
            subflujo_eleccion_sede(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "eleccion_sede":
            subflujo_eleccion_sede(sender, nombre_cliente, pregunta_usuario)
        elif (clasificacion_mensaje == "direccion" or clasificacion_mensaje == "consulta_menu") and obtener_intencion_futura(sender) == "eleccion_sede":
            subflujo_eleccion_sede(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "esperando_confirmacion_pago":
            subflujo_verificación_pago(sender, nombre_cliente, pregunta_usuario)
        elif (clasificacion_mensaje == "continuacion_pedido") and obtener_intencion_futura(sender) == "eleccion_sede":
            subflujo_eleccion_sede(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "direccion":
            try:
                ultimo_mensaje=extraer_ultimo_mensaje(pregunta_usuario)
                direccion=get_direction(ultimo_mensaje)
                if not direccion:
                    send_text_response(sender, "Comparteme la dirección a actualizar por favor")
                    return
                geocode_and_assign(sender, direccion, os.environ.get("ID_RESTAURANTE", "5"))
                datos_cliente_temp: dict = obtener_datos_cliente_por_telefono(sender, os.environ.get("ID_RESTAURANTE", "5"))
                latitud_cliente: float = datos_cliente_temp.get("latitud", 0.0)
                longitud_cliente: float = datos_cliente_temp.get("longitud", 0.0)
                resultado=calcular_distancia_entre_sede_y_cliente(sender,latitud_cliente, longitud_cliente,os.environ.get("ID_RESTAURANTE", "5"), nombre_cliente)
                if not resultado:
                    send_text_response(sender, f"Lo siento {nombre_cliente}, pero tu dirección está fuera de nuestra área de cobertura. puedes recogerla en el restaurante o enviarnos otra dirección.")
                    execute_query("""
                                            UPDATE clientes_whatsapp
                                            SET direccion_google = %s
                                            WHERE telefono = %s AND id_restaurante = %s;
                                            """, (None, sender, os.environ.get("ID_RESTAURANTE", "5")))
                    return
                mensaje = direccion_bd(nombre_cliente, direccion)
                send_text_response(sender, mensaje)
                guardar_intencion_futura(sender, "confirmar_direccion", obtener_intencion_futura_observaciones(sender))
                log_message(f"Dirección corregida guardada en BD para {sender}", "INFO")
            except Exception as e:
                log_message(f"Error al corregir dirección: {e}", "ERROR")
                send_text_response(sender, "Hubo un error al procesar tu dirección. Por favor, intenta nuevamente.")
        elif clasificacion_mensaje == "tiempo_de_recogida":
            subflujo_tiempo_recogida(sender,pregunta_usuario)
            send_text_response(sender, "¡Perfecto! Te esperamos. Si necesitas algo más, no dudes en decírmelo.")
        elif clasificacion_mensaje == "despedida":
            send_text_response(sender, "¡Perfecto! Te esperamos. Si necesitas algo más, no dudes en decírmelo.")
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
