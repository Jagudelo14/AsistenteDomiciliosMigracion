# utils_database.py
# Last modified: 2025-09-30 by Andrés Bermúdez

import os
import psycopg2
from psycopg2.extensions import connection, cursor
import logging

def connect_database() -> connection:
    try:
        """Establece una conexión a la base de datos PostgreSQL usando variables de entorno."""
        dbname: str = os.getenv("DB_NAME", "")
        user: str = os.getenv("DB_USER", "")
        password: str = os.getenv("DB_PASSWORD", "")
        host: str = os.getenv("DB_HOST", "")
        port: str = os.getenv("DB_PORT", "5432")
        if not all([dbname, user, password, host]):
            raise ValueError("Faltan variables de entorno para la conexión a la base de datos.")
        conn: connection = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        cur: cursor = conn.cursor()
        cur.execute("SELECT current_database(), inet_server_addr(), inet_server_port();")
        info = cur.fetchone()
        cur.close()
        return conn
    except Exception as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        raise

def execute_query(query: str, params: tuple = (), fetchone: bool = False):
    try:
        conn: connection = connect_database()
        cur: cursor = conn.cursor()
        cur.execute(query, params)
        results = None
        lowered = query.strip().lower()
        if lowered.startswith("select") or "returning" in lowered:
            results = cur.fetchone() if fetchone else cur.fetchall()
        conn.commit()
        cur.close()
        conn.close()
        return results
    except Exception as e:
        logging.error(f"Error al ejecutar la consulta: {e}")
        raise

def execute_query_columns(query: str, params: tuple = (), fetchone: bool = False, return_columns: bool = False):
    try:
        conn = connect_database()
        cur = conn.cursor()
        cur.execute(query, params)
        data = None
        cols = None
        if cur.description:  # La query tiene columnas
            cols = [desc[0] for desc in cur.description]
        if fetchone:
            data = cur.fetchone()
        else:
            data = cur.fetchall()
        conn.commit()
        cur.close()
        if return_columns:
            return data, cols
        return data
    except Exception as e:
        logging.error(f"Error en execute_query: {e}")
        raise e