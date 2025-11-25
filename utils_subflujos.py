# utils_subflujos.py
# Last modified: 2025-11-05 by Andrés Bermúdez

import ast
import json
import os
import random
import logging
from typing import Any, Dict

# --- IMPORTS INTERNOS --- #
from utils import (
    actualizar_medio_pago,
    actualizar_total_productos,
    eliminar_pedido,
    eliminar_una_instancia_orden_por_nombre,
    guardar_intencion_futura,
    guardar_ordenes,
    guardar_pedido_completo,
    insertar_orden,
    log_message,
    marcar_intencion_como_resuelta,
    marcar_pedido_como_definitivo,
    match_item_to_menu,
    normalizar_entities_items,
    obtener_estado_pedido_por_codigo,
    obtener_intencion_futura_mensaje_chatbot,
    obtener_intencion_futura_mensaje_usuario,
    obtener_intencion_futura_observaciones,
    obtener_menu,
    obtener_pedido_por_codigo,
    obtener_pedido_por_codigo_orignal,
    obtener_ultima_intencion_no_resuelta,
    recalcular_y_actualizar_pedido,
    send_pdf_response,
    send_text_response,
    guardar_clasificacion_intencion,
    obtener_intencion_futura,
    borrar_intencion_futura,
    to_json_safe
)
from utils_chatgpt import actualizar_pedido_con_mensaje, clasificar_pregunta_menu_chatgpt, enviar_menu_digital, generar_mensaje_cancelacion, generar_mensaje_confirmacion_modificacion_pedido, generar_mensaje_confirmacion_pedido, interpretar_eleccion_promocion, mapear_modo_pago, mapear_pedido_al_menu, pedido_incompleto_dynamic, pedido_incompleto_dynamic_promocion, responder_pregunta_menu_chatgpt, responder_sobre_pedido, responder_sobre_promociones, respuesta_quejas_graves_ia, respuesta_quejas_ia, saludo_dynamic, sin_intencion_respuesta_variable, solicitar_medio_pago, solicitar_metodo_recogida
from utils_database import execute_query, execute_query_columns

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
            send_text_response(sender, "Procesando tu pedido anterior...")
            observaciones_pedido = obtener_intencion_futura_observaciones(sender)
            mensaje_chatbot_intencion_futura: str = obtener_intencion_futura_mensaje_chatbot(sender)
            mensaje_usuario_intencion_futura: str = obtener_intencion_futura_mensaje_usuario(sender)
            pedido_dict = actualizar_pedido_con_mensaje(observaciones_pedido, pregunta_usuario, items_menu, mensaje_chatbot_intencion_futura, mensaje_usuario_intencion_futura)
            send_text_response(sender, f"Pedido actualizado: {str(pedido_dict)}")
            bandera_revision = True
        if not bandera_revision:
            entidades_text = normalizar_entities_items(entidades_text)
            pedido_dict = mapear_pedido_al_menu(entidades_text, items_menu)
        send_text_response(sender, str(pedido_dict))
        if not pedido_dict.get("order_complete", False):
            no_completo: dict = pedido_incompleto_dynamic(pregunta_usuario, items_menu, str(pedido_dict))
            send_text_response(sender, "Analizando tu pedido... pq faltó algo.")
            send_text_response(sender, no_completo.get("mensaje"))
            guardar_intencion_futura(sender, "continuacion_pedido", str(pedido_dict), no_completo.get("mensaje"), pregunta_usuario)
            return
        pedido_info = guardar_pedido_completo(sender, pedido_dict, es_temporal=True)
        if not pedido_info or not isinstance(pedido_info, dict) or "idpedido" not in pedido_info:
            log_message(f'No se pudo crear el pedido para {sender}. pedido_info={pedido_info}', 'ERROR')
            send_text_response(sender, "Lo siento, no pude guardar tu pedido. Por favor inténtalo de nuevo más tarde.")
            return
        items_info = guardar_ordenes(pedido_info["idpedido"], pedido_dict, sender)
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
        guardar_intencion_futura(sender, "confirmacion_modificacion_pedido", pedido_info['codigo_unico'], str(pedido_dict), pregunta_usuario)
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
            datos_eliminar: dict = eliminar_pedido(sender, codigo_unico_temp)
            send_text_response(sender, dict_temp_cancelacion.get("mensaje"))
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
            send_text_response(sender, f"Un asesor se comunicará contigo muy pronto.")
        mensaje_medio_pago: dict = solicitar_medio_pago(nombre_cliente, codigo_unico, "Sierra Nevada", pedido_temp.get("producto", ""))
        send_text_response(sender, mensaje_medio_pago.get("mensaje"))
        guardar_intencion_futura(sender, "medio_pago", codigo_unico)
        log_message(f'Pedido {confirmar_dict.get("codigo_unico")} confirmado correctamente para {sender}.', 'INFO')
    except Exception as e:
        log_message(f'Error en <SubflujoConfirmacionPedido>: {e}.', 'ERROR')
        raise e

def subflujo_consulta_menu(sender: str, nombre_cliente: str) -> None:
    """Maneja la consulta del menú por parte del usuario."""
    try:
        log_message(f'Iniciando función <SubflujoConsultaMenu> para {sender}.', 'INFO')
        menu = obtener_menu()
        mensaje_menu: dict = enviar_menu_digital(nombre_cliente, "Sierra Nevada", menu)
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
            except:
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
        promos_rows, promo_cols = execute_query_columns(
            """
            SELECT *
            FROM promociones
            WHERE fecha_inicio <= NOW()
              AND fecha_fin >= NOW()
              AND estado = 'true';
            """,
            fetchone=False,
            return_columns=True
        )
        promociones_info = [
            {col: to_json_safe(val) for col, val in zip(promo_cols, row)}
            for row in promos_rows
        ]
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
        mensaje_metodo_recogida: dict = solicitar_metodo_recogida(nombre_cliente, codigo_unico, "Sierra Nevada", datos_actualizados.get("producto", ""))
        send_text_response(sender, mensaje_metodo_recogida.get("mensaje"))
        guardar_intencion_futura(sender, "metodo_recogida", codigo_unico)
    except Exception as e:
        log_message(f'Error en <SubflujoMedioPago>: {e}.', 'ERROR')
        raise e

def subflujo_modificacion_pedido(sender: str, nombre_cliente: str, pregunta_usuario: str) -> dict:
    """
    clasificacion_payload ejemplo:
    {
      "accion": "quitar" / "añadir" / "reemplazar",
      "items": [
         {"producto": "malteada de chocolate", "especificaciones": []},
         ...
      ],
      # Si reemplazar: podríamos recibir también {"replace_with": [...] } o pares en items
    }
    Retorna dict con resumen de cambios y nuevo total.
    """
    try:
        log_message(f'Iniciando función <SubflujoModificacionPedido> para {sender}.', 'INFO')
        codigo_unico: str = obtener_intencion_futura_observaciones(sender)  # como dijiste ya lo tienes
        clasificacion_payload: dict = obtener_intencion_futura_mensaje_chatbot(sender)
        if not codigo_unico:
            raise ValueError("No se encontró codigo_unico en la intención futura del usuario.")

        pedido = obtener_pedido_por_codigo(codigo_unico)
        if not pedido:
            raise ValueError(f"No existe pedido con código {codigo_unico}.")

        idpedido = pedido["idpedido"]
        id_whatsapp = pedido["id_whatsapp"] or 1

        accion = (clasificacion_payload.get("accion") or "").lower()
        items = clasificacion_payload.get("items", [])

        # obtener menu para mapear productos nuevos
        items_menu = obtener_menu()

        cambios_aplicados = {
            "añadidos": [],
            "quitados": [],
            "reemplazados": []
        }

        # Iniciar transacción (si tu execute_query no maneja transacciones, estos comandos intentan manejarlas)
        try:
            execute_query("BEGIN;", ())
        except Exception:
            # si DB no permite BEGIN así, ignoramos y seguimos (depende de tu wrapper)
            pass

        if accion in ("añadir", "add", "anadir", "agregar", "agrega"):
            for it in items:
                nombre_req = it.get("producto") or it.get("name")
                especs = ", ".join(it.get("especificaciones", [])) if it.get("especificaciones") else ""
                match = match_item_to_menu(nombre_req, items_menu)
                nombre_final = match["name"]
                precio = match["price"]
                idorden = insertar_orden(id_whatsapp, idpedido, nombre_final, precio, especs)
                cambios_aplicados["añadidos"].append({
                    "idorden": idorden,
                    "producto": nombre_final,
                    "precio": precio,
                    "found_in_menu": match["found"]
                })

        elif accion in ("quitar", "remove", "eliminar", "sacar"):
            for it in items:
                nombre_req = it.get("producto") or it.get("name")
                especs_text = ", ".join(it.get("especificaciones", [])) if it.get("especificaciones") else ""
                eliminado = eliminar_una_instancia_orden_por_nombre(idpedido, nombre_req, especs_text)
                cambios_aplicados["quitados"].append({
                    "producto_solicitado": nombre_req,
                    "eliminado": eliminado
                })

        elif accion in ("reemplazar", "replace"):
            # Se espera que 'items' contenga pares {'old': {...}, 'new': {...}} o una lista donde primero son a quitar y luego a añadir.
            # Hacemos soporte flexible:
            for pair in items:
                # si viene con estructura de par
                if "old" in pair and "new" in pair:
                    old = pair["old"]
                    new = pair["new"]
                    old_nombre = old.get("producto")
                    new_nombre = new.get("producto")
                    new_especs = ", ".join(new.get("especificaciones", [])) if new.get("especificaciones") else ""
                    # eliminar una instancia del viejo
                    eliminado = eliminar_una_instancia_orden_por_nombre(idpedido, old_nombre)
                    # insertar nuevo mapeado al menu
                    match = match_item_to_menu(new_nombre, items_menu)
                    idorden = insertar_orden(id_whatsapp, idpedido, match["name"], match["price"], new_especs)
                    cambios_aplicados["reemplazados"].append({
                        "eliminado": {"producto": old_nombre, "status": eliminado},
                        "añadido": {"idorden": idorden, "producto": match["name"], "precio": match["price"], "found_in_menu": match["found"]}
                    })
                else:
                    # fallback: intentar eliminar y luego añadir
                    old_nombre = pair.get("producto") or pair.get("old_producto")
                    new_nombre = pair.get("reemplazo") or pair.get("nuevo_producto")
                    if old_nombre and new_nombre:
                        eliminado = eliminar_una_instancia_orden_por_nombre(idpedido, old_nombre)
                        match = match_item_to_menu(new_nombre, items_menu)
                        idorden = insertar_orden(id_whatsapp, idpedido, match["name"], match["price"])
                        cambios_aplicados["reemplazados"].append({
                            "eliminado": {"producto": old_nombre, "status": eliminado},
                            "añadido": {"idorden": idorden, "producto": match["name"], "precio": match["price"], "found_in_menu": match["found"]}
                        })

        else:
            # si no entendemos la acción, intentar inferir por texto libre
            # por ejemplo: si pregunta_usuario contiene "añade" o "agrega" tratamos como añadir
            txt = pregunta_usuario.lower()
            if any(k in txt for k in ["añad", "agreg", "pon", "mete"]):
                # reusar lógica de añadir:
                for it in items:
                    nombre_req = it.get("producto") or it.get("name")
                    especs = ", ".join(it.get("especificaciones", [])) if it.get("especificaciones") else ""
                    match = match_item_to_menu(nombre_req, items_menu)
                    idorden = insertar_orden(id_whatsapp, idpedido, match["name"], match["price"], especs)
                    cambios_aplicados["añadidos"].append({
                        "idorden": idorden,
                        "producto": match["name"],
                        "precio": match["price"],
                        "found_in_menu": match["found"]
                    })
            elif any(k in txt for k in ["quitar", "sacar", "eliminar", "quité", "quita"]):
                for it in items:
                    nombre_req = it.get("producto") or it.get("name")
                    eliminado = eliminar_una_instancia_orden_por_nombre(idpedido, nombre_req)
                    cambios_aplicados["quitados"].append({
                        "producto_solicitado": nombre_req,
                        "eliminado": eliminado
                    })
            else:
                # acción desconocida: rollback y devolver error
                try:
                    execute_query("ROLLBACK;", ())
                except Exception:
                    pass
                raise ValueError("Acción de modificación no reconocida.")

        # Recalcular totales y actualizar pedido
        resumen_actualizado = recalcular_y_actualizar_pedido(idpedido)

        try:
            execute_query("COMMIT;", ())
        except Exception:
            pass

        # Respuesta/salida: resumen de cambios y nuevo total
        mensaje_resumen = {
            "status": "success",
            "codigo_unico": resumen_actualizado["codigo_unico"],
            "idpedido": resumen_actualizado["idpedido"],
            "nuevo_total": resumen_actualizado["total_productos"],
            "cambios": cambios_aplicados
        }
        log_message(f'Pedido {resumen_actualizado["codigo_unico"]} modificado: {json.dumps(cambios_aplicados)}', 'INFO')
        send_text_response(sender, json.dumps(mensaje_resumen))
        return mensaje_resumen

    except Exception as e:
        send_text_response(sender, f"Error: {e}")
        try:
            execute_query("ROLLBACK;", ())
        except Exception:
            pass
        log_message(f'Error en <SubflujoModificacionPedido>: {e}.', 'ERROR')
        return {"status": "error", "mensaje": str(e)}

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
        elif clasificacion_mensaje == "solicitud_pedido" or clasificacion_mensaje == "continuacion_promocion":
            subflujo_solicitud_pedido(sender, pregunta_usuario, entidades_text, id_ultima_intencion)
        elif clasificacion_mensaje == "confirmacion_general":
            return subflujo_confirmacion_general(sender, pregunta_usuario)
        elif clasificacion_mensaje == "negacion_general":
            subflujo_negacion_general(sender, pregunta_usuario, nombre_cliente)
        elif clasificacion_mensaje == "consulta_promociones":
            subflujo_promociones(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "consulta_menu" and type_text != "pregunta":
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
        elif clasificacion_mensaje == "validacion_pago" and obtener_intencion_futura(sender) == "medio_pago":
            subflujo_medio_pago(sender, nombre_cliente, pregunta_usuario)
        elif clasificacion_mensaje == "modificacion_pedido":
            subflujo_modificacion_pedido(sender, nombre_cliente, pregunta_usuario)
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
