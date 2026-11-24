# Harness image (python -m harness serve, or the stub until sample data exists) and the model gateway.
# Build context: repo root. No data/, .env or key goes in (harness.Dockerfile.dockerignore is an allowlist).
#   docker build -f ops/nt548/compose/harness.Dockerfile -t harness .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
# Dependencies first (cached while only src/ changes); fastapi + uvicorn run scripts/model_gateway.py.
COPY pyproject.toml .
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/requirements.txt \
 && pip install --no-cache-dir -r /tmp/requirements.txt "fastapi>=0.110" "uvicorn>=0.29" \
 && rm /tmp/requirements.txt
COPY config config
COPY migrations migrations
COPY src src
COPY scripts/model_gateway.py scripts/model_gateway.py
COPY ops/nt548/compose/harness_stub.py ops/nt548/compose/harness_stub.py
ARG REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/LuanLuKim/tripguardian-nt548" \
      org.opencontainers.image.revision="${REVISION}"
RUN useradd --create-home --uid 10001 app
USER app
CMD ["python", "ops/nt548/compose/harness_stub.py"]
