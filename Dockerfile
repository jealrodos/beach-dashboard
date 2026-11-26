FROM python:3.12-slim
ARG ATRIA_GIT_SHA=untracked
LABEL org.opencontainers.image.title="BeachWatch" \
      org.opencontainers.image.revision="${ATRIA_GIT_SHA}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Lisbon
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home beach
COPY app.py configuration.py beaches.example.json ./
COPY templates ./templates
COPY static ./static
USER beach
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "90", "app:app"]
