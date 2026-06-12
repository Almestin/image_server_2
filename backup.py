#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime

BACKUP_DIR = '/backups'
DB_HOST = os.environ.get('DB_HOST', 'db')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'images_db')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'secretpass')


def create_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f'backup_{timestamp}.sql')

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
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        print(f"Backup created successfully: {backup_file}")
        return backup_file
    except subprocess.CalledProcessError as e:
        print(f"Backup failed with error: {e.stderr}")
        return None


if __name__ == '__main__':
    create_backup()