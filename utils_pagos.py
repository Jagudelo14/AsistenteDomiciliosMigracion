import requests
import json
import uuid
import os
from utils import log_message
from utils_database import execute_query

def generar_link_pago():
    userName = os.environ.get("userCrediBanco")
    password = os.environ.get("ClaveCredibanco")

    order_number = str(uuid.uuid4()).replace("-", "")[:12] #se puede hcaer la generación del número de orden como se desee

    # Endpoint UAT Credibanco
    url = "https://ecouat.credibanco.com/payment/rest/register.do"

    payload = {
        "userName": userName,
        "password": password,
        "orderNumber": order_number,
        "amount": 10000,  # en centavos (100.00 COP)
        "returnUrl": "https://tu-sitio.com/pago-exitoso", #urls a donde retorna
        "failUrl": "https://tu-sitio.com/pago-fallido",
        "currency": 170,  # 170 = COP
        "jsonParams": json.dumps({
            "installments": "1",
            "IVA.amount": "0"
        })
    }

    response = requests.post(url, data=payload)
    data = response.json()

    if data.get("errorCode") != 0:
        print("❌ Error al generar el link de pago:")
        print(data)
        return None

    form_url = data.get("formUrl")
    order_id = data.get("orderId")

    return form_url, order_id

def validar_pago(order_id: str):
    url = "https://ecouat.credibanco.com/payment/rest/getOrderStatusExtended.do"

    payload = {
        "userName": "DACASIGNAVNP33-api",
        "password": "SierraNevada2025*",
        "orderId": order_id,
        "language": "es"
    }

    response = requests.post(url, data=payload)
    data = response.json()

    # Si Credibanco devuelve error
    if str(data.get("errorCode")) not in ["0", ""]:
        print("❌ Error consultando el pago")
        print(data)
        return {"status": "error", "detalle": data}

    order_status = data.get("orderStatus")
    action_code = data.get("actionCode")
    descripcion = data.get("actionCodeDescription")

    if order_status == 2:
        resultado = "aprobado"
    elif order_status in [3, 6]:
        resultado = "rechazado"
    elif order_status in [0, 1, 5, 7]:
        resultado = "pendiente"
    else:
        resultado = "desconocido"

    info = {
        "orderId": order_id,
        "resultado": resultado,
        "orderStatus": order_status,
        "actionCode": action_code,
        "descripcion": descripcion
    }

    print("📬 Resultado de la validación:", info)
    return info

def guardar_id_pago_en_db(order_id: str, codigo_unico: str) -> bool:
    try:
        query="""
            UPDATE public.pedidos
            SET id_pago = '%s'
            WHERE codigo_unico = '%s';
        """
        params=(order_id, codigo_unico)
        execute_query(query % params)
        log_message(f"Pago guardado en la base de datos: {order_id})", "INFO")
        return True
    except Exception as e:
        log_message(f"Error guardando el pago en la base de datos:{e}", "ERROR")
        return False