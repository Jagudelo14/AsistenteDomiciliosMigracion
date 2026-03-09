# utils_database.py
# Last modified: 2025-21-12 Juan Agudelo

import os
from psycopg2.extensions import connection, cursor
from psycopg2.pool import ThreadedConnectionPool
import logging
import time
_pool = None

def connect_database() -> connection:
    global _pool
    try:
        dbname = os.getenv("DB_NAME", "")
        user = os.getenv("DB_USER", "")
        password = os.getenv("DB_PASSWORD", "")
        host = os.getenv("DB_HOST", "")
        port = os.getenv("DB_PORT", "5432")

        minconn = 1
        maxconn = 20

        if not all([dbname, user, password, host]):
            raise ValueError("Faltan variables de entorno para la conexión a la base de datos.")

        if _pool is None:

            _pool = ThreadedConnectionPool(
                minconn,
                maxconn,
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                sslmode='require',
                application_name="whatsapp_bot"
            )

        conn = _pool.getconn()

        if conn is None:
            raise Exception("No se pudo obtener conexión del pool.")



        return conn

    except Exception as e:
        logging.error(f"Error al conectar a la base de datos (pool): {e}")
        raise

def execute_query(query: str, params: tuple = (), fetchone: bool = False):
    attempts = 3
    global _pool

    if params is None:
        params = ()

    for attempt in range(1, attempts + 1):
        conn = None
        try:
            conn = connect_database()



            with conn.cursor() as cur:

                cur.execute(query, params)

                lowered = query.strip().lower()

                if lowered.startswith("select") or "returning" in lowered or lowered.startswith("with"):
                    result = cur.fetchone() if fetchone else cur.fetchall()
                else:
                    result = None

                conn.commit()

                return result

        except Exception as e:


            if conn:
                conn.rollback()

            if attempt == attempts:
                raise

            sleep_time = 2 ** attempt
            time.sleep(sleep_time)

        finally:

            if conn:
                try:
                    if _pool:
                        _pool.putconn(conn)
                    else:
                        conn.close()

                except Exception as e:
                    print(f"⚠️ Error cerrando conexión: {e}")

def execute_query_columns(query: str, params: tuple = (), fetchone: bool = False, return_columns: bool = False):
    global _pool
    conn = None
    cur = None
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
    finally:
        try:
            if cur and not cur.closed:
                cur.close()
        except Exception:
            pass
        try:
            if conn and not conn.closed:
                if _pool is not None:
                    _pool.putconn(conn)
                else:
                    conn.close()
        except Exception:
            pass