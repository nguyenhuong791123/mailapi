# Wheels are built in a separate stage (pyminizip needs a C compiler and zlib).
FROM python:3.12-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc zlib1g-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8082
WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels && useradd --system --uid 10001 app
COPY app ./app
COPY wsgi.py .
USER app
EXPOSE 8082
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['PORT'], timeout=2)"
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers ${WORKERS:-2} --threads ${THREADS:-4} --timeout ${TIMEOUT:-60} --access-logfile - wsgi:app"]
