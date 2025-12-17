# utils_google.py
# Last modified: 2025-10-02 by Andrés Bermúdez

import logging
import googlemaps
from googlemaps.exceptions import ApiError
from utils import borrar_intencion_futura, guardar_intencion_futura, log_message, obtener_intencion_futura_observaciones, obtener_pedido_pendiente_reciente, point_in_polygon, send_text_response
from utils_chatgpt import solicitar_confirmacion_direccion
from utils_database import execute_query
import json
import os

CANTIDAD_TIEMPO_PEDIDO: int = 5 # Cantidad de tiempo por pedido en cola en minutos
TIEMPO_TOLERANCIA: int = 5 # Cantidad de minutos de tolerancia para tiempo total de domicilio
UMBRAL_TIEMPO: int = 150 # Cantidad de minutos de umbral máximo para un domicilio (2 horas y 30 minutos)
API_KEY_GOOGLE_MAPS: str = os.environ.get("API_KEY_GOOGLE_MAPS", "")

def obtener_cliente_google_maps() -> googlemaps:
    try:
        """Crea el cliente de google maps"""
        gmaps: googlemaps = googlemaps.Client(key=API_KEY_GOOGLE_MAPS)
        log_message("Crea cliente gmaps sin problema", "INFO")
        return gmaps
    except Exception as e:
        log_message(f"Ocurrió un error al crear cliente, {e}", "ERROR")
        raise e 
        
def calcular_valor_envio(distancia: float) -> int:
    try:
        """Se calcula el valor del envio a razón de la distancia"""
        log_message(f"Empieza a calcular el valor del envio con distancia {distancia} km.", "INFO")
        valor: float
        if distancia <= 2000:
            valor = 2000
        else:
            valor = 2000 + ((distancia -2000)*0.4)
        valor_redondeado: int = round(valor // 100)*100
        log_message(f"Valor del envio es de {valor_redondeado} COP.", "INFO")
        return valor_redondeado
    except Exception as e:
        log_message(f"Error en calcular valor envio {e}", "ERROR")
        raise e

def primera_regla_tiempo(id_sede: str, tiempo_base: int) -> int:
    """
    Regla para calcular el tiempo estimado de pedido basado en la demanda actual.
    Suma 8 minutos por cada 10 hamburguesas en preparación en la sede indicada.
    """
    try:
        query = """
        SELECT
        p.idpedido,
        COUNT(d.id_detalle) AS total_items
        FROM pedidos p
        LEFT JOIN detalle_pedido d
        ON p.idpedido = d.id_pedido
        WHERE p.idsede = %s
        AND p.estado = 'pendiente'
        GROUP BY p.idpedido;
        """
        params = (id_sede,)

        # debug antes de ejecutar
        log_message(f"[primera_regla_tiempo] SQL: {query.strip()}", "DEBUG")
        log_message(f"[primera_regla_tiempo] params: {params}", "DEBUG")

        rows = execute_query(query, params)
        # rows expected: list of tuples (idpedido, total_items)
        if not rows:
            # no hay pedidos pendientes -> no aumento sobre el tiempo base
            log_message("[primera_regla_tiempo] No hay pedidos pendientes.", "DEBUG")
            return tiempo_base

        # Sumar la cantidad de items (productos) en preparación en todos los pedidos pendientes
        total_items = sum(r[1] or 0 for r in rows)
        log_message(f"Total de productos en preparación: {total_items}", "INFO")

        # Por cada 10 productos sumar 7 minutos
        incremento = (total_items // 10) * 7
        tiempo_estimado = int(tiempo_base + incremento)
        log_message(f"Tiempo base: {tiempo_base} | Incremento: {incremento} | Total estimado: {tiempo_estimado}", "INFO")

        return tiempo_estimado

    except Exception as e:
        log_message(f"Error en primera_regla_tiempo: {str(e)}", "ERROR")
        return tiempo_base

def formatear_tiempo_entrega(minutos: int) -> str:
    """
    Convierte minutos enteros en un string presentable.
    Ejemplos:
    - 45 -> '45 minutos'
    - 70 -> '1 hora 10 minutos'
    - 120 -> '2 horas'
    """
    try:
        if minutos < 0:
            return "Tiempo no disponible"

        if minutos < 60:
            return f"{minutos} minutos"

        horas = minutos // 60
        mins = minutos % 60

        # Pluralización correcta
        h_text = "hora" if horas == 1 else "horas"

        if mins == 0:
            return f"{horas} {h_text}"

        return f"{horas} {h_text} {mins} minutos"

    except Exception:
        return "Tiempo no disponible"


def calcular_tiempo_pedido(tiempo_domicilio: str, id_sede: str) -> int:
    try:
        """Se calcula el tiempo dependiendo la cantidad de pedidos con base al tiempo distancia entre cliente y sede"""
        log_message(f"Se inicia tiempo de pedido con tiempo de envio de {tiempo_domicilio}", "INFO")
        tiempo_domicilio = tiempo_domicilio.lower()
        minutos_totales: int = 0
        if "hora" in tiempo_domicilio:
            partes: list = tiempo_domicilio.split("hora")
            horas: int = int(partes[0].strip())
            minutos_totales = horas*60
            if len(partes) > 1 and "min" in partes[1]:
                minutos_extra: int = ''.join(filter(str.isdigit, tiempo_domicilio))
                if minutos_extra:
                    minutos_totales += int(minutos_extra)
        elif "min" in tiempo_domicilio:
            minutos_totales += int(''.join(filter(str.isdigit, tiempo_domicilio)))
        log_message(f"Minutos totales iniciales: {minutos_totales}", "INFO")
        minutos_totales = primera_regla_tiempo(id_sede, minutos_totales) # Ajuste por demanda
        tiempo_pedido: int = minutos_totales + TIEMPO_TOLERANCIA
        if tiempo_pedido > UMBRAL_TIEMPO:
            log_message(f"Tiempo de pedido supera el umbral {tiempo_pedido} minutos.", "INFO")
            return -1
        log_message(F"El tiempo de pedido es de {tiempo_pedido} minutos.", "INFO")
        return tiempo_pedido
    except Exception as e:
        log_message(f"Ocurrió un error al calcular tiempo pedido {e}", "ERROR")
        return -1

def buscar_sede_mas_cercana_dentro_area(latitud_cliente: float, longitud_cliente: float, id_restaurante: str):
    try:
        log_message(f"Buscando la sede más cercana dentro de su área para coordenadas ({latitud_cliente}, {longitud_cliente})", "INFO")

        # ------------------------------------
        # 1. Obtener sedes
        # ------------------------------------
        sedes = execute_query("""
            SELECT id_sede, nombre, ciudad, latitud, longitud
            FROM sedes
            WHERE estado = TRUE
              AND id_restaurante = %s
              AND latitud IS NOT NULL
              AND longitud IS NOT NULL;
        """, (id_restaurante,))

        if not sedes:
            return None
        for s in sedes:
            logging.info(f"Sede: {s}")  
        ids = [s[0] for s in sedes]
        areas_map = {}

        # ------------------------------------
        # 2. Obtener áreas de cobertura
        # ------------------------------------
        if ids:
            placeholders = ",".join(["%s"] * len(ids))
            query_areas = f"""
                SELECT id_sede, valor
                FROM sedes_areas
                WHERE id_sede IN ({placeholders});
            """
            log_message(f"Query areas: {query_areas}", "INFO")
            areas_rows = execute_query(query_areas, tuple(ids))

            if areas_rows:
                for id_sede_row, valor in areas_rows:
                    log_message(f"Valor raw: {valor}", "INFO")
                    parsed = None
                    logging.info(f"Valor: {valor}")

                    if valor is None:
                        parsed = None
                    elif isinstance(valor, (dict, list)):
                        parsed = valor
                    else:
                        try:
                            parsed = json.loads(valor)
                        except Exception:
                            try:
                                cleaned = valor.replace('""', '"')
                                parsed = json.loads(cleaned)
                            except Exception:
                                parsed = None

                    logging.info(f"Final parsed {parsed}")

                    if parsed:
                        areas_map.setdefault(id_sede_row, []).append(parsed)

        # ------------------------------------
        # 3. Verificar si el cliente cae dentro de un área válida
        # ------------------------------------
        candidatos = []

        for s in sedes:
            
            sede_id, nombre, ciudad, lat_sede, lon_sede = s
            polygons = areas_map.get(sede_id)

            logging.info(f"Polys {polygons}")
            log_message(f"Verificando sede {sede_id} - {nombre} en ciudad {ciudad}", "INFO")
            if not polygons:
                continue

            encontrada = None

            for poly in polygons:
                logging.info(f"Poly for in {poly}")
                log_message(f"Verificando polígono: {poly}", "INFO")
                try:
                    if point_in_polygon(latitud_cliente, longitud_cliente, poly):
                        logging.info("Punto dentro del polígono")
                        log_message("Punto dentro del polígono", "INFO")
                        encontrada = poly
                        break
                    else:
                        logging.info("Punto fuera del polígono")
                        log_message("Punto fuera del polígono", "INFO")
                except Exception as e:
                    logging.info(f"Error e {e}")
                    log_message(f"Error al verificar punto en polígono: {e}", "ERROR")
                    continue

            if encontrada is not None:
                candidatos.append((s, lat_sede, lon_sede, encontrada))

        if not candidatos:
            return None

        # ------------------------------------
        # 4. Llamar Google Distance Matrix
        # ------------------------------------
        gmaps = obtener_cliente_google_maps()

        origen = (latitud_cliente, longitud_cliente)
        destinos = [(item[1], item[2]) for item in candidatos]

        logging.info(f"destinos {destinos}")

        try:
            resultado = gmaps.distance_matrix(
                origins=[origen],
                destinations=destinos,
                mode="driving",
                language="es"
            )
        except ApiError as ae:
            log_message(f"Google Maps ApiError al calcular distancia para sedes: {ae}", "ERROR")
            logging.error(f"Google Maps ApiError: {ae}")
            return None
        except Exception as ex:
            log_message(f"Error llamando Google Maps distance_matrix para sedes: {ex}", "ERROR")
            logging.error(f"Error calling distance_matrix: {ex}")
            return None

        # Direcciones humanas devueltas por Google
        #direccion_origen = resultado.get("origin_addresses", [""])[0]
        direcciones_destinos = resultado.get("origin_addresses", [])

        # ------------------------------------
        # 5. Construir opciones válidas
        # ------------------------------------
        opciones_validas = []
        elements = resultado.get("rows", [])[0].get("elements", []) if resultado.get("rows") else []

        for i, elem in enumerate(elements):
            if elem.get("status") != "OK":
                continue
            distancia_m = elem["distance"]["value"]
            duracion_s = elem["duration"]["value"]
            sede_tuple = candidatos[i][0]
            area_usada = candidatos[i][3]
            direccion_destino = direcciones_destinos[i] if i < len(direcciones_destinos) else ""
            opciones_validas.append({
                "id": sede_tuple[0],
                "nombre": sede_tuple[1],
                "ciudad": sede_tuple[2],
                "distancia_km": round(distancia_m / 1000, 2),
                "tiempo_min": round(duracion_s / 60, 1),
                "lat": candidatos[i][1],
                "lon": candidatos[i][2],
                "area": area_usada,
                "direccion_envio": direccion_destino  # <-- agregado
            })
        if not opciones_validas:
            return None
        # ------------------------------------
        # 6. Seleccionar la sede más cercana
        # ------------------------------------
        opciones_validas.sort(key=lambda x: x["distancia_km"])
        return opciones_validas[0]
    except Exception as e:
        logging.error(f"Error en buscar_sede_mas_cercana_dentro_area: {e}")
        log_message(f"Ocurrió un error al buscar sede más cercana: {e}", "ERROR")
        return None

def set_sede_cliente(id_sede: str, numero_cliente, id_restaurante: str) -> bool:
    try:
        """Asigna la sede seleccionada al cliente en la base de datos."""
        log_message(f"Asignando sede {id_sede} al cliente {numero_cliente}", "INFO")
        execute_query("""
            UPDATE clientes_whatsapp
            SET id_sede = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """, (id_sede, numero_cliente, id_restaurante))
        log_message("Sede asignada correctamente.", "INFO")
        return True
    except Exception as e:
        log_message(f"Error al asignar sede al cliente: {e}", "ERROR")
        return False

def set_lat_lon(numero_cliente: str, latitud_client: float, longitud_client: float, id_restaurante) -> bool:
    try:
        """Asigna la sede seleccionada al cliente en la base de datos."""
        log_message(f"Asignando lat y long al cliente {numero_cliente}", "INFO")
        execute_query("""
            UPDATE clientes_whatsapp
            SET latitud = %s, longitud = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """, (latitud_client, longitud_client, numero_cliente, id_restaurante))
        log_message("Sede asignada correctamente.", "INFO")
        return True
    except Exception as e:
        log_message(f"Error al asignar sede al cliente: {e}", "ERROR")
        return False

def set_direccion_cliente(numero_cliente: str, direccion: str, id_restaurante: str) -> bool:
    try:
        """Actualiza la dirección del cliente en la base de datos."""
        log_message(f"Actualizando dirección para el cliente {numero_cliente}", "INFO")
        log_message(f"Dirección a actualizar: {direccion}", "INFO")
        query = """
            UPDATE clientes_whatsapp
            SET direccion_google = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (direccion, numero_cliente, id_restaurante)
        # Imprimir y loguear la query y sus parámetros antes de ejecutar
        log_message(f"Executing SQL query: {query}", "DEBUG")
        log_message(f"SQL params: {params}", "DEBUG")
        execute_query(query, params)

        log_message(f"Dirección actualizada a '{direccion}' para el cliente {numero_cliente}.", "INFO")
        return True
    except Exception as e:
        log_message(f"Error al actualizar dirección del cliente: {e}", "ERROR")
        raise e

def calcular_valor(distancia) -> float: 
    #calcular valor del domicilio   
    if distancia <= 2000:
        valor = 2000
    else:
        valor = 2000 + ((distancia - 2000) * 0.4)

    #valor_redondeado = round(valor // 100) * 100
    valor_redondeado = 0.0  # establecer valor del domicilio en 0
    return valor_redondeado

def calcular_distancia_y_tiempo(origen: tuple, destino: tuple, numero_telefono: str, id_restaurante: str, id_sede: str):
    try:
        """"""
        log_message(f"Calculando distancia entre {origen} y {destino}", "INFO")
        gmaps = obtener_cliente_google_maps()
        try:
            resultado = gmaps.distance_matrix(origins=[origen],
                                       destinations=[destino],
                                       mode='driving',
                                       language='es')
        except ApiError as ae:
            # Errores de autorización/servicio de Google Maps (REQUEST_DENIED, etc.)
            log_message(f"Google Maps ApiError al calcular distancia: {ae}", "ERROR")
            logging.error(f"Google Maps ApiError: {ae}")
            return None
        except Exception as ex:
            # Otros errores de red/cliente
            log_message(f"Error llamando Google Maps distance_matrix: {ex}", "ERROR")
            logging.error(f"Error calling distance_matrix: {ex}")
            return None
        duracion = resultado['rows'][0]['elements'][0]['duration']['text']
        direccion_envio = resultado['destination_addresses'][0]
        if not set_direccion_cliente(numero_telefono, direccion_envio, id_restaurante):
            log_message(f"No se pudo actualizar la dirección del cliente {numero_telefono}", "ERROR")
        #distancia = resultado['rows'][0]['elements'][0]['distance']['text']
        distancia_metros = resultado['rows'][0]['elements'][0]['distance']['value']
        duracion = calcular_tiempo_pedido(duracion, id_sede)
        tiempo_pedido: str = formatear_tiempo_entrega(duracion)
        valor = calcular_valor(distancia_metros)
        log_message("Termina de calcular distancia y tiempo", "INFO")
        return valor, tiempo_pedido, float(distancia_metros), direccion_envio
    except Exception as e:
        log_message(f"Error en la funcion calcular distancia y tiempo {e}", "ERROR")
        logging.error(f"Error en la función main_googlemaps: {e}")
        return None

def obtener_valores_sede(id_sede: str) -> tuple:
    try:
        log_message("Empieza obtener valores sede", "INFO")
        sede_info = execute_query("""
                SELECT latitud, longitud
                FROM sedes
                WHERE id_sede = %s;
            """, (id_sede,), fetchone=True)
        if not sede_info:
            log_message(f"No se encontró información de la sede con id {id_sede}", "ERROR")
            return None
        lat_sede, lon_sede = sede_info
        return lat_sede, lon_sede
    except Exception as e:
        log_message("Error en obtener valores sede", "ERROR")
        raise e

def calcular_distancia_entre_sede_y_cliente(sender: str, latitud_cliente: float, longitud_cliente: float, id_restaurante: str, nombre_cliente: str):
    try:
        sede_cercana = buscar_sede_mas_cercana_dentro_area(latitud_cliente, longitud_cliente, id_restaurante)
        if sede_cercana is None:
            log_message("No se encontró sede cercana. Retornando None.", "WARNING")
            borrar_intencion_futura(sender)
            return None

        if not set_sede_cliente(sede_cercana["id"], sender, id_restaurante) or not set_lat_lon(sender, latitud_cliente, longitud_cliente, id_restaurante) or not set_direccion_cliente(sender, sede_cercana["direccion_envio"], id_restaurante):
            return None

        return True
    except Exception as e:
        log_message(f"Ocurrió un error con el orquestador, revisar {e}", "ERROR")
        raise e


def orquestador_ubicacion_exacta(sender: str, latitud_cliente: float, longitud_cliente: float, id_restaurante: str, nombre_cliente: str):
    try:
        log_message(f"Se inicia el orquestador con datos de longitud {longitud_cliente} y latitud {latitud_cliente}", "INFO")
        codigo_pedido: str = obtener_intencion_futura_observaciones(sender)
        if not codigo_pedido:
            codigo_pedido = obtener_pedido_pendiente_reciente(sender)
            if not codigo_pedido:
                send_text_response("Lo siento, no tienes un pedido activo dentro de la última hora, te invitamos a pedir nuevamente. 😊 - Sierra Nevada")
        sede_cercana = buscar_sede_mas_cercana_dentro_area(latitud_cliente, longitud_cliente, id_restaurante)
        if sede_cercana is None:
            log_message("No se encontró sede cercana. Retornando None.", "WARNING")
            send_text_response(sender, "Gracias por tu ubicación.\nEn este momento no encontramos una sede que pueda atender tu dirección dentro de nuestra zona de cobertura.\nEsperamos estar próximamente en tu barrio. 😊 - Sierra Nevada")
            borrar_intencion_futura(sender)
            return None
        if not set_sede_cliente(sede_cercana["id"], sender, id_restaurante) or not set_lat_lon(sender, latitud_cliente, longitud_cliente, id_restaurante) or not set_direccion_cliente(sender, sede_cercana["direccion_envio"], id_restaurante):
            return None
        mensaje_direccion: dict = solicitar_confirmacion_direccion(nombre_cliente, sede_cercana)
        guardar_intencion_futura(sender, "confirmar_direccion", codigo_pedido)
        send_text_response(sender, mensaje_direccion.get("mensaje"))
    except Exception as e:
        log_message(f"Ocurrió un error con el orquestador, revisar {e}", "ERROR")
        raise e

def orquestador_tiempo_y_valor_envio(latitud_cliente: float, longitud_cliente: float, id_sede: str, numero_telefono: str, id_restaurante: str):
    try:
        log_message(f"Se inicia orquestador tiempo y valor envio con latitud {latitud_cliente} y longitud {longitud_cliente}", "INFO")
        sede_info = execute_query("""
            SELECT latitud, longitud
            FROM sedes
            WHERE id_sede = %s;
        """, (id_sede,), fetchone=True)
        if not sede_info:
            log_message(f"No se encontró información de la sede con id {id_sede}", "ERROR")
            return None
        lat_sede, lon_sede = sede_info
        resultado = calcular_distancia_y_tiempo(
            origen=(lat_sede, lon_sede),
            destino=(latitud_cliente, longitud_cliente),
            numero_telefono=numero_telefono,
            id_restaurante=id_restaurante,
            id_sede=id_sede
        )
        if not resultado:
            log_message(f"No se pudo calcular distancia/tiempo entre sede {id_sede} y cliente ({latitud_cliente},{longitud_cliente}). Devolviendo valores por defecto.", "WARN")
            # Devolver valores por defecto para evitar que los subflujos fallen al desestructurar
            return 0, "0 min", 0.0, ""
        return resultado
    except Exception as e:
        log_message(f"Ocurrió un error en orquestador tiempo y valor envio: {e}", "ERROR")
        raise e

def geocode_address(direccion: str) -> dict | None:
    """
    Geocodifica una dirección de texto usando Google Maps Geocoding API.
    Retorna {'lat': float, 'lon': float, 'formatted_address': str} o None si no hay resultado.
    """
    try:
        log_message(f"geocode_address: geocodificando dirección '{direccion}'", "INFO")
        if not direccion or not isinstance(direccion, str):
            log_message("geocode_address: dirección inválida", "WARN")
            return None
        gmaps = obtener_cliente_google_maps()
        resultados = gmaps.geocode(direccion, language="es")
        if not resultados:
            log_message(f"geocode_address: no se encontró resultado para '{direccion}'", "INFO")
            return None
        first = resultados[0]
        loc = first.get("geometry", {}).get("location", {})
        lat = loc.get("lat")
        lon = loc.get("lng")
        formatted = first.get("formatted_address", "") or direccion
        log_message(f"geocode_address: resultado para '{direccion}': lat={lat}, lon={lon}, formatted_address={formatted}", "INFO")
        if lat is None or lon is None:
            log_message(f"geocode_address: resultado incompleto para '{direccion}'", "WARN")
            return None
        return {"lat": float(lat), "lon": float(lon), "formatted_address": formatted}
    except ApiError as ae:
        log_message(f"geocode_address: Google Maps ApiError para '{direccion}': {ae}", "ERROR")
        return None
    except Exception as e:
        log_message(f"geocode_address: error al geocodificar '{direccion}': {e}", "ERROR")
        return None

def geocode_and_assign(numero_cliente: str, direccion: str, id_restaurante: str) -> dict | None:
    """
    Geocodifica la dirección y, si hay resultado, guarda lat/lon y dirección formateada
    en la tabla clientes_whatsapp (usa set_lat_lon y set_direccion_cliente).
    Retorna el mismo dict que geocode_address o None si falla.
    """
    try:
        res = geocode_address(direccion)
        if not res:
            return None
        lat = res["lat"]
        lon = res["lon"]
        formatted = res["formatted_address"]
        # Persistir coordenadas y dirección (los helpers devuelven True/False)
        try:
            set_lat_lon(numero_cliente, lat, lon, id_restaurante)
            set_direccion_cliente(numero_cliente, formatted, id_restaurante)
        except Exception as e:
            log_message(f"geocode_and_assign: fallo al guardar coords/dirección: {e}", "ERROR")
        return res
    except Exception as e:
        log_message(f"geocode_and_assign: excepción general: {e}", "ERROR")
        return None

