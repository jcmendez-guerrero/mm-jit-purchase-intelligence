# syntax=docker/dockerfile:1
# Test-support image: Siweb mock and dev issuer. Never deployed to Azure. Context: repository root.
FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY packages/contracts /app/packages/contracts
COPY packages/testing /app/packages/testing
RUN pip install ./packages/contracts ./packages/testing \
 && useradd --system --uid 10001 --no-create-home app
USER 10001
EXPOSE 8089 8090
CMD ["python", "-m", "siweb_mock"]
