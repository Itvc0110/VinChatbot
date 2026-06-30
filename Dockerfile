# Backend (FastAPI) image.
# Qdrant stays on Qdrant Cloud (via QDRANT_URL in .env) — not containerized here.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the package from pyproject. fastembed/onnxruntime, pymupdf, tiktoken, pydantic
# all ship manylinux wheels, so no build toolchain is needed for the base dependency set.
COPY pyproject.toml README.md ./
COPY vinchatbot ./vinchatbot
RUN pip install --upgrade pip --retries 10 --timeout 120 --progress-bar off \
    && pip install --retries 10 --timeout 120 --progress-bar off .

EXPOSE 8000

# 0.0.0.0 so the container is reachable from the frontend service on the compose network.
CMD ["uvicorn", "vinchatbot.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
