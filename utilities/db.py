# utilities/db.py
import time
import psycopg2
from .constants import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
from .logging_config import logger


def get_db_connection():
    """Return a connection to PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def wait_for_db(max_retries=30, delay=1):
    """Wait until the database is ready."""
    for i in range(max_retries):
        try:
            conn = get_db_connection()
            conn.close()
            logger.info("Database is ready")
            return True
        except Exception:
            logger.warning(f"Waiting for DB... ({i+1}/{max_retries})")
            time.sleep(delay)
    raise Exception("Database not ready after retries")


def init_db():
    """Create the images table if it does not exist."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                original_name TEXT NOT NULL,
                size INTEGER NOT NULL,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_type TEXT NOT NULL
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Database table 'images' initialized")
    except Exception as e:
        logger.error(f"DB init failed: {e}")


def save_metadata(filename, original_name, size, file_type):
    """Save image metadata to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO images (filename, original_name, size, file_type)
            VALUES (%s, %s, %s, %s)
        """, (filename, original_name, size, file_type))
        conn.commit()
        logger.info(f"Metadata saved for {filename}")
    except Exception as e:
        logger.error(f"Failed to save metadata for {filename}: {e}")
        raise
    finally:
        cursor.close()
        conn.close()