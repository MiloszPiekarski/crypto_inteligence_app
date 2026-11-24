"""wait-for-alerts.py LIMIT_S NAZWA...: czeka, aż każdy alert NAZWA trafi do Alertmanagera Grafany
jako aktywny (stan po ocenie reguły i `for`, czyli wysłany do punktów kontaktu: e-mail
i Telegram). Wypisuje czas od startu dla każdego alertu; kod 1, gdy któryś nie dotarł w LIMIT_S.
Używa go alert-drill.yml (F-03: „powiadomienie < 5 min”).
Zmienne: GRAFANA_URL (adres stosu), GRAFANA_TOKEN (konto serwisowe, rola Viewer).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from typing import cast

PATH = "/api/alertmanager/grafana/api/v2/alerts?active=true&silenced=false&inhibited=false"


def active_names(body: str) -> set[str]:
    alerts = cast(list[dict[str, object]], json.loads(body))
    return {
        str(cast(dict[str, object], a.get("labels") or {}).get("alertname"))
        for a in alerts
        if cast(dict[str, object], a.get("status") or {}).get("state") == "active"
    }


def fetch(url: str, token: str) -> str:
    # Adres sprawdzony w main(): tylko https.
    req = urllib.request.Request(url + PATH, headers={"Authorization": f"Bearer {token}"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return resp.read().decode("utf-8")


def main(argv: list[str]) -> int:
    limit, wanted = int(argv[1]), argv[2:]
    url, token = os.environ["GRAFANA_URL"].rstrip("/"), os.environ["GRAFANA_TOKEN"]
    if not url.startswith("https://") or not wanted:
        print(__doc__)
        return 2
    start = time.monotonic()
    seen: dict[str, int] = {}
    while time.monotonic() - start <= limit:
        names: set[str] = set()
        try:
            names = active_names(fetch(url, token))
        except (OSError, ValueError) as exc:
            print(f"  (błąd odczytu Alertmanagera: {exc.__class__.__name__}, ponawiam)")
        for name in wanted:
            if name in names and name not in seen:
                seen[name] = int(time.monotonic() - start)
                print(f"  PASS alert „{name}” aktywny po {seen[name]} s")
        if len(seen) == len(wanted):
            slowest = max(seen.values())
            print(f"== alert-drill: PASS, najwolniejszy alert {slowest} s (limit {limit} s)")
            return 0
        time.sleep(15)
    for name in wanted:
        if name not in seen:
            print(f"  FAIL alert „{name}” nie dotarł w {limit} s")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
