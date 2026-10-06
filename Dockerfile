# Imagen base: un Linux pequeño que ya trae Python 3.13.
FROM python:3.13-slim

# PYTHONDONTWRITEBYTECODE: no crear archivos __pycache__ (no sirven en la caja).
# PYTHONUNBUFFERED: mostrar los mensajes de la app al instante en los logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instalamos Tesseract (el programa de OCR) con sus idiomas inglés y español.
# --no-install-recommends evita paquetes extra; borrar /var/lib/apt/lists
# deja la imagen más liviana.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Carpeta de trabajo dentro de la caja. Todo lo que sigue ocurre aquí.
WORKDIR /app

# Copiamos primero SOLO requirements.txt e instalamos las librerías.
# Así Docker reutiliza este paso si solo cambiaste código y no las librerías,
# y las reconstrucciones son mucho más rápidas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ahora sí, copiamos nuestro código.
COPY app ./app

# Por seguridad, la API no corre como administrador (root) dentro de la caja.
RUN useradd --create-home appuser
USER appuser

# Puerto por defecto. Render define su propio puerto con la variable PORT,
# por eso el comando de abajo la lee y usa 8000 si no existe.
ENV PORT=8000
EXPOSE 8000

# 0.0.0.0 = aceptar conexiones desde fuera de la caja (si no, nadie podría entrar).
# Un solo proceso (sin --workers): el plan gratuito tiene solo 512 MB de memoria.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
