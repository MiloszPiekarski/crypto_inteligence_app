"""goatcash-render-env (sudo, root): zapis plików .env i klucza TLS nie może dać się przekierować
dowiązaniem podstawionym przez użytkownika deploy ani dopisać zmiennej przez nową linię."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / "infra/ansible/roles/goatcash/files/goatcash-render-env"
)
SECRETS = {
    "postgres": {"POSTGRES_PASSWORD": "p1", "PGBACKREST_REPO1_CIPHER_PASS": "c1"},
    "api": {"GOATCASH_DATABASE_URL": "postgresql+psycopg://x"},
    "tls": {"ORIGIN_KEY": "-----KEY-----\nabc\n"},
    "sops": {"version": "3"},
}


def load(root: Path, secrets: Mapping[str, object], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("goatcash_render_env", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    (root / "compose").mkdir(parents=True)
    (root / "tls").mkdir()
    monkeypatch.setattr(mod, "ROOT", root)
    out = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(secrets))
    me = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())

    def fake_run(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return out

    def fake_user(_name: str) -> SimpleNamespace:
        return me

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod.pwd, "getpwnam", fake_user)
    return mod


def test_writes_env_files_and_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = load(tmp_path, SECRETS, monkeypatch)
    assert mod.main() == 0
    env = tmp_path / "compose" / "env"
    assert (
        env / "postgres.env"
    ).read_text() == "POSTGRES_PASSWORD=p1\nPGBACKREST_REPO1_CIPHER_PASS=c1\n"
    assert (env / "postgres.env").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "tls" / "origin.key").read_text() == "-----KEY-----\nabc\n"
    assert not (env / "sops.env").exists()


def test_env_dir_symlink_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = load(tmp_path / "srv", SECRETS, monkeypatch)
    victim = tmp_path / "etc"
    victim.mkdir()
    (tmp_path / "srv" / "compose" / "env").symlink_to(victim)
    with pytest.raises(OSError, match=r"symbolic links|Not a directory"):
        mod.main()
    assert list(victim.iterdir()) == []


def test_tmp_file_symlink_does_not_overwrite_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = load(tmp_path / "srv", SECRETS, monkeypatch)
    victim = tmp_path / "shadow"
    victim.write_text("nie ruszać\n")
    (tmp_path / "srv" / "tls" / ".origin.key.tmp").symlink_to(victim)
    assert mod.main() == 0
    assert victim.read_text() == "nie ruszać\n"
    assert not (tmp_path / "srv" / "tls" / "origin.key").is_symlink()


@pytest.mark.parametrize(
    "values",
    [{"A": "x\nB=wstrzyknięte"}, {"zla_nazwa": "x"}, {"A": 5}],
)
def test_bad_values_rejected(
    values: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = load(tmp_path, {"api": values}, monkeypatch)
    assert mod.main() == 1
    assert not (tmp_path / "compose" / "env" / "api.env").exists()
