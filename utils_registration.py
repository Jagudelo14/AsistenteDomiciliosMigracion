import logging
from utils_database import execute_query
from utils import log_message

def update_tratamiento_datos(sender: str, id_restaurante: str, valor: bool) -> None:
    try:
        query = """
            UPDATE public.clientes_whatsapp
            SET tratamiento_datos = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (valor, sender, id_restaurante)
        execute_query(query, params)
    except Exception as e:
        log_message(f"update_tratamiento_datos error: {e}", "ERROR")
        logging.error(f"update_tratamiento_datos error: {e}")
        raise

def update_dir_primera_vez(sender: str, id_restaurante: str, valor: bool) -> None:
    try:
        query = """
            UPDATE public.clientes_whatsapp
            SET dir_primera_vez = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (valor, sender, id_restaurante)
        execute_query(query, params)
    except Exception as e:
        log_message(f"update_dir_primera_vez error: {e}", "ERROR")
        logging.error(f"update_dir_primera_vez error: {e}")
        raise

def update_datos_personales(sender: str, id_restaurante: str, valor: bool) -> None:
    try:
        query = """
            UPDATE public.clientes_whatsapp
            SET datos_personales = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (valor, sender, id_restaurante)
        execute_query(query, params)
    except Exception as e:
        log_message(f"update_datos_personales error: {e}", "ERROR")
        logging.error(f"update_datos_personales error: {e}")
        raise

def save_personal_data(sender: str, id_restaurante: str, tipo_doc: str, n_doc: str, email: str) -> None:
    try:
        query = """
            UPDATE public.clientes_whatsapp
            SET "Tipo_Doc" = %s, "N_Doc" = %s, email = %s
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (tipo_doc or None, n_doc or None, email or None, sender, id_restaurante)
        execute_query(query, params)
    except Exception as e:
        log_message(f"save_personal_data error: {e}", "ERROR")
        logging.error(f"save_personal_data error: {e}")
        raise

def save_personal_data_partial(sender: str, id_restaurante: str, tipo_doc: str, n_doc: str, email: str, nombre: str) -> None:
    """
    Actualiza solo los campos que traigan valor útil (no None y != "No proporcionado").
    """
    try:
        sets = []
        params = []
        if tipo_doc and tipo_doc != "No proporcionado":
            sets.append('"Tipo_Doc" = %s')
            params.append(tipo_doc.strip())
        if n_doc and n_doc != "No proporcionado":
            sets.append('"N_Doc" = %s')
            params.append(n_doc.strip())
        if email and email != "No proporcionado":
            sets.append('email = %s')
            params.append(email.strip())
        if nombre and nombre != "No proporcionado":
            sets.append('nombre = %s')
            params.append(nombre.strip())

        if not sets:
            # nada que actualizar
            return

        query = f"""
            UPDATE public.clientes_whatsapp
            SET {', '.join(sets)}
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params.extend([sender, id_restaurante])
        execute_query(query, tuple(params))
    except Exception as e:
        log_message(f"save_personal_data_partial error: {e}", "ERROR")
        logging.error(f"save_personal_data_partial error: {e}")
        raise

def check_and_mark_datos_personales(sender: str, id_restaurante: str) -> list:
    """
    Consulta los 4 campos (Tipo_Doc, N_Doc, email).
    - Si todos están presentes y no vacíos marca datos_personales = True.
    - Devuelve lista de columnas faltantes (ej: ["Tipo_Doc","email"]) — vacía si ya está completo.
    """
    try:
        query = """
            SELECT "Tipo_Doc", "N_Doc", email , nombre
            FROM public.clientes_whatsapp
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (sender, id_restaurante)
        result = execute_query(query, params)
        row = result[0] if result and result[0] else (None, None, None)
        missing = []
        if not row[0] or str(row[0]).strip() == "":
            missing.append("Tipo_Doc")
        if not row[1] or str(row[1]).strip() == "":
            missing.append("N_Doc")
        if not row[2] or str(row[2]).strip() == "":
            missing.append("email")
        if not row[3] or str(row[3]).strip() == "" or row[3]=="Desconocido":
            missing.append("nombre")

        if not missing:
            # marcar como completos
            update_query = """
                UPDATE public.clientes_whatsapp
                SET datos_personales = TRUE
                WHERE telefono = %s AND id_restaurante = %s;
            """
            execute_query(update_query, (sender, id_restaurante))
        return missing
    except Exception as e:
        log_message(f"check_and_mark_datos_personales error: {e}", "ERROR")
        logging.error(f"check_and_mark_datos_personales error: {e}")
        # En caso de error asumimos que faltan datos para evitar marcar completo por error
        return ["Tipo_Doc", "N_Doc", "email"]

def validate_personal_data(sender: str, id_restaurante: str) -> bool:
    try:
        query = """
            SELECT datos_personales
            FROM public.clientes_whatsapp
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (sender, id_restaurante)
        result = execute_query(query, params)
        if result and result[0]:
            datos_personales = result[0][0]
            return bool(datos_personales)
        return False
    except Exception as e:
        log_message(f"validate_personal_data error: {e}", "ERROR")
        logging.error(f"validate_personal_data error: {e}")
        return False

def validate_direction_first_time(sender: str, id_restaurante: str) -> bool:
    try:
        query = """
            SELECT dir_primera_vez
            FROM public.clientes_whatsapp
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (sender, id_restaurante)
        result = execute_query(query, params)
        if result and result[0]:
            dir_primera_vez = result[0][0]
            return bool(dir_primera_vez)
        return False
    except Exception as e:
        log_message(f"validate_direction_first_time error: {e}", "ERROR")
        logging.error(f"validate_direction_first_time error: {e}")
        return False

def validate_data_treatment(sender: str, id_restaurante: str) -> bool:
    try:
        query = """
            SELECT tratamiento_datos
            FROM public.clientes_whatsapp
            WHERE telefono = %s AND id_restaurante = %s;
        """
        params = (sender, id_restaurante)
        result = execute_query(query, params)
        if result and result[0]:
            tratamiento_datos = result[0][0]
            return bool(tratamiento_datos)
        return False
    except Exception as e:
        log_message(f"validate_data_treatment error: {e}", "ERROR")
        logging.error(f"validate_data_treatment error: {e}")
        return False