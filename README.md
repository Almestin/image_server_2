# Image Hosting Service 2.0  
*Image server with PostgreSQL support, pagination, deletion, and automatic backup*

---

## 1. System Requirements

- **Operating System**: Windows 11 / Linux / macOS  
- **Docker Desktop** (version 20.10 or later) with WSL2 support (for Windows)  
- **Docker Compose** (included in Docker Desktop)  
- **Web browser**: Google Chrome (recommended) or any modern browser  
- **Free ports**:  
  - `8000` – backend (Python HTTP server)  
  - `8080` – Nginx (web interface and proxy)  
  - `5432` – PostgreSQL (optional, for external access)

---

## 2. Project Structure

```text
image_server_2/
├── app.py                          # Entry point (server startup)
├── requirements.txt                # Python dependencies (Pillow, psycopg2)
├── Dockerfile                      # Backend image build instructions
├── docker-compose.yml              # Service orchestration (db, app, nginx)
├── nginx.conf                      # Nginx configuration (proxy and static)
├── utilities/                      # Refactored module (all logic)
│   ├── __init__.py
│   ├── constants.py                # Constants (paths, limits, DB parameters)
│   ├── logging_config.py           # Logger setup
│   ├── db.py                       # PostgreSQL operations (connection, init, metadata)
│   ├── file_utils.py               # File checks, name generation, image validation
│   ├── backup.py                   # Backup creation (pg_dump)
│   └── image_handler.py            # HTTP handler (routes, pagination, deletion)
├── static/                         # Frontend
│   ├── index.html                  # Main page (random image)
│   ├── form/
│   │   └── upload.html             # Image upload page
│   └── image-uploader/             # CSS, JS, icons
├── images/                         # Bind mount – uploaded pictures storage
├── logs/                           # Bind mount – log files (app.log)
├── backups/                        # Bind mount – database dumps (*.sql)
└── README.md
```

---

## 3. Start and Stop Commands

### First start (build and run)

```bash
docker compose up --build
```

After successful start you will see logs from all three containers (`db`, `app`, `nginx`).

### Stop

Press `Ctrl+C` in the terminal where the project is running, or execute:

```bash
docker compose down 
```

### Run in background

```bash
docker compose up -d
```

Check status: `docker compose ps`

### Full cleanup (including volumes with database data and bind‑mount folders)

```bash
docker compose down -v
```

> **Warning**: Bind‑mount folders `images/`, `logs/`, `backups/` are not deleted, but the `db_data` volume (PostgreSQL data) will be removed.

### View logs

```bash
docker compose logs app      # backend logs
docker compose logs nginx    # webserver logs
docker compose logs db       # database logs
```

---

## 4. Routes and Functionality

### Access URLs (via Nginx on port 8080)

| URL | Description |
| --- | --- |
| `http://localhost:8080/` | Main page (static `index.html`) |
| `http://localhost:8080/upload` | Image upload page (GET) – form |
| `http://localhost:8080/images-list` | **Dynamic** page with list of all images (pagination, delete buttons) |
| `http://localhost:8000/` | Direct backend access (welcome message) |

### Backend API (accessible via Nginx or directly on port 8000)

#### `POST /upload`
Uploads an image.  
**Parameters**: `multipart/form-data`, field `file`.  
**Limits**:
- Max file size: 5 MB
- Allowed extensions: `.jpg`, `.jpeg`, `.png`, `.gif`
- Content must be a valid image (Pillow verification)

**Success response (200)**:
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "filename": "1706123456_abc12345.jpg",
  "url": "http://localhost:8080/images/1706123456_abc12345.jpg"
}
```

**Error codes**:
- `400` – unsupported format / file too large / missing file field
- `415` – extension allowed but content is not a valid image
- `500` – internal server error (e.g. database connection failure)

After successful upload:
- The file is saved to the `images/` folder (on the host).
- Metadata is written to the `images` table in PostgreSQL.
- A database backup is automatically created in the `backups/` folder.

#### `GET /images-list`
Returns an HTML page with a table of all images.  
**Query parameters**: `?page=N` (default 1).  
Pagination: 10 records per page.  
Table columns: file name (link), original name, size (KB), upload time, type, Delete button.

#### `POST /delete/<id>`
Deletes the image by its database ID.  
- Removes the physical file from the `images/` folder.
- Removes the record from PostgreSQL.
- Creates a new backup.
- Redirects back to `/images-list`.

#### `GET /images/<filename>`
Direct image serving by Nginx (no Python overhead).  
Example: `http://localhost:8080/images/1706123456_abc12345.jpg`

### Backup and Restore

- **Automatic**: A backup is created on server startup (if no `.sql` files exist), after each successful upload, and after each deletion. Files are saved in `backups/` with name `backup_YYYY-MM-DD_HHMMSS.sql`.

- **Manual backup**:
  ```bash
  docker compose exec app python -c "from utilities.backup import create_backup; create_backup()"
  ```

- **Restore from backup**:
  ```bash
  # Copy the backup file into the db container
  docker compose cp backups/your_backup.sql db:/tmp/restore.sql
  # Perform restore
  docker compose exec db psql -U postgres -d images_db -f /tmp/restore.sql
  ```

### Logging

- All actions (upload, deletion, backup creation, errors) are written to `logs/app.log` and also printed to the console.
- Log format:  
  `[2025-06-14 21:00:47] INFO: Metadata saved for 1706140847_c73895b8.jpg`

---

## 5. User Interface (Frontend)

- **Main page (`/`)** – random banner from five images; button leads to upload form.
- **Upload page (`/upload`)** – file selection via button or drag & drop; after success displays the image link and a COPY button.
- **Images list page (`/images-list`)** – table with pagination; each row has a "Delete" button that sends a POST request to the server and reloads the list.

---

## 6. Verification Checklist

1. Start the project: `docker compose up --build`
2. Open `http://localhost:8080/` – main page loads.
3. Click the button to go to `/upload` – upload several images (allowed formats, size < 5 MB).
4. After each upload, check that files appear in the `images/` folder on the host and records in the database:  
   `docker compose exec db psql -U postgres -d images_db -c "SELECT * FROM images;"`
5. Go to `/images-list` – the table should appear with pagination (if >10 images). Test navigation between pages.
6. Click "Delete" on any image – it should disappear from the table and the file from `images/`.
7. Ensure that after deletion a new `.sql` file appears in the `backups/` folder.
8. Test error handling: upload a text file renamed to `.jpg` – you should get the message "File content is not a valid image".

---

## 7. Troubleshooting

| Issue | Solution |
|-------|----------|
| Ports 8000, 8080 or 5432 already in use | Stop other services or change ports in `docker-compose.yml` |
| Upload fails with 502 Bad Gateway | Check that the `app` container is running: `docker compose ps app`. View logs: `docker compose logs app` |
| `/images-list` is empty even after upload | Make sure you uploaded files **after** adding PostgreSQL. Old images (from earlier versions) are not in the database. Upload a new image. |
| Backups are not created | Verify that `pg_dump` is installed in the `app` container: `docker compose exec app which pg_dump`. If missing, add `postgresql-client` to `Dockerfile` and rebuild. |
| Nginx fails to start with `proxy_pass` error | Check `nginx.conf` syntax. Do not place `proxy_pass` inside a `location` with an `if` block without proper wrapping. Use the provided `nginx.conf`. |
| Circular import error in Python | Ensure the `utilities/` structure exactly matches the description. Files `db.py`, `file_utils.py`, `backup.py` must not import from `app.py`. |

---

## 8. Environment Variables (for `app` container)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST`  | `db`    | PostgreSQL hostname (service name in Docker Compose) |
| `DB_PORT`  | `5432`  | PostgreSQL port |
| `DB_NAME`  | `images_db` | Database name |
| `DB_USER`  | `postgres` | Database user |
| `DB_PASSWORD` | `secretpass` | Password |

These are set in `docker-compose.yml`. If you change them, keep consistency with the `db` service.

---

## 9. Notes for Developers

- The code is split into logical modules inside the `utilities/` folder for easy maintenance.
- Database access uses `psycopg2` with `RealDictCursor`.
- Static files are served by Nginx; dynamic routes are proxied to the Python backend.
- Uploaded images, logs and backups are available on the host via bind mounts (`images/`, `logs/`, `backups/`). PostgreSQL data is stored in a named volume `db_data`.

---

**The project fully complies with the technical specification “Image Server 2.0”. All mandatory features (metadata in DB, pagination, deletion, backup) are implemented and tested.**