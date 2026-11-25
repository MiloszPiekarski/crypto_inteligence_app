# Obraz platformy (api/worker/ingest/scheduler). Build z katalogu głównego repo:
#   docker build -f services/platform/Dockerfile .
# Wieloplatformowy: linux/arm64 (Oracle A1) i linux/amd64 (CI, executor).
FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv

FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/platform/pyproject.toml services/platform/pyproject.toml
COPY services/executor/pyproject.toml services/executor/pyproject.toml
COPY services/platform/src services/platform/src
COPY services/executor/src services/executor/src
RUN uv sync --frozen --no-dev --package goatcash-platform --no-editable

FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS runtime
RUN useradd --create-home --uid 10001 goatcash
COPY --from=build --chown=goatcash:goatcash /app/.venv /app/.venv
# Konfiguracja Alembic: migracje uruchamiane z obrazu (`alembic upgrade head` w /app) przy
# wdrożeniu (deploy-staging.yml, E3). Skrypty migracji są w pakiecie goatcash.migrations.
COPY --chown=goatcash:goatcash services/platform/alembic.ini /app/alembic.ini
ENV PATH="/app/.venv/bin:${PATH}" PYTHONUNBUFFERED=1
USER goatcash
WORKDIR /app
EXPOSE 8000
# Domyślnie wypisuje wersję; proces api uruchamia Compose (infra/compose/staging/compose.yaml):
#   uvicorn --factory goatcash.http_api.app:create_app --host 0.0.0.0 --port 8000
CMD ["python", "-m", "goatcash"]
