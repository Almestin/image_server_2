#!/usr/bin/env python3
# shebang

import os
import uuid
import time
import json
import logging
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from PIL import Image
import psycopg2
from psycopg2.extras import RealDictCursor


MAX_FILE_SIZE = 5 * 1024 * 1024   # 5 МБ
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
UPLOAD_DIR = "/images"
LOG_FILE = "/logs/app.log"
DB_HOST = os.environ.get('DB_HOST', 'db')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'images_db')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'secretpass')

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

# new table
def init_db():
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

def is_allowed_file(filename):
    ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS

# new name - timestamp_uuid.ext
def generate_unique_filename(original_filename):
    ext = '.' + original_filename.lower().split('.')[-1] if '.' in original_filename else ''
    unique_id = str(uuid.uuid4())[:8]
    timestamp = int(time.time())
    return f"{timestamp}_{unique_id}{ext}"

def validate_image_content(file_data):

    try:

        from io import BytesIO
        img = Image.open(BytesIO(file_data))
        img.verify()
        return True
    except Exception:
        return False

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()   # to console
    ]
)
logger = logging.getLogger(__name__)

def save_metadata(filename, original_name, size, file_type):
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
        raise  # пробросим выше, чтобы удалить файл
    finally:
        cursor.close()
        conn.close()

class ImageHandler(BaseHTTPRequestHandler):
    def render_images_list(self, images, page, total_pages, total):
        rows = ''
        for img in images:
            size_kb = round(img['size'] / 1024, 1)

            filename_esc = img['filename'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            original_esc = img['original_name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            upload_time_str = img['upload_time'].strftime('%Y-%m-%d %H:%M:%S')
            rows += f'''
                    <tr>
                        <td><a href="/images/{filename_esc}">{filename_esc}</a></td>
                        <td>{original_esc}</td>
                        <td>{size_kb}</td>
                        <td>{upload_time_str}</td>
                        <td>{img['file_type']}</td>
                        <td><button class="delete-btn" data-id="{img['id']}">Delete</button></td>
                    </tr>
                '''

        pagination = ''
        if page > 1:
            pagination += f'<a href="/images-list?page={page - 1}">← Next</a> '
        else:
            pagination += '<span class="disabled">← Previous</span> '

        pagination += f'<span>Page {page} из {total_pages}</span> '

        if page < total_pages:
            pagination += f'<a href="/images-list?page={page + 1}">Next →</a>'
        else:
            pagination += '<span class="disabled">Next →</span>'

        html = f'''<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>List of images</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .delete-btn {{ background-color: #e74c3c; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 3px; }}
            .pagination {{ margin: 20px 0; }}
            .pagination a, .pagination span {{ display: inline-block; padding: 5px 10px; margin: 0 2px; border: 1px solid #ccc; text-decoration: none; color: #333; }}
            .disabled {{ color: #aaa; background: #eee; pointer-events: none; }}
        </style>
    </head>
    <body>
        <h1>Downloaded images</h1>
        {f'<p>Total: {total}</p>' if total > 0 else ''}
        {f'<table><thead><tr><th>Name</th><th>Original name</th><th>Size (КB)</th><th>Date</th><th>Type</th><th>Action</th></tr></thead><tbody>{rows}</tbody></table>' if images else '<p>No images uploaded</p>'}
        <div class="pagination">{pagination}</div>
        <br>
        <a href="/">Return to upload</a>
        <script>
            
            document.querySelectorAll('.delete-btn').forEach(btn => {{
                btn.addEventListener('click', async () => {{
                    const id = btn.dataset.id;
                    if(confirm('Delete this image?')) {{
                        const resp = await fetch(`/delete/${{id}}`, {{ method: 'POST' }});
                        if(resp.ok) window.location.reload();
                        else alert('Mistake!');
                    }}
                }});
            }});
        </script>
    </body>
    </html>'''
        return html

    def serve_image(self, filename):

        safe_filename = os.path.basename(filename)
        filepath = os.path.join(UPLOAD_DIR, safe_filename)
        if not os.path.exists(filepath):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Image not found")
            return

        ext = safe_filename.split('.')[-1].lower()
        mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/png' if ext == 'png' else 'image/gif'
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.end_headers()
        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())

    def log_message(self, format, *args):
        logger.info(f"Request: {format % args}")

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Welcome to Image Hosting. Use POST /upload or visit /images-list")
        elif path == "/images-list":
            self.handle_images_list(query)
        elif path.startswith("/images/"):
            # Извлекаем имя файла (обрезаем /images/)
            filename = path[8:]
            self.serve_image(filename)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def handle_images_list(self, query):
        # Получаем номер страницы, по умолчанию 1
        try:
            page = int(query.get('page', ['1'])[0])
        except:
            page = 1
        if page < 1:
            page = 1
        per_page = 10
        offset = (page - 1) * per_page

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT COUNT(*) as count FROM images")
        total = cursor.fetchone()['count']

        cursor.execute("""
            SELECT id, filename, original_name, size, upload_time, file_type
            FROM images
            ORDER BY upload_time DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        images = cursor.fetchall()
        cursor.close()
        conn.close()

        total_pages = (total + per_page - 1) // per_page if total > 0 else 1

        html = self.render_images_list(images, page, total_pages, total)
        self.send_html_response(html)

    def send_html_response(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def handle_delete(self, id_str):
        try:
            image_id = int(id_str)
        except ValueError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid image ID")
            return

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # get name
        cursor.execute("SELECT filename FROM images WHERE id = %s", (image_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Image not found in database")
            return

        filename = row['filename']
        file_path = os.path.join(UPLOAD_DIR, filename)

        # del file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete file {file_path}: {e}")
        else:
            logger.warning(f"File {file_path} not found on disk, but DB record will be deleted")

        # del record from db
        cursor.execute("DELETE FROM images WHERE id = %s", (image_id,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Deleted DB record for image id {image_id}")

        # return to list
        self.send_response(303)
        self.send_header('Location', '/images-list')
        self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path.startswith('/delete/'):
            self.handle_delete(path[8:])
            return

        if path != "/upload":
            self.send_response(404)
            self.end_headers()
            return

        content_type = self.headers.get('Content-Type')
        if not content_type or not content_type.startswith('multipart/form-data'):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Expected multipart/form-data")
            logger.warning("Bad request: missing multipart content type")
            return


        match = re.search(r'boundary=([^;]+)', content_type)
        if not match:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Boundary not found")
            logger.warning("Bad request: boundary not found in Content-Type")
            return

        boundary = match.group(1).encode('utf-8')
        # add prefix
        boundary = b'--' + boundary



        try:
            # read request
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            parts = body.split(boundary)
            file_data = None
            original_filename = None

            for part in parts:
                # find filename=
                if b'filename="' in part:
                # Извлекаем имя файла
                    fn_match = re.search(rb'filename="([^"]+)"', part)
                    if fn_match:
                        original_filename = fn_match.group(1).decode('utf-8')

                # find start of data
                data_start = part.find(b'\r\n\r\n')
                if data_start != -1:
                    file_data = part[data_start + 4:]

                    if file_data.endswith(b'\r\n'):
                        file_data = file_data[:-2]
                    break

            if not file_data or not original_filename:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing file field 'file'")
                logger.warning("Upload failed: missing file field")
                return

            # check ext
            if not is_allowed_file(original_filename):
                logger.warning(f"Unsupported file format: {original_filename}")
                self.send_response(400)
                self.end_headers()
                self._send_error(400, "Unsupported file format. Allowed: .jpg, .png, .gif")
                return

            # check size
            if len(file_data) > MAX_FILE_SIZE:
                logger.warning(f"File too large: {original_filename} ({len(file_data)} bytes)")
                self.send_response(400)
                self.end_headers()
                self._send_error(400, f"File size exceeds {MAX_FILE_SIZE // 1024 // 1024} MB")
                return

            if not validate_image_content(file_data):
                logger.warning(f"Invalid image content: {original_filename}")
                self._send_error(415, "File content is not a valid image (JPEG, PNG, GIF)")
                return

            # gen name
            unique_name = generate_unique_filename(original_filename)
            save_path = os.path.join(UPLOAD_DIR, unique_name)

            # write file
            with open(save_path, 'wb') as f:
                f.write(file_data)

            logger.info(f"Success: image {unique_name} uploaded (original: {original_filename})")

            try:
                save_metadata(unique_name, original_filename, len(file_data), original_filename.split('.')[-1].lower())
            except Exception as db_err:
                # if mistake – del file
                os.remove(save_path)
                logger.error(f"DB error, file {unique_name} deleted: {db_err}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Database error, upload failed")
                return

            #  JSON  responce
            image_url = f"http://localhost:8080/images/{unique_name}"

            response = {
                 "status": "success",
                 "message": "File uploaded successfully",
                 "filename": unique_name,
                 "url": image_url
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            logger.error(f"Upload error: {str(e)}", exc_info=True)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal server error")

def run_server():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    os.makedirs('/backups', exist_ok=True)  # для бекапов
    init_db()
    server_address = ('0.0.0.0', 8000)
    httpd = HTTPServer(server_address, ImageHandler)
    logger.info("Starting HTTP server on port 8000")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()