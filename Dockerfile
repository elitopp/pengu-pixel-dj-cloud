FROM python:3.12-slim

# Instalar FFmpeg, Node.js y dependencias de audio del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    libffi-dev \
    libnacl-dev \
    libopus0 \
    libopus-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip "yt-dlp[default]" yt-dlp-ejs && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "bot.py"]
