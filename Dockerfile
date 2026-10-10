FROM node:24-bookworm-slim AS dashboard
WORKDIR /build
COPY web_dashboard/package*.json ./
RUN npm ci
COPY web_dashboard/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
COPY backend/requirements-voice.txt ./requirements-voice.txt
ARG ENABLE_VOICE=true
RUN pip install --no-cache-dir -r requirements.txt && if [ "$ENABLE_VOICE" = "true" ]; then pip install --no-cache-dir -r requirements-voice.txt; fi
COPY backend/ ./backend/
COPY --from=dashboard /build/dist ./backend/staticapp
RUN DJANGO_DEBUG=true python backend/manage.py collectstatic --noinput && useradd --create-home --uid 10001 lily && mkdir -p /app/backend/media && chown -R lily:lily /app
USER lily
EXPOSE 8000
ENTRYPOINT ["python", "/app/backend/entrypoint.py"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "180"]
