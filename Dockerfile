# Usa una imagen oficial de Python 3.11 (slim para menor tamaño)
FROM python:3.11-slim

# Instala ffmpeg y otras dependencias del sistema necesarias para bots de música
RUN apt-get update && apt-get install -y \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia primero requirements.txt para aprovechar el cache de Docker
COPY requirements.txt .

# Instala las dependencias de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia el resto de los archivos del proyecto
COPY . .

# Expone el puerto 10000 (requerido por Render para servicios web)
EXPOSE 10000

# Comando para ejecutar el bot
CMD ["python", "music_bot.py"]
