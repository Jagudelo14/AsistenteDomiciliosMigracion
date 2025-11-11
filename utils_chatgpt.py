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

def analizar_respuesta_usuario_sin_intencion(respuesta_cliente: str, intencion_anterior: str, model: str = "gpt-3.5-turbo") -> dict:
    """
    Analiza si la respuesta del usuario tiene continuidad con la intención anterior.
    
    Parámetros:
        respuesta_cliente (str): Respuesta dada por el usuario (e.g., "sí", "no", "no entiendo").
        intencion_anterior (str): Intención previa detectada en el flujo conversacional.
        model (str): Modelo de OpenAI a utilizar.
    
    Retorna:
        dict: JSON con la estructura solicitada.
    """
    client: OpenAI = OpenAI()
    prompt = f"""
        Eres un asistente que analiza si la respuesta de un usuario mantiene continuidad con la intención anterior.
        Tu salida debe ser un JSON EXACTO con la forma:
        {{
        "intencion_respuesta": "nombre_intencion",
        "continuidad": bool,
        "observaciones": "texto opcional si hay duda o ruptura de flujo"
        }}

        Ejemplos:

        1️⃣
        intencion_anterior: "consulta_promociones"
        respuesta_cliente: "sí"
        →
        {{
        "intencion_respuesta": "consulta_promociones",
        "continuidad": true,
        "observaciones": ""
        }}

        2️⃣
        intencion_anterior: "consulta_promociones"
        respuesta_cliente: "no"
        →
        {{
        "intencion_respuesta": "consulta_promociones",
        "continuidad": false,
        "observaciones": "El usuario rechazó la continuidad de la promoción"
        }}

        3️⃣
        intencion_anterior: "consulta_productos"
        respuesta_cliente: "no entiendo"
        →
        {{
        "intencion_respuesta": "consulta_productos",
        "continuidad": false,
        "observaciones": "El usuario parece confundido o necesita aclaración"
        }}

        4️⃣
        intencion_anterior: "reclamo_servicio"
        respuesta_cliente: "ya lo solucionaron"
        →
        {{
        "intencion_respuesta": "reclamo_servicio",
        "continuidad": false,
        "observaciones": "El usuario indica que el problema ya se resolvió"
        }}

        5️⃣
        intencion_anterior: "consulta_horarios"
        respuesta_cliente: "perfecto, gracias"
        →
        {{
        "intencion_respuesta": "consulta_horarios",
        "continuidad": true,
        "observaciones": "El usuario confirma que recibió la información"
        }}

        Ahora analiza:
        intencion_anterior: "{intencion_anterior}"
        respuesta_cliente: "{respuesta_cliente}"

        Devuelve SOLO el JSON, sin explicación.
    """ 
    response = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.3
    )
    text_output = response.output[0].content[0].text.strip()
    try:
        result = json.loads(text_output)
    except json.JSONDecodeError:
        result = {
            "intencion_respuesta": intencion_anterior,
            "continuidad": False,
            "observaciones": "Error al interpretar la respuesta del modelo"
        }
    log_message('Finalizando función <AnalizarRespuestaUsuarioSinIntencion>.', 'INFO')
    log_message(f'Respuesta analizada: {result}', 'INFO')
    return result

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

def responder_pregunta_menu_chatgpt(pregunta_usuario: str, items, model: str = "gpt-4o") -> tuple:
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
        return result, prompt

    except Exception as e:
        logging.error(f"Error en <ResponderPreguntaMenuChatGPT>: {e}")
        log_message(f'Error en <ResponderPreguntaMenuChatGPT>: {e}', 'ERROR')
        return {
            "respuesta": "Lo siento 😔, tuve un problema para responder tu pregunta.",
            "recomendacion": False,
            "productos": []
        }, prompt
