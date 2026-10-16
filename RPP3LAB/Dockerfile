FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
RUN useradd --uid 10001 --no-create-home appuser
COPY *.py ./
ENV PORT=8000 LOG_LEVEL=info PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/health', timeout=2)"
# один процесс-обработчик: данные хранятся в памяти процесса
CMD ["sh", "-c", "exec gunicorn --workers 1 --bind 0.0.0.0:${PORT} --log-level ${LOG_LEVEL} --access-logfile - app:app"]
