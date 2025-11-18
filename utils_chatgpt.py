# utils_chatgpt.py
# Last modified: 2025-11-05 by Andrés Bermúdez

from openai import OpenAI
import logging
from typing import Any, Optional, Tuple, Dict
import os
import json
from utils import send_text_response, limpiar_respuesta_json, log_message

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
        Debes responder **únicamente** en formato JSON válido con la siguiente estructura:
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
        - modificar_pedido
        - negacion_general (puede ser en otros idiomas: no, non, nein, etc.)
        - preguntas_generales
        - quejas (quejas de menor nivel: retraso en la entrega, mal servicio del domiciliario, problemas con la app, cocción desfasada solamente)
        - saludo
        - sin_intencion
        - solicitud_pedido
        - transferencia (quejas de mayor nivel: no entrega de domicilio, pedido equivocado, mal estado del pedido solamente)
        - validacion_pago

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
            max_tokens=500,
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

def mapear_pedido_al_menu(contenido_clasificador: dict, menu_items: list, model: str = "gpt-4o") -> dict:
    """
    Mapear los items provenientes del clasificador al menú usando gpt-4o.
    - contenido_clasificador: dict con la salida del clasificador (ver ejemplo en tu mensaje).
    - menu_items: lista de dicts con cada producto del menú, por ejemplo:
        [
          {"id": "p_001", "name": "Sierra Picante", "price": 14000, "aliases": ["sierra picante","sierra"]},
          {"id": "p_002", "name": "Gaseosa 400ml", "price": 4000, "aliases": ["gaseosa","refresco"]}
        ]
    Devuelve un JSON con la forma especificada en el prompt.
    """

    client = OpenAI()  # instancia del cliente
    # Construimos el prompt que recibirá gpt-4o
    prompt = f"""
Eres un asistente encargado de mapear pedidos (extraídos por un clasificador) a un MENÚ estructurado.
Debes RESPONDER ÚNICA Y EXCLUSIVAMENTE con un JSON válido (sin texto adicional) con esta estructura:

{{
  "order_complete": true|false,           // true si TODOS los items fueron encontrados
  "items": [
    {{
      "requested": {{ "producto": "...", "modalidad": "...", "especificaciones": [ ... ] }},
      "status": "found" | "not_found" | "multiple_matches",
      "matched": {{ "name": "...", "id": "...", "price": number }}  // si status == found
      "candidates": [ {{ "name":"...", "id":"...", "price": number }}, ... ], // si status == multiple_matches
      "modifiers_applied": [ ... ],   // incluir especificaciones tal como aparecen en requested si se aplican
      "note": "texto corto si es necesario"  // ej. "producto exacto no hallado, se devolvieron candidatos"
    }}
  ],
  "total_price": number  // suma de los precios de matched (ignorar cambios de precio por modificadores a menos que el menu indique un modificador con precio)
}}

REGLAS CLAVE:
1) Usa exactamente el NOMBRE del producto como aparece en el campo 'name' del MENÚ cuando haya coincidencia.
2) Haz matching case-insensitive y considera 'aliases' si están disponibles en el MENÚ.
3) Si hay coincidencia exacta (nombre o alias) → status = "found" y devuelve name/id/price desde el menú.
4) Si hay más de una coincidencia plausible y no hay forma de decidir exactamente → status = "multiple_matches" y devuelve up to 3 candidates (name,id,price).
5) Si no encuentras ninguna coincidencia → status = "not_found". En ese caso coloca matched = {{}}, agrega note = "producto no encontrado" y AL FINAL del JSON setea "order_complete": false.
6) Si cualquier item tiene status "not_found" → order_complete = false; si todos están "found" → order_complete = true.
7) Si el menú incluye objetos 'modifiers' o precios por especificación, aplícalos; si no, inclúyelos en 'modifiers_applied' pero NO cambies el price base (a menos que el menú indique explícitamente el costo del modificador).
8) Devuelve siempre números (no strings) para los precios y para total_price.
9) No incluyas explicaciones, solo el JSON.

A continuación se incluyen el MENU y la entrada del CLASIFICADOR (ambos en JSON). Usa esa información para mapear.

MENU:
{json.dumps(menu_items, ensure_ascii=False)}

CLASIFICADOR:
{json.dumps(contenido_clasificador, ensure_ascii=False)}

Ejemplo (para orientación — NO lo copies como salida, la salida debe seguir la estructura anterior):
Si el clasificador pide "sierra picante" con especificación ["extra ají"] y el menú tiene "Sierra Picante" con id "p_001" y price 14000 → status found y matched.name = "Sierra Picante", matched.id = "p_001", matched.price = 14000, modifiers_applied = ["extra ají"].

DEVUELVE SOLO EL JSON.
"""

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0
        )

        # Extraer texto (ajusta según la forma en que tu SDK devuelve el output)
        text_output = response.output[0].content[0].text.strip()
        result = json.loads(text_output)
        return result

    except json.JSONDecodeError:
        logging.error("Error al parsear JSON desde el modelo. Output crudo:")
        logging.error(text_output if 'text_output' in locals() else 'no output')
        return {
            "order_complete": False,
            "items": [],
            "total_price": 0,
            "error": "parse_error",
            "raw_output": text_output if 'text_output' in locals() else None
        }
    except Exception as e:
        logging.exception("Error llamando al API")
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
            - Incluye siempre el nombre del cliente: {nombre_cliente}
            - Incluye siempre el nombre del local: {nombre_local}
            - Responde en máximo 1 o 2 frases.
            - Escoge UNA intención entre:
                - "consulta_menu"
                - "consulta_promociones"

            FORMATO:
            Debes responder en un JSON válido:

            {
                "mensaje": "texto aquí",
                "intencion": "consulta_menu"
            }

            No incluyas texto adicional fuera del JSON.
            """
        client = OpenAI()
        prompt = PROMPT_SALUDO_DYNAMIC.format(
            nombre_cliente=nombre,
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
        # Intentar parsear JSON
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
        # Intentar parsear JSON
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