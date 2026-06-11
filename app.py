#!/usr/bin/env python3
# shebang

import os
import uuid
import time
import json
import logging
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from PIL import Image


MAX_FILE_SIZE = 5 * 1024 * 1024   # 5 МБ
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
UPLOAD_DIR = "/images"
LOG_FILE = "/logs/app.log"

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

class ImageHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        logger.info(f"Request: {format % args}")

    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Welcome to Image Hosting. Use POST /upload.")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def _send_error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        error_body = json.dumps({"status": "error", "message": message}, ensure_ascii=False)
        self.wfile.write(error_body.encode('utf-8'))


    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path != "/upload":
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
    server_address = ('0.0.0.0', 8000)
    httpd = HTTPServer(server_address, ImageHandler)
    logger.info("Starting HTTP server on port 8000")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()