#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from http.server import HTTPServer

from utilities.constants import UPLOAD_DIR, LOG_FILE
from utilities.logging_config import logger
from utilities.db import wait_for_db, init_db
from utilities.backup import create_backup
from utilities.image_handler import ImageHandler


def run_server():
    """Start the HTTP server."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    os.makedirs('/backups', exist_ok=True)

    wait_for_db()
    init_db()

    # Create initial backup if none exists
    existing_backups = [f for f in os.listdir('/backups') if f.endswith('.sql')]
    if not existing_backups:
        logger.info("No backups found, creating initial backup...")
        create_backup()
    else:
        logger.info(f"Found {len(existing_backups)} existing backup(s), skipping initial backup")

    server_address = ('0.0.0.0', 8000)
    httpd = HTTPServer(server_address, ImageHandler)
    logger.info("Starting HTTP server on port 8000")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()