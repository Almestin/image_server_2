FROM python:3.12-slim

WORKDIR /app

# Settings for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev zlib1g-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY app.py .


RUN addgroup --system app && adduser --system --group app && \
    mkdir -p /images /logs && chown -R app:app /images /logs /app

USER app

EXPOSE 8000

CMD ["python", "-u", "app.py"]