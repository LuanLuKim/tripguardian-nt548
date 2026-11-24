# Fake OpenAI-compatible LLM (ops/nt548/llm_fake/server.py). Build context: ops/nt548/llm_fake
#   docker build -t llm-fake ops/nt548/llm_fake
#   docker run -p 8000:8000 -e FAKE_VERSION=v2 -e FAKE_ERROR_RATE=0.3 llm-fake
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn>=0.29"
WORKDIR /app
COPY server.py .
USER nobody
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8000"]
