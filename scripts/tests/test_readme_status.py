"""README (EN i PL) pokazuje aktualny etap: ostatnią zaliczoną bramkę i następny etap.

Pilnuje, żeby zamknięcie etapu (nowy docs/gates/G<nr>.passed.json) aktualizowało też status
w README.md i README.pl.md (w E2 status został na E1, PR z poprawką po raporcie z E2).
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DASH = "\N{EN DASH}"  # README pisze zakres etapów z półpauzą (E0, półpauza, E2)


def last_passed_gate() -> int:
    numbers = [
        int(m.group(1))
        for p in (ROOT / "docs/gates").glob("G*.passed.json")
        if (m := re.fullmatch(r"G(\d+)\.passed\.json", p.name))
    ]
    assert numbers, "brak dowodów bramek w docs/gates"
    return max(numbers)


@pytest.mark.parametrize("readme", ["README.md", "README.pl.md"])
def test_readme_status_matches_passed_gates(readme: str) -> None:
    last = last_passed_gate()
    status = next(
        line for line in (ROOT / readme).read_text("utf-8").splitlines() if "**Status:**" in line
    )
    stages = f"E0{DASH}E{last}"
    assert f"**{stages}**" in status, f"{readme}: status nie wymienia etapów {stages}"
    text = (ROOT / readme).read_text("utf-8")
    assert f"**E{last + 1}**" in text, f"{readme}: brak następnego etapu E{last + 1}"
