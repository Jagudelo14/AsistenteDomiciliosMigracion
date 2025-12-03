import requests
import json
import uuid
import os
import traceback
from utils import log_message
from utils_database import execute_query

def generar_link_pago(amount: int, Address: str, City: str, docType: str, docValue: int, phone: str, email: str):
    try:
        userName = os.environ.get("userCrediBanco")
        password = os.environ.get("ClaveCredibanco")
        if not userName or not password:
            log_message("Credibanco: faltan credenciales en las variables de entorno", "ERROR")
            return None

        order_number = str(uuid.uuid4()).replace("-", "")[:12]
        url = "https://ecouat.credibanco.com/payment/rest/register.do"
        payload = {
            "userName": userName,
            "password": password,
            "orderNumber": order_number,
            "amount": amount,
            "returnUrl": "https://tu-sitio.com/pago-exitoso",
            "failUrl": "https://tu-sitio.com/pago-fallido",
            "currency": 170,
            "jsonParams": json.dumps({
                "installments": "1",
                "IVA.amount": "0",
                "postAddress": Address,
                "payerCity": "Bogotá D.C.",
                "payerCountry": "CO",
                "payerPostalCode": "110111",
                "payerState": "Bogotá D.C.",
                "docType": docType,
                "docValue": docValue,
                "phone": phone,
                "email": email,
                "shippingAddress": Address
            })
        }
        # Log payload salvo datos sensibles (no imprimir password)
        safe_payload = dict(payload)
        if "password" in safe_payload:
            safe_payload["password"] = "****"
        log_message(f"[GenerarLinkPago] Llamando endpoint Credibanco. url={url} payload={json.dumps(safe_payload)}", "INFO")

        response = requests.post(url, data=payload, timeout=15)
        log_message(f"[GenerarLinkPago] status_code={getattr(response, 'status_code', 'no-status')}", "INFO")
        try:
            data = response.json()
            log_message(f"[GenerarLinkPago] response_json={json.dumps(data)}", "INFO")
        except Exception:
            log_message(f"[GenerarLinkPago] No se pudo parsear JSON de la respuesta. text={response.text}", "ERROR")
            return None

        if str(data.get("errorCode", "")) not in ["0", ""]:
            log_message(f"[GenerarLinkPago] Credibanco devolvió error. errorCode={data.get('errorCode')} detalle={data}", "ERROR")
            return None

        form_url = data.get("formUrl")
        order_id = data.get("orderId")
        if not form_url or not order_id:
            log_message(f"[GenerarLinkPago] Respuesta incompleta de Credibanco. data={data}", "ERROR")
            return None

        log_message(f"[GenerarLinkPago] Link generado correctamente. order_id={order_id} form_url_len={len(form_url)}", "INFO")
        return form_url, order_id
    except requests.exceptions.RequestException as re:
        log_message(f"[GenerarLinkPago] RequestException: {re}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return None
    except Exception as e:
        log_message(f"[GenerarLinkPago] Excepción generando link: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return None

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
        query = """
            UPDATE public.pedidos
            SET id_pago = %s
            WHERE codigo_unico = %s;
        """
        params = (order_id, codigo_unico)
        execute_query(query, params)
        log_message(f"Pago guardado en la base de datos: {order_id}", "INFO")
        return True
    except Exception as e:
        log_message(f"Error guardando el pago en la base de datos:{e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False