# utils_database.py
# Last modified: 2025-09-26 by Andrés Bermúdez

import os
import psycopg2
from psycopg2.extensions import connection, cursor
import logging

def connect_database() -> connection:
    try:
        """Establece una conexión a la base de datos PostgreSQL usando variables de entorno."""
        logging.info('Conectando a la base de datos PostgreSQL')
        dbname: str = os.getenv("DB_NAME", "")
        user: str = os.getenv("DB_USER", "")
        password: str = os.getenv("DB_PASSWORD", "")
        host: str = os.getenv("DB_HOST", "")
        port: str = os.getenv("DB_PORT", "5432")
        if not all([dbname, user, password, host]):
            raise ValueError("Faltan variables de entorno para la conexión a la base de datos.")
        logging.info(f"Conectando a base de datos: {user}@{host}:{port}/{dbname}")
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
        logging.info(f"Conectado a base: {info[0]} en {info[1]}:{info[2]}")
        cur.close()
        return conn
    except Exception as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        raise

def execute_query(query: str, params: tuple = ()) -> list:
    try:
        results: list = []
        """Ejecuta una consulta SQL y devuelve los resultados."""
        conn: connection = connect_database()
        cur: cursor = conn.cursor()
        logging.info(f"Ejecutando consulta: {query} con parámetros {params}")
        cur.execute(query, params)
        if query.strip().lower().startswith("select"):
            results = cur.fetchall()
        conn.commit()
        cur.close()
        conn.close()
        logging.info("Consulta ejecutada correctamente.")
        return results
    except Exception as e:
        logging.error(f"Error al ejecutar la consulta: {e}")
        raise