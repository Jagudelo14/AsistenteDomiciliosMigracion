# utils_chatgpt.py
# Last modified: 2025-11-05 by Andrés Bermúdez

import re
from openai import OpenAI
import logging
from typing import Any, List, Optional, Tuple, Dict
import os
import json
import ast
from utils import REPLACE_PHRASES, obtener_pedido_por_codigo, send_text_response, limpiar_respuesta_json, log_message, _safe_parse_order, _merge_items, _price_of_item, convert_decimals, to_json_safe

def get_openai_key() -> str:
    try:
        """Obtiene la clave API de OpenAI desde variables de entorno."""
        log_message('Iniciando función <GetOpenAIKey>.', 'INFO')
        logging.info('Obteniendo clave de OpenAI')
        api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("No se encontró la clave OPENAI_API_KEY en las variables de entorno.")
        logging.info('Clave de OpenAI obtenida')
        log_message('Finalizando función <GetOpenAIKey>.', 'INFO')
        return api_key
    except Exception as e:
        log_message(f"Error al obtener la clave de OpenAI: {e}", 'ERROR')
        logging.error(f"Error al obtener la clave de OpenAI: {e}")
        raise
    
def get_classifier(msj: str, sender: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    try:
        """Clasifica un mensaje de WhatsApp usando un modelo fine-tuned de OpenAI."""
        log_message('Iniciando función <GetClassifier>.', 'INFO')
        logging.info('Clasificando mensaje')
        classification_prompt: str = """
            Eres un clasificador de mensajes para un asistente de WhatsApp de un restaurante.
            Tu tarea es identificar la **intención (intent)**, el **tipo de mensaje (type)** y cualquier **entidad relevante (entities)**.

            A continuación tienes un ejemplo de cómo debes estructurar las entidades cuando el usuario pide varios productos:

            EJEMPLO DE ENTRADA:
            "me das una sierra picante con extra picante y una malteada de chocolate"

            EJEMPLO DE SALIDA:
            {
            "intent": "solicitud_pedido",
            "type": "pedido",
            "entities": {
                "items": [
                {
                    "producto": "sierra picante",
                    "especificaciones": ["extra picante"]
                },
                {
                    "producto": "malteada de chocolate",
                    "especificaciones": []
                }
                ]
            }
            }
            EJEMPLO DE ENTRADA:
            "me das una sierra picante con extra picante y una malteada de chocolate"

            EJEMPLO DE SALIDA:
            {
            "intent": "solicitud_pedido",
            "type": "pedido",
            "entities": {
                "items": [
                {
                    "producto": "sierra picante",
                    "especificaciones": ["extra picante"]
                },
                {
                    "producto": "malteada de chocolate",
                    "especificaciones": []
                }
                ]
            }
            }
            Debes responder únicamente en formato JSON válido con la siguiente estructura:
            {
            "intent": "<una de las intenciones permitidas>",
            "type": "<tipo de mensaje>",
            "entities": { }
            }

            Lista de intenciones posibles:
            - confirmacion_general (puede ser en otros idiomas: yes, oui, ja, etc.)
            - consulta_menu
            - consulta_pedido
            - consulta_promociones
            - continuacion_pedido (puede ser en otros idiomas: yes, oui, ja, etc.)
            - direccion
            - info_personal
            - mas_datos_direccion
            - modificar_pedido (puede ser con palabras clave como cambiar, quitar, agregar, modificar, también, etc.)
            Ejemplo: "quiero agregar una malteada de vainilla", "quiero que la hamburguesa no traiga lechuga", "cambia mi pedido por favor por...", "quitar la malteada", "también quiero una gaseosa coca cola original", "dame también una malteada de chocolate", etc.
            - negacion_general (puede ser en otros idiomas: no, non, nein, etc.)
            - preguntas_generales
            - quejas (quejas de menor nivel)
            - saludo
            - sin_intencion
            - solicitud_pedido (pedidos de comida o bebida)
            - transferencia (quejas de mayor nivel)
            - validacion_pago (breb, nequi, daviplata, tarjeta, efectivo)
            - recoger_restaurante   (NUEVA intención: cuando el usuario dice que pasará a recoger, irá al restaurante o lo recoge en tienda)
            - domicilio             (NUEVA intención: cuando el usuario pide entrega a domicilio, "tráelo", "envíamelo", "a mi casa", etc.)

            Instrucciones importantes:
            - No incluyas texto fuera del JSON.
            - No uses comentarios, explicaciones o saltos de línea innecesarios.
            - Si no puedes determinar la intención, usa "sin_intencion".
            """

        messages = [
            {"role": "system", "content": classification_prompt},
            {"role": "user", "content": msj}
        ]
        client: OpenAI = OpenAI(api_key=get_openai_key())
        respuesta: Any = client.chat.completions.create(
            model="ft:gpt-3.5-turbo-0125:net-applications:domicilios:CaSlaPnG",
            messages=messages,
            max_tokens=700,
            temperature=0
        )
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
        log_message('Finalizando función <GetClassifier>.', 'INFO')
        return intent, type_, entities
    except Exception as e:
        log_message(f'Error al hacer uso de función <GetClassifier>: {e}.', 'ERROR')
        logging.error(f"Error al clasificar el mensaje: {e}")
        send_text_response(sender, "Lo siento, hubo un error al procesar tu mensaje. ¿Podrías repetirlo?")
        return None, None, {}

def clasificar_pregunta_menu_chatgpt(pregunta_usuario: str, model: str = "gpt-3.5-turbo") -> dict:
    """
    Clasifica si una pregunta del usuario está relacionada con el menú o con servicios
    del negocio (hamburguesería) usando un modelo de lenguaje (ChatGPT).
    """

    log_message('Iniciando función <ClasificarPreguntaMenuChatGPT>.', 'INFO')
    client: OpenAI = OpenAI()

    prompt: str = f"""
    Eres un asistente que clasifica preguntas de clientes de una hamburguesería.

    Debes responder con un JSON EXACTO con la siguiente forma:
    {{
        "clasificacion": "relacionada" o "no_relacionada"
    }}

    Instrucciones:
    - Si la pregunta se refiere a comidas, hamburguesas, bebidas, malteadas, ingredientes, precios, combos,
      opciones vegetarianas o cualquier cosa del menú → "relacionada".
    - También clasifica como "relacionada" si el cliente pregunta sobre:
        • formas de pago (Nequi, Daviplata, efectivo, tarjetas, etc.)
        • si hacen domicilios o envíos
        • horarios de atención
        • dirección o ubicación del local
        • contacto, pedidos o reservas
        • promociones o descuentos
    - Si la pregunta es sobre temas generales, ajenos al restaurante (por ejemplo: Bogotá, clima, películas, tecnología, etc.) → "no_relacionada".

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
        result = json.loads(text_output)
        log_message('Finalizando función <ClasificarPreguntaMenuChatGPT>.', 'INFO')
        return result

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

def responder_pregunta_menu_chatgpt(pregunta_usuario: str, items, model: str = "gpt-4o") -> dict:
    """
    Responde preguntas del usuario sobre el menú o servicios del restaurante Sierra Nevada 🍔.
    Incluye información sobre horarios, sedes y medios de pago.
    Devuelve: (result: dict, prompt: str)
    """
    log_message('Iniciando función <ResponderPreguntaMenuChatGPT>.', 'INFO')

    # Prompt unificado
    prompt = f"""
        Eres PAKO, el asistente cálido y cercano de Sierra Nevada, La Cima del Sabor 🏔️🍔.
        Tu tarea es ayudar al cliente con información sobre el menú, horarios, sedes y servicios,
        siempre con el tono oficial de la marca: amable, natural y con un toque sabroso, sin exagerar.

        Información del restaurante:
        🕐 Horario: Todos los días de 12:00 p.m. a 7:00 p.m.
        📍 Sedes:
        - Galerías: Calle 53 #27-16
        - Centro Mayor: CC Centro Mayor, local 3-019
        - Centro Internacional: Calle 32 #07-10
        - Chicó 2.0: Calle 100 #9A-45, local 7A
        - Virrey: Carrera 15 #88-67
        💳 Medios de pago: Nequi, Daviplata, tarjeta débito, crédito y efectivo.

        El cliente preguntó: "{pregunta_usuario}"

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
        client = OpenAI()
        response = client.responses.create(
            model=model,
            input=prompt
        )

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

        log_message('Finalizando función <ResponderPreguntaMenuChatGPT>.', 'INFO')
        return result

    except Exception as e:
        logging.error(f"Error en <ResponderPreguntaMenuChatGPT>: {e}")
        log_message(f'Error en <ResponderPreguntaMenuChatGPT>: {e}', 'ERROR')
        return {
            "respuesta": "Lo siento 😔, tuve un problema para responder tu pregunta.",
            "recomendacion": False,
            "productos": []
        }

def mapear_pedido_al_menu(contenido_clasificador: dict, menu_items: list, model: str = "gpt-5.1") -> dict:
    """
    Mapear los items provenientes del clasificador AL MENÚ usando GPT.
    """
    client = OpenAI()

    prompt = f"""
        Eres un asistente encargado de mapear pedidos (extraídos por un clasificador) a un MENÚ estructurado.
        Debes RESPONDER ÚNICA Y EXCLUSIVAMENTE con un JSON válido (sin texto adicional) con esta estructura:
        {{
            "order_complete": true|false,
            "items": [
                {{
                    "requested": {{ "producto": "...", "modalidad": "...", "especificaciones": [ ... ] }},
                    "status": "found" | "not_found" | "multiple_matches",
                    "matched": {{ "name": "...", "id": "...", "price": number }},
                    "candidates": [ {{ "name":"...", "id":"...", "price": number }}, ... ],
                    "modifiers_applied": [ ... ],
                    "note": ""
                }}
            ],
            "total_price": number
        }}

        ======================================================
        = COMPORTAMIENTO GLOBAL DEL MODELO =
        ======================================================
        Debes identificar los productos del menú incluso cuando estén:
        - mal escritos,
        - abreviados,
        - rotos en sílabas,
        - fusionados,
        - con espacios de más o de menos,
        - escritos fonéticamente,
        - mezclados con palabras irrelevantes,
        - con diminutivos o versiones coloquiales,
        - con apodos informales,
        - usando solo parte del nombre (ej: “insaciable”, “clásica”, “queso”, “mulata”, “costeña”, “malte vaini”, “roman 400”, “perro toci”, etc.).

        DEBES RECONOCER *CUALQUIER* producto del menú mediante:
        - normalización,
        - sinonimia,
        - fuzzy matching,
        - similitud semántica,
        - heurísticas inteligentes.

        ======================================================
        = NORMALIZACIÓN EXTREMA (APLICAR A TODA ENTRADA) =
        ======================================================
        Antes de buscar coincidencias debes:
        - pasar todo a minúsculas,
        - quitar acentos,
        - corregir repeticiones (“queeesssooo” → “queso”),
        - eliminar palabras vacías (un, una, de, porfa, porfaaa, ml, tamaño, etc.),
        - corregir deformaciones fonéticas:
            * “quesuo”, “kezo”, “keeso” → “queso”
            * “vete”, “vegui”, “begui” → “veggie”
            * “ancasiable”, “insasiable” → “insaciable”
            * “melaoo”, “melaon”, “melado” → “melao”
            * “paguer”, “power”, “pauer” → “pagüer”
            * “mulate”, “mulatta”, “mulada” → “mulata”
            * “costeno”, “costenio” → “costeño”
            * “super pero”, “supe perro”, “superperro” → “super perro”
            * “tocino”, “tocineta”, “tocinita” → “tocineta”
            * “fuse”, “fuzetea” → “fuze tea”
        - convertir palabras con número → posibles tamaños (ej: 400 → 400 ml)
        - eliminar texto irrelevante (“porfa”, “quiero”, “dame”, “sería”, “de pronto”, etc.)

        ======================================================
        = SINONIMIA SEMÁNTICA (PARA TODO EL MENÚ) =
        ======================================================
        Debes asumir que los clientes pueden decir:
        - solo una parte del nombre (“insaciable”, “queso”, “paguer”, “perro toci”)
        - apodos: 
            * “clasica” → “Sierra Clasica”
            * “melao” → “Sierra Melao”
            * “picante” → “Sierra Picante”
            * “costeña” → “Sierra Costeña”
            * “bomba” → “Sierra Bomba”
            * “mulata” → “Sierra Mulata”
            * "doble carne" → "Doble Carne"
        - equivalencias:
            * “hamburguesa”, “burgesa”, “burguer”, “hambur” → categoría hamburguesas
            * “perro”, “hotdog”, “dog”, “hot dog” → perros calientes
            * “papa”, “papitas”, “fritas” → papas / acompañamientos
            * “adicion”, “agregado”, “extra”, “sumale” → adicionales
            * “salsita”, “sauce”, “aderezo” → salsas

        ======================================================
        = TOLERANCIA TOTAL A ERRORES (FUZZY MATCHING) =
        ======================================================
        Un producto cuenta como posible match si:
        - distancia Levenshtein < 35%
        - similitud semántica razonable
        - palabra base suena similar (matching fonético)
        - comparte palabras clave del nombre real

        Ejemplo:
        - “vegui queso” → “Veggie Queso”
        - “perro toci” → “Perro Tocineta”
        - “insasiable” → “La Insaciable”
        - “paguer” → “Sierra Pagüer”
        - “queso sierra” → “Sierra Queso”

        ======================================================
        = PRIORIDAD DE MATCHING =
        ======================================================
        A) Coincidencia exacta → FOUND.
        B) Coincidencia por alias → FOUND.
        C) Coincidencia parcial fuerte → FOUND.
        D) Coincidencia semántica → FOUND.
        E) Fuzzy match → FOUND si solo coincide uno.
        F) Si 2+ coinciden → MULTIPLE_MATCHES.
        G) Si 0 coinciden:
            → NOT_FOUND
            → sugerir máximo 3 alternativas de la misma categoría.

        ======================================================
        = REGLAS FINALES =
        ======================================================
        - Usa exactamente el nombre del menú en el campo matched.name.
        - Si un ítem es not_found → order_complete = false.
        - total_price = suma de precios.
        - Respuesta SIEMPRE debe ser solamente el JSON.

        MENÚ COMPLETO:
        {json.dumps(menu_items, ensure_ascii=False)}

        CLASIFICADOR:
        {json.dumps(contenido_clasificador, ensure_ascii=False)}

        DEVUELVE SOLO EL JSON.
        """
    try:
        log_message('Iniciando función <MapearPedidoAlMenu>.', 'INFO')

        response = client.responses.create(
            model=model,
            input=prompt,
            max_completion_tokens = 500,
            temperature=0
        )

        text_output = response.output[0].content[0].text.strip()
        log_message(f'Output crudo de modelo en <MapearPedidoAlMenu>: {text_output}', 'DEBUG')

        clean = text_output.strip()
        clean = re.sub(r'^```json', '', clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r'^```', '', clean).strip()
        clean = re.sub(r'^json', '', clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r'```$', '', clean).strip()

        result = json.loads(clean)

        log_message('Finalizando función <MapearPedidoAlMenu>.', 'INFO')
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

    
def sin_intencion_respuesta_variable(contenido_usuario: str, nombre_cliente: str) -> str:
    try:
        log_message('Iniciando función <sin_intencion>.', 'INFO')
        PROMPT_SIN_INTENCION = (
            "Eres el asistente oficial de Sierra Nevada, La Cima del Sabor.\n"
            "Tu objetivo es responder cuando el cliente envía algo que no tiene sentido, "
            "como una palabra suelta, emojis sin contexto, números o símbolos.\n\n"

            "TONO DE MARCA:\n"
            "- Cálido, cercano y respetuoso.\n"
            "- Puedes usar un toque juguetón o ligero, pero sin sarcasmo ni ironía.\n"
            "- Lenguaje natural, claro y amable, como un buen anfitrión bogotano.\n"
            "- Puedes usar 1 emoji suave si queda natural.\n"
            "- Nunca suenes burlón, defensivo o exagerado.\n\n"

            "REGLAS:\n"
            "- Si el usuario envía algo aleatorio como 'a', 'su', emojis o símbolos, "
            "responde con amabilidad y un guiño ligero, manteniendo calidez.\n"
            "- Si envía banderas, puedes decir algo como: "
            "\"No estoy seguro cómo se relaciona {contenido}, pero aquí estoy para ayudarte\".\n"
            "- Termina SIEMPRE con un llamado a la acción invitando al cliente a contarte "
            "qué desea pedir o consultar.\n"
            "- Incluye el nombre del cliente: {nombre_cliente}.\n"
            "- Máximo 1 o 2 frases.\n"
            "- No inventes productos.\n\n"

            "Contenido del usuario: \"{contenido}\"\n"
            "Nombre del cliente: \"{nombre_cliente}\"\n\n"
            "Responde aquí:"
        )
        client = OpenAI()
        prompt = PROMPT_SIN_INTENCION.format(
            contenido=contenido_usuario,
            nombre_cliente=nombre_cliente
        )
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente de un restaurante que responde con humor amable y ligero sarcasmo."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=80,
            temperature=0.9
        )
        mensaje = response.choices[0].message.content
        log_message('Finalizando función <sin_intencion>.', 'INFO')
        return mensaje.strip()
    except Exception as e:
        log_message(f'Error en función <sin_intencion>: {e}', 'ERROR')
        logging.error(f"Error en función <sin_intencion>: {e}")
        return "Lo siento, no entendí tu mensaje. ¿Podrías repetirlo de otra forma?"

def saludo_dynamic(mensaje_usuario: str, nombre: str, nombre_local: str) -> dict:
    try:
        log_message('Iniciando función <saludo_dynamic>.', 'INFO')
        PROMPT_SALUDO_DYNAMIC = """
            Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
            Tu tarea es generar un saludo personalizado según el tono que use el cliente.

            El cliente escribió: "{mensaje_usuario}"

            PAUTAS DE TONO:
            1. Si el cliente usa expresiones informales como:
            "q hubo", "quiubo", "k hubo", "que más", "que mas", "q mas",
            "hey", "holi", "epa", "epaaa", "hoola", "hola parce",
            entonces:
                - Usa un tono cercano, relajado y natural, sin jerga excesiva.
                - Puedes usar 1 emoji suave si fluye bien.
                - Mantén calidez y sensación de bienvenida al estilo Sierra Nevada.

            2. Si el cliente usa expresiones formales como:
            "buenas tardes", "buenos días", "buen dia",
            "cordial saludo", "mucho gusto", "estimados",
            entonces:
                - Usa un tono respetuoso, profesional y sereno.
                - No uses emojis.
                - Mantén claridad, amabilidad y un toque cálido sin exagerar.

            3. En cualquier otro caso:
                - Usa un tono cordial estándar: amable, natural y con sabor.
                - Puedes usar un emoji suave si queda orgánico.

            REGLAS DE ESTILO SIERRA NEVADA:
            - Habla como un buen anfitrión: cálido, claro y con energía positiva.
            - Evita expresiones barriales, sarcasmo o exageraciones.
            - Mantén un lenguaje cotidiano y respetuoso.
            - No inventes productos ni detalles.
            - Puedes mencionar solamente: “menú”, “promociones”, “burgers”, “recomendaciones”.
            - Incluye siempre el nombre del cliente: {nombre}
            - Incluye siempre el nombre del local: {nombre_local}
            - Responde en máximo 1 o 2 frases.
            - Escoge UNA intención entre:
                - "consulta_menu"
                - "consulta_promociones"
            FORMATO:
            Debes responder en un JSON válido:
            {{
                "mensaje": "texto aquí",
                "intencion": "consulta_menu"
            }}
            No incluyas texto adicional fuera del JSON.
            """
        client = OpenAI()
        prompt = PROMPT_SALUDO_DYNAMIC.format(
            nombre=nombre,
            nombre_local=nombre_local,
            mensaje_usuario=mensaje_usuario.lower()
        )
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un generador de saludos que adapta su tono al del cliente."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.85
        )
        raw = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except:
            data = {
                "mensaje": f"¡Hola {nombre}! Bienvenido a {nombre_local}. ¿Quieres que te muestre el menú?",
                "intencion": "consulta_menu"
            }
        log_message('Finalizando función <saludo_dynamic>.', 'INFO')
        return data
    except Exception as e:
        log_message(f'Error en función <saludo_dynamic>: {e}', 'ERROR')
        logging.error(f"Error en función <saludo_dynamic>: {e}")
        return {
            "mensaje": f"¡Hola {nombre}! Bienvenido a {nombre_local}. ¿Quieres que te muestre el menú?",
            "intencion": "consulta_menu"
        }
    
def respuesta_quejas_ia(mensaje_usuario: str, nombre: str, nombre_local: str) -> dict:
    try:
        log_message('Iniciando función <respuesta_quejas>.', 'INFO')
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
            model="gpt-3.5-turbo",
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
        try:
            data = json.loads(raw)
        except:
            data = {
                "respuesta_cordial": f"{nombre}, gracias por escribirnos. Lamentamos que tu experiencia en {nombre_local} no haya sido perfecta; estamos aquí para ayudarte 😊",
                "resumen_queja": "Queja leve del cliente sobre su experiencia.",
                "intencion": "quejas"
            }
        log_message('Finalizando función <respuesta_quejas>.', 'INFO')
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
        log_message('Iniciando función <respuesta_quejas_graves_ia>.', 'INFO')
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
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un generador de respuestas para quejas graves de clientes."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=220,
            temperature=0.6
        )
        raw = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except:
            data = {
                "respuesta_cordial": f"{nombre}, ya reviso lo ocurrido con tu experiencia en {nombre_local} y activo el seguimiento de inmediato.",
                "resumen_queja": "Queja grave del cliente sobre servicio o pedido.",
                "accion_recomendada": "Revisión urgente con el punto y estado del pedido.",
                "resumen_ejecutivo": "Cliente reporta una queja grave; requiere revisión del punto y logística.",
                "intencion": "queja_grave"
            }
        log_message('Finalizando función <respuesta_quejas_graves_ia>.', 'INFO')
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
        log_message('Iniciando función <pedido_incompleto_dynamic>.', 'INFO')
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
            - SIEMPRE pedir que el cliente vuelva a escribir TODO su pedido claramente.
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
            Aquí está el menú disponible:
            {menu_str}
            LAS HAMBURGESAS SE LLAMAN:
            "Veggie Queso"
            "La Insaciable"
            "Sierra Bomba"
            "Sierra Mulata"
            "Sierra Pagüer"
            "Sierra Picante"
            "Sierra Costeña"
            "Sierra Melao"
            "Sierra Clasica"
            "Camino a la cima"
            "Sierra Queso"
        HAY PERROS CALIENTES LLAMADOS:
            "Super Perro"
            "Super Chanchita"
            "Perro Tocineta"
        CUANDO PIDAN UN ADICIONAL EN CUALQUIER PRODUCTO, SOLO PUEDE SER:
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
        CUANDO PIDAN SALSAS, SOLO PUEDE SER:
            "Salsa de tomate"
            "Salsa mostaza"
            "Salsa bbq"
            "Salsa mayonesa"
        CUANDO PIDAN BEBIDAS, SOLO PUEDE SER:
            "Malteada de Vainilla"
            "Malteada de Mil0"
            "Malteada de Frutos Rojos"
            "Malteada de Chocolate y avellanas"
            "Malteada de Arequipe"
            "Malteada Oblea"
            "Malteada Galleta"
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
        CUANDO PIDAN ACOMPAÑAMIENTOS, SOLO PUEDE SER:
            "Platanitos maduros"
            "Papas Costeñas (francesas medianas + 4 deditos de queso costeño)"
            "Costeñitos fritos + Suero Costeño"
            "Anillos de Cebolla"
            "Papas francesas"
            """
        menu_str = "\n".join([f"- {item['nombre']}" for item in menu])

        prompt = PROMPT_PEDIDO_INCOMPLETO.format(
            mensaje_usuario=mensaje_usuario.lower(),
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
        try:
            data = json.loads(raw)
        except Exception:
            recomendaciones_backup = [i["nombre"] for i in menu[:2]]
            data = {
                "mensaje": "Puedo mostrarte el menú completo si deseas. ¿Quieres que te comparta las opciones?",
                "recomendaciones": recomendaciones_backup,
                "intencion": "consulta_menu"
            }
        log_message('Finalizando función <pedido_incompleto_dynamic>.', 'INFO')
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
    
def actualizar_pedido_con_mensaje(
        pedido_actual: Any,
        mensaje_usuario: str,
        menu_items: List[Dict],
        mensaje_chatbot_previo: str = "",
        mensaje_usuario_previo: str = "",
        model: str = "gpt-5.1"
        ) -> Dict:
    """
    Función robusta para actualizar pedidos con lógica de fallback y limpieza.
    """
    try:
        log_message('Iniciando función <actualizar_pedido_con_mensaje>.', 'INFO')
        logging.info("Iniciando actualizar_pedido_con_mensaje.")
        pedido_actual = _safe_parse_order(pedido_actual)
        text_for_replace_check = " ".join([str(mensaje_usuario or ""), str(mensaje_chatbot_previo or ""), str(mensaje_usuario_previo or "")]).lower()
        replace_all = any(phrase in text_for_replace_check for phrase in REPLACE_PHRASES)
        pedido_actual_limpio = {
            **pedido_actual,
            "items": [
                it for it in (pedido_actual.get("items") or [])
                if it and it.get("status") != "not_found"
            ]
        }
        pedido_para_modelo = {
            **pedido_actual_limpio,
            "items": [] if replace_all else pedido_actual_limpio.get("items", [])
        }
        prompt = f"""
        Eres un asistente experto actualizando pedidos de comida.
        TIENES QUE PROCESAR TODOS los productos que el cliente menciona.
        Devuelve un JSON solo con la estructura: {{ "order_complete": bool, "items":[...], "total_price": number }}
        === MENSAJE DEL USUARIO ===
        {mensaje_usuario}
        === PEDIDO ACTUAL LIMPIO ===
        {json.dumps(pedido_para_modelo, ensure_ascii=False)}
        === MENÚ ===
        {json.dumps(menu_items, ensure_ascii=False)}
        LAS HAMBURGESAS SE LLAMAN:
            "Veggie Queso"
            "La Insaciable"
            "Sierra Bomba"
            "Sierra Mulata"
            "Sierra Pagüer"
            "Sierra Picante"
            "Sierra Costeña"
            "Sierra Melao"
            "Sierra Clasica"
            "Camino a la cima"
            "Sierra Queso"
        HAY PERROS CALIENTES LLAMADOS:
            "Super Perro"
            "Super Chanchita"
            "Perro Tocineta"
        CUANDO PIDAN UN ADICIONAL EN CUALQUIER PRODUCTO, SOLO PUEDE SER:
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
        CUANDO PIDAN SALSAS, SOLO PUEDE SER:
            "Salsa de tomate"
            "Salsa mostaza"
            "Salsa bbq"
            "Salsa mayonesa"
        CUANDO PIDAN BEBIDAS, SOLO PUEDE SER:
            "Malteada de Vainilla"
            "Malteada de Mil0"
            "Malteada de Frutos Rojos"
            "Malteada de Chocolate y avellanas"
            "Malteada de Arequipe"
            "Malteada Oblea"
            "Malteada Galleta"
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
        CUANDO PIDAN ACOMPAÑAMIENTOS, SOLO PUEDE SER:
            "Platanitos maduros"
            "Papas Costeñas (francesas medianas + 4 deditos de queso costeño)"
            "Costeñitos fritos + Suero Costeño"
            "Anillos de Cebolla"
            "Papas francesas"
        """
        client = OpenAI()
        response = client.responses.create(model=model, input=prompt, temperature=0)
        raw = ""
        try:
            raw = response.output[0].content[0].text.strip()
        except Exception:
            raw = ""
        clean = raw
        clean = re.sub(r'^```json', '', clean, flags=re.I).strip()
        clean = re.sub(r'^```', '', clean).strip()
        clean = re.sub(r'```$', '', clean).strip()
        parsed = None
        parse_debug = {"method": None, "raw_excerpt": clean[:1000]}
        try:
            parsed = json.loads(clean)
            parse_debug["method"] = "json.loads"
        except Exception:
            try:
                parsed = ast.literal_eval(clean)
                parse_debug["method"] = "ast.literal_eval"
            except Exception as e:
                try:
                    candidate = re.search(r'(\{.*\})', clean, flags=re.DOTALL)
                    if candidate:
                        parsed = json.loads(candidate.group(1))
                        parse_debug["method"] = "regex_json_extract"
                except Exception:
                    parsed = None
                    parse_debug["error"] = str(e)
        if not isinstance(parsed, dict):
            items_final = pedido_para_modelo.get("items", [])
            total_price = sum(_price_of_item(it) for it in items_final)
            order_complete = bool(items_final) and all(it.get("status") == "found" for it in items_final)
            return {
                "order_complete": order_complete,
                "items": items_final,
                "total_price": round(total_price, 2),
                "debug": {"parse_ok": False, "raw_model": raw, **parse_debug}
            }
        model_items = parsed.get("items") or []
        if not isinstance(model_items, list):
            model_items = []
        model_items = [it for it in model_items if it and it.get("status") != "not_found"]
        final_items = _merge_items(pedido_para_modelo.get("items", []), model_items, replace_all=replace_all)
        total_price = sum(_price_of_item(it) for it in final_items)
        total_price = round(total_price, 2)
        order_complete = bool(final_items) and all(it.get("status") == "found" for it in final_items)
        result = {
            "order_complete": order_complete,
            "items": final_items,
            "total_price": total_price
        }
        if parsed.get("debug") or parsed.get("warnings"):
            result["debug_from_model"] = parsed.get("debug") or parsed.get("warnings")
        logging.info("Finalizando actualizar_pedido_con_mensaje.")
        log_message('Finalizando función <actualizar_pedido_con_mensaje>.', 'INFO')
        return result
    except Exception as e:
        logging.exception("Error en actualizar_pedido_con_mensaje")
        return {
            "order_complete": False,
            "items": [],
            "total_price": 0,
            "error": str(e)
        }

def generar_mensaje_confirmacion_pedido(
        pedido_json: dict,
        promocion: bool = False,
        promociones_info: list = None,
        pedido_completo_promocion: dict = None,
        model: str = "gpt-5.1",
    ) -> dict:
    """
    Genera un mensaje de confirmación de pedido.
    - Si promocion=False → usa el prompt normal con pedido_json.
    - Si promocion=True → usa un prompt especial basado en promociones_info y pedido_completo_promocion.
    """

    raw = ""  # para debug si falla

    try:
        client = OpenAI()

        # ------------------------------------------------------------------
        # PROMPT NORMAL (sin promoción)
        # ------------------------------------------------------------------
        if not promocion:
            prompt = f"""
                Eres un asistente de WhatsApp de un restaurante llamado Sierra Nevada, La Cima del Sabor.
                TU NOMBRE ES PAKO.
                RECIBES un JSON de pedido ya completo y validado:
                {json.dumps(pedido_json, ensure_ascii=False)}

                TU MISIÓN:
                1. Generar un MENSAJE amable y claro para el cliente preguntando por la confirmación de lo que pidió.
                - Lista cada producto.
                - Incluye sus modificadores ("sin cebolla", etc.).
                - Muestra precios individuales.
                - Muestra el total.
                - No inventes productos ni precios.

                2. Devuelve un JSON VÁLIDO:
                {{
                    "mensaje": "mensaje natural preguntando por la confirmación del pedido",
                    "intencion_siguiente": "confirmar_pedido"
                }}

                REGLAS:
                - No incluyas texto fuera del JSON.
                - No uses emojis.
                - Mensaje corto, conversacional, profesional.
                - Tono cálido y cercano, estilo Sierra Nevada.
                - Debes cerrar preguntando si desea confirmar: "¿Desea confirmar su pedido?" o "¿Es correcto su pedido?".
            """

        # ------------------------------------------------------------------
        # PROMPT ESPECIAL (promoción=True) - CORREGIDO
        # ------------------------------------------------------------------
        else:
            if promociones_info is None or pedido_completo_promocion is None:
                raise ValueError("Cuando promocion es True, promociones_info y pedido_completo_promocion son obligatorios.")

            # Incluimos tanto el pedido original (pedido_json) como el pedido con la promoción aplicada (pedido_completo_promocion)
            # IMPORTANTE: escapamos las llaves del JSON de formato con {{ }} donde corresponde.
            prompt = f"""
                Eres PAKO, asistente oficial del restaurante Sierra Nevada.

                RECIBES:
                1) Pedido original detectado (fuente de todos los productos):
                {json.dumps(pedido_json, ensure_ascii=False)}

                2) Resultado del análisis de promoción (si existe), con precios finales aplicados:
                {json.dumps(pedido_completo_promocion, ensure_ascii=False)}

                3) Listado de promociones vigentes:
                {json.dumps(promociones_info, ensure_ascii=False)}

                TU MISIÓN (PROMOCIÓN):
                - Explicar al cliente en lenguaje natural qué incluye la promoción identificada.
                - Mostrar claramente QUÉ productos de su pedido entraron en la promoción y cuáles NO.
                - Para cada producto del pedido (tanto promocionado como no):
                  * indicar nombre,
                  * precio original,
                  * precio final que pagará (después de la promoción),
                  * marcar si la promoción fue aplicada.
                - Indicar el precio especial TOTAL de la promoción y el TOTAL FINAL del pedido (suma de todos los final_price).
                - No inventes nada: usa SOLO la información en los JSON arriba (pedido_json, pedido_completo_promocion, promociones_info).

                FORMATO OBLIGATORIO (JSON sin texto adicional). Usa exactamente estas claves:
                {{
                    "mensaje": "Mensaje en lenguaje natural, breve y cálido, explicando la promoción y listando los productos promocionados y no promocionados. Finalizar con pregunta de confirmación.",
                    "intencion_siguiente": "confirmar_pedido"
                }}

                REGLAS ESTILÍSTICAS:
                - Mensaje corto (1-3 frases principales + listado corto).
                - Tono: cálido, profesional y cercano.
                - No uses emojis.
                - No incluyas la "fórmula interna" de cálculo (ej. no explicar cómo se dividió el precio); sí debes mostrar los precios finales por producto.
                - Final obligatorio: pregunta si desea confirmar la promoción/pedido, por ejemplo: "¿Desea confirmar esta promoción y proceder con el pedido?".
            """

        # Enviar al modelo
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0
        )

        raw = response.output[0].content[0].text.strip()

        # Limpieza de bloques ```json
        clean = raw
        clean = re.sub(r'^```json', '', clean, flags=re.I).strip()
        clean = re.sub(r'^```', '', clean).strip()
        clean = re.sub(r'```$', '', clean).strip()

        log_message('Finalizando función <generar_mensaje_confirmacion_pedido>.', 'INFO')
        return json.loads(clean)

    except Exception as e:
        log_message(f'Error en función <generar_mensaje_confirmacion_pedido>: {e}', 'ERROR')
        return {
            "mensaje": "Hubo un error generando el mensaje de confirmación.",
            "intencion_siguiente": "confirmar_pedido",
            "raw_output": raw
        }

def generar_mensaje_cancelacion(
        sender: str,
        codigo_unico: str,
        nombre_cliente: str,
        model: str = "gpt-5.1",
    ) -> dict:
    """
    Genera un JSON con el mensaje de confirmación de pedido.
    Formato de salida:
    {
        "mensaje": "...",
        "siguiente_intencion": "confirmar_pedido"
    }
    """
    try:
        log_message('Iniciando función <generar_mensaje_cancelacion>.', 'INFO')
        dict_registro_temp: dict = obtener_pedido_por_codigo(sender, codigo_unico)
        producto = dict_registro_temp.get("producto", "N/A")
        total_productos = dict_registro_temp.get("total_productos", "N/A")
        client = OpenAI()
        prompt = f"""
        Eres un asistente de WhatsApp de un restaurante llamado Sierra Nevada, La Cima del Sabor.
        TU NOMBRE ES PAKO.
        RECIBES esta información del pedido que el cliente había enviado, pero que no se pudo confirmar porque estaba incompleto, confuso o mal estructurado:
        - Producto(s): {producto}
        - Total estimado de productos: {total_productos}
        - Nombre cliente: {nombre_cliente}
        TU MISIÓN:
        1. Generar un MENSAJE claro y amable explicándole al cliente que su pedido no se pudo confirmar porque algo estaba mal.
        2. Preguntar exactamente: **“¿Qué parte del pedido está mal?”**
        3. Pedirle que vuelva a escribir su pedido de forma completa y clara.
        4. Debes sonar cálido, cercano y respetuoso, estilo Sierra Nevada.
        5. No uses emojis.
        6. No inventes productos, no supongas nada, no des confirmaciones.
        7. Devuelve un JSON **válido**:
        {{
        "mensaje": "mensaje natural pidiendo al cliente que explique qué está mal y escriba de nuevo su pedido",
        "siguiente_intencion": "corregir_pedido"
        }}
        REGLAS:
        - No incluyas texto fuera del JSON.
        - El mensaje debe ser corto, profesional y conversacional.
        - Incluye el código único del pedido en el mensaje.
        - No inventes información adicional.
        """
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0
        )
        raw = response.output[0].content[0].text.strip()
        clean = raw
        clean = re.sub(r'^```json', '', clean, flags=re.I).strip()
        clean = re.sub(r'^```', '', clean).strip()
        clean = re.sub(r'```$', '', clean).strip()
        log_message('Finalizando función <generar_mensaje_cancelacion>.', 'INFO')
        return json.loads(clean)
    except Exception as e:
        log_message(f'Error en función <generar_mensaje_cancelacion>: {e}', 'ERROR')
        return {
            "mensaje": "Hubo un error generando el mensaje de cancelación.",
            "siguiente_intencion": "confirmar_pedido",
            "raw_output": raw
        }

def solicitar_medio_pago(nombre: str, codigo_unico: str, nombre_local: str, pedido_str: str) -> dict:
    try:
        log_message('Iniciando función <solicitar_medio_pago>.', 'INFO')
        PROMPT_MEDIOS_PAGO = """
        Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
        Te llamas PAKO.
        El cliente {nombre} ya confirmó su pedido con el código único: {codigo_unico}.
        Este es el pedido que hizo:
        "{pedido_str}"
        TAREA:
        - Haz un comentario alegre, sabroso y un poquito divertido sobre el pedido.
        - Estilo: cálido, entusiasta, como “¡Wow qué delicia eso!”, “Ese pedido está brutal”, etc.
        - No uses sarcasmo, groserías ni exageres demasiado.
        - Máximo 1 o 2 frases.
        - Después del comentario, pídele que elija su medio de pago.
        - Menciona el local: {nombre_local}
        - Menciona siempre todos los medios de pago disponibles.
        Debes listar estas opciones de pago:
        - Efectivo
        - Transferencia (Nequi, Daviplata, Bre-B)
        - Tarjeta débito
        - Tarjeta crédito
        FORMATO DE RESPUESTA (OBLIGATORIO):
        {{
            "mensaje": "texto aquí"
        }}
        Nada fuera del JSON.
        """
        client = OpenAI()
        prompt = PROMPT_MEDIOS_PAGO.format(
            nombre=nombre,
            codigo_unico=codigo_unico,
            nombre_local=nombre_local,
            pedido_str=pedido_str
        )
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres el generador oficial de mensajes alegres y de pago para Sierra Nevada."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.95
        )
        raw = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except:
            data = {
                "mensaje": f"¡{nombre}, ese pedido está para antojar a cualquiera! 🤤 Tu orden ({codigo_unico}) en {nombre_local} quedó tremenda. ¿Qué medio de pago prefieres: efectivo, transferencia (Nequi/Daviplata/Bre-B), tarjeta débito o tarjeta crédito?"
            }
        log_message('Finalizando función <solicitar_medio_pago>.', 'INFO')
        return data
    except Exception as e:
        log_message(f'Error en función <solicitar_medio_pago>: {e}', 'ERROR')
        logging.error(f"Error en función <solicitar_medio_pago>: {e}")
        return {
            "mensaje": f"¡{nombre}, tu pedido ({codigo_unico}) quedó delicioso! ¿Qué medio de pago deseas usar?"
        }

def enviar_menu_digital(nombre: str, nombre_local: str, menu) -> dict:
    try:
        log_message('Iniciando función <solicitar_medio_pago>.', 'INFO')
        PROMPT = f"""
        Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
        El cliente {nombre} pidió el menú digital.
        Este es el menú que tienes disponible:
        {json.dumps(menu, ensure_ascii=False)}
        TAREA:
        - Haz un comentario alegre, sabroso y un poquito divertido sobre el menú.
        - Estilo: cálido, entusiasta, como “Listo para pedir", vamos a consentirnos hoy y así.
        - No uses sarcasmo, groserías ni exageres demasiado.
        - Máximo 1 o 2 frases.
        - Después del comentario, recomienda que el cliente haga su pedido y 2 opciones del menu (hamburguesas o malteadas).
        - Menciona el local: {nombre_local}
        FORMATO DE RESPUESTA (OBLIGATORIO):
        {{
            "mensaje": "texto aquí"
        }}
        Nada fuera del JSON.
        """
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres el generador oficial de mensajes alegres y de pago para Sierra Nevada."},
                {"role": "user", "content": PROMPT}
            ],
            max_tokens=250,
            temperature=0.95
        )
        raw = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except:
            data = {
                "mensaje": f"¡{nombre}, el menú de {nombre_local} está para chuparse los dedos! 🤤 ¿Qué esperas para pedir una de nuestras deliciosas hamburguesas como 'La Insaciable' o una refrescante malteada de 'Chocolate y avellanas'?"
            }
        log_message('Finalizando función <solicitar_medio_pago>.', 'INFO')
        return data
    except Exception as e:
        log_message(f'Error en función <solicitar_medio_pago>: {e}', 'ERROR')
        logging.error(f"Error en función <solicitar_medio_pago>: {e}")
        return {
            "mensaje": f"¡{nombre}, ¿qué esperas para pedir del delicioso menú de {nombre_local}? ¡Anímate y cuéntame qué se te antoja hoy!"
        }

def responder_sobre_pedido(nombre: str, nombre_local: str, pedido_info: dict, pregunta_usuario: str) -> dict:
    try:
        log_message('Iniciando función <ResponderSobrePedido>.', 'INFO')
        pedido_info_serializable = convert_decimals(pedido_info)
        pedido_info_serializable = {
            k: to_json_safe(v)
            for k, v in pedido_info.items()
        }
        PROMPT = f"""
        Eres PAKO, la voz oficial y amigable de {nombre_local}.
        Información del pedido:
        {json.dumps(pedido_info_serializable, ensure_ascii=False)}
        PREGUNTA:
        {pregunta_usuario}
        REGLAS IMPORTANTES:
        - La respuesta debe basarse SOLO en la información contenida en pedido_info.
        - Si el usuario pregunta por algo que NO está en pedido_info, responde amablemente
          que no tienes ese dato exacto y ofrece revisar menú o promociones.
        - Estilo: cálido, alegre, amable, un poquito divertido, sin sarcasmo y sin exagerar.
        - Máximo 2 frases.
        - Siempre incluir un llamado a la acción al final para "consultar menú" o "consultar promociones".
          Debe ser natural, como:
          "Si quieres, puedo mostrarte el menú o contarte las promociones".
        - No inventes datos adicionales.
        - No mencionar que eres una IA.
        - Respuesta SIEMPRE en JSON.
        OPCIONES PARA futura_intencion:
        - "consulta_menu"
        - "consulta_promociones"
        FORMATO DE RESPUESTA OBLIGATORIO:
        {{
          "mensaje": "texto aquí",
          "futura_intencion": "consulta_menu o consulta_promociones"
        }}
        Nada por fuera del JSON.
        REGLA CRÍTICA:
        NO puedes asumir el estado del pedido. NO puedes decir que está listo, procesado, en preparación, entregado ni nada similar.
        Solo puedes repetir literalmente lo que aparezca en el campo "estado" dentro de pedido_info.
        Si "estado" no está presente en pedido_info:
        - debes responder que no tienes el estado exacto del pedido.
        - y ofrecer consultar menú o promociones.
        PROHIBIDO:
        - Decir que el pedido está "listo", "procesado", "en camino", "confirmado" o cualquier estado NO presente literalmente en el dict.
        - Interpretar o adivinar datos.
        - Inventar palabras relacionadas al estado.
        INFORMACIÓN PERMITIDA:
        Solo puedes usar lo que aparece literalmente en este diccionario:
        {json.dumps(pedido_info_serializable, ensure_ascii=False)}
        Si algo no está allí, responde "No tengo ese dato exacto".
        """
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Eres PAKO, representante alegre de {nombre_local}."},
                {"role": "user", "content": PROMPT}
            ],
            max_tokens=200,
            temperature=0.8
        )
        raw = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except:
            data = {
                "mensaje": f"{nombre}, aquí en {nombre_local} estoy para ayudarte con tu pedido. "
                           f"Si quieres, puedo mostrarte el menú o contarte nuestras promociones.",
                "futura_intencion": "consulta_menu"
            }
        log_message('Finalizando función <ResponderSobrePedido>.', 'INFO')
        return data
    except Exception as e:
        log_message(f'Error en función <ResponderSobrePedido>: {e}', 'ERROR')
        logging.error(f"Error en función <ResponderSobrePedido>: {e}")
        return {
            "mensaje": f"{nombre}, tuve un problema procesando tu solicitud, pero si quieres puedo mostrarte el menú o las promociones.",
            "futura_intencion": "consulta_menu"
        }
    
def responder_sobre_promociones(nombre: str, nombre_local: str, promociones_info: list, pregunta_usuario: str) -> dict:
    """
    Similar a responder_sobre_pedido, pero ahora responde únicamente
    sobre promociones y nada más. Basado SOLO en promociones_info.
    """
    try:
        log_message('Iniciando función <ResponderSobrePromociones>.', 'INFO')

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
#            max_completion_tokens=350,
            temperature=0.85
        )

        raw = response.choices[0].message.content.strip()

        try:
            data = json.loads(raw)
        except:
            data = {
                "mensaje": f"{nombre}, aquí en {nombre_local} tengo varias promociones buenísimas. "
                           f"Si quieres, puedo mostrarte más o llevarte al menú.",
                "futura_intencion": "continuacion_promocion"
            }

        log_message('Finalizando función <ResponderSobrePromociones>.', 'INFO')
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
    log_message('Iniciando función <interpretar_eleccion_promocion>.', 'INFO')
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
#        max_output_tokens=500,
        temperature=0
    )
    try:
        raw = response.output_text   # ← ESTE ES EL CORRECTO
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
    log_message('Finalizando función <interpretar_eleccion_promocion>.', 'INFO')
    return data

def pedido_incompleto_dynamic_promocion(mensaje_usuario: str, promociones_lst: str, json_pedido: str) -> dict:
    try:
        log_message('Iniciando función <pedido_incompleto_dynamic_promocion>.', 'INFO')

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
        - Si pide algo muy general (ej: “una hamburguesa”), sugiere opciones específicas del menú.
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
        - Usa ÚNICAMENTE nombres EXACTOS del menú.

        Aquí está las promociones disponibles:
        {promociones_str}

        LAS HAMBURGESAS SE LLAMAN:
            "Veggie Queso"
            "La Insaciable"
            "Sierra Bomba"
            "Sierra Mulata"
            "Sierra Pagüer"
            "Sierra Picante"
            "Sierra Costeña"
            "Sierra Melao"
            "Sierra Clasica"
            "Camino a la cima"
            "Sierra Queso"

        HAY PERROS CALIENTES LLAMADOS:
            "Super Perro"
            "Super Chanchita"
            "Perro Tocineta"

        CUANDO PIDAN UN ADICIONAL EN CUALQUIER PRODUCTO, SOLO PUEDE SER:
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

        CUANDO PIDAN SALSAS, SOLO PUEDE SER:
            "Salsa de tomate"
            "Salsa mostaza"
            "Salsa bbq"
            "Salsa mayonesa"

        CUANDO PIDAN BEBIDAS, SOLO PUEDE SER:
            "Malteada de Vainilla"
            "Malteada de Mil0"
            "Malteada de Frutos Rojos"
            "Malteada de Chocolate y avellanas"
            "Malteada de Arequipe"
            "Malteada Oblea"
            "Malteada Galleta"
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

        CUANDO PIDAN ACOMPAÑAMIENTOS, SOLO PUEDE SER:
            "Platanitos maduros"
            "Papas Costeñas (francesas medianas + 4 deditos de queso costeño)"
            "Costeñitos fritos + Suero Costeño"
            "Anillos de Cebolla"
            "Papas francesas"
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
#            max_completion_tokens=200,
            temperature=0.8
        )
        raw = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "mensaje": "Por favor elige solo los productos de la promoción o inicia un pedido desde cero escribiendo 'menu' u 'hola'.",
                "recomendaciones": [],
                "intencion": "consulta_menu"
            }
        log_message('Finalizando función <pedido_incompleto_dynamic_promocion>.', 'INFO')
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
        log_message('Iniciando función <mapear_modo_pago>.', 'INFO')
        client = OpenAI()
        PROMPT_MAPEO_PAGO = """
        Eres un clasificador experto en interpretar el método de pago que un cliente escribe en WhatsApp, incluso cuando lo escribe con errores, abreviaciones o de forma muy informal.

        Debes analizar el texto del usuario y responder exclusivamente uno de los siguientes valores:

        - "transferencia - nequi"
        - "transferencia - daviplata"
        - "transferencia - bre-b"
        - "transferencia - otro"
        - "efectivo"
        - "tarjeta"
        - "nfc"
        - "desconocido"

        Reglas:
        1. Aunque esté mal escrito, identifica la intención correcta.
        2. Si menciona:
        - nequi / neki / nekii / nequi bbva → "transferencia - nequi"
        - daviplata / davi / dabiplya / daviplaya → "transferencia - daviplata"
        - bre-b / breb → "transferencia - bre-b"
        - “movil”, “transfer”, “transfe”, “pse”, “lo hago por el celu”, “paso por app” → "transferencia - otro"
        3. tarjeta, tc, td, targta, tarjta, crédito, débito → "tarjeta"
        4. nfc, acercar la tarjeta, contactless → "nfc"
        5. efectivo, cash → "efectivo"
        6. Si no puedes entenderlo → "desconocido"

        Formato de salida OBLIGATORIO (JSON puro):
        {
            "metodo": "uno de los valores permitidos"
        }
        """
        if not respuesta_usuario:
            return "desconocido"

        prompt = PROMPT_MAPEO_PAGO + f'\n\nTexto del usuario: "{respuesta_usuario}"'
        response = client.responses.create(
            model="gpt-3.5-turbo",
            input=prompt,
            max_output_tokens=60,
            temperature=0
        )
        raw = response.output_text
        data = json.loads(raw)
        metodo = data.get("metodo", "desconocido")
        log_message('Finalizando función <mapear_modo_pago>.', 'INFO')
        return metodo
    except Exception as e:
        log_message(f"Error mapeando método de pago: {e}", "ERROR")
        return "desconocido"

def solicitar_metodo_recogida(nombre: str, codigo_unico: str, nombre_local: str, pedido_str: str) -> dict:
    try:
        log_message('Iniciando función <solicitar_metodo_recogida>.', 'INFO')
        PROMPT_METODOS_RECOGIDA = """
            Eres la voz oficial de Sierra Nevada, La Cima del Sabor.
            Te llamas PAKO.
            El cliente {nombre} ya confirmó su pedido con el código único: {codigo_unico}.
            Este es el pedido que hizo:
            "{pedido_str}"

            TAREA:
            - Haz un comentario alegre, sabroso y un poquito divertido sobre el pedido.
            - Estilo: cálido, entusiasta, como “¡Wow qué delicia eso!”, “Ese pedido está brutal!”, etc.
            - No uses sarcasmo, groserías ni exageres demasiado.
            - Máximo 1 o 2 frases.

            Después del comentario:
            - Pregúntale de forma amable y cercana dónde quiere recibir su pedido.
            - Menciona el local: {nombre_local}.
            - Lista claramente las dos opciones de recogida que puede elegir:
                • Recoger en tienda:
                    Centro Mayor (Cc. Centro Mayor, local 3-019)
                    Galerías (Calle 53 # 27-16)
                    Centro Internacional (Calle 32 # 07-10)
                    Chicó 2.0 (Calle 100 # 9a - 45 local 7A)
                    Virrey (Carrera 15 # 88-67)
                • Envío a domicilio (depende de la zona y tiene costo adicional).
            Haz que el cliente se sienta especial y bien atendido.
            Siempre envia el codigo unico del pedido en el mensaje.
            FORMATO DE RESPUESTA (OBLIGATORIO):
            {{
                "mensaje": "texto aquí"
            }}
            Nada fuera del JSON.
        """
        client = OpenAI()
        prompt = PROMPT_METODOS_RECOGIDA.format(
            nombre=nombre,
            codigo_unico=codigo_unico,
            nombre_local=nombre_local,
            pedido_str=pedido_str
        )
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres el generador oficial de mensajes alegres y de pago para Sierra Nevada."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.95
        )
        raw = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except:
            data = {
                "mensaje": f"¡{nombre}, ese pedido está para antojar a cualquiera! 🤤 Tu orden ({codigo_unico}) en {nombre_local} quedó tremenda. ¿Vas a querer domicilio o prefieres recogerlo en el restaurante?"
            }
        log_message('Finalizando función <solicitar_metodo_recogida>.', 'INFO')
        return data
    except Exception as e:
        log_message(f'Error en función <solicitar_metodo_recogida>: {e}', 'ERROR')
        logging.error(f"Error en función <solicitar_metodo_recogida>: {e}")
        return {
            "mensaje": f"¡{nombre}, tu pedido ({codigo_unico}) quedó delicioso! ¿Vas a querer domicilio o prefieres recogerlo en el restaurante?"
        }
