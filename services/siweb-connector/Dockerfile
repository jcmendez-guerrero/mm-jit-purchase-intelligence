# syntax=docker/dockerfile:1
# Build context: repository root (shared contracts are installed from packages/contracts).
FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY packages/contracts /app/packages/contracts
COPY services/siweb-connector/pyproject.toml /app/services/siweb-connector/pyproject.toml
# Dependencies come from the service's pyproject; production builds use the hashed uv.lock (uv sync --frozen).
RUN python -c "import tomllib;print(chr(10).join(d for d in tomllib.load(open('services/siweb-connector/pyproject.toml','rb'))['project']['dependencies'] if not d.startswith('mmi-')))" > /tmp/req.txt \
 && pip install -r /tmp/req.txt ./packages/contracts
COPY services/siweb-connector/ /app/services/siweb-connector/
RUN useradd --system --uid 10001 --no-create-home app \
 && mkdir -p /data/blobs && chown 10001 /data/blobs
USER 10001
ENV PYTHONPATH=/app/services/siweb-connector/src
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
