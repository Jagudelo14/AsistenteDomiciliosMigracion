# utils_google.py
# Last modified: 2025-10-02 by Andrés Bermúdez

import logging
import googlemaps
import math
from utils import log_message, point_in_polygon
from utils_database import execute_query
import json

CANTIDAD_TIEMPO_PEDIDO: int = 5 # Cantidad de tiempo por pedido en cola en minutos
TIEMPO_TOLERANCIA: int = 10 # Cantidad de minutos de tolerancia para tiempo total de domicilio
UMBRAL_TIEMPO: int = 150 # Cantidad de minutos de umbral máximo para un domicilio (2 horas y 30 minutos)
API_KEY_GOOGLE_MAPS: str = 'AIzaSyC_6rzG31npWbVIIOGprcB-jEQtHnHJKSc'

def obtener_cliente_google_maps() -> googlemaps:
    try:
        """Crea el cliente de google maps"""
        gmaps: googlemaps = googlemaps.Client(key=API_KEY_GOOGLE_MAPS)
        log_message(f"Crea cliente gmaps sin problema", "INFO")
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
        log_message("Iniciando primera regla de tiempo.", "INFO")
        query = """
            SELECT COUNT(*) 
            FROM pedidos
            WHERE estado = 'En preparación'
              AND producto ILIKE '%hamburguesa%'
              AND id_sede = %s;
        """
        resultado = execute_query(query, (id_sede,), fetchone=True)
        hamburguesas_en_preparacion = resultado[0] if resultado and resultado[0] is not None else 0
        log_message(f"Hamburguesas en preparación: {hamburguesas_en_preparacion}", "INFO")
        incremento = (hamburguesas_en_preparacion // 10) * 8
        tiempo_estimado = int(tiempo_base + incremento)
        log_message(f"Tiempo base: {tiempo_base} | Incremento: {incremento} | Total estimado: {tiempo_estimado}", "INFO")
        return tiempo_estimado
    except Exception as e:
        log_message(f"Error en primera_regla_tiempo: {str(e)}", "ERROR")
        return tiempo_base

def calcular_tiempo_pedido(tiempo_domicilio: str, id_sede: str) -> int:
    try:
        """Se calcula el tiempo dependiendo la cantidad de pedidos con base al tiempo distancia entre cliente y sede"""
        log_message(f"Se inicia tiempo de pedido con tiempo de envio de {tiempo_domicilio}", "INFO")
        pedidos: int = 3 # ---> implementar función de traer cantidad de pedidos en cola por sede
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
        minutos_totales += primera_regla_tiempo(id_sede, minutos_totales) # Ajuste por demanda
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
        ids = [s[0] for s in sedes]
        areas_map = {}
        if ids:
            placeholders = ",".join(["%s"] * len(ids))
            query_areas = f"""
                SELECT id_sede, valor
                FROM sedes_areas
                WHERE id_sede IN ({placeholders});
            """
            areas_rows = execute_query(query_areas, tuple(ids))
            if areas_rows:
                for id_sede_row, valor in areas_rows:
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
        candidatos = []
        for s in sedes:
            sede_id, nombre, ciudad, lat_sede, lon_sede = s
            polygons = areas_map.get(sede_id)
            logging.info(f"Polys {polygons}")
            if not polygons:
                continue
            encontrada = None
            for poly in polygons:
                logging.info(f"Poly for in {poly}")
                try:
                    if point_in_polygon(latitud_cliente, longitud_cliente, poly):
                        encontrada = poly
                        break
                except Exception as e:
                    logging.info(f"Error e {e}")
                    continue
            if encontrada is not None:
                candidatos.append((s, lat_sede, lon_sede, encontrada))
        if not candidatos:
            return None
        gmaps = obtener_cliente_google_maps()
        origen = (latitud_cliente, longitud_cliente)
        destinos = [(lat, lon) for (_, lat, lon, _) in candidatos]
        logging.info(f"destinos {destinos}")
        destinos = [(item[1], item[2]) for item in candidatos]
        resultado = gmaps.distance_matrix(
            origins=[origen],
            destinations=destinos,
            mode="driving",
            language="es"
        )
        opciones_validas = []
        elements = resultado.get("rows", [])[0].get("elements", []) if resultado.get("rows") else []
        for i, elem in enumerate(elements):
            if elem.get("status") != "OK":
                continue
            distancia_m = elem["distance"]["value"]
            duracion_s = elem["duration"]["value"]
            sede_tuple = candidatos[i][0]
            area_usada = candidatos[i][3]
            opciones_validas.append({
                "id": sede_tuple[0],
                "nombre": sede_tuple[1],
                "ciudad": sede_tuple[2],
                "distancia_km": round(distancia_m / 1000, 2),
                "tiempo_min": round(duracion_s / 60, 1),
                "area": area_usada
            })
        if not opciones_validas:
            return None
        opciones_validas.sort(key=lambda x: x["distancia_km"])
        return opciones_validas[0]
    except Exception as e:
        logging.error(f"Error en buscar_sede_mas_cercana_dentro_area: {e}")
        return None

def set_sede_cliente(id_sede: str, numero_cliente, id_restaurante: str) -> None:
    try:
        """Asigna la sede seleccionada al cliente en la base de datos."""
        log_message(f"Asignando sede {id_sede} al cliente {id_restaurante}", "INFO")
        execute_query("""
            UPDATE clientes_whatsapp
            SET id_sede = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """, (id_sede, numero_cliente, id_restaurante))
        log_message(f"Sede asignada correctamente.", "INFO")
    except Exception as e:
        log_message(f"Error al asignar sede al cliente: {e}", "ERROR")
        raise e

def set_direccion_cliente(numero_cliente: str, direccion: str, id_restaurante: str) -> bool:
    try:
        """Actualiza la dirección del cliente en la base de datos."""
        log_message(f"Actualizando dirección para el cliente {numero_cliente}", "INFO")
        execute_query("""
            UPDATE clientes_whatsapp
            SET direccion_google = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """, (direccion, numero_cliente, id_restaurante))
        log_message(f"Dirección actualizada correctamente.", "INFO")
        return True
    except Exception as e:
        log_message(f"Error al actualizar dirección del cliente: {e}", "ERROR")
        raise e

def calcular_distancia_y_tiempo(origen: tuple, destino: tuple, numero_telefono: str, id_restaurante: str, id_sede: str):
    try:
        """"""
        log_message(f"Calculando distancia entre {origen} y {destino}", "INFO")
        gmaps = obtener_cliente_google_maps()
        resultado = gmaps.distance_matrix(origins=[origen],
                                   destinations=[destino],
                                   mode='driving',
                                   language='es')
        duracion = resultado['rows'][0]['elements'][0]['duration']['text']
        direccion_envio = resultado['destination_addresses'][0]
        if not set_direccion_cliente(numero_telefono, direccion_envio, id_restaurante):
            log_message(f"No se pudo actualizar la dirección del cliente {numero_telefono}", "ERROR")
        distancia = resultado['rows'][0]['elements'][0]['distance']['text']
        distancia_metros = resultado['rows'][0]['elements'][0]['distance']['value']
        duracion = calcular_tiempo_pedido(duracion, id_sede)
        valor = CalcularValor(distancia_metros)
        log_message(f"Envío a: {direccion_envio}")
        log_message(f"Tiempo estimado: {duracion}")
        log_message(f"Distancia: {distancia}")
        log_message(f"Valor del envío: ${valor:.0f}")
        logging.info("Terminando conexión con Google Maps")
        return valor, duracion, distancia, direccion_envio
    except Exception as e:
        logging.error(f"Error en la función main_googlemaps: {e}")
        return None

def orquestador_ubicacion_exacta(numero_telefono: str, latitud_cliente: float, longitud_cliente: float, id_restaurante: str) -> tuple:
    try:
        """Orquestador principal cuando se envia un mensaje tipo ubicación exacta"""
        log_message(f"Se inicia el orquestador con datos de longitud {longitud_cliente} y latitud {latitud_cliente}", "INFO")
        sede_cercana = buscar_sede_mas_cercana_dentro_area(latitud_cliente, longitud_cliente, id_restaurante)
        set_sede_cliente(sede_cercana["id"], numero_telefono, id_restaurante)
        calcular_distancia_y_tiempo(sede_cercana["ubicacion"], (latitud_cliente, longitud_cliente), numero_telefono, id_restaurante, sede_cercana["id"])
        return sede_cercana
    except Exception as e:
        log_message(f"Ocurrió un error con el orquestador, revisar {e}", "ERROR")
        raise e