FROM python:3.12-slim

# No escribir .pyc y no bufferear stdout: los logs aparecen al instante
# en `docker compose logs`, sin esperar a que se llene el buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Las dependencias se copian primero y en su propia capa: mientras
# requirements.txt no cambie, Docker reutiliza esta capa y el build
# tarda segundos en vez de minutos.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuario sin privilegios. Evita además que los archivos creados en
# volúmenes montados queden a nombre de root en el host.
RUN useradd --create-home --uid 1000 sentinel && chown -R sentinel:sentinel /app
USER sentinel

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
