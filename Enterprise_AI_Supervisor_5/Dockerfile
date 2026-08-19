FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8501

WORKDIR /app

RUN groupadd --system supervisor && useradd --system --gid supervisor --home-dir /app supervisor

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/data && chown -R supervisor:supervisor /app && chmod +x /app/start.sh

USER supervisor
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=7s --start-period=30s --retries=3 \
  CMD ["python", "healthcheck.py"]

ENTRYPOINT ["./start.sh"]
