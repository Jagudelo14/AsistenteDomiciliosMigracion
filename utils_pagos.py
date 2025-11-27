import requests
import json
import uuid

def generar_link_pago():
    userName = "DACASIGNAVNP33-api"
    password = "SierraNevada2025*"

    order_number = str(uuid.uuid4()).replace("-", "")[:12]

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

    # Si hubo error
    if data.get("errorCode") != 0:
        print("❌ Error al generar el link de pago:")
        print(data)
        return None

    # Link para redirigir al usuario
    form_url = data.get("formUrl")
    order_id = data.get("orderId")

    print("✔️ Link generado correctamente:")
    print("OrderId:", order_id)
    print("Link de pago:", form_url)

    return form_url
#generar_link_pago()

def validar_pago(order_id):
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

validar_pago("2a5a8511-4032-7cbd-bb45-0ce200c265f7")