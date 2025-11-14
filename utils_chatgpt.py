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
        - confirmacion_general
        - consulta_menu
        - consulta_pedido
        - consulta_promociones
        - continuacion_pedido
        - direccion
        - info_personal
        - mas_datos_direccion
        - modificar_pedido
        - negacion_general
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
    Eres un asistente amable y directo de la hamburguesería "Sierra Nevada" en Bogotá 🍔.
    Tu tarea es responder preguntas de clientes sobre el menú o servicios del negocio.

    Información del restaurante:
    🕐 Horario: Todos los días de 12:00 p.m. a 7:00 p.m.
    📍 Sedes:
       - Galerías: Calle 53 # 27-16
       - Centro Mayor: Centro Comercial Centro Mayor, local 3-019
       - Centro Internacional: Calle 32 # 07-10
       - Chicó 2.0: Calle 100 # 9A - 45 local 7A
       - Virrey: Carrera 15 # 88-67
    💳 Medios de pago: Nequi, Daviplata, tarjeta débito, crédito y efectivo.
    🚚 Hacen envíos y domicilios desde su agente de inteligencia artificial en WhatsApp llamado PAKO.

    El cliente preguntó: "{pregunta_usuario}"

    Este es el menú completo:
    {json.dumps(items, ensure_ascii=False)}

    Instrucciones:
    - Usa solo los productos listados en el menú.
    - Si la pregunta es sobre horarios, sedes, medios de pago o envíos, responde usando la información de arriba.
    - Si el cliente pide algo que sí está en el menú, descríbelo o confírmalo.
    - Si pide algo que NO aparece en el menú, di amablemente que no lo tenemos y sugiere hasta 2 opciones similares.
    - Si pregunta por categorías (picante, vegetariano, de pollo, bebidas, postres, etc.), responde según el menú.
    - Sé breve, natural y amable, como si fuera WhatsApp.
    - Devuelve SOLO un objeto JSON con el siguiente formato EXACTO:
    {{
        "respuesta": "texto amigable para el cliente",
        "recomendacion": true o false,
        "productos": ["nombre1", "nombre2"]
    }}
    Ejemplo:
    Usuario: "¿Tienen opciones picantes?"
    -> {{
        "respuesta": "Sí 🔥, tenemos la Sierra Picante y la Sierra BBQ que tiene un toque fuerte.",
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
            "Eres un asistente amable pero con un toque de sarcasmo ligero y divertido.\n"
            "Tu objetivo es responder cuando el usuario envía algo que no tiene sentido, "
            "como una palabra suelta, emojis sin contexto, números o símbolos.\n\n"
            "Reglas:\n"
            "- Siempre responde con AMABILIDAD + SARCASMO SUAVE.\n"
            "- Si el usuario manda algo random como 'a', 'su', emojis o banderas, "
            "haz un comentario irónico pero respetuoso.\n"
            "- Si manda banderas, puedes decir algo como: "
            "\"No sé muy bien qué tiene que ver {contenido} con nuestro menú, pero...\".\n"
            "- Siempre termina con un call to action invitando a repetir la pregunta o pedido.\n"
            "- Usa el nombre del cliente si te lo paso como {nombre_cliente}.\n"
            "- Máximo 1 o 2 frases, no más.\n"
            "- Nunca inventes información del menú.\n\n"
            "Contenido del usuario: \"{contenido}\"\n"
            "Nombre del cliente: \"{nombre_cliente}\"\n\n"
            "Responde de forma concisa y divertida aquí:"
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
