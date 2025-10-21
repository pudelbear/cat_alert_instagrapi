# Basis-Image mit gutem Torch-Support
FROM python:3.11-slim

# Systempakete für OpenCV + Torch
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libopencv-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Arbeitsverzeichnis kopieren
COPY . .

# Standardbefehl
CMD ["python", "cat_alert_instagrapi.py"]
