import os

MAX_FILE_SIZE = 5 * 1024 * 1024   # 5 МБ
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
UPLOAD_DIR = "/images"
LOG_FILE = "/logs/app.log"

DB_HOST = os.environ.get('DB_HOST', 'db')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'images_db')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'secretpass')