import os
import json
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from psycopg2.extras import RealDictCursor

from .constants import UPLOAD_DIR, MAX_FILE_SIZE
from .logging_config import logger
from .db import get_db_connection, save_metadata
from .file_utils import is_allowed_file, generate_unique_filename, validate_image_content
from .backup import create_backup


class ImageHandler(BaseHTTPRequestHandler):
    """Handles HTTP GET and POST requests for image hosting."""

    def log_message(self, format, *args):
        logger.info(f"Request: {format % args}")

    def _send_error(self, code, message):
        """Send a JSON error response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        error_body = json.dumps({"status": "error", "message": message}, ensure_ascii=False)
        self.wfile.write(error_body.encode('utf-8'))

    def send_html_response(self, html):
        """Send an HTML response."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def serve_image(self, filename):
        """Serve an image file from the upload directory."""
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

    def handle_images_list(self, query):
        """Handle GET /images-list with pagination."""
        try:
            page = int(query.get('page', ['1'])[0])
        except Exception:
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
            FROM images ORDER BY upload_time DESC LIMIT %s OFFSET %s
        """, (per_page, offset))
        images = cursor.fetchall()
        cursor.close()
        conn.close()

        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        html = self.render_images_list(images, page, total_pages, total)
        self.send_html_response(html)

    def render_images_list(self, images, page, total_pages, total):
        """Generate HTML table of images with pagination controls."""
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
            pagination += f'<a href="/images-list?page={page - 1}">← Previous</a> '
        else:
            pagination += '<span class="disabled">← Previous</span> '
        pagination += f'<span>Page {page} of {total_pages}</span> '
        if page < total_pages:
            pagination += f'<a href="/images-list?page={page + 1}">Next →</a>'
        else:
            pagination += '<span class="disabled">Next →</span>'

        html = f'''<!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>List of images</title>
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
        {f'<table><thead><tr><th>Name</th><th>Original name</th><th>Size (KB)</th><th>Date</th><th>Type</th><th>Action</th></tr></thead><tbody>{rows}</tbody></table>' if images else '<p>No images uploaded</p>'}
        <div class="pagination">{pagination}</div>
        <br><a href="/upload">Return to upload</a>
        <script>
            document.querySelectorAll('.delete-btn').forEach(btn => {{
                btn.addEventListener('click', async () => {{
                    const id = btn.dataset.id;
                    if(confirm('Delete this image?')) {{
                        const resp = await fetch(`/delete/${{id}}`, {{ method: 'POST' }});
                        if(resp.ok) window.location.reload();
                        else alert('Error!');
                    }}
                }});
            }});
        </script>
    </body>
    </html>'''
        return html

    def handle_delete(self, id_str):
        """Handle POST /delete/<id> – deletes image file and database record."""
        try:
            image_id = int(id_str)
        except ValueError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid image ID")
            return

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
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
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete file {file_path}: {e}")
        else:
            logger.warning(f"File {file_path} not found on disk, but DB record will be deleted")

        cursor.execute("DELETE FROM images WHERE id = %s", (image_id,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Deleted DB record for image id {image_id}")

        self.send_response(303)
        self.send_header('Location', '/images-list')
        self.end_headers()
        try:
            create_backup()
        except Exception as e:
            logger.error(f"Backup after delete failed: {e}")

    def do_GET(self):
        """Process GET requests."""
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
            self.serve_image(path[8:])
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        """Process POST requests: /upload and /delete/<id>."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path.startswith('/delete/'):
            self.handle_delete(path[8:])
            return

        if path != "/upload":
            self.send_response(404)
            self.end_headers()
            return

        # ----- Upload handling -----
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

        boundary = b'--' + match.group(1).encode('utf-8')
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            parts = body.split(boundary)
            file_data = None
            original_filename = None

            for part in parts:
                if b'filename="' in part:
                    fn_match = re.search(rb'filename="([^"]+)"', part)
                    if fn_match:
                        original_filename = fn_match.group(1).decode('utf-8')
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

            if not is_allowed_file(original_filename):
                logger.warning(f"Unsupported file format: {original_filename}")
                self._send_error(400, "Unsupported file format. Allowed: .jpg, .png, .gif")
                return

            if len(file_data) > MAX_FILE_SIZE:
                logger.warning(f"File too large: {original_filename} ({len(file_data)} bytes)")
                self._send_error(400, f"File size exceeds {MAX_FILE_SIZE // 1024 // 1024} MB")
                return

            if not validate_image_content(file_data):
                logger.warning(f"Invalid image content: {original_filename}")
                self._send_error(415, "File content is not a valid image (JPEG, PNG, GIF)")
                return

            unique_name = generate_unique_filename(original_filename)
            save_path = os.path.join(UPLOAD_DIR, unique_name)

            with open(save_path, 'wb') as f:
                f.write(file_data)
            logger.info(f"Success: image {unique_name} uploaded (original: {original_filename})")

            try:
                save_metadata(unique_name, original_filename, len(file_data), original_filename.split('.')[-1].lower())
            except Exception as db_err:
                os.remove(save_path)
                logger.error(f"DB error, file {unique_name} deleted: {db_err}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Database error, upload failed")
                return

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

            # Create a backup after successful upload
            try:
                create_backup()
            except Exception as e:
                logger.error(f"Backup after upload failed: {e}")

        except Exception as e:
            logger.error(f"Upload error: {str(e)}", exc_info=True)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal server error")