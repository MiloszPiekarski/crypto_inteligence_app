# Obraz executora bota (osobny obraz, osobne sekrety). Build z katalogu głównego repo:
#   docker build -f services/executor/Dockerfile .
# Wieloplatformowy: linux/arm64 (Oracle A1) i linux/amd64 (CI, executor).
FROM ghcr.io/astral-sh/uv:0.13.9 AS uv

FROM python:3.15-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/platform/pyproject.toml services/platform/pyproject.toml
COPY services/executor/pyproject.toml services/executor/pyproject.toml
COPY services/platform/src services/platform/src
COPY services/executor/src services/executor/src
RUN uv sync --frozen --no-dev --package goatcash-executor --no-editable

FROM python:3.15-slim AS runtime
RUN useradd --create-home --uid 10001 goatcash
COPY --from=build --chown=goatcash:goatcash /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}" PYTHONUNBUFFERED=1
USER goatcash
WORKDIR /app
CMD ["python", "-m", "goatcash_executor"]
