# MarkItDown Web — container image with OCR baked in.
# Build:  docker build -t markitdown-web .
# Run:    docker run -p 5005:5005 --env-file .env markitdown-web
#
# Everything the app needs (Tesseract + OCRmyPDF + ffmpeg for audio) is
# installed here, so there's nothing to set up on the host.

FROM python:3.12-slim

# System tools:
#   ocrmypdf + tesseract-ocr -> OCR for scanned PDFs and images
#   ghostscript              -> ocrmypdf's PDF rendering backend
#   (ffmpeg comes from the imageio-ffmpeg pip wheel, no apt needed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ocrmypdf \
        tesseract-ocr \
        ghostscript \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY . .

# Bind to all interfaces inside the container; Docker maps it to the host.
ENV HOST=0.0.0.0 \
    PORT=5005 \
    OCR_ENABLED=1 \
    OCR_LANGUAGE=eng

EXPOSE 5005

# 2 workers, 5-min timeout for big/slow conversions (matches the systemd unit).
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5005", "--timeout", "300", "app:app"]
