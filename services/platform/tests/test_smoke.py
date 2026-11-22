"""Testy dymne szkieletu: pakiet się importuje, moduły mają publiczne API."""

import importlib

import pytest
from hypothesis import given
from hypothesis import strategies as st

from goatcash.__main__ import main
from goatcash.common.api import package_version

MODULES = [
    "marketdata",
    "features",
    "agents",
    "fusion",
    "ledger",
    "ml",
    "llm",
    "backtest",
    "alerts",
    "users",
    "bot_core",
    "common",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_has_public_api(module: str) -> None:
    api = importlib.import_module(f"goatcash.{module}.api")
    assert hasattr(api, "__all__")


def test_package_version_is_known() -> None:
    assert package_version() == "0.1.0"


def test_unknown_distribution_is_explicit() -> None:
    assert package_version("goatcash-does-not-exist") == "unknown"


def test_main_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    assert capsys.readouterr().out.strip() == "goatcash-platform 0.1.0"


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=40))
def test_version_lookup_never_raises(name: str) -> None:
    result = package_version(f"zz-not-installed-{name}")
    assert result == "unknown"
