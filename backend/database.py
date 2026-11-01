import os
import logging
from pathlib import Path
from contextlib import contextmanager
import mysql.connector
from mysql.connector import pooling, Error
from config import Config

logger = logging.getLogger("EduTrack.database")

_pool = None

def get_connection_config():
    """Build connection configuration dict supporting local and Aiven MySQL."""
    cfg = {
        "host": Config.MYSQL_HOST,
        "port": Config.MYSQL_PORT,
        "user": Config.MYSQL_USER,
        "password": Config.MYSQL_PASSWORD,
        "database": Config.MYSQL_DATABASE,
        "charset": "utf8mb4",
        "use_unicode": True,
        "autocommit": False,
        "connection_timeout": 10
    }

    # Handle SSL for Aiven or hosted MySQL
    if Config.MYSQL_SSL_CA and os.path.exists(Config.MYSQL_SSL_CA):
        cfg["ssl_ca"] = Config.MYSQL_SSL_CA
        cfg["ssl_verify_cert"] = True
    elif Config.DB_SSL or (Config.MYSQL_HOST and "aivencloud.com" in Config.MYSQL_HOST):
        # Aiven cloud requires SSL
        cfg["ssl_disabled"] = False

    return cfg

def init_pool():
    """Initialize MySQL connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    cfg = get_connection_config()
    try:
        _pool = pooling.MySQLConnectionPool(
            pool_name=Config.DB_POOL_NAME,
            pool_size=Config.DB_POOL_SIZE,
            pool_reset_session=True,
            **cfg
        )
        logger.info(f"Initialized MySQL connection pool to {cfg['host']}:{cfg['port']}/{cfg['database']}")
    except Error as err:
        logger.warning(f"Connection pool initialization warning: {err}. Falling back to direct connections.")
        _pool = None
    return _pool

@contextmanager
def get_db_connection():
    """Context manager for acquiring and safely releasing a MySQL connection."""
    global _pool
    conn = None
    try:
        if _pool is not None:
            try:
                conn = _pool.get_connection()
            except Error:
                # If pool exhausted or failed, create direct connection
                conn = mysql.connector.connect(**get_connection_config())
        else:
            conn = mysql.connector.connect(**get_connection_config())
        yield conn
    finally:
        if conn is not None and conn.is_connected():
            conn.close()

def execute_query(sql, params=None, fetch="all", commit=False, dictionary=True):
    """
    Safely execute a parameterized query.
    fetch options:
      - 'all': returns list of dicts/tuples
      - 'one': returns single dict/tuple or None
      - 'val': returns first scalar column of first row or None
      - None: returns lastrowid or rowcount
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=dictionary)
        try:
            cursor.execute(sql, params or ())
            
            if commit:
                conn.commit()
                res = {
                    "lastrowid": cursor.lastrowid,
                    "rowcount": cursor.rowcount
                }
                cursor.close()
                return res

            if fetch == "all":
                result = cursor.fetchall()
            elif fetch == "one":
                result = cursor.fetchone()
            elif fetch == "val":
                row = cursor.fetchone()
                if row:
                    if dictionary:
                        result = next(iter(row.values()))
                    else:
                        result = row[0]
                else:
                    result = None
            else:
                result = None

            cursor.close()
            return result
        except Error as err:
            if commit:
                conn.rollback()
            cursor.close()
            logger.error(f"Database error executing query: {err} | SQL: {sql}")
            raise err

def execute_transaction(queries_with_params):
    """
    Execute multiple queries within an atomic transaction.
    queries_with_params: list of tuples (sql, params)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            for sql, params in queries_with_params:
                cursor.execute(sql, params or ())
            conn.commit()
            cursor.close()
            return True
        except Error as err:
            conn.rollback()
            cursor.close()
            logger.error(f"Transaction failed, rolled back: {err}")
            raise err

def init_database_schema():
    """
    Initialize database schema if required without dropping existing tables.
    Reads database.sql and runs statements safely.
    """
    sql_path = Path(__file__).resolve().parent.parent / "database.sql"
    if not sql_path.exists():
        logger.warning(f"Schema file {sql_path} not found.")
        return False

    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split statements
    statements = [s.strip() for s in content.split(";") if s.strip()]
    
    cfg = get_connection_config()
    db_name = cfg.pop("database", "EduTrack_db")

    try:
        # First ensure database exists
        server_conn = mysql.connector.connect(**cfg)
        server_cursor = server_conn.cursor()
        server_cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        server_cursor.close()
        server_conn.close()

        # Now run statements on target database
        cfg["database"] = db_name
        db_conn = mysql.connector.connect(**cfg)
        db_cursor = db_conn.cursor()
        for stmt in statements:
            try:
                db_cursor.execute(stmt)
            except Error as stmt_err:
                logger.debug(f"Statement notice/error: {stmt_err}")
        db_conn.commit()
        db_cursor.close()
        db_conn.close()
        logger.info(f"Database schema verified/initialized successfully on {db_name}.")
        return True
    except Error as err:
        logger.error(f"Failed to initialize database schema: {err}")
        return False
