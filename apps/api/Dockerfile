FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./

FROM base AS development

COPY src ./src
COPY tests ./tests

RUN python -m pip install -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "intihal_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production

COPY src ./src

RUN python -m pip install . \
    && groupadd --system api \
    && useradd --system --gid api --create-home api

USER api

EXPOSE 8000

CMD ["uvicorn", "intihal_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
