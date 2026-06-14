# utilities/file_utils.py
import uuid
import time
from PIL import Image
from io import BytesIO
from .constants import ALLOWED_EXTENSIONS


def is_allowed_file(filename):
    """Check if the file extension is allowed."""
    ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS


def generate_unique_filename(original_filename):
    """Generate a unique filename (timestamp_uuid.extension)."""
    ext = '.' + original_filename.lower().split('.')[-1] if '.' in original_filename else ''
    unique_id = str(uuid.uuid4())[:8]
    timestamp = int(time.time())
    return f"{timestamp}_{unique_id}{ext}"


def validate_image_content(file_data):
    """Verify that the file content is a valid image."""
    try:
        img = Image.open(BytesIO(file_data))
        img.verify()
        return True
    except Exception:
        return False