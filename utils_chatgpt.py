# utils_chatgpt.py
# Last modified: 2025-21-12 Juan Agudelo

import re
from openai import OpenAI
import logging
from typing import Any,  Optional, Tuple, Dict
import os
import json
from utils import calcular_costo_openai, send_text_response, limpiar_respuesta_json, log_message, to_json_safe,corregir_total_price_en_result
from utils_database import execute_query
from datetime import datetime, date
from utils_registration import validate_personal_data
from psycopg2.extras import Json

ID_RESTAURANTE: str = os.getenv("ID_RESTAURANTE", "9")

def get_openai_key() -> str:
    try:
        """Obtiene la clave API de OpenAI desde variables de entorno."""
        logging.info('Obteniendo clave de OpenAI')
        api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("No se encontró la clave OPENAI_API_KEY en las variables de entorno.")
        logging.info('Clave de OpenAI obtenida')
        return api_key
    except Exception as e:
        log_message(f"Error al obtener la clave de OpenAI: {e}", 'ERROR')
        logging.error(f"Error al obtener la clave de OpenAI: {e}")
        raise
    
def get_classifier(msj: str, sender: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    try:
        """Clasifica un mensaje de WhatsApp usando un modelo fine-tuned de OpenAI."""
        logging.info('Clasificando mensaje')
        classification_prompt: str = """
Eres un clasificador de mensajes para un asistente de WhatsApp de un restaurante.

Tu tarea es identificar:
- intent
- type
- entities (si aplica)

Recibirás un JSON con el historial de conversación.
Debes analizar principalmente el ÚLTIMO mensaje del usuario.
Puedes usar el contexto inmediato si el mensaje es ambiguo (ej: "sí", "no", "efectivo").

Debes responder únicamente con JSON válido con esta estructura exacta:

{
  "intent": "<una intención permitida>",
  "type": "<tipo de mensaje>",
  "entities": {}
}

No incluyas texto adicional fuera del JSON.

----------------------------------------------------
INTENCIONES DISPONIBLES
----------------------------------------------------

- saludo
- despedida
- confirmacion_general
- negacion_general
- consulta_menu
- consulta_pedido
- consulta_promociones
- preguntas_generales
- quejas
- transferencia
- sin_intencion
- solicitud_pedido
- validacion_pago
- recoger_restaurante
- domicilio
- Tiempo_de_recogida
- esperando_confirmacion_pago
- direccion
- eleccion_sede
- confirmar_pedido

----------------------------------------------------
REGLAS DE CLASIFICACIÓN IMPORTANTES
----------------------------------------------------

1) solicitud_pedido:
Pedidos nuevos, agregar productos, modificar pedido existente, aclarar cantidades o productos.
Ejemplos:
- agregar producto
- quitar producto
- cambiar producto
- modificar ingredientes
- ajustar cantidades
- aclarar pedido previo

2) confirmacion_general / negacion_general:
Si el usuario dice solo "sí" o "no" sin contexto adicional.

3) preguntas_generales:
Incluye preguntas sobre:
- horarios
- pagos
- domicilios
- ubicación
- ingredientes
- recomendaciones
- reservas
- Sedes

4) transferencia:
Cuando el usuario pide hablar con humano, asesor, gerente, soporte, o presenta queja grave.

5) validacion_pago:
Cuando el usuario envía datos de facturación:
- documento (6 a 10 dígitos numéricos)
- tipo documento (RC, TI, CC, CE, PA)
- correo
- método de pago (Nequi, Daviplata, tarjeta, efectivo)

6) direccion:
Solo cuando el usuario ENVÍA su dirección para un domicilio.

Ejemplos:
- "mi dirección es calle 10 # 20-30"
- "carrera 15 # 80-21 apto 301"
- "cámbiala por calle 100 # 9-45"
- "la dirección correcta es..."

NO usar esta intención cuando el usuario pregunta por la dirección de una sede.
En ese caso usar: preguntas_generales.

7) recoger_restaurante:
Cuando indica que pasará a recoger el pedido.

8) domicilio:
Cuando solicita envío a casa.

9) sin_intencion:
Cuando el tema no tiene relación con el restaurante.

----------------------------------------------------
REGLAS DE ENTIDADES (solo si intent = solicitud_pedido)
----------------------------------------------------

- Extrae productos en entities.items
- Usa estructura:

{
  "items": [
    {
      "producto": "...",
      "especificaciones": [],
      "cantidad": 1
    }
  ]
}

- Si hay cantidad explícita, usar campo "cantidad" (no duplicar items).
- Si se modifican ingredientes, agregar a "especificaciones".
- No crear nuevo item si solo modifica uno existente.

----------------------------------------------------
REGLAS DE COMBO
----------------------------------------------------

- Un producto en combo es diferente a su versión individual.
- Si el usuario pide solo el combo, no agregues versión individual.
- Solo agrega ambos si lo menciona explícitamente.

----------------------------------------------------
REGLAS ESPECÍFICAS
----------------------------------------------------

- Agua = "Agua normal 600 ml"
- Agua con gas = "Agua con gas 600 ml"
- Reservas → preguntas_generales
- Si responde a elección de sede → eleccion_sede

Analiza únicamente el último mensaje del usuario.
Nunca clasifiques mensajes del asistente.
Responde solo JSON válido."""
        messages = [
            {
                "role": "system",
                "content": classification_prompt
            },
            {
                "role": "user",
                "content": msj
            }
        ]
        client: OpenAI = OpenAI(api_key=get_openai_key())
        respuesta: Any = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            #max_tokens=700,
            temperature=0
        )
        tokens_used = _extract_total_tokens(respuesta)
        costo=calcular_costo_openai(respuesta,"gpt-4.1-mini")
        log_message(f"[OpenAI] get_classifier costo={costo:.6f}","DEBUG")
        if tokens_used is not None:
            log_message(f"[OpenAI] get_classifier tokens_used={tokens_used}", "DEBUG")
        raw_response: str = respuesta.choices[0].message.content.strip()
        logging.info(f"[Clasificador RAW] {raw_response!r}")
        json_str: str = limpiar_respuesta_json(raw_response)
        result: Dict[str, Any] = json.loads(json_str)
        intent: Optional[str] = result.get("intent")
        type_: Optional[str] = result.get("type")
        entities: Dict[str, Any] = result.get("entities", {})
        if not intent or not type_:
            raise ValueError(f"Respuesta inválida, faltan claves: {result}")
        logging.info(f"Respuesta del clasificador: {result}")
        logging.info(f"Intent: {intent}, Type: {type_}, Entities: {entities}")
        log_message(f'Respuesta del clasificador: {result}', 'INFO')
        return intent, type_, entities
    except Exception as e:
        log_message(f'Error al hacer uso de función <GetClassifier>: {e}.', 'ERROR')
        logging.error(f"Error al clasificar el mensaje: {e}")
        send_text_response(sender, "Lo siento, hubo un error al procesar tu mensaje. ¿Podrías repetirlo?")
        return None, None, {}

def clasificar_pregunta_menu_chatgpt(pregunta_usuario: str, items, model: str = "gpt-4o") -> dict:
    """
    Clasifica si una pregunta del usuario está relacionada con el menú o con servicios
    del negocio (hamburguesería) usando un modelo de lenguaje (ChatGPT).
    """

    client: OpenAI = OpenAI()

    prompt: str = f"""
    Eres un asistente que clasifica preguntas de clientes de una hamburguesería.

    Debes responder con un JSON EXACTO con la siguiente forma:
    {{
        "clasificacion": "relacionada" o "no_relacionada"
        "intencion": "informacion_menu" o "informacion_servicios" o "informacion_pedido"
    }}
    Intenciones:
    - informacion_menu: preguntas sobre comidas, bebidas, ingredientes, precios, opciones vegetarianas o cualquier cosa del menú.
    - informacion_servicios: preguntas sobre formas de pago, domicilios, horarios, ubicación, contacto, promociones.
    - informacion_pedido: preguntas relacionadas con el estado, costo o seguimiento de un pedido.
    Instrucciones:
    - Si la pregunta se refiere a comidas, hamburguesas, bebidas, malteadas, ingredientes, precios,
      opciones vegetarianas o cualquier cosa del menú → "relacionada".
    - También clasifica como "relacionada" si el cliente pregunta sobre:
        • formas de pago (Nequi, Daviplata, efectivo, tarjetas, etc.)
        • si hacen domicilios o envíos
        • horarios de atención
        • dirección o ubicación del local
        • contacto, pedidos o reservas
        • promociones o descuentos
        • preguntas sobre productos (hamburguesas, malteadas, perros, gaseosas)
    - Si la pregunta es sobre temas generales, ajenos al restaurante (por ejemplo: Bogotá, clima, películas, tecnología, etc.) → "no_relacionada".
    - Responde SOLO con el JSON, sin explicaciones ni texto adicional.
    Ejemplos:
    1️⃣ "qué hamburguesas tienen?" → {{"clasificacion": "relacionada"}}
    2️⃣ "hay hamburguesas de pollo?" → {{"clasificacion": "relacionada"}}
    3️⃣ "qué malteadas tienen?" → {{"clasificacion": "relacionada"}}
    4️⃣ "tienen opciones vegetarianas?" → {{"clasificacion": "relacionada"}}
    5️⃣ "aceptan pagos por nequi?" → {{"clasificacion": "relacionada"}}
    6️⃣ "hacen envíos a suba?" → {{"clasificacion": "relacionada"}}
    7️⃣ "cuál es su horario?" → {{"clasificacion": "relacionada"}}
    8️⃣ "dónde están ubicados?" → {{"clasificacion": "relacionada"}}
    9️⃣ "dónde queda Bogotá?" → {{"clasificacion": "no_relacionada"}}
    🔟 "qué es Python?" → {{"clasificacion": "no_relacionada"}}

    Este es el menú completo si la pregunta incluye un producto del menu o se refiere a comidas o bebidas es relacionada:
    {json.dumps(items, ensure_ascii=False)}
    
    Ahora clasifica la siguiente pregunta del usuario:
    "{pregunta_usuario}"

    Devuelve SOLO el JSON, sin explicación adicional.
    """

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0
        )
        text_output = response.output[0].content[0].text.strip()
        # limpiar posibles fences/triple-backticks u otros prefijos
        try:
            text_output = _clean_model_output(text_output)
        except Exception:
            pass
        costo=calcular_costo_openai(response,"gpt-4o")
        log_message(f"[OpenAI] clasificar pregunta menu chatgpt costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] clasificar_pregunta_menu_chatgpt tokens_used={tokens_used}", "DEBUG")
        # Extraer JSON dentro de fences ```json ... ``` o buscar primer objeto JSON
        clean = text_output or ""
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, flags=re.IGNORECASE)
        if m:
            clean = m.group(1).strip()
        else:
            clean = clean.strip()
        if not clean.startswith('{'):
            m2 = re.search(r"(\{[\s\S]*\})", clean)
            if m2:
                clean = m2.group(1)

        try:
            result = json.loads(clean)
            return result
        except json.JSONDecodeError:
            logging.error(f"Error al parsear JSON en clasificar_pregunta_menu_chatgpt: {clean!r}")
            log_message(f'Error al parsear JSON en <ClasificarPreguntaMenuChatGPT>: {clean}', 'ERROR')
            return {"clasificacion": "no_relacionada"}

    except json.JSONDecodeError:
        logging.error(f"Error al parsear JSON: {text_output}")
        log_message(f'Error al parsear JSON en <ClasificarPreguntaMenuChatGPT>: {text_output}', 'ERROR')
        return {"clasificacion": "no_relacionada"}
    except Exception as e:
        logging.error(f"Error en <ClasificarPreguntaMenuChatGPT>: {e}")
        log_message(f'Error en <ClasificarPreguntaMenuChatGPT>: {e}.', 'ERROR')
        return {"clasificacion": "no_relacionada"}

def _clean_model_output(raw: str) -> str:
    """
    Limpia output que pueda venir en triple-backticks o con '```json' al inicio.
    Devuelve el string JSON limpio (o el raw si no había marcas).
    """
    if not raw:
        return ""
    s = raw.strip()

    # Si el modelo devolvió bloque con ```json ... ```
    if s.startswith("```"):
        # eliminar backticks al inicio y final
        s = s.strip("`").strip()
        # si aún tiene prefijo 'json' eliminarlo
        if s.lower().startswith("json"):
            s = s[len("json"):].lstrip("\r\n ").strip()

    return s

def _extract_text_from_response(response) -> str:
    """
    Extrae texto del objeto devuelto por client.responses.create de forma robusta.
    Prioriza response.output_text, luego response.output[*].content[*].text, 
    luego intenta concatenar todo lo que encuentre.
    """
    # 1) output_text (forma simple)
    try:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return str(output_text).strip()
    except Exception:
        pass

    # 2) response.output -> content
    try:
        if hasattr(response, "output") and response.output:
            parts = []
            for out in response.output:
                # cada out puede tener 'content' que es lista de dicts
                content = getattr(out, "content", None) or out.get("content", None) if isinstance(out, dict) else None
                if content:
                    for c in content:
                        # c puede ser dict con 'text' u 'type' y 'content'
                        if isinstance(c, dict):
                            if "text" in c and c["text"]:
                                parts.append(c["text"])
                            elif "type" in c and c["type"] == "output_text" and "text" in c:
                                parts.append(c["text"])
                            else:
                                # intentar stringify
                                parts.append(json.dumps(c, ensure_ascii=False))
                        else:
                            parts.append(str(c))
            if parts:
                return "\n".join(parts).strip()
    except Exception:
        pass

    # 3) fallback: str(response)
    try:
        return str(response).strip()
    except Exception:
        return ""

def responder_pregunta_menu_chatgpt(pregunta_usuario: str, items,sender: str, model: str = "gpt-4o") -> dict:
    """
    Responde preguntas del usuario sobre el menú o servicios del restaurante Sierra Nevada 🍔.
    Incluye información sobre horarios, sedes y medios de pago.
    Devuelve: (result: dict, prompt: str)
    """
    # Obtener id_sede del cliente usando el teléfono
    telefono = sender  # Asumiendo que 'sender' es el teléfono
    query_id_sede = f"SELECT id_sede FROM clientes_whatsapp WHERE telefono = '{telefono}'"
    result_id_sede = execute_query(query_id_sede)
    id_sede = None
    if result_id_sede and len(result_id_sede) > 0:
        id_sede = result_id_sede[0][0]
    direccion = None
    if id_sede:
        query_direccion = f"SELECT direccion FROM sedes WHERE id_sede = '{id_sede}'"
        result_direccion = execute_query(query_direccion)
        if result_direccion and len(result_direccion) > 0:
            direccion = result_direccion[0][0]
    # Prompt unificado
    msj_mismo_dia = obtener_respuestas_mismo_dia(sender)
    extraer_resumen_corto(msj_mismo_dia, sender, ID_RESTAURANTE)
    resumen=obtener_resumen(sender)
    if resumen is None:
        resumen = {}
    if isinstance(resumen, dict):
        resumen_str = json.dumps(resumen, ensure_ascii=False)
    else:
        resumen_str = str(resumen)
    sedes = execute_query("""
        SELECT nombre, direccion, horarios
        FROM sedes
        WHERE estado = TRUE
        AND id_restaurante = %s
        AND latitud IS NOT NULL
        AND longitud IS NOT NULL;
    """, (ID_RESTAURANTE,))

    if not sedes:
        return None

    sedes_contexto = []

    for s in sedes:
        nombre = s[0]
        direccion = s[1]
        horarios = s[2]

        # convertir horarios a json si viene como string
        if isinstance(horarios, str):
            horarios = json.loads(horarios)

        sede_dict = {
            "nombre": nombre,
            "direccion": direccion,
            "horarios": horarios
        }

        sedes_contexto.append(sede_dict)

    # convertir a json para pasarlo al LLM
    sedes_json = json.dumps(sedes_contexto, ensure_ascii=False, indent=2)

    print(sedes_json)
    prompt = f"""
        Eres PAKO, el asistente cálido y cercano de Sierra Nevada, La Cima del Sabor 🏔️🍔.
        Tu tarea es ayudar al cliente con información sobre el menú, horarios, sedes y servicios,
        siempre con el tono oficial de la marca: amable, natural y con un toque sabroso, sin exagerar.

        Información del restaurante:
        Sedes y horarios:
        {sedes_json}
        💳 Medios de pago: solo contraentrega efectivo y datafono.
        - Tenemos domicilios siempre y cuando esten en el area de cobertura si no esta no podria entregar a domicilio.
        - Si el cliente menciona que no le gusta un ingrediente dile que puede quitarlo del producto
        - Si preguntan por hamburguesas sierras diles que hubo un cambio en el menu
        
        El cliente preguntó: "{pregunta_usuario}"
        La sede asignada del cliente es: "{direccion if direccion else 'No asignada'}".
        El resumen de la conversación con el cliente es: {resumen_str}
        Este es el menú completo:
        {json.dumps(items, ensure_ascii=False)}
        PAUTAS DE TONO (OBLIGATORIAS):
        - Habla como un buen anfitrión bogotano: cálido, natural y claro.
        - Siempre cordial, sin sarcasmo, sin ironía y sin jerga barrial.
        - Puedes usar máximo 1 emoji suave si queda natural.
        - No inventes productos, ingredientes ni sedes.
        - Sé breve y humano, como si hablaras por WhatsApp.
        - Mantén un toque emocional o visual de sabor cuando sea apropiado.

        INSTRUCCIONES DE RESPUESTA:
        - Si la pregunta es sobre horarios, sedes, medios de pago o envíos, responde con la información dada.
        - Si el cliente pide algo que sí aparece en el menú, descríbelo brevemente o confírmalo.
        - Si pide algo que NO está en el menú, indícalo con amabilidad y sugiere máximo 2 opciones similares.
        - Si pregunta por categorías (picante, vegetariano, pollo, bebidas, postres, etc.), responde según el menú.
        - Si pregunta por algo ambiguo, aclara con amabilidad.
        - Evita frases impersonales (ej. “su solicitud ha sido procesada”).
        - Evita exageraciones o tono juvenil extremo.
        - Mantén la respuesta en máximo 2 frases si es posible.
        - En este momento no manejamos reservas
        - Si la pregunta es sobre costo de domicilio recuerdale que actualmente dentro del area de cobertura es gratis
        - Los unicos metodos de pago disponibles son efectivo y datafono contraentrega, no manejamos transferencias ni pagos digitales ni pago con tarjeta 
        - Siempre que indiques una sede menciona su direccion
        REGLA ESTRICTA
        NUNCA LE DIGAS AL CLIENTE QUE EL PEDIDO HA SIDO CONFIRMADO
        FORMATO OBLIGATORIO DE SALIDA:
        Devuelve SOLO un JSON válido con esta estructura EXACTA:

        {{
            "respuesta": "texto amigable para el cliente",
            "recomendacion": true o false,
            "productos": ["nombre1", "nombre2"]
        }}

        Ejemplo:
        Usuario: "¿Tienen opciones picantes?"
        -> {{
            "respuesta": "Claro 👍 Tenemos opciones con carácter como la Sierra Picante y la Sierra BBQ, ambas con un toque fuerte.",
            "recomendacion": false,
            "productos": ["Sierra Picante", "Sierra BBQ"]
        }}
        """
    try:
        log_message(f"Prompt para ChatGPT preguntas generales: {prompt}", "DEBUG")
        client = OpenAI()
        response = client.responses.create(
            model=model,
            input=prompt
        )
        costo=calcular_costo_openai(response,"gpt-4o")
        log_message(f"[OpenAI] responder_pregunta_menu_chatgpt costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] responder_pregunta_menu_chatgpt tokens_used={tokens_used}", "DEBUG")
        raw_text = _extract_text_from_response(response)
        raw_text = _clean_model_output(raw_text)
        logging.info(f"[DEBUG] Texto crudo del modelo: {raw_text!r}")

        if not raw_text:
            raise ValueError("Respuesta vacía del modelo")

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            import re
            m = re.search(r"(\{[\s\S]*\})", raw_text)
            if m:
                result = json.loads(m.group(1))
            else:
                result = {"respuesta": raw_text, "recomendacion": False, "productos": []}

        if "productos" in result and isinstance(result["productos"], list):
            result["productos"] = [p.replace('\u00a0', ' ').strip() for p in result["productos"]]

        pregunta_lower = pregunta_usuario.lower()
        if any(token in pregunta_lower for token in ["?", "tienen", "hay", "venden", "cuáles", "qué opciones", "me recomiendas", "qué hay"]):
            respuesta_txt = str(result.get("respuesta", "")).strip()
            if respuesta_txt and not respuesta_txt.endswith(("?", ".", "!", "😋", "😉", "😎")):
                result["respuesta"] = respuesta_txt + " ¿Quieres probarla? 😋"

        result.setdefault("productos", [])
        result.setdefault("recomendacion", False)
        log_message(f"Respuesta generada: {result}", "INFO")
        return result

    except Exception as e:
        logging.error(f"Error en <ResponderPreguntaMenuChatGPT>: {e}")
        log_message(f'Error en <ResponderPreguntaMenuChatGPT>: {e}', 'ERROR')
        return {
            "respuesta": "Lo siento 😔, tuve un problema para responder tu pregunta.",
            "recomendacion": False,
            "productos": []
        }

def mapear_pedido_al_menu(contenido_clasificador: dict, menu_items: list,sender: str, model: str = "gpt-5.1") -> dict:
    """
    Mapear los items provenientes del clasificador AL MENÚ usando GPT.
    """
    client = OpenAI()
    pedido=obtener_pedido_en_proceso(sender, ID_RESTAURANTE)
    prompt = f"""
        Eres un asistente encargado de interpretar mensajes de clientes para la toma y modificación de pedidos de domicilios.
        Tu función es:
        1) Clasificar la INTENCIÓN del mensaje del usuario.
        2) Mapear los productos solicitados al MENÚ estructurado.
        3) Identificar los productos afectados cuando el pedido es una modificación.
        4) Devolver ÚNICAMENTE un JSON válido, sin ningún texto adicional.

        ======================================================
        = ESTRUCTURA DE RESPUESTA (OBLIGATORIA) =
        ======================================================
        Debes responder ÚNICA Y EXCLUSIVAMENTE con un JSON válido con esta estructura exacta:

        {{
            "intent": "ADD_ITEM | REMOVE_ITEM | REPLACE_ITEM",
            "intent_confidence": number,
            "target_items": [
                {{
                    "producto": "...",
                    "especificaciones": [ ... ]
                }}
            ],
            "order_complete": true|false,
            "items": [
                {{
                    "requested": {{ "producto": "...", "especificaciones": [ ... ] }},
                    "status": "found" | "not_found" | "multiple_matches",
                    "matched": {{ "name": "...", "id": "...", "price": number }},
                    "candidates": [ {{ "name":"...", "id":"...", "price": number }}, ... ],
                    "modifiers_applied": [ ... ],
                    "cantidad": number,
                    "note": ""
                }}
            ]
        }}

        ======================================================
        = CLASIFICACIÓN DE INTENCIÓN =
        ======================================================
        ANTES de mapear los productos debes identificar la INTENCIÓN del mensaje.
 
        INTENCIONES DISPONIBLES:
        - ADD_ITEM: el usuario agrega productos al pedido actual ejemplo (Agregar, añadir, poner, sumar, traer, pedir, incluir,También, además, extra, otro, otra, uno más.).
        - REMOVE_ITEM: El usuario elimina un producto completo.
            REGLA CRÍTICA: Si el usuario dice "SIN [PRODUCTO]" (ej. sin las aguas, sin la soda), y ese producto existe de forma independiente en el menú, es REMOVE_ITEM.
            REGLA CRÍTICA 2: Si el usuario menciona un producto general en su mensaje puedes buscar el producto especifico en el contexto comparandolo con el menu por ejemplo el mensaje del agente puede mencionar a que producto se refiere el cliente.
        - UPDATE_ITEM: El usuario modifica un ingrediente o cantidad de un ítem que SE QUEDA en el pedido, si el usuario pide ajuste en el pedido (solo es una bebida) si los items siguen siendo los mismos luego de la modificacion es UPDATE_ITEM si pide solo x producto pero ya estaba en el pedido es UPDATE_ITEM.
            REGLA CRÍTICA: Si el usuario dice "SIN [INGREDIENTE]" (ej. sin salsas, sin cebolla), y el ingrediente NO es un producto vendible por sí solo, es UPDATE_ITEM.
        - REPLACE_ITEM: el usuario quiere cambiar un peoducto por otro ejemplo(Cambiar, sustituir, reemplazar, permutar,X por Y", "en vez de X quiero Y", "mejor cámbiame...).
        - REESCRIBIR_PEDIDO: el usuario quiere que el pedido se reescriba completamente con los productos mencionados en el mensaje, "solo quiero este producto", "quiero que mi pedido sea solo...", "quiero que mi pedido incluya únicamente...", "quiero que mi pedido tenga solamente...", "quiero solo esto no lo demas", "ya no quiero lo demas solo esto".
        - ACLARACION: el mensaje del usuario no permite identificar de forma clara una acción sobre el pedido, o es ambiguo con dos o mas iintenciones en el pedido, incompleto o confuso.
 
        REGLAS ABSOLUTAS:
        - Si la intención es REMOVE_ITEM, el campo "note" dentro del array "items" DEBE contener exactamente el string "delete"
        - Es OBLIGATORIO usar REMOVE_ITEM cuando el usuario cancela un producto principal usando la palabra "todas", "sin", "ya no", o "quita".
        - Ejemplo: "Sin las aguas" -> intent: REMOVE_ITEM, note: "delete"
        - Si el mensaje contiene palabras de ajuste como "mejor", "solo", "en vez de", o especificaciones de ingredientes ("sin salsas", "con queso"), la intención debe ser UPDATE_ITEM o REPLACE_ITEM, nunca ADD_ITEM.
        - Solo puede existir UNA intención por mensaje.
        - Si la intención NO es NEW_ORDER, debes identificar los productos afectados en target_items.
        - intent_confidence debe ser un valor entre 0 y 1 según claridad del mensaje.
        - Si la intención detectada es REPLACE_ITEM, debes asignar obligatoriamente el campo note de la siguiente manera:
            -Para el producto que ingresa al pedido, establece el valor exacto: "Producto de reemplazo".
            -Para el producto que sale del pedido, establece el valor exacto: "Producto a reemplazar".
            -Esta regla es estricta y debe cumplirse siempre que la intención sea REPLACE_ITEM, sin excepciones.
        - Nunca clasificar como REPLACE_ITEM si no existen dos productos claramente identificables en el mensaje O en el contexto del PEDIDO ACTUAL EN PROCESO.
        - Cuando el cliente pide "platanitos" "platanos" o "plátanos" se refiere a los platanitos maduros el ACOMPAÑAMIENTO DE 7900 a menos que explicitamente mencione sea la adicion en ese caso son los platanos maduros de 2900 el adicional
        - Si colocas order_complete en true debes colocar la coincidencia mas aproximada en el campo matched de los candidatos
        - En las hamburguesas que se puedan elegir proteina si el cliente no elige proteina pon de res SOLO CUANDO EL CLIENTE NO ELIJA
        - Si la intención es REESCRIBIR_PEDIDO:
            - Debes ignorar completamente todos los productos y modificadores previos del pedido.
            - Solo deben existir en "items" los productos mencionados explícitamente en el mensaje actual.
            - No heredes modificadores, bebidas ni adicionales anteriores.
            - No mantengas adiciones pagas previas si el usuario no las menciona nuevamente.

        ======================================================
        = COMPORTAMIENTO GLOBAL DEL MODELO =
        ======================================================
        Debes identificar los productos del menú incluso cuando estén:
        - mal escritos, abreviados, rotos en sílabas, fusionados,
        - con espacios de más o de menos,
        - escritos fonéticamente,
        - mezclados con palabras irrelevantes,
        - con diminutivos, coloquialismos o apodos.

        Debes reconocer CUALQUIER producto del menú mediante:
        - normalización,
        - sinonimia,
        - fuzzy matching,
        - similitud semántica,
        - heurísticas inteligentes.

        ======================================================
        = NORMALIZACIÓN EXTREMA =
        ======================================================
        Antes de buscar coincidencias debes:
        - pasar todo a minúsculas,
        - quitar acentos,
        - corregir repeticiones,
        - eliminar palabras vacías (“quiero”, “dame”, “porfa”, etc.),
        - corregir deformaciones fonéticas conocidas,
        - convertir números a posibles tamaños,
        - eliminar texto irrelevante.

        ======================================================
        = SINONIMIA SEMÁNTICA =
        ======================================================
        Asume que los clientes pueden usar:
        - partes del nombre,
        - apodos informales,
        - equivalencias de categoría,
        - nombres fonéticos o deformados.

        ======================================================
        = TOLERANCIA TOTAL A ERRORES =
        ======================================================
        Un producto es match válido si:
        - la similitud semántica es razonable,
        - comparte palabras clave,
        - suena similar fonéticamente,
        - fuzzy match aceptable.

        ======================================================
        = PRIORIDAD DE MATCHING =
        ======================================================
        A) Exacta → FOUND  
        B) Alias → FOUND  
        C) Parcial fuerte → FOUND  
        D) Semántica → FOUND  
        E) Fuzzy único → FOUND  
        F) 2+ → MULTIPLE_MATCHES  
        G) 0 → NOT_FOUND (máx. 3 sugerencias)

        ======================================================
        = REGLAS FINALES ABSOLUTAS =
        ======================================================
        - Usa EXACTAMENTE el nombre del menú en matched.name.
        - Si algún ítem es NOT_FOUND → order_complete = false.
        - Si todos son FOUND → order_complete = true.
        - matched.price SIEMPRE es el precio UNITARIO.
        - NO multipliques matched.price por cantidad.
        - total_price es el ÚNICO lugar donde se multiplica por cantidad.
        - La cantidad NO modifica matched.price.
        - La respuesta debe ser SOLO el JSON.
        - Las adiciones deben ser mapeadas como un modificador del pedido respectivo y como un producto aparte para la suma del precio
        - Cuando el usuario mencione combos, recuerdale que no manejamos combos actualmente pero podemos armarlo a su gusto con los acompañamientos y bebidas del menu
        - Si un modificador tiene precio mayor a 0, DEBES crear un item adicional en el array "items" con ese producto como producto independiente, manteniendo también su presencia en modifiers_applied.
        - Las adiciones pagas (precio > 0) SIEMPRE deben existir como item independiente en el array "items".
        - No es opcional. Es obligatorio.
        - Los objetos dentro de "modifiers_applied" NUNCA deben contener precio, id ni información monetaria.
        - "modifiers_applied" es únicamente descriptivo.
        - Si un modificador tiene costo, debe agregarse obligatoriamente como un item independiente dentro del array "items".
        - El precio SOLO puede existir dentro del objeto "matched" de los items principales o adicionales independientes.
        - Está estrictamente prohibido incluir precio dentro de "modifiers_applied".
        - Cuando el producto principal sea un COMBO del menú, los componentes incluidos en su descripción (bebida y acompañamiento) NO deben crearse como items independientes.
        - La bebida y el acompañamiento incluidos estructuralmente en un combo NO son adiciones.
        - Solo deben crearse como items independientes si el usuario los pide adicionalmente fuera del combo.
        - La regla de "adiciones pagas como item independiente" NO aplica a componentes estructurales de combos.
        - Los productos cuyo nombre empiece por "Combo" son unidades cerradas indivisibles y su precio ya incluye bebida y acompañamiento.
        REGLA CRÍTICA DE COMBOS:

        Cuando el cliente mencione una bebida inmediatamente después de que el agente haya
        preguntado por la bebida de un combo, esa bebida se interpreta como una elección
        de bebida del combo.

        NO debe crearse un item independiente para esa bebida.

        La bebida debe agregarse únicamente como modificador del combo dentro de
        "modifiers_applied".

        Ejemplo:

        Cliente:
        "Con quatro"

        Resultado:

        Combo con Platanito Maduro
        modifiers_applied:
        ["bebida: Quatro 400 ml"]

        NO crear item independiente de bebida.
        REGLA DE CONTEXTO DEL PEDIDO:

        El campo "PEDIDO ACTUAL EN PROCESO" representa el producto activo
        sobre el cual el cliente está hablando.

        Si el cliente utiliza frases como:

        - "mejor"
        - "cámbialo"
        - "ponlo"
        - "hazlo"
        - "en combo"
        - "solo"
        - "sin"

        y no menciona el producto explícitamente,
        debes asumir que se refiere al producto activo del
        PEDIDO ACTUAL EN PROCESO.
        REGLA DE CONVERSIÓN A COMBO:

        Si el usuario dice expresiones como:
        "mejor en combo"
        "hazlo combo"
        "ponlo en combo"
        "que sea combo"
        "vuélvelo combo"

        y el pedido actual contiene una hamburguesa que tiene versión en combo
        en el menú, debes convertir automáticamente ese producto a su
        versión de combo equivalente.

        Ejemplo:

        "Con Platanito Maduro y Queso Costeño"
        → "Combo con Platanito Maduro"

        "Con Queso"
        → "Combo Con Queso"

        "Con Chicharrón"
        → "Combo con Chicharrón"

        "Con Doble Tocineta"
        → "Combo Doble Tocineta"

        Esta conversión debe clasificarse como:
        intent: REPLACE_ITEM
        ======================================================
        Tono de la conversacion:
        -Directo,formal,cercano y amable
        MENÚ COMPLETO:
        {json.dumps(menu_items, ensure_ascii=False)}

        CLASIFICADOR:
        {json.dumps(contenido_clasificador, ensure_ascii=False)}

        PEDIDO ACTUAL EN PROCESO:
        {pedido if pedido else "No hay pedido en proceso"}
        DEVUELVE SOLO EL JSON.
        """

    try:
        log_message(f'Prompt generado en <MapearPedidoAlMenu>: {prompt}', 'DEBUG')
        response = client.responses.create(
            model=model,
            input=prompt,
 #           max_completion_tokens = 500,
            temperature=0
        )
        
        text_output = response.output[0].content[0].text.strip()
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] mapear_pedido_Al_menu costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] mapear_pedido tokens_used={tokens_used}", "DEBUG")
        log_message(f'Output crudo de modelo en <MapearPedidoAlMenu>: {text_output}', 'DEBUG')
        ##### Validacion costo
    
        clean = text_output.strip()
        clean = re.sub(r'^```json', '', clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r'^```', '', clean).strip()
        clean = re.sub(r'^json', '', clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r'```$', '', clean).strip()

        result = json.loads(clean)

        log_message(f'Resultado parseado en <MapearPedidoAlMenu>: {result}', 'DEBUG')
        result = corregir_total_price_en_result(result)
        return result

    except json.JSONDecodeError:
        logging.error("Error al parsear JSON desde el modelo.")
        logging.error(text_output if 'text_output' in locals() else 'no output')
        log_message(f'Error al parsear JSON en <MapearPedidoAlMenu>: {text_output}', 'ERROR')

        return {
            "order_complete": False,
            "items": [],
            "total_price": 0,
            "error": "parse_error",
            "raw_output": text_output if 'text_output' in locals() else None
        }

    except Exception as e:
        logging.exception("Error llamando al API")
        log_message(f'Error en <MapearPedidoAlMenu>: {e}', 'ERROR')

        return {
            "order_complete": False,
            "items": [],
            "total_price": 0,
            "error": str(e)
        }

def saludo_dynamic(mensaje_usuario: str, nombre: str, nombre_local: str) -> dict:
    try:
        PROMPT_SALUDO_DYNAMIC = """
        Eres la voz oficial de Sierra Nevada, La Cima del Sabor.

        Genera un saludo breve para el cliente.

        El cliente escribió: "{mensaje_usuario}"

        REGLAS:
        - Máximo 1 frase corta (máximo 20 palabras).
        - Incluye el nombre del cliente: {nombre}
        - Incluye el nombre del local: {nombre_local}
        - Usa un tono natural según cómo escriba el cliente.
        - Solo puedes usar 1 emoji si el tono es informal.
        - Incluye un recordatorio breve usando "recuerda" para no enviar varios mensajes seguidos.
        - No hagas preguntas.
        - No agregues explicaciones.
        - No inventes información.

        FORMATO OBLIGATORIO (JSON válido):
        {
            "mensaje": "texto aquí",
            "intencion": "consulta_menu"
        }
        No incluyas texto fuera del JSON.
        """

        client = OpenAI()
        prompt = PROMPT_SALUDO_DYNAMIC.format(
            nombre=nombre,
            nombre_local=nombre_local,
            mensaje_usuario=mensaje_usuario.lower()
        )
        
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": "Eres un generador de saludos que adapta su tono al del cliente."},
                {"role": "user", "content": prompt}
            ],
#            max_tokens=350,
            temperature=0.85
        )

        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] saludo dynamic costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] saludo_dynamic tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except:  # noqa: E722
            # fallback con tips incluidos
            data = {
                "mensaje": f"¡Hola {nombre}! Bienvenido a {nombre_local}. ¿Te muestro el menú o las promociones?",
                "intencion": "consulta_menu",
                "tips": [
                    "Escribe mensajes claros y específicos",
                    "Envía un mensaje a la vez",
                    "Sigue los pasos que te comparta el bot",
                    "Espera mi respuesta antes de enviar otro mensaje",
                ]
            }

        return data

    except Exception as e:
        log_message(f'Error en función <saludo_dynamic>: {e}', 'ERROR')
        logging.error(f"Error en función <saludo_dynamic>: {e}")
        return {
            "mensaje": f"¡Hola {nombre}! Bienvenido a {nombre_local}. ¿Quieres ver el menú?",
            "intencion": "consulta_menu",
            "tips": [
                "Escribe mensajes claros y específicos",
                "Envía un mensaje a la vez",
                "Sigue los pasos que te comparta el bot",
                "Espera mi respuesta antes de enviar otro mensaje",
            ]
        }
    
def respuesta_quejas_ia(mensaje_usuario: str, nombre: str, nombre_local: str) -> dict:
    try:
        PROMPT_QUEJA_LEVE = """
            Eres el asistente oficial de servicio al cliente de Sierra Nevada, La Cima del Sabor.

            Tu tarea es responder una queja leve con el tono y personalidad de la marca:
            - Cálido, cercano y respetuoso.
            - Natural, humano, sin excesos.
            - Con un toque de sabor y buena energía, sin sonar exagerado.
            - Orgullosamente colombiano, pero sin clichés.
            - Hablas como un buen anfitrión bogotano: amable, claro y sin jerga popular.
            El cliente llamado {nombre} escribió lo siguiente: "{mensaje_usuario}"
            OBJETIVO:
            - Tranquilizar al cliente.
            - Validar su experiencia sin culpas ni defensividad.
            - Incluir SIEMPRE una acción concreta para mostrar que estás atendiendo el caso 
            (por ejemplo: “le cuento al equipo”, “reviso con cocina”, “lo paso al encargado del punto”).
            - Mostrar disposición a ayudar SIN escalar el caso a un agente humano.
            - Mantener un tono amable y con toque emocional de Sierra Nevada.
            - Usar máximo 1 emoji suave si fluye de manera natural.
            - Responder en máximo 2 frases.

            REGLAS DE TONO:
            - No uses sarcasmo, ironías ni expresiones barriales.
            - No suenes robótico ni impersonal.
            - No inventes información.
            - Mantén una sensación de servicio, calidez y sabor.
            - Evita anglicismos y tecnicismos.
            - Puedes mencionar solo: equipo, servicio, experiencia, tiempo de entrega, sabor, atención.

            CONTENIDO:
            Debes generar:
            1. "respuesta_cordial": un mensaje amable y empático que tranquilice al cliente, 
            incluyendo una acción concreta como “reviso con cocina”, “le cuento al equipo del punto” 
            o “dejo la nota para mejorar tu próxima experiencia”.
            2. "resumen_queja": una frase corta que resuma la queja sin inventar detalles.
            3. "intencion": siempre "queja_leve".

            FORMATO DE RESPUESTA:
            La respuesta DEBE ser un JSON válido:
            {
                "respuesta_cordial": "texto aquí",
                "resumen_queja": "texto aquí",
                "intencion": "queja_leve"
            }
            Genera solo el JSON sin texto adicional.
            """
        client = OpenAI()
        prompt = PROMPT_QUEJA_LEVE.format(
            mensaje_usuario=mensaje_usuario,
            nombre=nombre
        )
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un generador de respuestas amables para quejas leves de clientes."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=180,
            temperature=0.6
        )
        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] respuesta quejas ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] respuesta_quejas tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except:  # noqa: E722
            data = {
                "respuesta_cordial": f"{nombre}, gracias por escribirnos. Lamentamos que tu experiencia en {nombre_local} no haya sido perfecta; estamos aquí para ayudarte 😊",
                "resumen_queja": "Queja leve del cliente sobre su experiencia.",
                "intencion": "quejas"
            }
        return data
    except Exception as e:
        log_message(f'Error en función <respuesta_quejas>: {e}', 'ERROR')
        logging.error(f"Error en función <respuesta_quejas>: {e}")
        return {
            "respuesta_cordial": f"{nombre}, gracias por avisarnos. Estamos atentos para que tu experiencia en {nombre_local} sea mejor cada vez.",
            "resumen_queja": "Queja leve del cliente.",
            "intencion": "quejas"
        }

def respuesta_quejas_graves_ia(mensaje_usuario: str, nombre: str, nombre_local: str) -> dict:
    try:
        PROMPT_QUEJA_GRAVE = """
            Eres el asistente oficial de servicio al cliente de Sierra Nevada, La Cima del Sabor.
            Esta vez atenderás *quejas graves*, donde puede que el pedido NO haya llegado,
            haya habido un error fuerte, mala manipulación o tiempo excesivo.
            ***OBJETIVO GENERAL***
            - Calmar al cliente.
            - Asumir responsabilidad sin culpas excesivas.
            - Dar una ACCIÓN clara y concreta que el asistente realizará.
            - Preparar un resumen ejecutivo para un administrador humano.
            - NO escalar directamente en el mensaje al cliente (solo en el resumen interno).
            - Máximo 2 frases, tono cálido, humano, cercano, estilo Sierra Nevada, colombiano neutro.
            - La respuesta_cordial DEBE incluir explícitamente la frase:
            "Ya escalé el caso con un administrador y se comunicará contigo muy pronto."
            - Si la frase no aparece, la respuesta es inválida.
            ***DEBES ENTREGAR ESTOS CAMPOS***
            1. "respuesta_cordial": Mensaje calmado, empático y con acción concreta 
            (ej: “reviso ya mismo con cocina y logística”, “activo seguimiento con el punto”).
            2. "resumen_queja": Descripción breve de lo que reclama el cliente.
            3. "accion_recomendada": Acción clara que el sistema/administrador debe hacer 
            (ej: verificar estado del pedido, contactar punto, revisar domiciliario).
            4. "resumen_ejecutivo": Resumen para administrador (breve, objetivo, sin adornos).
            5. "intencion": Siempre "queja_grave".
            ***TONO***
            - Cálido y responsable.
            - Sin tecnicismos ni sarcasmo.
            - Evita respuestas robóticas.
            - Máximo un emoji, si fluye natural.

            Cliente llamado {nombre} escribió:
            "{mensaje_usuario}"
            ***FORMATO OBLIGATORIO***
            Devuelve SOLO un JSON válido:
            {{
                "respuesta_cordial": "",
                "resumen_queja": "",
                "accion_recomendada": "",
                "resumen_ejecutivo": "",
                "intencion": "queja_grave"
            }}
        """
        client = OpenAI()
        prompt = PROMPT_QUEJA_GRAVE.format(
            mensaje_usuario=mensaje_usuario,
            nombre=nombre
        )
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Eres un generador de respuestas para quejas graves de clientes."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=220,
            temperature=0.6
        )
        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] respuesta_quejas_graves_ia tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except:  # noqa: E722
            data = {
                "respuesta_cordial": f"{nombre}, ya reviso lo ocurrido con tu experiencia en {nombre_local} y activo el seguimiento de inmediato.",
                "resumen_queja": "Queja grave del cliente sobre servicio o pedido.",
                "accion_recomendada": "Revisión urgente con el punto y estado del pedido.",
                "resumen_ejecutivo": "Cliente reporta una queja grave; requiere revisión del punto y logística.",
                "intencion": "queja_grave"
            }
        return data
    except Exception as e:
        log_message(f'Error en función <respuesta_quejas_graves_ia>: {e}', 'ERROR')
        logging.error(f"Error en función <respuesta_quejas_graves_ia>: {e}")
        return {
            "respuesta_cordial": f"{nombre}, reviso de inmediato lo que pasó con tu experiencia en {nombre_local}.",
            "resumen_queja": "Queja grave del cliente.",
            "accion_recomendada": "Verificar con el punto y logística.",
            "resumen_ejecutivo": "Error en el proceso automático, requiere revisión manual.",
            "intencion": "queja_grave"
        }

def pedido_incompleto_dynamic(mensaje_usuario: str, menu: list, json_pedido: str) -> dict:
    try:
        menu_str = "\n".join([f"- {item['nombre']}" for item in menu])
        PROMPT_PEDIDO_INCOMPLETO = """
            Eres la voz oficial de Sierra Nevada, La Cima del Sabor. Te llamas PAKO.
            El cliente escribió: "{mensaje_usuario}"
            El gestor de pedidos detectó que el pedido está INCOMPLETO o POCO CLARO:
            {json_pedido}
            Tu tarea:
            - Responder SOLO con un JSON válido.
            - NO inventar productos. NO mencionar nada que NO esté en el menú.
            - Si el cliente pide algo que NO existe en el menú (ej: "lasaña", "lasagna"), debes:
                * Indicar amablemente que ese producto no está disponible.
                * Sugerir 1 a 3 opciones REALES y relacionadas del menú.
            - Si el cliente pide algo MUY GENERAL (ej: "una hamburguesa", "una bebida"), debes:
                * Dar 1 a 3 recomendaciones REALES del menú que sí coincidan.
            - Pedir que el cliente aclare el producto que falta
            -Si el cliente pide algo válido pero con nombre aproximado
                * Acepta coincidencias parciales SOLO si es OBVIO que se refiere a un producto real.
                * Nunca adivines si hay más de una opción posible.
            Responde SOLO en este formato exacto:
            {{
                "mensaje": "texto aquí",
                "recomendaciones": ["Opción 1", "Opción 2"],
                "intencion": "consulta_menu"
            }}
            Reglas estrictas:
            - No inventes productos. Usa ÚNICAMENTE nombres EXACTOS del menú.
            - Si el cliente menciona algo NO presente en el menú, dilo explícitamente.
            - No respondas como asistente conversacional. Solo JSON.
            - No agregues explicaciones fuera del JSON.
            - Nunca menciones que no esta en el menu di amablemente que no lo tenemos disponible en este momento.
            Aquí está el menú disponible:
            {menu_str}
            
        TEN EN CUENTA PUEDES USAR COINCIDENCIAS PARCIALES SOLO SI ES UNA VARIANTE CLARA PERO NO INVENTAR NI REEMPLAZAR SABORES.    
            """
        
        log_message(f'Prompt generado en <pedido_incompleto_dynamic>: {PROMPT_PEDIDO_INCOMPLETO}', 'DEBUG')
        prompt = PROMPT_PEDIDO_INCOMPLETO.format(
            mensaje_usuario=mensaje_usuario,
            menu_str=menu_str,
            json_pedido=json_pedido
        )
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": "Eres un asistente que ayuda al cliente a consultar el menú y elegir su pedido."},
                {"role": "user", "content": prompt}
            ],
#este modelo no limita los tokens            max_tokens=450,
            temperature=0.2
        )
        raw = response.choices[0].message.content

        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] solicitar medio pago costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] pedido_incompleto_dynamic tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except Exception:
            recomendaciones_backup = [i["nombre"] for i in menu[:2]]
            data = {
                "mensaje": "Puedo mostrarte el menú completo si deseas. ¿Quieres que te comparta las opciones?",
                "recomendaciones": recomendaciones_backup,
                "intencion": "consulta_menu"
            }
        return data
    except Exception as e:
        log_message(f'Error en función <pedido_incompleto_dynamic>: {e}', 'ERROR')
        logging.error(f"Error en función <pedido_incompleto_dynamic>: {e}")
        recomendaciones_backup = [i["nombre"] for i in menu[:2]] if menu else []
        return {
            "mensaje": "Si quieres, puedo mostrarte el menú para que elijas mejor.",
            "recomendaciones": recomendaciones_backup,
            "intencion": "consulta_menu"
        }

def solicitar_medio_pago(nombre: str, codigo_unico: str, nombre_local: str, pedido_str: str,sender: str) -> dict:
    try:
        if not validate_personal_data(sender,os.environ.get("ID_RESTAURANTE", "9")):
            PROMPT_MEDIOS_PAGO = f"""
El cliente {nombre} ha confirmado que quiere pedir pero aun no confirma su pedido.

OBJETIVO:
Generar un ÚNICO mensaje breve, cálido y entusiasta.

INSTRUCCIONES OBLIGATORIAS:
- Pide al cliente que elija un método de pago.
- Menciona únicamente estas opciones de pago:
  * Efectivo
  * Datáfono
- Solicita los datos personales listados abajo.
- La solicitud de datos DEBE tener EXACTAMENTE esta estructura y este orden,
  sin agregar texto intermedio ni variaciones:
- Usa saltos de línea reales usando \n
- Trata de acortar el mensaje lo antes posbile para que quepa en un solo mensaje de WhatsApp.
Datos personales requeridos:
-Metodo de pago
-Documento
-Tipo de documento
-Correo electronico

FORMATO DE RESPUESTA:
- Responde ÚNICA Y EXCLUSIVAMENTE con un JSON válido.
- No agregues texto antes ni después del JSON.

Estructura final:
{{
  "mensaje": "texto aquí"
}}
"""
        else:
            PROMPT_MEDIOS_PAGO = f"""            
Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
Tu nombre es PAKO.

El cliente {nombre} ha confirmado que quiere pedir pero aun no confirma su pedido.

OBJETIVO:
Generar un ÚNICO mensaje breve, cálido y entusiasta.

INSTRUCCIONES OBLIGATORIAS:
- Haz un comentario alegre y sabroso sobre el pedido.
- Pide al cliente que elija un método de pago.
- Menciona únicamente estas opciones de pago:
  * Efectivo
  * Datáfono
- El mensaje final debe ser muy corto
- Usa saltos de línea reales usando \n.
FORMATO DE RESPUESTA:
- Responde ÚNICA Y EXCLUSIVAMENTE con un JSON válido.
- No agregues texto antes ni después del JSON.

Estructura final:
{{
  "mensaje": "texto aquí"
}}
"""
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o-mini",   # O gpt-4o / gpt-5 / gpt-5.1
            messages=[
                {"role": "system", "content": "Eres PAKO y respondes siempre en JSON limpio."},
                {"role": "user", "content": PROMPT_MEDIOS_PAGO}
            ]
        )
    
        raw_text = response.choices[0].message.content
        log_message(f"Respuesta cruda:{raw_text}","INFO")
        costo=calcular_costo_openai(response,"gpt-4o-mini")
        log_message(f"[OpenAI] solicitarmedio pago costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] solicitar_medio_pago tokens_used={tokens_used}", "DEBUG")
        try:
            # Limpieza de escapes innecesarios que pueden romper el JSON
            clean_text = raw_text.replace('\\$', '$')
            data = json.loads(clean_text)
        except json.JSONDecodeError:
            # Fallback si GPT no devuelve JSON válido
            data = {
                "mensaje": f"¡{nombre}, ese pedido está para antojar a cualquiera! 🤤 Tu orden ({codigo_unico}) en {nombre_local} quedó tremenda. ¿Qué medio de pago prefieres: efectivo o datafono ambos son contraentrega"
            }

        return data

    except Exception as e:
        log_message(f'Error en función <solicitar_medio_pago>: {e}', 'ERROR')
        return {
            "mensaje": f"¡{nombre}, ese pedido está para antojar a cualquiera! 🤤 Tu orden ({codigo_unico}) en {nombre_local} quedó tremenda. ¿Qué medio de pago prefieres: efectivo, transferencia (Nequi/Daviplata/Bre-B), tarjeta débito o tarjeta crédito?"
        }

def enviar_menu_digital(nombre: str, nombre_local: str, menu, promociones_list: list | None) -> dict:
    try:
        if promociones_list:
            hoy = date.today()
            promociones_con_vigencia = []
            for p in promociones_list:
                try:
                    fecha_fin_raw = p.get("fecha_fin")
                    if isinstance(fecha_fin_raw, str):
                        fecha_fin = datetime.fromisoformat(fecha_fin_raw).date()
                    elif isinstance(fecha_fin_raw, datetime):
                        fecha_fin = fecha_fin_raw.date()
                    else:
                        fecha_fin = fecha_fin_raw  # por si ya es date
                    dias_restantes = (fecha_fin - hoy).days
                    if dias_restantes == 0:
                        vence_texto = "La promo vence **hoy**."
                    elif dias_restantes == 1:
                        vence_texto = "La promo vence **mañana**."
                    elif dias_restantes > 1:
                        vence_texto = f"Vence en {dias_restantes} días."
                    else:
                        vence_texto = "La promo ya no está vigente."
                    p_mod = p.copy()
                    p_mod["vence_en"] = dias_restantes
                    p_mod["vence_texto"] = vence_texto
                    promociones_con_vigencia.append(p_mod)
                except Exception:
                    p_mod = p.copy()
                    p_mod["vence_texto"] = "No se pudo calcular la vigencia."
                    promociones_con_vigencia.append(p_mod)
            promociones_json = json.dumps(promociones_con_vigencia, ensure_ascii=False)
            PROMPT = f"""
            Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
            El cliente {nombre} pidió ver las promociones activas.

            Estas son las promociones disponibles (JSON):
            {promociones_json}

            Cada promoción incluye un campo "vence_texto" que indica si la promo termina hoy, mañana o en cuántos días.

            TAREA:
            - Haz un mensaje alegre, sabroso y persuasivo resaltando las promociones.
            - En el mensaje, menciona la urgencia según "vence_texto".
            - Recomienda 1 o 2 promociones específicas.
            - Estilo: cálido, entusiasta, sin sarcasmo ni groserías.
            - Máximo 1 o 2 frases.
            - No saludes, el usuario esta en medio de una conversación

            FORMATO DE RESPUESTA (OBLIGATORIO):
            {{
                "mensaje": "texto aquí"
            }}
            Nada fuera del JSON.
            """
        else:
            menu_json = json.dumps(menu, ensure_ascii=False)
            PROMPT = f"""
            Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
            El cliente {nombre} pidió el menú digital.

            Este es el menú disponible:
            {menu_json}

            TAREA:
            - Haz un comentario alegre y sabroso.
            - Recomienda 2 opciones del menú.
            - Estilo cálido y entusiasta.
            - Máximo 1 o 2 frases.
            - Menciona el local: {nombre_local}
            - No saludes, el usuario esta en medio de una conversación

            FORMATO DE RESPUESTA (OBLIGATORIO):
            {{
                "mensaje": "texto aquí"
            }}
            Nada fuera del JSON.
            """
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Eres el generador oficial de mensajes alegres y de pago para Sierra Nevada."},
                {"role": "user", "content": PROMPT}
            ],
            max_tokens=250,
            temperature=0.95
        )
        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] enviar_menu_digital costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] enviar_menu_digital tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "mensaje": f"¡{nombre}, tenemos promociones activas en {nombre_local}! 😋 ¡Aprovecha y pide ya!"
            }

        return data
    except Exception as e:
        log_message(f'Error en función <enviar_menu_digital>: {e}', 'ERROR')
        logging.error(f"Error en función <enviar_menu_digital>: {e}")
        return {
            "mensaje": f"¡{nombre}, ¿qué esperas para pedir en {nombre_local}? ¡Cuéntame qué se te antoja hoy!"
        }

def responder_sobre_pedido(pregunta_usuario, Tiempo_estimado, Costo_total) -> dict:
    try:
        PROMPT = f"""
        Eres PAKO, la voz oficial y amigable
        Información del pedido:
        
        PREGUNTA:
        {pregunta_usuario}
        Tiempo estimado:{Tiempo_estimado}
        Costo total:{Costo_total}

        REGLAS IMPORTANTES:
        - La respuesta debe basarse SOLO en la información contenida en pedido_info.
        - Si el usuario pregunta por algo que NO está en pedido_info, responde amablemente
          que no tienes ese dato exacto y ofrece revisar menú o promociones.
        - Estilo: cálido, alegre, amable, un poquito divertido, sin sarcasmo y sin exagerar.
        - Máximo 2 frases.
        - No inventes datos adicionales.
        - No mencionar que eres una IA.
        - Respuesta SIEMPRE en JSON.
        - Si el tiempo estimado no existe indica que tardaras en promedio 30 minutos
        - Solo contesta lo que el usuario pregunta si no te pregunta por tiempo o costo no lo menciones aunque pregunte.

        FORMATO DE RESPUESTA OBLIGATORIO:
        {{
          "mensaje": "texto aquí",
        }}
        Nada por fuera del JSON.
        REGLA CRÍTICA:
        NO puedes asumir el estado del pedido. NO puedes decir que está listo, procesado, en preparación, entregado ni nada similar.
        Solo puedes repetir literalmente lo que aparezca en el campo "estado" dentro de pedido_info.

        PROHIBIDO:
        - Decir que el pedido está "listo", "procesado", "en camino", "confirmado" o cualquier estado.
        - Interpretar o adivinar datos.
        - Inventar palabras relacionadas al estado.
        - Solo usa la informacion que te di
        """
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Eres PAKO, representante alegre de Sierra Nevada."},
                {"role": "user", "content": PROMPT}
            ],
            max_tokens=200,
            temperature=0.8
        )
        raw = response.choices[0].message.content.strip()
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] responder_sobre_pedido tokens_used={tokens_used}", "DEBUG")
        data = json.loads(raw)
        mensaje = data["mensaje"]
        log_message(f'Respuesta cruda de GPT en <ResponderSobrePedido>: {mensaje}', 'DEBUG')
        return mensaje
    except Exception as e:
        log_message(f'Error en función <ResponderSobrePedido>: {e}', 'ERROR')
        logging.error(f"Error en función <ResponderSobrePedido>: {e}")
        return {
            "mensaje": "Tuve un problema procesando tu solicitud, pero si quieres puedo mostrarte el menú o las promociones.",
            "futura_intencion": "consulta_menu"
        }
    
def responder_sobre_promociones(nombre: str, nombre_local: str, promociones_info: list, pregunta_usuario: str) -> dict:
    """
    Similar a responder_sobre_pedido, pero ahora responde únicamente
    sobre promociones y nada más. Basado SOLO en promociones_info.
    """
    try:

        # Convertir valores a JSON-safe (Decimal, datetime, etc.)
        promociones_serializables = []
        for promo in promociones_info:
            limpio = {k: to_json_safe(v) for k, v in promo.items()}
            promociones_serializables.append(limpio)

        PROMPT = f"""
        Eres PAKO, la voz oficial, alegre y amigable de {nombre_local}.
        Estas son las promociones disponibles hoy:
        {json.dumps(promociones_serializables, ensure_ascii=False)}

        PREGUNTA DEL USUARIO:
        "{pregunta_usuario}"

        REGLAS IMPORTANTES:
        - SOLO puedes responder basándote en las promociones dentro del JSON mostrado arriba.
        - Si el usuario pregunta algo que NO está en las promociones (precio, disponibilidad, fechas, condiciones, etc.)
          debes responder: "No tengo ese dato exacto", y ofrecer consultar menú o ver más promociones.
        - Estilo: cálido, amable, alegre, un poquito divertido, sin sarcasmo y sin exagerar.
        - Máximo 2 frases.
        - Siempre incluir un llamado a la acción para "consultar menú" o "consultar promociones".
        - No inventes datos adicionales.
        - No menciones que eres una IA.
        - NO inventar promociones nuevas, solo usar las listadas.
        - Siempre haz un llamado a la acción al final para hacer pedido con base a las promociones listadas.

        OPCIONES válidas para futura_intencion:
        - "continuacion_promocion"

        FORMATO DE RESPUESTA OBLIGATORIO:
        {{
          "mensaje": "texto aquí",
          "futura_intencion": "continuacion_promocion"
        }}

        NINGÚN TEXTO por fuera del JSON.
        """

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": f"Eres PAKO, representante alegre y amigable de {nombre_local}, experto en promociones."},
                {"role": "user", "content": PROMPT}
            ],
            temperature=0.85
        )

        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] responder sobre promociones_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] responder_sobre_promociones tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except:  # noqa: E722
            data = {
                "mensaje": f"{nombre}, aquí en {nombre_local} tengo varias promociones buenísimas. "
                           f"Si quieres, puedo mostrarte más o llevarte al menú.",
                "futura_intencion": "continuacion_promocion"
            }

        return data

    except Exception as e:
        log_message(f'Error en función <ResponderSobrePromociones>: {e}', 'ERROR')
        logging.error(f"Error en función <ResponderSobrePromociones>: {e}")
        return {
            "mensaje": f"{nombre}, tuve un problema procesando las promociones, pero si quieres puedo mostrarte el menú o las promos disponibles.",
            "futura_intencion": "continuacion_promocion"
        }

def interpretar_eleccion_promocion(pregunta_usuario: str, info_promociones_str: str, respuesta_previa_promocion: str, pedido_dict: dict) -> dict:
    """
    info_promociones_str: viene como STR desde intencion_futura → lo convertimos a lista
    pedido_dict: contiene items, total_price, etc.
    """
    prompt = f"""
        Eres un sistema experto en análisis de promociones.
        ### Productos del pedido:
        {pedido_dict}
        ### Promociones disponibles:
        {info_promociones_str}
        ### Mensaje previo del chatbot:
        "{respuesta_previa_promocion}"
        ### Mensaje actual del usuario:
        "{pregunta_usuario}"
        Tu tarea:
        1. Detecta qué productos del pedido califican para cada promoción.
        2. Evalúa TODAS las promociones y determina la(s) que realmente aplican.
        3. Calcula el total_final correspondiente a la mejor promoción (mayor beneficio).
        4. Devuelve SOLO la mejor promoción aplicable.
        5. Si NO aplica ninguna promoción, responde con:
        - valida_promocion = false
        - total_final = total_original
        - idpromocion = ""

        ### Importante:
        - No inventes promociones, usa SOLO las del input.
        - Usa los precios reales en pedido_dict['items'][i]['matched']['price'].
        - Solo una promoción final debe seleccionarse.

        ### Salida OBLIGATORIA (JSON PURO):

        {{
        "valida_promocion": true/false,
        "idpromocion": "",
        "total_final": 0,
        "nombre_promocion": "",
        "motivo": "Explicación clara"
        }}
        """
    client = OpenAI()
    response = client.responses.create(
        model="gpt-5.1",
        input=prompt,
        temperature=0
    )
    try:
        raw = response.output_text   
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] interpretar_eleccion_promocion costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] interpretar_eleccion_promocion tokens_used={tokens_used}", "DEBUG")
        data = json.loads(raw)
    except Exception as e:
        log_message(f"Error en <interpretar_eleccion_promocion>: {e}", "ERROR")
        data = {
            "valida_promocion": False,
            "idpromocion": "",
            "total_final": pedido_dict.get("total_price", 0),
            "nombre_promocion": "",
            "motivo": "Error interpretando la IA"
        }
    return data

def pedido_incompleto_dynamic_promocion(mensaje_usuario: str, promociones_lst: str, json_pedido: str) -> dict:
    try:

        PROMPT_PEDIDO_INCOMPLETO = """
        Eres la voz oficial de Sierra Nevada, La Cima del Sabor. Te llamas PAKO.

        El cliente escribió: "{mensaje_usuario}"
        El gestor de pedidos detectó que el pedido está INCOMPLETO o POCO CLARO:
        {json_pedido}

        Tu tarea:
        - Responder SOLO con un JSON válido.
        - NO inventar productos. NO mencionar nada que NO esté en el menú.

        Otras reglas:
        - Si el cliente pide algo que NO existe en el menú, indícalo y sugiere 1 a 3 opciones reales.
        - Si pide algo muy general (ej: “una hamburguesa”), sugiere opciones del menú.
        - SIEMPRE pedir que el cliente vuelva a escribir todo su pedido claramente,
          excepto cuando esté mezclando cosas fuera de la promoción (ver regla nueva).

        Responde SOLO este formato exacto:
        {{
            "mensaje": "texto aquí",
            "recomendaciones": ["op1", "op2"],
            "intencion": "consulta_menu"
        }}

        Reglas estrictas:
        - No inventes productos.
        - Usa coincidencia aproximada para entender la intención del cliente,pero la respuesta final debe ser EXACTA del menú.

        Aquí está las promociones disponibles:
        {promociones_str}

        LAS HAMBURGESAS SE LLAMAN:
            "Sierra Veggie"
            "LInsaciable"
            "Sierra Bomba"
            "Sierra Costeña"
            "Sierra Melao"
            "Sierra Clasica"
            "Camino a la cima"
            "Sierra Queso"

        CUANDO PIDAN UN ADICIONAL EN CUALQUIER PRODUCTO, Usa coincidencia aproximada para entender la intención.
        PERO la respuesta final siempre debe ser una salsa EXACTA del menú:
            "Carne de res 120g"
            "Cebollas caramelizadas"
            "Cebollas caramelizadas picantes"
            "Pepinillos agridulces"
            "Plátano maduro frito"
            "Suero costeño"
            "Chicharrón"
            "Tocineta"
            "Queso costeño frito"
            "Queso cheddar"

        CUANDO PIDAN SALSAS, Usa coincidencia aproximada para entender la intención.
        PERO la respuesta final siempre debe ser una salsa EXACTA del menú.:
            "Salsa de tomate"
            "Salsa mostaza"
            "Salsa bbq"
            "Salsa mayonesa"

        CUANDO PIDAN BEBIDAS, Usa coincidencia aproximada para entender la intención.
        PERO la respuesta final siempre debe ser una bebida EXACTA del menú.:
            "Fuze tea de manzana 400 ml"
            "Fuze tea de limón 400 ml"
            "Fuze tea de durazno 400 ml"
            "Kola Roman 400 ml"
            "Quatro 400 ml"
            "Sprite 400ml"
            "Coca Cola Sin Azúcar 400 ml"
            "Coca Cola Original 400 ml"
            "Agua normal 600 ml"
            "Agua con gas 600ml"
            "Limonada de panela orgánica 350Ml"

        CUANDO PIDAN ACOMPAÑAMIENTOS,Usa coincidencia aproximada para entender la intención.
        PERO la respuesta final siempre debe ser un acompañamiento EXACTO del menú.:
            "Platanitos maduros"
            "Papas Costeñas (francesas medianas + 4 deditos de queso costeño)"
            "Costeñitos fritos + Suero Costeño"
            "Anillos de Cebolla"
            "Papas francesas"
        Acepta coincidencias parciales SOLO si es OBVIO que se refiere a un producto real.
        Nunca adivines si hay más de una opción posible.
        si el pedido es general, no específico, sugiere opciones del menú. siempre con un call 2 action.
        """
        promociones_str = str(promociones_lst)
        prompt = PROMPT_PEDIDO_INCOMPLETO.format(
            mensaje_usuario=mensaje_usuario.lower(),
            promociones_str=promociones_str,
            json_pedido=json_pedido
        )
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": "Eres PAKO, asistente oficial de Sierra Nevada."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )
        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] pedido incompleto dynamic costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] pedido_incompleto_dynamic_promocion tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "mensaje": "Por favor elige solo los productos de la promoción o inicia un pedido desde cero escribiendo 'menu' u 'hola'.",
                "recomendaciones": [],
                "intencion": "consulta_menu"
            }
        return data
    except Exception as e:
        log_message(f'Error en función <pedido_incompleto_dynamic_promocion>: {e}', 'ERROR')
        return {
            "mensaje": "Por favor elige solo los productos de la promoción o inicia un pedido desde cero escribiendo 'menu' u 'hola'.",
            "recomendaciones": [],
            "intencion": "consulta_menu"
        }

def mapear_modo_pago(respuesta_usuario: str) -> str:
    try:
        """Mapea la respuesta del usuario al método de pago estandarizado."""
        client = OpenAI()
        PROMPT_MAPEO_PAGO = f"""
        Eres un clasificador experto en interpretar el método de pago que un cliente escribe en WhatsApp, incluso cuando lo escribe con errores, abreviaciones o de forma muy informal.

        Debes analizar el texto del usuario y responder exclusivamente uno de los siguientes valores:

        - "datafono"
        - "efectivo"
        - "desconocido"
        - "datafono"

        Reglas:
        1. Aunque esté mal escrito, identifica la intención correcta.
        2. Si menciona:
        - "datafono", "datáfono", "dátáfono", "datafon" → "datafono"
        3. tarjeta, tc, td, targta, tarjta, crédito, débito → "datafono"
        4. efectivo, cash → "efectivo"
        5. Si no puedes entenderlo → "desconocido"

        Formato de salida OBLIGATORIO (JSON puro):
        {{
            "metodo": "uno de los valores permitidos"
        }}
        Aqui el mensaje del usuario:
        {respuesta_usuario}
        """
        if not respuesta_usuario:
            return "desconocido"

        prompt = PROMPT_MAPEO_PAGO 
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            max_output_tokens=60,
            temperature=0
        )
        raw = response.output_text
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] mapear_modo_pago costo={costo:.6f}","DEBUG")
        log_message(f'Raw response de <mapear_modo_pago>: {raw}', 'DEBUG')
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] mapear_modo_pago tokens_used={tokens_used}", "DEBUG")

        try:
            clean = str(raw or "").strip()
            clean = re.sub(r'^```json\s*', '', clean, flags=re.I)
            clean = re.sub(r'^```', '', clean, flags=re.I).strip()
            clean = re.sub(r'```$', '', clean, flags=re.I).strip()

            if not clean:
                log_message("mapear_modo_pago: respuesta vacía después de sanear", "WARN")
                return "desconocido"

            try:
                data = json.loads(clean)
            except Exception:
                m = re.search(r'\{.*\}', clean, flags=re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(0))
                    except Exception as e:
                        log_message(f"mapear_modo_pago: fallo al parsear objeto JSON extraído: {e}", "ERROR")
                        data = None
                else:
                    data = None

            if data and isinstance(data, dict):
                metodo = data.get("metodo", "desconocido")
                log_message(f"mapear_modo_pago: metodo detectado desde JSON -> {metodo}", "DEBUG")
                return metodo
            # Fallback por keywords si no hay JSON parseable
            text = clean.lower()
            if "nequi" in text or "neki" in text:
                metodo = "transferencia - nequi"
            elif "daviplata" in text or "davi" in text:
                metodo = "transferencia - daviplata"
            elif "bre-b" in text or "breb" in text:
                metodo = "transferencia - bre-b"
            elif any(k in text for k in ("tarjeta", "tc", "td", "targta", "tarjta", "crédito", "credito", "débito", "debito")):
                metodo = "tarjeta"
            elif any(k in text for k in ("nfc", "contactless", "acercar")):
                metodo = "nfc"
            elif any(k in text for k in ("efectivo", "cash")):
                metodo = "efectivo"
            elif any(k in text for k in ("datafono", "datáfono", "datafon")):
                metodo = "datafono"
            else:
                metodo = "desconocido"

            log_message(f"mapear_modo_pago: metodo detectado por fallback -> {metodo}", "DEBUG")
            return metodo
        except Exception as e:
            log_message(f"mapear_modo_pago: excepción inesperada al parsear respuesta: {e}", "ERROR")
            return "desconocido"
    except Exception as e:
        log_message(f"Error mapeando método de pago: {e}", "ERROR")
        return "desconocido"

def solicitar_metodo_recogida(nombre: str, codigo_unico: str, nombre_local: str, pedido_str: str) -> str:
    try:

        prompt = f"""
Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
Te llamas PAKO.

El cliente {nombre} ya confirmó que quiere pedir
Este es el pedido que hizo:
"{pedido_str}"

TAREA:
- Estilo: cálido, entusiasta.
- Máximo 1 frase en dos lineas.
Después:
- Pregunta amablemente dónde quiere recibir su pedido.
- No saludes estamos en medio de una conversación
- Lista ambas opciones:
  • Recoger en tienda
  • Envío a domicilio (depende de la zona).
- Usa saltos de línea reales usando '\n'
FORMATO ESTRICTO:
{{
  "mensaje": "texto aquí"
}}
"""

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Eres PAKO y respondes siempre en JSON válido."},
                {"role": "user", "content": prompt}
            ],
        )

        raw = response.choices[0].message.content
        costo=calcular_costo_openai(response,"gpt-4o-mini")
        log_message(f"[OpenAI] solicitar_metodo_recogida costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] solicitar_metodo_recogida tokens_used={tokens_used}", "DEBUG")
        # normalizar a str
        if isinstance(raw, dict):
            mensaje = raw.get("mensaje", "")
        else:
            raw_str = str(raw).strip()
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, dict):
                    mensaje = parsed.get("mensaje", "")
                else:
                    mensaje = raw_str
            except Exception:
                mensaje = raw_str

        mensaje = mensaje.strip() if isinstance(mensaje, str) else ""
        if not mensaje:
            # fallback seguro (texto por defecto)
            mensaje = f"¡{nombre}, tu pedido ({codigo_unico}) quedó delicioso! ¿Vas a querer domicilio o prefieres recogerlo en el restaurante?"

        log_message(f'Respuesta de <solicitar_metodo_recogida> (mensaje): {mensaje[:300]}', 'DEBUG')
        return mensaje

    except Exception as e:
        log_message(f'Error en función <solicitar_metodo_recogida>: {e}', 'ERROR')
        return f"¡{nombre}, tu pedido ({codigo_unico}) quedó delicioso! ¿Vas a querer domicilio o prefieres recogerlo en el restaurante?"
    
def generar_mensaje_confirmacion_modificacion_pedido(
        pedido_json: dict,
        items_menu: list,
        promocion: bool = False,
        promociones_info: list = None,
        pedido_completo_promocion: dict = None,
        model: str = "gpt-5.1",
    ) -> dict:
    """
    Presenta el pedido al cliente y finaliza SIEMPRE con:
    “¿Desea modificar algo de su pedido?”

    No realiza confirmaciones ni preguntas adicionales.
    """
    raw = ""

    try:
        client = OpenAI()
        if not promocion:
            prompt = f"""
Eres PAKO, asistente de WhatsApp del restaurante Sierra Nevada, La Cima del Sabor.

RECIBES un JSON de pedido validado:
{json.dumps(pedido_json, ensure_ascii=False)}

Y una lista de productos del menú:
{json.dumps(items_menu, ensure_ascii=False)}

TU MISIÓN:
1. Presentar el pedido al cliente:
   - Lista cada producto.
   - Incluye sus modificadores (si existen).
   - Muestra precios individuales.
   - Muestra el total.
   - No inventes productos ni precios.

TONO:
- Cercano, muy amigable y natural.
- Profesional y claro, sin sonar robótico.

RECOMENDACIONES (SI APLICA):
1. SI EL PEDIDO TIENE MENOS DE 2 PRODUCTOS:
   - Ofrece 1 producto adicional del menú.
2. OFRECER 1 acompañamiento, bebida o adición:
   - NO menciones el nombre exacto del producto del menú.
   - Usa descripciones genéricas y apetitosas.
     Ejemplos:
       - “unas papitas bien crocantes”
       - “una bebida bien fría”
   - SÍ incluye el precio real del producto.
   - No inventes precios ni categorías.
   - Si ya hay bebidas no recomiendes más bebidas.
   - Si ya hay acompañamientos no recomiendes más acompañamientos.
   - Si ya hay adiciones no recomiendes más adiciones.
3. Si la proteina del producto (res,cerdo y pollo) no ha sido definida preguntale al cliente que proteina quiere

CIERRE:
- Si das recomendaciones, finaliza exactamente con:
  "o ¿tu pedido está bien así?"
- Si NO das recomendaciones, finaliza con:
  "¿Confirmas tu pedido?"

FORMATO OBLIGATORIO (JSON LISO):
{{
  "mensaje": "mensaje breve en lenguaje natural presentando el pedido y cerrando con la pregunta obligatoria",
  "intencion_siguiente": "preguntar_modificacion"
}}

REGLAS:
- No incluyas texto fuera del JSON.
- No uses emojis.
- No inventes productos, precios ni condiciones.
- No incluyas las descripciones de los productos del menú.
- Si el cliente pide papitas se refiere a una porcion de papas francesas.
"""

        else:
            if promociones_info is None or pedido_completo_promocion is None:
                raise ValueError("promociones_info y pedido_completo_promocion son obligatorios cuando promocion=True.")

            prompt = f"""
Eres PAKO, asistente de WhatsApp del restaurante Sierra Nevada.

RECIBES:
1) Pedido original:
{json.dumps(pedido_json, ensure_ascii=False)}

2) Pedido final con promociones aplicadas:
{json.dumps(pedido_completo_promocion, ensure_ascii=False)}

3) Promociones vigentes:
{json.dumps(promociones_info, ensure_ascii=False)}

TU MISIÓN:
- Presentar el pedido final al cliente.
- Explicar brevemente cuál promoción aplica (si aplica).
- Indicar los precios finales por producto.
- No inventes datos.

FINAL OBLIGATORIO:
“¿Desea modificar algo de su pedido?”

FORMATO JSON EXACTO:
{{
  "mensaje": "presentación del pedido + pregunta obligatoria",
  "intencion_siguiente": "preguntar_modificacion"
}}

REGLAS:
- No uses emojis.
- No incluyas texto fuera del JSON.
- Tono cálido y profesional.
"""

        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0
        )
        log_message(f'prompt: {prompt}', 'DEBUG')
        raw = response.output[0].content[0].text.strip()
        tokens_used = _extract_total_tokens(response)
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] generar_mensaje_confirmacion_modificacion_pedido costo={costo:.6f}","DEBUG")
        if tokens_used is not None:
            log_message(f"[OpenAI] generar_mensaje_confirmacion_modificacion_pedido tokens_used={tokens_used}", "DEBUG")
        clean = raw
        clean = re.sub(r'^```json', '', clean, flags=re.I).strip()
        clean = re.sub(r'^```', '', clean).strip()
        clean = re.sub(r'```$', '', clean).strip()

        return json.loads(clean)

    except Exception as e:
        log_message(f'Error en función <generar_mensaje_confirmacion_modificacion_pedido>: {e}', 'ERROR')
        return {
            "mensaje": "Hubo un error generando el mensaje.",
            "intencion_siguiente": "preguntar_modificacion",
            "raw_output": raw
        }

def solicitar_confirmacion_direccion(cliente_nombre: str, sede_info: dict) -> dict:
    """
    Genera un mensaje personalizado para confirmar la dirección de envío,
    usando ChatGPT con tono cálido y cercano.
    """
    try:

        PROMPT_CONFIRMAR_DIRECCION = """
        Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
        Te llamas PAKO.

        El cliente se llama: {cliente_nombre}.

        Información de la sede asignada:
        - ID sede: {id_sede}
        - Nombre sede: {nombre_sede}
        - Ciudad: {ciudad_sede}
        - Distancia desde cliente: {distancia_km} km

        Dirección detectada del cliente:
        "{direccion_envio}"

        TAREA:
        - Envíale un mensaje cálido, alegre y amigable al cliente llamándolo por su nombre.
        - Pregunta SIEMPRE si esa dirección está correcta para realizar el envío.
        - Tono: amable, cercano, estilo.
        - Máximo 1 o 2 frases antes de la pregunta.
        - No uses groserías ni sarcasmo.
        - Pregunta si confirma su direccion guardada
        - Lo mas puntual posible

        FORMATO DE RESPUESTA (OBLIGATORIO):
        {{
            "mensaje": "texto aquí"
        }}
        Nada fuera del JSON.
        """

        prompt = PROMPT_CONFIRMAR_DIRECCION.format(
            cliente_nombre=cliente_nombre,
            id_sede=sede_info.get("id"),
            nombre_sede=sede_info.get("nombre"),
            ciudad_sede=sede_info.get("ciudad"),
            distancia_km=sede_info.get("distancia_km"),
            direccion_envio=sede_info.get("direccion_envio")
        )

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres PAKO, generador oficial de mensajes cálidos y profesionales de Sierra Nevada."},
                {"role": "user", "content": prompt}
            ],
            #max_tokens=150,
            temperature=0.85
        )
        print
        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-4o-mini")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] solicitar_confirmacion_direccion tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except:  # noqa: E722
            # fallback seguro
            data = {
                "mensaje": (
                    f"¡Hola {cliente_nombre}! Qué alegría tenerte por aquí 🙌 "
                    f"Tenemos registrada la dirección: \"{sede_info.get('direccion_envio')}\". "
                    "¿es correcta? si no lo es envianos la correcta"
                )
            }
        return data

    except Exception as e:
        log_message(f'Error en función <solicitar_confirmacion_direccion>: {e}', 'ERROR')
        logging.error(f"Error en función <solicitar_confirmacion_direccion>: {e}")

        return {
            "mensaje": (
                f"¡Hola {cliente_nombre}! Tenemos la dirección: \"{sede_info.get('direccion_envio')}\". "
                "¿Está correcta para hacerte el envío?"
            )
        }

def generar_mensaje_invitar_pago(
        nombre_cliente: str,
        valor: float,
        duracion: str,
        distancia: float,
        direccion_envio: str,
        codigo_pedido: str,
        valor_total_pedido: str,
        model: str = "gpt-4o-mini"
    ) -> str:
    """
    Llama a ChatGPT para generar un mensaje cordial que:
    - Sintetice valor, duración, distancia y dirección de envío.
    - Invite al cliente a realizar el pago.
    """

    try:
        prompt = f"""
Eres un asistente amable de una hamburguesería.
Genera un mensaje CORTO, cálido y claro para un cliente.

Datos:
- Valor del domicilio: {valor}
- Duración estimada del envío: {duracion}
- Distancia aproximada: {distancia} m
- Dirección de envío: {direccion_envio}
- Nombre del cliente: {nombre_cliente}
- Código del pedido {codigo_pedido}
- Valor total pedido: {valor_total_pedido}

Instrucciones del mensaje:
- Resume los datos de manera natural.
- Confirma que esa es la dirección de envío.
- Invita al cliente a realizar el pago para continuar con el pedido.
- No inventes información adicional.
- Tono amable, profesional y cercano.
- Siempre di el codigo del pedido, valor del domicilio y total del pedido
- Di que estara en camino una vez se confirme el pago.
"""
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Eres un asistente de pedidos experto en atención al cliente."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.5
        )
        costo=calcular_costo_openai(response,"gpt-4o-mini")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] generar_mensaje_invitar_pago tokens_used={tokens_used}", "DEBUG")

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error al generar mensaje: {str(e)}"

def generar_mensaje_seleccion_sede(nombre_cliente: str,sender: str, model: str = "gpt-4o-mini") -> str:
    """
    Genera un mensaje personalizado con ChatGPT invitando al cliente
    a seleccionar una de las sedes disponibles.
    """
    try:
        # Obtener id_sede más cercana y su info
        query = """SELECT id_sede FROM clientes_whatsapp WHERE telefono = %s and id_restaurante = %s LIMIT 1"""
        result = execute_query(query, (sender, ID_RESTAURANTE))
        id_sede_cercana = result[0][0] if result else None

        query = """SELECT nombre, direccion FROM sedes WHERE id_sede = %s and id_restaurante = %s LIMIT 1"""
        result = execute_query(query, (id_sede_cercana, ID_RESTAURANTE))
        sede_cercana = result[0] if result else ("", "")

        # Obtener todas las sedes
        query = """SELECT nombre, direccion FROM sedes WHERE estado = true and id_restaurante = %s"""
        result = execute_query(query, (ID_RESTAURANTE,))
        sedes = [{"nombre": row[0], "direccion": row[1]} for row in result]

        # Formatear sedes para el prompt
        sedes_str = "\n".join([f"- {s['nombre']}: {s['direccion']}" for s in sedes])

        prompt = f"""
Eres PAKO, la voz oficial de Sierra Nevada, La Cima del Sabor.
Tu misión es hablar de manera cálida, confiable y amigable.

El cliente se llama: {nombre_cliente}
La sede más cercana al cliente es: {sede_cercana[0]} ({sede_cercana[1]})

Genera un mensaje corto y amable invitándolo a escoger una de las siguientes sedes:

📍 **Sedes disponibles**
{sedes_str}

Instrucciones:
- Habla como asistente conversacional (no en formato técnico).
- Menciona su nombre.
- Invita a seleccionar una sede.
- No inventes sedes nuevas.
- Sé detallado con las direcciones de cada una.
- No enumeres.
- Pide que escriban el nombre de la sede para recoger.
- Siempre ofrece recogerlo en la sede más cercana primero y luego lista las otras como opciones.
- De las direcciones obtenidas no menciones ni la ciudad ni el pais solo la direccion y el barrio si aplica.
- No saludes al cliente estas en medio de una conversacion
- Haz el mensaje lo mas corto que puedas
"""
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Eres un asistente experto redactando mensajes conversacionales."},
                {"role": "user", "content": prompt}
            ],
            #max_tokens=200,
            temperature=0.7
        )
        print(prompt)
        costo=calcular_costo_openai(response,"gpt-4o-mini")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] generar_mensaje_seleccion_sede tokens_used={tokens_used}", "DEBUG")

        return response.choices[0].message.content.strip()
    except Exception as e:
        log_message(f"Error al generar mensae seleccion sede {e}", "ERROR")
        return f"Error al generar mensaje: {e}"
    
def mapear_sede_cliente(texto_cliente: str):
    """
    Usa ChatGPT 5.1 para identificar la sede mencionada por el cliente
    y retorna sus datos completos desde la BD.
    """
    client = OpenAI()
    # 1. Obtener sedes desde BD
    sedes = execute_query("""
        SELECT nombre, direccion, id_sede, latitud, longitud
        FROM sedes
        where estado = true and id_restaurante = %s
    """, (ID_RESTAURANTE,))

    if not sedes:
        return {"error": "No se encontraron sedes en la base de datos."}

    # Construir un diccionario para ChatGPT
    lista_sedes = [
        {
            "nombre": s[0],
            "direccion": s[1],
            "id_sede": s[2],
            "latitud": s[3],
            "longitud": s[4]
        }
        for s in sedes
    ]

    # 2. Prompt para ChatGPT
    prompt = f"""
Eres un asistente experto en normalización de texto.
Un cliente escribió: "{texto_cliente}"

Tu tarea: identificar cuál de las siguientes sedes quiso decir el cliente.

Sedes disponibles (datos reales):
{lista_sedes}

        Reglas:
        - Debes devolver el nombre EXACTO de la sede según está en la lista.
        - Si el cliente escribe con errores, corrige e interpreta.
        - Si escribe solo una palabra ("virrey", "galerias", "centro mayor"), mapea a la sede correcta.
        - Si no puedes identificar ninguna sede, responde "NINGUNA".

        Devuelve SOLO el nombre EXACTO de la sede, sin explicaciones.
        """

    completion = client.chat.completions.create(
        model="gpt-5.1",
        messages=[
            {"role": "system", "content": "Eres un asistente preciso para mapear sedes de restaurantes."},
            {"role": "user", "content": prompt}
        ]
    )

    nombre_predicho = completion.choices[0].message.content
    costo=calcular_costo_openai(completion,"gpt-5.1")
    log_message(f"[OpenAI] mapear_sede_cliente costo={costo:.6f}","DEBUG")
    tokens_used = _extract_total_tokens(nombre_predicho)
    if tokens_used is not None:
        log_message(f"[OpenAI] mapear_sede_cliente tokens_used={tokens_used}", "DEBUG")

    if nombre_predicho.upper() == "NINGUNA":
        return {"error": "No se pudo identificar la sede mencionada."}

    # 4. Buscar la sede real en la tabla
    for sede in lista_sedes:
        if sede["nombre"].lower() == nombre_predicho.lower():
            return {
                "nombre_sede": sede["nombre"],
                "direccion_sede": sede["direccion"],
                "id_sede": sede["id_sede"],
                "latitud_sede": sede["latitud"],
                "longitud_sede": sede["longitud"]
            }

    return {"error": "La IA mencionó una sede que no existe en la BD."}

def generar_mensaje_recogida_invitar_pago(
        nombre_cliente: str,
        nombre_sede: str,
        direccion_sede: str,
        valor_total_pedido: float,
        tiempo_pedido: str,
        codigo_pedido: str,
        model: str = "gpt-5.1"
    ) -> str:
    """
    Genera un mensaje amable para pedidos con recogida en sede.
    """
    try:
        client = OpenAI()
        prompt = f"""
Eres PAKO, la voz oficial de Sierra Nevada, La Cima del Sabor.

Tu tarea:
Generar un mensaje cálido, claro y corto para un cliente que recogerá su pedido en una sede.

Datos:
- Nombre del cliente: {nombre_cliente}
- Sede de recogida: {nombre_sede}
- Dirección de la sede: {direccion_sede}
- Valor total del pedido: {valor_total_pedido}
- Código del pedido: {codigo_pedido}

Instrucciones del mensaje:
- Habla con tono amable y profesional.
- Di el nombre del cliente.
- Confirma la sede y su dirección donde recogerá el pedido.
- Indica en cuánto tiempo puede pasar por él.
- Indica el valor total del pedido.
- Menciona claramente el código del pedido.
- No mencionar domicilio ni distancias porque es recogida en tienda.
- No inventar información adicional.

Finaliza: Preguntando al cliente en cuanto tiempo pasara por su pedido
"""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Eres un asistente experto redactando mensajes cordiales y personalizados para clientes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )
        # Registrar consumo de tokens
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] generar_mensaje_recogida_invitar_pago costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] generar_mensaje_recogida_invitar_pago tokens_used={tokens_used}", "DEBUG")


        return response.choices[0].message.content

    except Exception as e:
        log_message(f"Error en generar mensaje recogida invitar pago {e}", "ERROR")
        return f"Error al generar mensaje: {e}"
    
def extraer_info_personal(mensaje: str) -> dict:
    """
    Usa ChatGPT para extraer información personal del cliente
    a partir de su mensaje en WhatsApp.
    Devuelve un dict con campos tipo_documento, numero_documento, email.
    Siempre retorna un dict con las 3 claves; si no se extrae, el valor será "No proporcionado".
    """
    try:
        prompt = f"""
Eres un asistente experto en extraer información personal de mensajes de clientes.
Un cliente escribió el siguiente mensaje: "{mensaje}"
Tu tarea: extraer la siguiente información si está disponible:
- Tipo de documento (ej: CC, CE, TI, PA, NIT, PEP, PT, RC)
Si te dicen Cedula de ciudadania, responde CC.
Si te dicen Cedula de extranjeria, responde CE.
Si te dicen NIT, responde NIT.
Si te dicen Pasaporte, responde PA.
Si te dicen Tarjeta de identidad, responde TI.
Si te dicen Permiso especial de permanencia, responde PEP.
Si te dicen Registro civil, responde RC.
- Número de documento
- Email
Devuélvelo SOLO en formato JSON EXACTO, sin texto adicional, por ejemplo:
{{
    "tipo_documento": "CC",
    "numero_documento": "12345678",
    "email": "correo@ejemplo.com",
}}
Si no encuentras un campo coloca exactamente "No proporcionado" como valor para ese campo.
"""
        client = OpenAI(api_key=get_openai_key())
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Eres PAKO, asistente experto en extracción de datos."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0
        )
        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] extraer_info_personal costo={costo:.6f}","DEBUG")
        # Registrar consumo de tokens
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] extraer_info_personal tokens_used={tokens_used}", "DEBUG")
        # Limpieza básica de bloques ```json``` o ``` alrededor
        if raw.startswith("```"):
            raw = raw.strip("`").strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()

        # Intentar parsear JSON directo
        try:
            parsed = json.loads(raw)
        except Exception:
            # intentar extraer first JSON object with regex
            import re
            m = re.search(r'(\{[\s\S]*\})', raw)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                except Exception:
                    parsed = None
            else:
                parsed = None

        # Normalizar salida garantizando llaves requeridas
        resultado = {
            "tipo_documento": "No proporcionado",
            "numero_documento": "No proporcionado",
            "email": "No proporcionado",
            "nombre": "No proporcionado"
        }
        if isinstance(parsed, dict):
            for k in ["tipo_documento", "numero_documento", "email", "nombre"]:
                val = parsed.get(k)
                if val and isinstance(val, str) and val.strip():
                    resultado[k] = val.strip()
        return resultado
    except Exception as e:
        log_message(f"Error en extraer_info_personal: {e}", "ERROR")
        logging.error(f"Error en extraer_info_personal: {e}")
        return {
            "tipo_documento": "No proporcionado",
            "numero_documento": "No proporcionado",
            "email": "No proporcionado",
            "nombre": "No proporcionado"
        }
    
def direccion_bd(nombre_cliente: str, direccion_google: str, sender: str) -> str:
    """
    Genera un mensaje amable para confirmar la dirección guardada
    """
    try:
        resultado=execute_query("""SELECT observaciones_dir 
                                   FROM clientes_whatsapp
                                   WHERE telefono= %s and id_restaurante = %s
                                   LIMIT 1""", (sender, ID_RESTAURANTE))
        indicaciones=resultado[0][0] if resultado and resultado[0] and resultado[0][0] else ""
        client = OpenAI()
        prompt = f"""
Eres PAKO, la voz oficial de Sierra Nevada, La Cima del Sabor.

Tu tarea:
Generar un mensaje cálido, claro y corto para un cliente que confirmara la dirección que tenemos guardada en la base de datos

Datos:
- Nombre del cliente: {nombre_cliente}
- Dirección del cliente: {direccion_google}
- Indicaciones adicionales u observaciones: {indicaciones}

Instrucciones del mensaje:
- Comienza con confirmas la siguiente direccion: {direccion_google} ?
- Si la ciudad se repite simplificalo a una vez
- No saludes al cliente probablemente este en mitad de la conversacion
- Habla con tono amable y profesional.
- Di el nombre del cliente.
- Pregunta si confirma su direccion guardada
- Comienza el mensaje con la pregunta de confirmacion
- No inventar información adicional.
- Recuerdale al usuario que si va a actualizar su direccion indique su barrio y cualquier referencia necesaria
- El mensaje debe ser muy corto
-
"""

        response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un asistente experto redactando mensajes cordiales y personalizados para clientes."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )   
        costo=calcular_costo_openai(response,"gpt-4o-mini")
        log_message(f"[OpenAI] direccion_bd costo={costo:.6f}","DEBUG")
        # Registrar consumo de tokens
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] direccion_bd tokens_used={tokens_used}", "DEBUG")
        return response.choices[0].message.content
    except Exception as e:
        log_message(f"<direccion_bd>Error en generar mensaje confirmación {e}", "ERROR")
        logging.error(f"<direccion_bd>Error en generar mensaje confirmación {e}")
        return f"Error al generar mensaje: {e}"

def get_direction(text: tuple) -> str | None:
    """
    Extrae una dirección del texto del cliente usando el LLM.
    Retorna la dirección como string (si se encontró) o None.
    """
    try:
        #if not text or not isinstance(text, str):
        #    return None
        client = OpenAI(api_key=get_openai_key())
        prompt = f"""Eres un asistente experto en extraer direcciones de texto libre en Colombia.

Extrae SÓLO la dirección del siguiente texto y si no encuentras una dirección responde como "No presente".

REGLAS ESTRICTAS:
- La "direccion" debe incluir:
  • Tipo de vía + número + complemento (#)
  • Barrio o sector si está presente (ej: Cedritos, Suba, Chapinero)
  • Al final SIEMPRE: "Bogota, Colombia"

- Las "observaciones" deben incluir ÚNICAMENTE:
  • Apartamento (apt, apartamento, apto)
  • Torre
  • Interior
  • Conjunto residencial
  • Bloque
  • Piso
  • Etapa
  • Casa
  • Oficina
  • Villa
  • Referencias adicionales

- Los barrios o sectores NUNCA van en "observaciones".

- Si no hay observaciones, devuelve un string vacío "".

Texto: "{text}"

RESPONDE únicamente con un JSON con la dirección extraída y las observaciones.

EJEMPLOS:

Entrada:
"Calle 123 #45-67 Barrio Centro cerca a la iglesia principal"

Salida:
{{
  "direccion": "Calle 123 #45-67 Barrio Centro Bogota, Colombia",
  "observaciones": "Cerca a la iglesia principal"
}}

Entrada:
"Cr 20 # 137 -48"

Salida:
{{
  "direccion": "Cr 20 # 137 -48 Bogota, Colombia",
  "observaciones": ""
}}

Entrada:
"Cr 57 #153-52 Torre Farfala"

Salida:
{{
  "direccion": "Cr 57 #153-52 Bogota, Colombia",
  "observaciones": "Torre Farfala"
}}

Entrada:
"Studio 30"

Salida:
{{
  "direccion": "No presente",
  "observaciones": "Studio 30"
}}

Entrada:
"Cr 145 #19-13 cedritos apt 508"

Salida:
{{
  "direccion": "Cr 145 #19-13 Cedritos Bogota, Colombia",
  "observaciones": "Apto 508"
}}
"""
        response = client.chat.completions.create(
        model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Eres un extractor preciso de direcciones."},
                {"role": "user", "content": prompt}
            ],
 #           max_tokens=80,
            temperature=0
        )
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] get_direction costo={costo:.6f}","DEBUG")
        raw = response.choices[0].message.content
        # Registrar consumo de tokens
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] get_direction tokens_used={tokens_used}", "DEBUG")
        if raw == "" or raw is None or raw == "No presente":
            return None
        # Intentar parsear el JSON devuelto
        direccion = None
        observaciones = None
        try:
            # Limpieza básica de bloques ```json``` o ``` alrededor
            raw_str = str(raw).strip().strip("`").strip()
            if raw_str.lower().startswith("json"):
                raw_str = raw_str[4:].lstrip()
            # Intentar parsear JSON directo
            data = json.loads(raw_str)
            direccion = data.get("direccion")
            observaciones = data.get("observaciones")
        except Exception:
            # fallback: intentar extraer primer objeto JSON con regex
            import re
            m = re.search(r'(\{[\s\S]*\})', str(raw))
            if m:
                try:
                    data = json.loads(m.group(1))
                    direccion = data.get("direccion")
                    observaciones = data.get("observaciones")
                except Exception:
                    direccion = None
            else:
                direccion = None
        if not direccion or direccion == "No presente":
            return None
        # Si la dirección no contiene "bogota", añadirlo
        if "bogota" not in direccion.lower():
            direccion = direccion + " BOGOTA, COLOMBIA"
        log_message(f"Dirección extraída: {direccion} | Observaciones: {observaciones}", "INFO")
        return data
    except Exception as e:
        log_message(f"Error en get_direction: {e}", "ERROR")
        return None

def corregir_direccion(direccion_almacedada: str, mensaje_cliente: str) -> str:
    """
    Usa ChatGPT para corregir o mejorar la dirección almacenada
    basándose en el mensaje del cliente.
    Retorna la dirección corregida o la original si no se puede corregir.
    """
    try:
        if not direccion_almacedada or not mensaje_cliente:
            return direccion_almacedada

        client = OpenAI(api_key=get_openai_key())
        prompt = f"""eres un experto en direcciones tu trabajo es corregir completar y revisar direcciones, debes comparar la que tenemos almacenada en nuestra base con el comentario proporcionado por el cliente y revisar si debes completar la direccion si es la misma o si debes cambiarla totalmente por ejemplo tenemos esta calle 1 #45 sur "esa direccion esta mal, por favor a esta "calle 45 23" debes cambiarla toda si tenemos calle 123 #53 sur y el cliente dice " es calle 123 #53 norte" debes modificarla y si tenemos calle 45 y el cliente dice falta sur oriente la completas como calle 45 sur oriente UNICAMENTE DEVUELVE LA DIRECCIÓN COMO RESPUESTA NO DES EXPLICACIONES NI AGREGUES NADA APARTE DE LA DIRECCION
Esta es la Direccion almacenada: {direccion_almacedada} y este es el mensaje del cliente {mensaje_cliente}"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente experto en corrección de direcciones."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] corregir_direccion costo={costo:.6f}","DEBUG")
        raw = response.choices[0].message.content
                # Registrar consumo de tokens
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] corregir_direccion tokens_used={tokens_used}", "DEBUG")
        # normalizar a string y limpiar backticks
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        addr = str(raw).strip().strip("`").strip()
        if not addr:
            return None
        log_message("Dirección extraída: " + addr, "INFO")
        return addr
    except Exception as e:
        log_message(f"Error en corregir_direccion: {e}", "ERROR")
        return direccion_almacedada

def _extract_total_tokens(resp) -> int | None:
    """Extrae total_tokens de distintos formatos de respuesta OpenAI (robusto)."""
    try:
        # objeto con atributo usage (p. ej. chat.completions)
        usage = getattr(resp, "usage", None)
        if usage:
            return int(getattr(usage, "total_tokens", usage.get("total_tokens") if isinstance(usage, dict) else None) or 0)
        # dict-like respuesta
        if isinstance(resp, dict):
            return resp.get("usage", {}).get("total_tokens")
        # algunos wrappers exponen output_text y usage como dict
        return None
    except Exception:
        return None


def clasificador_consulta_menu(pedido_resumen: str) -> str:
    """
    Usa ChatGPT para clasificar si es una pregunta solicitando el menu o aclaracion de prodcuto
    """
    try:

        prompt = f"""
Eres PAKO, asistente de WhatsApp del restaurante Sierra Nevada, La Cima del Sabor.
Tu tarea es determinar si el siguiente mensaje del cliente es una consulta sobre el menú o una aclaración sobre un producto.
Mensaje del cliente: "{pedido_resumen}"
Responde SOLO con una de las siguientes opciones:
- consulta_menu si el cliente está preguntando por el menú o dice que quiere ver el menu o que le des el menu o que le muestres el menu
- aclaracion_producto si el cliente está preguntando algo sobre un producto específico.
BAJO NINGUNA CIRCUSTANCIA PUEDES USAR ALGO DIFERENTE A ESTAS DOS RESPUESTAS Y NO DEBES AÑADIR NADA MAS.
"""

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Eres PAKO, asistente experto en clasificación de mensajes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        # Registrar consumo de tokens
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] clasificador_consulta_menu tokens_used={tokens_used}", "DEBUG")
        log_message(f'Respuesta de clasificación: {raw}', 'INFO')
        return raw
    except Exception as e:
        log_message(f'Error en función <clasificador_consulta_menu>: {e}', 'ERROR')
        return "error_clasificacion"
    
def get_name(text: str) -> str | None:
    """
    Extrae un nombre del texto del cliente usando el LLM.
    Retorna el nombre como string (si se encontró) o None.
    """
    try:
        if not text or not isinstance(text, str):
            return None
        client = OpenAI(api_key=get_openai_key())
        prompt = f"""Eres un asistente experto en extraer nombres de texto libre.
Extrae SÓLO el nombre del siguiente texto y si no encuentras nombre responde como "No presente".
Texto: "{text}"
RESPONDE únicamente con el nombre, nada más."""
        response = client.chat.completions.create(
        model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Eres un extractor preciso de nombres."},
                {"role": "user", "content": prompt}
            ],
 #           max_tokens=80,
            temperature=0
        )
        raw = response.choices[0].message.content
        # Registrar consumo de tokens
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] get_direction tokens_used={tokens_used}", "DEBUG")
        if raw == "" or raw is None or raw == "No presente":
            return None
        # normalizar a string y limpiar backticks
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        name = str(raw).strip().strip("`").strip()
        if not name:
            return None
        log_message("Nombre extraído: " + name, "INFO")
        return name
    except Exception as e:
        log_message(f"Error en get_name: {e}", "ERROR")
        return None

def clasificar_confirmación_general(pregunta_usuario: str, items, model: str = "gpt-4o") -> dict:
    """
    Usa ChatGPT para clasificar si la pregunta del usuario está relacionada con el menú
    de la hamburguesería o no.
    """

    client: OpenAI = OpenAI()

    prompt: str = f"""
    Eres un asistente que clasifica preguntas de clientes de una hamburguesería.

    Debes responder con un JSON EXACTO con la siguiente forma:
    {{
        "intencion": "intencion detectada"
    }}

    IMPORTANTE: TENER EN CUENTA EL CONTEXTO DE LOS MENSAJES ANTERIORES PARA DEFINIR LA INTENCION

    Las posibles intenciones son:
    - "solicitud_pedido":
    * si la pregunta del usuario está relacionada con agregar quitar modificar o solicitar productos del menú de su pedido tenga o no tenga.
    * cuando el usuario conteste a si a las preguntas del agente sobre probar pedidos va aqui 
    - "confirmar_direccion":
    * si la pregunta del usuario está relacionada con confirmar o cambiar una dirección de envío.
    * si el usuario dice si a la pregunta del agente cuando pregunta direccion va aqui
    * si el usuario afirma en un contexto con direcciones
    - "confirmar_pedido" : 
    * si la pregunta del usuario está relacionada con confirmar o  un pedido existente.
    * si el usuario confirma un pedido
    * responde si a la pregunta del agente de confirmar pedido debe clasificarse como confirmar pedido
    * si responde a la pregunta del agente de si su pedido esta bien con una afirmacion
    * Cuando el usuario confirme que su pedido esta bien como esta
    * responde si a la pregunta del agente de confirmar pedido debe clasificarse como confirmar pedido
    * CUANDO EL MENSAJE ANTERIOR DEL AGENTE TERMINE CON "o ¿tu pedido está bien así?" O "¿Confirmas tu pedido? Y EL USUARIO RESPONDE AFIRMATIVAMENTE VA AQUI
    - "sin_intencion": Cuando no puedas detectar ninguna de las dos anteriores intenciones. 

    Este es el menú completo si la pregunta incluye un producto del menu o se refiere a comidas o bebidas es relacionada:
    {json.dumps(items, ensure_ascii=False)}
    
    Ahora clasifica la siguiente pregunta del usuario:
    "{pregunta_usuario}"

    Devuelve SOLO el JSON, sin explicación adicional.
    """

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0
        )
        log_message(f'prompt: {prompt}', 'DEBUG')
        text_output = response.output[0].content[0].text.strip()
        # limpiar posibles fences/triple-backticks u otros prefijos
        try:
            text_output = _clean_model_output(text_output)
        except Exception:
            pass
        costo=calcular_costo_openai(response,"gpt-4o")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] clasificar_confirmacion_general_chatgpt tokens_used={tokens_used}", "DEBUG")
        # Extraer JSON dentro de fences ```json ... ``` o buscar primer objeto JSON
        clean = text_output or ""
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, flags=re.IGNORECASE)
        if m:
            clean = m.group(1).strip()
        else:
            clean = clean.strip()
        if not clean.startswith('{'):
            m2 = re.search(r"(\{[\s\S]*\})", clean)
            if m2:
                clean = m2.group(1)

        try:
            result = json.loads(clean)
            return result
        except json.JSONDecodeError:
            logging.error(f"Error al parsear JSON en clasificar_pregunta_menu_chatgpt: {clean!r}")
            log_message(f'Error al parsear JSON en <ClasificarPreguntaMenuChatGPT>: {clean}', 'ERROR')
            return {"clasificacion": "no_relacionada"}

    except json.JSONDecodeError:
        logging.error(f"Error al parsear JSON: {text_output}")
        log_message(f'Error al parsear JSON en <ClasificarPreguntaMenuChatGPT>: {text_output}', 'ERROR')
        return {"clasificacion": "no_relacionada"}
    except Exception as e:
        logging.error(f"Error en <ClasificarPreguntaMenuChatGPT>: {e}")
        log_message(f'Error en <ClasificarPreguntaMenuChatGPT>: {e}.', 'ERROR')
        return {"clasificacion": "no_relacionada"}
    
def generar_mensaje_sin_intencion(
        mensaje: str,
        items: list,
        model: str = "gpt-4.1-mini",
    ) -> str:
    """
    Llama a ChatGPT para generar un mensaje cordial que:
    - Responda a un mensaje sin intención clara.
    """

    try:
        prompt = f"""
Eres un asistente amable de una hamburguesería.
Genera un mensaje CORTO, cálido y claro para un cliente.

Datos:
- Mensaje del cliente: {mensaje}
- Menu {json.dumps(items, ensure_ascii=False)}
Instrucciones del mensaje:
- Resume los datos de manera natural.
- No inventes información adicional.
- Tono amable, profesional y cercano.
- Responde la duda del cliente de la mejor manera posible relacionando el contexto entregado en los mensajes.
- Si no hay una duda pero hay una peticion relacionada al pedido intenta que describa su pedido lo mejor posible
- Si el cliente menciona que no le gusta un ingrediente dile que puede quitarlo del producto
- Si el cliente pregunta por domicilios si los tenemos siempre y cuando esten bajo el area de cobertura
"""
            
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Eres un asistente de pedidos experto en atención al cliente."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.5
        )
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        log_message(f'prompt: {prompt}', 'DEBUG')
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] generar_mensaje_invitar_pago tokens_used={tokens_used}", "DEBUG")

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error al generar mensaje: {str(e)}"


def get_tiempo_recogida(text: str) -> str | None:
    """
    Extrae el tiempo en el que pasara el cliente por su pedido
    usando un LLM
    """
    try:
        client = OpenAI(api_key=get_openai_key())
        prompt = f"""Eres un asistente experto en extraer tiempos de recogida de texto libre.
Extrae SÓLO el tiempo del siguiente texto y si no encuentras tiempo responde como "No presente".
Si el usuario menciona una hora especifica regresa la hora en formato h:MM (ejemplo 2:30 )
Texto: "{text}"
RESPONDE únicamente con el tiempo cuando puedas convertirlo a minutos hazlo, nada más.
EJEMPLO:
2 horas -> 120 minutos
1 hora  -> 60 minutos
30 minutos -> 30 minutos
15 minutos  
media hora -> 30 minutos
en una hora -> 60 minutos
faltando 20 para las 9 -> 8:40
faltando 15 para las 3 -> 2:45
a las 7 y 45 -> 7:45
a las 8 y media -> 8:30
8:30
2:15
7:45
"""
        response = client.chat.completions.create(
        model="gpt-5.1",
            messages=[
                {"role": "system", "content": "Eres un extractor preciso de tiempos de recogida."},
                {"role": "user", "content": prompt}
            ],
 #           max_tokens=80,
            temperature=0
        )
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        raw = response.choices[0].message.content
        # Registrar consumo de tokens
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] get_direction tokens_used={tokens_used}", "DEBUG")
        if raw == "" or raw is None or raw == "No presente":
            return None
        # normalizar a string y limpiar backticks
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False)
        name = str(raw).strip().strip("`").strip()
        if not name:
            return None
        log_message("Nombre extraído: " + name, "INFO")
        return name
    except Exception as e:
        log_message(f"Error en get_name: {e}", "ERROR")
        return None
    
def clasificar_negacion_general(pregunta_usuario: str, items, model: str = "gpt-4o") -> dict:
    """
    Usa ChatGPT para clasificar si la pregunta del usuario está relacionada con el menú
    de la hamburguesería o no.
    """

    client: OpenAI = OpenAI()

    prompt: str = f"""
    Eres un asistente que clasifica preguntas de clientes de una hamburguesería.

    Debes responder con un JSON EXACTO con la siguiente forma:
    {{
        "intencion": "intencion detectada"
    }}

    IMPORTANTE: TENER EN CUENTA EL CONTEXTO DE LOS MENSAJES ANTERIORES PARA DEFINIR LA INTENCION

    Las posibles intenciones son:
    - "confirmar_pedido" : 
    * si la pregunta del usuario está relacionada con confirmar o  un pedido existente.
    * si el usuario confirma un pedido
    * responde no, asi esta bien o no quiero cambiar o no a la pregunta del agente de confirmar pedido debe clasificarse como confirmar pedido
    * si responde a la pregunta del agente de si su pedido esta bien con una afirmacion
    * Cuando el usuario confirme que su pedido esta bien como esta
    * responde si a la pregunta del agente de confirmar pedido debe clasificarse como confirmar pedido
    * CUANDO EL MENSAJE ANTERIOR DEL AGENTE TERMINE CON "o ¿tu pedido está bien así?" O "¿Confirmas tu pedido? Y EL USUARIO RESPONDE NEGATIVAMENTE A LOS CAMBIOS O SUGERENCIAS VA AQUI
    - "sin_intencion": Cuando no puedas detectar una confirmacion de pedido 
    - Si el cliente menciona que no le gusta un ingrediente dile que puede quitarlo del producto
    Este es el menú completo si la pregunta incluye un producto del menu o se refiere a comidas o bebidas es relacionada:
    {json.dumps(items, ensure_ascii=False)}
    
    Ahora clasifica la siguiente pregunta del usuario:
    "{pregunta_usuario}"

    Devuelve SOLO el JSON, sin explicación adicional.
    """

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0
        )
        log_message(f'prompt: {prompt}', 'DEBUG')
        text_output = response.output[0].content[0].text.strip()
        # limpiar posibles fences/triple-backticks u otros prefijos
        try:
            text_output = _clean_model_output(text_output)
        except Exception:
            pass
        costo=calcular_costo_openai(response,"gpt-4o")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] clasificar_confirmacion_general_chatgpt tokens_used={tokens_used}", "DEBUG")
        # Extraer JSON dentro de fences ```json ... ``` o buscar primer objeto JSON
        clean = text_output or ""
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, flags=re.IGNORECASE)
        if m:
            clean = m.group(1).strip()
        else:
            clean = clean.strip()
        if not clean.startswith('{'):
            m2 = re.search(r"(\{[\s\S]*\})", clean)
            if m2:
                clean = m2.group(1)

        try:
            result = json.loads(clean)
            return result
        except json.JSONDecodeError:
            logging.error(f"Error al parsear JSON en clasificar_pregunta_menu_chatgpt: {clean!r}")
            log_message(f'Error al parsear JSON en <ClasificarPreguntaMenuChatGPT>: {clean}', 'ERROR')
            return {"clasificacion": "no_relacionada"}

    except json.JSONDecodeError:
        logging.error(f"Error al parsear JSON: {text_output}")
        log_message(f'Error al parsear JSON en <ClasificarPreguntaMenuChatGPT>: {text_output}', 'ERROR')
        return {"clasificacion": "no_relacionada"}
    except Exception as e:
        logging.error(f"Error en <ClasificarPreguntaMenuChatGPT>: {e}")
        log_message(f'Error en <ClasificarPreguntaMenuChatGPT>: {e}.', 'ERROR')
        return {"clasificacion": "no_relacionada"}
    
def respuesta_transferencia(mensaje_usuario: str, nombre: str, nombre_local: str) -> dict:
    try:
        PROMPT_QUEJA_GRAVE = """
            Eres el asistente oficial de servicio al cliente de Sierra Nevada, La Cima del Sabor.
            Esta vez atenderás transferencias,donde el cliente expresa algo que debe ser escalado
            ***OBJETIVO GENERAL***
            - Indicarle al cliente que su caso ha sido escalado a un administrador y pronto se comunicarán con él.
            - Asumir responsabilidad sin culpas excesivas.
            - Dar una ACCIÓN clara y concreta que el asistente realizará.
            - Preparar un resumen ejecutivo para un administrador humano.
            - NO escalar directamente en el mensaje al cliente (solo en el resumen interno).
            - Máximo 2 frases, tono cálido, humano, cercano, estilo Sierra Nevada, colombiano neutro.
            - La respuesta_cordial DEBE incluir explícitamente la frase:
            "Ya pregunte al administrador del punto se comunicara contigo pronto."
            - Si la frase no aparece, la respuesta es inválida.
            - Debes indicar que pronto se comunicaran con el
            ***DEBES ENTREGAR ESTOS CAMPOS***
            1. "respuesta_cordial": Mensaje calmado, empático y con acción concreta 
            (ej: “reviso ya mismo con cocina y logística”, “activo seguimiento con el punto”).
            2. "resumen_queja": Descripción breve de lo que reclama el cliente.
            3. "accion_recomendada": Acción clara que el sistema/administrador debe hacer 
            (ej: verificar estado del pedido, contactar punto, revisar domiciliario).
            4. "resumen_ejecutivo": Resumen para administrador (breve, objetivo, sin adornos).
            5. "intencion": Siempre "queja_grave".
            ***TONO***
            - Cálido y responsable.
            - Sin tecnicismos ni sarcasmo.
            - Evita respuestas robóticas.
            - Máximo un emoji, si fluye natural.

            Cliente llamado {nombre} escribió:
            "{mensaje_usuario}"
            ***FORMATO OBLIGATORIO***
            Devuelve SOLO un JSON válido:
            {{
                "respuesta_cordial": "",
                "resumen_queja": "",
                "accion_recomendada": "",
                "resumen_ejecutivo": "",
                "intencion": "queja_grave"
            }}
        """
        client = OpenAI()
        prompt = PROMPT_QUEJA_GRAVE.format(
            mensaje_usuario=mensaje_usuario,
            nombre=nombre
        )
        response = client.chat.completions.create(
            model="gpt-4.1 mini",
            messages=[
                {"role": "system", "content": "Eres un generador de respuestas para quejas graves de clientes."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=220,
            temperature=0.6
        )
        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-4.1-mini")
        log_message(f"[OpenAI] respuesta_quejas_graves_ia costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] respuesta_quejas_graves_ia tokens_used={tokens_used}", "DEBUG")
        try:
            data = json.loads(raw)
        except:  # noqa: E722
            data = {
                "respuesta_cordial": f"{nombre}, ya reviso lo ocurrido con tu experiencia en {nombre_local} y activo el seguimiento de inmediato.",
                "resumen_queja": "Queja grave del cliente sobre servicio o pedido.",
                "accion_recomendada": "Revisión urgente con el punto y estado del pedido.",
                "resumen_ejecutivo": "Cliente reporta una queja grave; requiere revisión del punto y logística.",
                "intencion": "queja_grave"
            }
        return data
    except Exception as e:
        log_message(f'Error en función <respuesta_quejas_graves_ia>: {e}', 'ERROR')
        logging.error(f"Error en función <respuesta_quejas_graves_ia>: {e}")
        return {
            "respuesta_cordial": f"{nombre}, reviso de inmediato lo que pasó con tu experiencia en {nombre_local}.",
            "resumen_queja": "Queja grave del cliente.",
            "accion_recomendada": "Verificar con el punto y logística.",
            "resumen_ejecutivo": "Error en el proceso automático, requiere revisión manual.",
            "intencion": "queja_grave"
        }
def extraer_resumen(mensajes , resumen ) -> dict:
    try:
        PROMPT_SALUDO_DYNAMIC = f"""
        Analiza estos mensajes recientes de un cliente de restaurante.

        Ademas este es el perfil que hemos construido del cliente basado en sus mensajes anteriores:
        {resumen}
        Basándote en el perfil del cliente y los mensajes recientes, actualiza el perfil del cliente con cualquier nueva información relevante que puedas extraer, como preferencias, intenciones, estado emocional o cualquier detalle personal que el cliente haya compartido. Si no hay nueva información, mantén el perfil igual. Devuelve el perfil actualizado en formato JSON.
        Devuelve el siguiente JSON con el perfil actualizado del cliente:
        {mensajes}
         {{
            "le_gusta": ,
            "no_le_gusta": ,
            "preferencias":,
            "puntos_importantes": ,
            "resumen":
            }}
        Reglas:
        - No inventes información que no esté presente en los mensajes.
        - Extrae solo información que el cliente haya mencionado explícitamente.
        - Si no hay informacion no te preocupes por llenar los campos vacíos, es mejor dejarlos vacíos que inventar datos.
        - Se muy puntual y concreto en la información que extraes, no agregues explicaciones ni detalles adicionales.
        """
        client = OpenAI()
        prompt = PROMPT_SALUDO_DYNAMIC
        
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": "Eres un Analista de mensajes recientes de un cliente de restaurante."},
                {"role": "user", "content": prompt}
            ],
#            max_tokens=350,
            temperature=0.1
        )
        log_message(f'prompt: {prompt}', 'DEBUG')
        raw = response.choices[0].message.content.strip()
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] extraer resumen costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] extraer_resumen tokens_used={tokens_used}", "DEBUG")
        
        data = json.loads(raw)
        return data
    except Exception as e:
        log_message(f'Error en función <extraer_resumen>: {e}', 'ERROR')
        return None
    

def obtener_respuestas_mismo_dia(telefono: str) -> list:
    query = """
    SELECT mensaje
    FROM conversaciones,
         jsonb_array_elements(conversacion->'mensajes') WITH ORDINALITY AS m(mensaje, idx)
    WHERE telefono = %s
      AND (mensaje->>'fecha')::timestamp::date = CURRENT_DATE
      AND id_cliente=%s
    ORDER BY idx DESC
    """

    mensajes = execute_query(query, (telefono, ID_RESTAURANTE,))

    # execute_query devuelve lista de tuplas → extraemos primer elemento
    mensajes = [m[0] for m in mensajes]

    # Volvemos al orden cronológico
    mensajes = list(reversed(mensajes))

    return mensajes
def obtener_resumen(telefono: str) -> list:
    log_message(f"Consultando resumen para {telefono}", "DEBUG")
    try:
        query = """
        SELECT resumen
        FROM clientes_whatsapp
        WHERE telefono = %s
        AND id_restaurante = %s
        LIMIT 1;
        """

        result = execute_query(query, (telefono, ID_RESTAURANTE,), fetchone=True)

        if not result:
            log_message(f"No existe resumen previo para {telefono}", "INFO")
            return None

        log_message(f"Resumen obtenido para {telefono}", "DEBUG")
        return result[0]
    except Exception as e:
        log_message(f"Error al obtener resumen para {telefono}: {e}", "ERROR")
        return None
def guardar_resumen(telefono: str, resumen: dict) -> None:
    log_message(f"Guardando resumen para {telefono}", "DEBUG")
    try:
        query = """
        UPDATE clientes_whatsapp
        SET resumen = %s 
        WHERE telefono = %s
        AND id_restaurante = %s;
        """

        execute_query(query, (Json(resumen), telefono, ID_RESTAURANTE,))
        log_message(f"Resumen guardado para {telefono}", "DEBUG")
    except Exception as e:
        log_message(f"Error guardando resumen para {telefono}: {e}", "ERROR")
        # swallow to avoid bubbling up
        pass
def resumen_conversacion(telefono: str) -> str:
    log_message(f"Iniciando resumen_conversacion para {telefono}", "DEBUG")
    try:
        mensajes = obtener_respuestas_mismo_dia(telefono)
        resumen = obtener_resumen(telefono)
        if not resumen:
            log_message(f"No había resumen previo para {telefono}, inicializando estructura vacía", "DEBUG")
            resumen_sesion = {
                "le_gusta": None,
                "no_le_gusta": None,
                "preferencias": None,
                "puntos_importantes": None,
                "resumen": None
            }
        else:
            resumen_sesion = resumen
        resumen_actualizado = extraer_resumen(mensajes, resumen_sesion)
        if resumen_actualizado:
            log_message(f"Resumen actualizado para {telefono}: {resumen_actualizado}", "DEBUG")
            guardar_resumen(telefono, resumen_actualizado)
        return resumen_actualizado
    except Exception as e:
        log_message(f"Error en resumen_conversacion para {telefono}: {e}", "ERROR")
        return None 

def extraer_resumen_corto(mensajes, telefono, id_restaurante):
    try:
        # 1️⃣ Obtener resumen actual desde clientes_whatsapp
        query = """
            SELECT resumen
            FROM clientes_whatsapp
            WHERE telefono = %s
            AND id_restaurante = %s
            LIMIT 1;
        """

        result = execute_query(query, (telefono, id_restaurante), fetchone=True)

        resumen_actual = result[0] if result else {} if result else {}

        if resumen_actual is None:
            resumen_actual = {}

        if isinstance(resumen_actual, str):
            resumen_actual = json.loads(resumen_actual)
        mensajes=mensajes[-8:]
        # 2️⃣ Prompt híbrido (solo detectar cambios)
        PROMPT = fPROMPT = f"""
Analiza los mensajes recientes de un cliente de restaurante.

Perfil actual:
{json.dumps(resumen_actual, ensure_ascii=False)}

Mensajes:
{mensajes}

Devuelve SOLO los campos que deban actualizarse.
Si no hay cambios devuelve {{}}.

Estructura posible:
{{
  "pedido_en_proceso": "",
  "metodo_pago_seleccionado": "",
  "direccion_confirmada": false,
  "resumen_contextual": "",
  "Importante": "",
  "gusta": [],
  "no_le_gusta": []
}}

Reglas importantes:

1. PRODUCTOS
- Usa SIEMPRE el nombre del producto como aparece en los mensajes del AGENTE.
- Si el usuario usa una descripción distinta, normalízala al nombre usado por el agente.
- Ejemplo:
  usuario: "quiero una con doble tocineta"
  agente: "Con Doble Tocineta"
  salida correcta: "Con Doble Tocineta"

2. PEDIDO EN PROCESO
- Debe ser MUY corto.
- Solo listar productos confirmados.
- No incluir historia ni explicaciones.

Ejemplo correcto:
"pedido_en_proceso": "Con Doble Tocineta, Papas francesas, Coca Cola Zero"

3. GUSTA
- Solo productos que el cliente pidió o mostró preferencia.
- Usar nombres del menú del agente.
- No repetir productos que solo aparecen una vez si no reflejan preferencia.

4. NO_LE_GUSTA
- Solo ingredientes explícitamente rechazados.

5. RESUMEN_CONTEXTUAL
Debe ser extremadamente corto.
Solo información relevante para futuras interacciones.

Ejemplos:
"Cliente recoge en sede Caobos"
"Cliente fuera de área de domicilio"
"Prefiere pago en efectivo"

NO escribir párrafos.

6. IMPORTANTE
Solo usar si es información crítica.

7. No inventar información.

8. No repetir campos si no cambiaron.

9. Respuestas muy cortas.

Devuelve únicamente JSON válido.
"""

        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": "Eres un analista de cambios en perfiles de clientes."},
                {"role": "user", "content": PROMPT}
            ],
            temperature=0.1
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        costo=calcular_costo_openai(response,"gpt-5.1")
        log_message(f"[OpenAI] extraer_resumen costo={costo:.6f}","DEBUG")
        tokens_used = _extract_total_tokens(response)
        if tokens_used is not None:
            log_message(f"[OpenAI] extraer_resumen tokens_used={tokens_used}", "DEBUG")
        cambios = json.loads(raw)

        # 3️⃣ Validación defensiva
        if not isinstance(cambios, dict):
            log_message("Respuesta del LLM no es dict", "ERROR")
            return resumen_actual

        # 4️⃣ Merge controlado en backend
        resumen_actual.update(cambios)

        # 5️⃣ Guardar en jsonb (reemplazando el objeto final consolidado)
        update_query = """
            UPDATE clientes_whatsapp
            SET resumen = %s::jsonb
            WHERE telefono = %s
            AND id_restaurante = %s;
        """

        execute_query(
            update_query,
            (json.dumps(resumen_actual, ensure_ascii=False), telefono, id_restaurante)
        )

        return resumen_actual

    except Exception as e:
        log_message(f'Error en <extraer_resumen_corto>: {e}', 'ERROR')
        return None
    
def obtener_pedido_en_proceso(telefono: str, id_restaurante: int) -> str:
    query = """
        SELECT COALESCE(NULLIF(resumen->>'pedido_en_proceso', ''), '')
        FROM clientes_whatsapp
        WHERE telefono = %s
        AND id_restaurante = %s
        LIMIT 1;
    """

    result = execute_query(query, (telefono, id_restaurante), fetchone=True)

    if not result:
        return ""

    return result[0] or ""