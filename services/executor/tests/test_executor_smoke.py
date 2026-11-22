"""Test dymny executora."""

import pytest

from goatcash_executor.__main__ import main


def test_executor_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    assert capsys.readouterr().out.strip() == "goatcash-executor 0.1.0"
