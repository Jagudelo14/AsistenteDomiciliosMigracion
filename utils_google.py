# utils_google.py
# Last modified: 2025-10-02 by Andrés Bermúdez

import logging
import googlemaps
import math
from utils import log_message
from utils_database import execute_query

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

def calcular_tiempo_pedido(tiempo_domicilio: str) -> int:
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
        tiempo_pedido: int = minutos_totales + TIEMPO_TOLERANCIA + pedidos * CANTIDAD_TIEMPO_PEDIDO
        if tiempo_pedido > UMBRAL_TIEMPO:
            log_message(f"Tiempo de pedido supera el umbral {tiempo_pedido} minutos.", "INFO")
            return -1
        log_message(F"El tiempo de pedido es de {tiempo_pedido} minutos.", "INFO")
        return tiempo_pedido
    except Exception as e:
        log_message(f"Ocurrió un error al calcular tiempo pedido {e}", "ERROR")
        return -1

def calcular_distancia(lat1, lon1, lat2, lon2):
    try:
        """Calcula la distancia entre dos puntos en coordenadas geográficas (en km)."""
        log_message(f"Calculando distancia entre ({lat1}, {lon1}) y ({lat2}, {lon2})", "INFO")
        R = 6371  # radio de la Tierra en km
        lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
        lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        log_message(f"Distancia calculada: {R * c} km", "INFO")
        return R * c
    except Exception as e:
        log_message(f"Error al calcular distancia {e}", "ERROR")
        raise e
polygon = [
    {"lat": 4.6536113, "lng": -74.1060089},
    {"lat": 4.6773013, "lng": -74.0885049},
    {"lat": 4.6676444, "lng": -74.0748025},
    {"lat": 4.664017849925693, "lng": -74.0801680847168}
]
# Falta implementar función de búsqueda sede más cercana
def buscar_sedes_cercanas(latitud_cliente, longitud_cliente, max_sedes=3):
    """
    Busca las sedes más cercanas al cliente usando la API de Google Maps Distance Matrix.
    Retorna una lista con las 'max_sedes' más cercanas en formato:
    [
        {"id": 1, "nombre": "Sede Centro", "ciudad": "Bogotá", "distancia_km": 2.3, "tiempo_min": 8},
        ...
    ]
    """
    try:
        log_message(f"Buscando las {max_sedes} sedes más cercanas para coordenadas ({latitud_cliente}, {longitud_cliente})", "INFO")

        # --- 1. Obtener todas las sedes ---
        sedes = execute_query("""
            SELECT idsede, nombre, ciudad, latitud, longitud
            FROM public.sedes
            WHERE latitud IS NOT NULL AND longitud IS NOT NULL;
        """)

        if not sedes:
            raise ValueError("No se encontraron sedes con coordenadas válidas.")

        # --- 2. Configurar cliente de Google Maps ---
        gmaps = obtener_cliente_google_maps()
        origen = (latitud_cliente, longitud_cliente)

        # --- 3. Preparar los destinos ---
        destinos = [(lat, lon) for (_, _, _, lat, lon) in sedes]

        # --- 4. Calcular distancias usando Google Maps Distance Matrix ---
        resultado = gmaps.distance_matrix(
            origins=[origen],
            destinations=destinos,
            mode="driving",
            language="es"
        )

        # --- 5. Construir lista de resultados con distancia y duración ---
        sedes_distancias = []
        for i, element in enumerate(resultado["rows"][0]["elements"]):
            if element["status"] == "OK":
                distancia_m = element["distance"]["value"]
                duracion_s = element["duration"]["value"]
                sedes_distancias.append({
                    "id": sedes[i][0],
                    "nombre": sedes[i][1],
                    "ciudad": sedes[i][2],
                    "distancia_km": round(distancia_m / 1000, 2),
                    "tiempo_min": round(duracion_s / 60, 1)
                })

        # --- 6. Ordenar por distancia ---
        sedes_ordenadas = sorted(sedes_distancias, key=lambda x: x["distancia_km"])

        # --- 7. Tomar las más cercanas ---
        sedes_cercanas = sedes_ordenadas[:max_sedes]

        log_message(f"Sedes más cercanas: {sedes_cercanas}", "INFO")
        return sedes_cercanas

    except Exception as e:
        logging.error(f"Error en buscar_sedes_cercanas: {e}")
        return None
    
def orquestador_ubicacion_exacta(latitud_cliente: float, longitud_cliente: float) -> tuple:
    try:
        """Orquestador principal cuando se envia un mensaje tipo ubicación exacta"""
        log_message(f"Se inicia el orquestador con datos de longitud {longitud_cliente} y latitud {latitud_cliente}", "INFO")
        cliente_gmaps = obtener_cliente_google_maps()
        sede_cercana = buscar_sedes_cercanas(latitud_cliente, longitud_cliente)
        return sede_cercana
    except Exception as e:
        log_message(f"Ocurrió un error con el orquestador, revisar {e}", "ERROR")
        raise e