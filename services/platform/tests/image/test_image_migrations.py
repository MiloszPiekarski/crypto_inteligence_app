"""Obraz platformy uruchamia migracje (bramka G3, `image-migrations`; ADR-0007).

Wdrożenie staging (`deploy-staging.yml`) uruchamia `alembic upgrade head` z obrazu, więc obraz
musi zawierać `alembic.ini` i skrypty migracji. Test buduje obraz z Dockerfile (tak jak CI),
uruchamia go w jednej sieci Dockera z Postgresem 17 + TimescaleDB + pgvector i sprawdza
wynik z zewnątrz. Wymaga Dockera; uruchomienie: `make image-migration-test`. W zwykłym
`make test` pomijany markerem `image`.
"""

import subprocess
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.network import Network

pytestmark = pytest.mark.image

PLATFORM = Path(__file__).resolve().parents[2]
ROOT = PLATFORM.parents[1]
TAG = "goatcash-platform:image-migration-test"
# Ten sam obraz bazy co w teście migracji G2 (przypięty do digestu, ADR-0002).
DB_IMAGE = (
    "timescale/timescaledb-ha:pg17"
    "@sha256:c72b4cb8aaa0a52c0870c2b0a48173c595ee9bef0f3d8f92c3f546c69fef3567"
)
DB_ALIAS = "db"


def docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - stałe argumenty z testu
        ["docker", *args],  # noqa: S607 - docker z PATH (jak testcontainers)
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )


def head_revision() -> str:
    script = ScriptDirectory.from_config(Config(str(PLATFORM / "alembic.ini")))
    head = script.get_current_head()
    assert head, "brak rewizji head w migracjach"
    return head


@pytest.fixture(scope="module")
def image() -> str:
    built = docker("build", "-f", str(PLATFORM / "Dockerfile"), "-t", TAG, str(ROOT))
    assert built.returncode == 0, built.stderr[-3000:]
    return TAG


@pytest.fixture(scope="module")
def database() -> Iterator[tuple[str, str, str]]:
    """(nazwa sieci Dockera, adres bazy w tej sieci, adres bazy z hosta)."""
    with Network() as network:
        pg = PostgresContainer(DB_IMAGE, driver=None)
        pg.with_network(network).with_network_aliases(DB_ALIAS)
        with pg:
            inside = f"postgresql+psycopg://{pg.username}:{pg.password}@{DB_ALIAS}:5432/{pg.dbname}"
            yield network.name, inside, pg.get_connection_url()


def run_in_image(image: str, network: str, url: str, *cmd: str) -> subprocess.CompletedProcess[str]:
    return docker(
        "run", "--rm", "--network", network, "-e", f"GOATCASH_DATABASE_URL={url}", image, *cmd
    )


def test_image_runs_as_non_root(image: str) -> None:
    assert docker("run", "--rm", image, "id", "-u").stdout.strip() == "10001"


def test_image_contains_alembic_config(image: str) -> None:
    found = docker("run", "--rm", image, "cat", "/app/alembic.ini")
    assert found.returncode == 0, found.stderr
    assert "script_location = goatcash:migrations" in found.stdout


def test_migrations_from_image_reach_head(image: str, database: tuple[str, str, str]) -> None:
    network, inside, outside = database
    upgraded = run_in_image(image, network, inside, "alembic", "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr[-3000:]
    current = run_in_image(image, network, inside, "alembic", "current")
    assert current.returncode == 0, current.stderr[-3000:]
    assert head_revision() in current.stdout, current.stdout
    with psycopg.connect(outside, autocommit=True) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        bot = conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'bot'").fetchone()
        ext = conn.execute(
            "SELECT count(*) FROM pg_extension WHERE extname IN ('timescaledb', 'vector')"
        ).fetchone()
    assert version is not None
    assert version[0] == head_revision()
    assert bot is not None
    assert int(bot[0]) > 0
    assert ext is not None
    assert int(ext[0]) == 2


def test_second_upgrade_is_a_no_op(image: str, database: tuple[str, str, str]) -> None:
    # Wdrożenie uruchamia migracje przy każdym commicie: ponowne uruchomienie nic nie zmienia.
    network, inside, _ = database
    again = run_in_image(image, network, inside, "alembic", "upgrade", "head")
    assert again.returncode == 0, again.stderr[-3000:]
    assert "Running upgrade" not in again.stderr


def test_migrations_fail_loudly_without_database_url(image: str) -> None:
    # Brak adresu bazy = błąd (wdrożenie zatrzymane), nie cicha migracja „donikąd”.
    missing = docker("run", "--rm", image, "alembic", "upgrade", "head")
    assert missing.returncode != 0
    assert "GOATCASH_DATABASE_URL" in missing.stderr
