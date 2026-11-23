"""Eksport specyfikacji OpenAPI z aplikacji FastAPI do `packages/contracts/openapi/openapi.json`.

Użycie: `uv run python scripts/export_openapi.py` (zapis) albo `--check` (kod 1, gdy plik
w repozytorium różni się od wygenerowanego, czyli ktoś zmienił API bez aktualizacji kontraktu).
"""

import json
import sys
from pathlib import Path

from goatcash.http_api.app import create_app

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "packages/contracts/openapi/openapi.json"


def render() -> str:
    spec = create_app().openapi()
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if not TARGET.exists() or TARGET.read_text("utf-8") != text:
            print(
                f"{TARGET.relative_to(ROOT)} nieaktualny: uruchom "
                "`uv run python scripts/export_openapi.py` i dodaj plik do commita",
                file=sys.stderr,
            )
            return 1
        print(f"{TARGET.relative_to(ROOT)}: zgodny z aplikacją")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text, "utf-8")
    print(f"zapisano {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
