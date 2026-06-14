# utilities/backup.py
import os
import subprocess
from datetime import datetime
from .constants import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
from .logging_config import logger


def create_backup():
    """Create a database backup using pg_dump."""
    backup_dir = '/backups'
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'backup_{timestamp}.sql')

    env = os.environ.copy()
    env['PGPASSWORD'] = DB_PASSWORD

    cmd = [
        'pg_dump',
        '-h', DB_HOST,
        '-p', DB_PORT,
        '-U', DB_USER,
        '-d', DB_NAME,
        '-f', backup_file
    ]
    try:
        subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        logger.info(f"Backup created: {backup_file}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed: {e.stderr}")