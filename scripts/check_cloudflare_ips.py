"""Lista IPv4 Cloudflare w Terraform zgadza się z bieżącą listą Cloudflare (make iac-lint).

Reguła „443 tylko z Cloudflare” (roadmapa E3) jest tak dobra jak lista zakresów. Gdy
Cloudflare doda zakres, ruch z niego byłby odrzucany; gdy usunie, zostałaby zbędna dziura.
Źródło: https://api.cloudflare.com/client/v4/ips (publiczne, bez klucza).
Użycie: python scripts/check_cloudflare_ips.py infra/terraform/oci/cloudflare_ips.tf
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import cast

from iac_policy import load_hcl

API = "https://api.cloudflare.com/client/v4/ips"


def local_ranges(tf_file: Path) -> list[str]:
    with tf_file.open(encoding="utf-8") as fh:
        data = cast(dict[str, object], load_hcl(fh))
    for block in cast(list[dict[str, object]], data.get("locals") or []):
        if "cloudflare_ipv4" in block:
            return [str(v).strip('"') for v in cast(list[object], block["cloudflare_ipv4"])]
    raise ValueError(f"{tf_file}: brak local.cloudflare_ipv4")


def compare(local: list[str], api_body: str) -> list[str]:
    data = cast(dict[str, object], json.loads(api_body))
    result = cast(dict[str, object], data.get("result") or {})
    if data.get("success") is not True or not isinstance(result.get("ipv4_cidrs"), list):
        return ["odpowiedź API Cloudflare bez listy ipv4_cidrs"]
    current = {str(c) for c in cast(list[object], result["ipv4_cidrs"])}
    problems = [
        f"zakres {c} jest u Cloudflare, brak w Terraform" for c in sorted(current - set(local))
    ]
    problems += [
        f"zakres {c} jest w Terraform, Cloudflare go już nie podaje"
        for c in sorted(set(local) - current)
    ]
    return problems


def main(argv: list[str]) -> int:
    local = local_ranges(Path(argv[1]))
    req = urllib.request.Request(API, headers={"User-Agent": "goatcash-iac-lint"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - stały adres https
        body = resp.read().decode("utf-8")
    problems = compare(local, body)
    for problem in problems:
        print(f"  NIEZGODNOŚĆ {problem}")
    verdict = "aktualna" if not problems else "NIEAKTUALNA"
    print(f"lista IP Cloudflare ({len(local)} zakresów): {verdict}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
