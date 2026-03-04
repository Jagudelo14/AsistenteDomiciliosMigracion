diff --git a/c:\Users\Juan Agudelo\Desktop\PAKO\AsistenteDomiciliosMigracion\utils_contexto.py b/c:\Users\Juan Agudelo\Desktop\PAKO\AsistenteDomiciliosMigracion\utils_contexto.py
--- a/c:\Users\Juan Agudelo\Desktop\PAKO\AsistenteDomiciliosMigracion\utils_contexto.py
+++ b/c:\Users\Juan Agudelo\Desktop\PAKO\AsistenteDomiciliosMigracion\utils_contexto.py
@@ -1,10 +1,12 @@
 # Last modified: 2025-21-12 Juan Agudelo
-import contextvars
-from typing import Optional
-from utils_database import execute_query
-from psycopg2.extras import Json
-import os
-# from utils import es_menor_24h
-from datetime import datetime, timedelta    
-from zoneinfo import ZoneInfo   
+import contextvars
+from typing import Optional
+from utils_database import execute_query
+from psycopg2.extras import Json
+import os
+import json
+import re
+# from utils import es_menor_24h
+from datetime import datetime, timedelta    
+from zoneinfo import ZoneInfo   
 
@@ -12,4 +14,13 @@
 
-_sender_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("sender", default=None)
-_id_cliente_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("id_cliente", default=None)
+_sender_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("sender", default=None)
+_id_cliente_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("id_cliente", default=None)
+
+_RESUMEN_ESTADO_TEXTO = {
+    "metodo_recogida": "Cliente confirmo pedido y define metodo de entrega.",
+    "confirmar_direccion": "Cliente confirmando domicilio.",
+    "medio_pago": "Cliente seleccionando metodo de pago.",
+    "esperando_confirmacion_pago": "Cliente pendiente de confirmacion de pago.",
+    "eleccion_sede": "Cliente eligiendo sede para recoger.",
+    "sin_estado_activo": "Sin flujo activo de pedido."
+}
 
@@ -32,5 +43,215 @@
 
-def get_id_sede() -> Optional[str]:
-    print(f'ID sede recuperado: {_id_cliente_var.get()}', 'INFO')
-    return _id_cliente_var.get()
+def get_id_sede() -> Optional[str]:
+    print(f'ID sede recuperado: {_id_cliente_var.get()}', 'INFO')
+    return _id_cliente_var.get()
+
+
+def _resumen_base() -> dict:
+    return {
+        "estado_actual": None,
+        "pedido_en_proceso": None,
+        "metodo_pago_seleccionado": None,
+        "direccion_confirmada": False,
+        "resumen_contextual": None,
+        "gusta": [],
+        "no_le_gusta": []
+    }
+
+
+def _normalizar_lista_texto(valor) -> list:
+    if valor is None:
+        return []
+    if isinstance(valor, str):
+        limpio = valor.strip()
+        return [limpio] if limpio else []
+    if isinstance(valor, (list, tuple, set)):
+        resultado = []
+        for item in valor:
+            if item is None:
+                continue
+            texto = str(item).strip()
+            if texto:
+                resultado.append(texto)
+        return resultado
+    texto = str(valor).strip()
+    return [texto] if texto else []
+
+
+def _deduplicar_texto(lista: list) -> list:
+    vistos = set()
+    resultado = []
+    for item in lista:
+        texto = str(item).strip()
+        if not texto:
+            continue
+        key = texto.lower()
+        if key in vistos:
+            continue
+        vistos.add(key)
+        resultado.append(texto)
+    return resultado
+
+
+def _limpiar_fragmento_preferencia(texto: str) -> str:
+    if not texto:
+        return ""
+    limpio = texto.strip(" ,.;:!?")
+    limpio = re.sub(r"\b(por favor|gracias|porfa)\b", "", limpio, flags=re.IGNORECASE)
+    limpio = re.sub(r"\s+", " ", limpio).strip()
+    if not limpio:
+        return ""
+    # Limitar ruido muy largo
+    return limpio[:60]
+
+
+def extraer_preferencias_desde_texto(texto_cliente: str) -> dict:
+    if not texto_cliente:
+        return {"gusta": [], "no_le_gusta": []}
+
+    texto = str(texto_cliente).strip()
+    if not texto:
+        return {"gusta": [], "no_le_gusta": []}
+
+    no_gusta = []
+    gusta = []
+
+    patrones_no_gusta = [
+        r"\bsin\s+([a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]{2,60})",
+        r"\bno\s+me\s+gusta(?:n)?\s+([a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]{2,60})",
+        r"\bodio\s+([a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]{2,60})"
+    ]
+    patrones_gusta = [
+        r"\bme\s+gusta(?:n)?\s+([a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]{2,60})",
+        r"\bamo\s+([a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]{2,60})"
+    ]
+
+    for patron in patrones_no_gusta:
+        for match in re.findall(patron, texto, flags=re.IGNORECASE):
+            item = _limpiar_fragmento_preferencia(match)
+            if item:
+                no_gusta.append(item)
+
+    for patron in patrones_gusta:
+        for match in re.findall(patron, texto, flags=re.IGNORECASE):
+            item = _limpiar_fragmento_preferencia(match)
+            if item:
+                gusta.append(item)
+
+    return {
+        "gusta": _deduplicar_texto(gusta),
+        "no_le_gusta": _deduplicar_texto(no_gusta)
+    }
+
+
+def obtener_resumen_cliente(telefono: str, id_restaurante: int) -> dict:
+    try:
+        query = """
+            SELECT resumen
+            FROM clientes_whatsapp
+            WHERE telefono = %s
+              AND id_restaurante = %s
+            LIMIT 1;
+        """
+        result = execute_query(query, (telefono, id_restaurante), fetchone=True)
+        resumen = _resumen_base()
+        if not result:
+            return resumen
+
+        valor = result[0]
+        if valor is None:
+            return resumen
+
+        if isinstance(valor, str):
+            try:
+                valor = json.loads(valor)
+            except Exception:
+                return resumen
+
+        if not isinstance(valor, dict):
+            return resumen
+
+        # Compatibilidad con estructura previa
+        if "le_gusta" in valor and "gusta" not in valor:
+            valor["gusta"] = valor.get("le_gusta")
+
+        resumen.update(valor)
+        resumen["gusta"] = _deduplicar_texto(_normalizar_lista_texto(resumen.get("gusta")))
+        resumen["no_le_gusta"] = _deduplicar_texto(_normalizar_lista_texto(resumen.get("no_le_gusta")))
+        return resumen
+    except Exception:
+        return _resumen_base()
+
+
+def guardar_resumen_cliente(telefono: str, id_restaurante: int, resumen: dict) -> None:
+    try:
+        query = """
+            UPDATE clientes_whatsapp
+            SET resumen = %s
+            WHERE telefono = %s
+              AND id_restaurante = %s;
+        """
+        execute_query(query, (Json(resumen), telefono, id_restaurante))
+    except Exception:
+        # El resumen nunca debe romper el flujo principal
+        pass
+
+
+def actualizar_resumen_cliente(
+    telefono: str,
+    id_restaurante: int,
+    updates: dict = None,
+    gustos: list = None,
+    no_gustos: list = None,
+    texto_cliente: str = None
+) -> None:
+    try:
+        resumen = obtener_resumen_cliente(telefono, id_restaurante)
+        updates = updates or {}
+
+        for key, value in updates.items():
+            if key in ("gusta", "no_le_gusta"):
+                continue
+            # Permitir bool false; ignorar None para no borrar accidentalmente
+            if value is None:
+                continue
+            resumen[key] = value
+
+        gustos_total = _normalizar_lista_texto(resumen.get("gusta"))
+        no_gustos_total = _normalizar_lista_texto(resumen.get("no_le_gusta"))
+
+        gustos_total.extend(_normalizar_lista_texto(gustos))
+        no_gustos_total.extend(_normalizar_lista_texto(no_gustos))
+
+        gustos_total.extend(_normalizar_lista_texto(updates.get("gusta")))
+        no_gustos_total.extend(_normalizar_lista_texto(updates.get("no_le_gusta")))
+
+        if texto_cliente:
+            preferencias = extraer_preferencias_desde_texto(texto_cliente)
+            gustos_total.extend(_normalizar_lista_texto(preferencias.get("gusta")))
+            no_gustos_total.extend(_normalizar_lista_texto(preferencias.get("no_le_gusta")))
+
+        resumen["gusta"] = _deduplicar_texto(gustos_total)
+        resumen["no_le_gusta"] = _deduplicar_texto(no_gustos_total)
+
+        estado = resumen.get("estado_actual")
+        if estado and not resumen.get("resumen_contextual"):
+            resumen["resumen_contextual"] = _RESUMEN_ESTADO_TEXTO.get(estado, resumen.get("resumen_contextual"))
+
+        resumen["ultima_actualizacion"] = datetime.now(tz=ZoneInfo("America/Bogota")).isoformat()
+        guardar_resumen_cliente(telefono, id_restaurante, resumen)
+    except Exception:
+        pass
+
+
+def actualizar_resumen_por_estado(telefono: str, id_restaurante: int, estado: str, codigo_pedido: str = None) -> None:
+    updates = {"estado_actual": estado}
+    if codigo_pedido:
+        updates["codigo_pedido_activo"] = codigo_pedido
+    if estado in _RESUMEN_ESTADO_TEXTO:
+        updates["resumen_contextual"] = _RESUMEN_ESTADO_TEXTO[estado]
+    actualizar_resumen_cliente(telefono, id_restaurante, updates=updates)
+
+
+def actualizar_resumen_por_mensaje(telefono: str, id_restaurante: int, texto_cliente: str) -> None:
+    actualizar_resumen_cliente(telefono, id_restaurante, texto_cliente=texto_cliente)
 
@@ -182,7 +403,7 @@
 
-def actualizar_estado_pedido(
-    telefono: str,
-    id_restaurante: int,
-    estado: str,
-    num_pedido: str = None
+def actualizar_estado_pedido(
+    telefono: str,
+    id_restaurante: int,
+    estado: str,
+    num_pedido: str = None
 ):
@@ -197,8 +418,9 @@
                 fecha_actualizacion = NOW();
-        """
-
-        execute_query(query, (telefono, id_restaurante, estado, num_pedido))
-
-    except Exception as e:
-        raise e
+        """
+
+        execute_query(query, (telefono, id_restaurante, estado, num_pedido))
+        actualizar_resumen_por_estado(telefono, id_restaurante, estado, num_pedido)
+
+    except Exception as e:
+        raise e
 
@@ -210,8 +432,9 @@
             AND id_restaurante = %s;
-        """
-
-        execute_query(query, (telefono, id_restaurante))
-
-    except Exception as e:
-        return None
+        """
+
+        execute_query(query, (telefono, id_restaurante))
+        actualizar_resumen_por_estado(telefono, id_restaurante, "sin_estado_activo")
+
+    except Exception as e:
+        return None
 
