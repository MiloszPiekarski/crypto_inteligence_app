"""Polityka sieci Terraform OCI (roadmapa E3; ADR-0006, ADR-0007 punkt 3; decyzja D5).

trivy nie ma reguł dla zasobów sieciowych OCI (sprawdzone 23.11.2026: otwarty SSH w NSG
nie jest wykrywany), więc ten skrypt sprawdza sparsowany HCL modułu infra/terraform/oci:
- reguła przychodząca NSG: tylko do NSG `platform`, tylko TCP 443, źródło wyłącznie
  z listy `local.cloudflare_ipv4` (for_each); executor nie ma żadnej reguły przychodzącej;
- Security List: przychodzący tylko ICMP 3/4 (MTU) albo ruch z wnętrza VCN (`var.vcn_cidr`);
- domyślna Security List VCN (OCI tworzy ją z SSH 22 z internetu) jest zarządzana
  i nie ma reguł przychodzących;
- podsieć prywatna nie przyjmuje publicznych IP.
Użycie: python scripts/iac_policy.py infra/terraform/oci (kod 1 przy naruszeniach).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO, cast

import hcl2

CLOUDFLARE_FOR_EACH = "${toset(local.cloudflare_ipv4)}"
VCN_CIDR = "${var.vcn_cidr}"
Resource = tuple[str, str, dict[str, object]]


def load_hcl(fh: TextIO) -> object:
    """hcl2.load bez typów w pakiecie; wynik sprawdzamy dalej jak dane z zewnątrz."""
    return cast(object, hcl2.load(fh))  # pyright: ignore[reportUnknownMemberType]


def _norm(value: object) -> object:
    """python-hcl2 8.x zostawia cudzysłowy w napisach i kluczach; usuwamy je."""
    if isinstance(value, str):
        if len(value) >= 2 and value[0] == value[-1] == '"':  # noqa: PLR2004
            return value[1:-1]
        return value
    if isinstance(value, dict):
        return {
            str(_norm(k)): _norm(v)
            for k, v in cast(dict[object, object], value).items()
            if k != "__is_block__"
        }
    if isinstance(value, list):
        return [_norm(v) for v in cast(list[object], value)]
    return value


def resources(module: Path) -> list[Resource]:
    found: list[Resource] = []
    for tf in sorted(module.glob("*.tf")):
        with tf.open(encoding="utf-8") as fh:
            data = cast(dict[str, object], _norm(load_hcl(fh)))
        for block in cast(list[dict[str, object]], data.get("resource") or []):
            for kind, named in block.items():
                for name, attrs in cast(dict[str, object], named).items():
                    found.append((kind, name, cast(dict[str, object], attrs)))
    return found


def _blocks(attrs: dict[str, object], key: str) -> list[dict[str, object]]:
    raw: object = attrs.get(key) or []
    items = cast(list[object], raw) if isinstance(raw, list) else [raw]
    return [cast(dict[str, object], b) for b in items if isinstance(b, dict)]


def _port_range(rule: dict[str, object]) -> tuple[object, object] | None:
    tcp = _blocks(rule, "tcp_options")
    ranges = _blocks(tcp[0], "destination_port_range") if tcp else []
    if len(tcp) != 1 or len(ranges) != 1:
        return None
    return ranges[0].get("min"), ranges[0].get("max")


def _check_nsg_ingress(name: str, attrs: dict[str, object]) -> list[str]:
    where = f"NSG {name}"
    problems: list[str] = []
    if "oci_core_network_security_group.platform." not in str(
        attrs.get("network_security_group_id")
    ):
        problems.append(f"{where}: ruch przychodzący dozwolony tylko do NSG platform")
    if str(attrs.get("protocol")) != "6" or _blocks(attrs, "udp_options"):
        problems.append(f"{where}: przychodzący tylko TCP (protokół 6)")
    if _port_range(attrs) not in {(443, 443), ("443", "443")}:
        problems.append(f"{where}: przychodzący tylko na port 443 (jest {_port_range(attrs)})")
    if attrs.get("for_each") != CLOUDFLARE_FOR_EACH or attrs.get("source") != "${each.value}":
        problems.append(f"{where}: źródło musi pochodzić z local.cloudflare_ipv4 (for_each)")
    return problems


def _check_security_list(kind: str, name: str, attrs: dict[str, object]) -> list[str]:
    problems: list[str] = []
    for rule in _blocks(attrs, "ingress_security_rules"):
        icmp = _blocks(rule, "icmp_options")
        mtu = (
            str(rule.get("protocol")) == "1"
            and len(icmp) == 1
            and str(icmp[0].get("type")) == "3"
            and str(icmp[0].get("code")) == "4"
        )
        if kind == "oci_core_default_security_list":
            problems.append(f"domyślna Security List {name}: nie może mieć reguł przychodzących")
        elif not (mtu or rule.get("source") == VCN_CIDR):
            problems.append(
                f"Security List {name}: przychodzący tylko ICMP 3/4 albo z VCN "
                f"(jest protokół {rule.get('protocol')} ze źródła {rule.get('source')})"
            )
    return problems


def check(module: Path) -> list[str]:
    found = resources(module)
    problems: list[str] = []
    for kind, name, attrs in found:
        if kind == "oci_core_network_security_group_security_rule":
            if attrs.get("direction") == "INGRESS":
                problems += _check_nsg_ingress(name, attrs)
        elif kind in {"oci_core_security_list", "oci_core_default_security_list"}:
            problems += _check_security_list(kind, name, attrs)
        elif (
            kind == "oci_core_subnet"
            and name == "private"
            and attrs.get("prohibit_public_ip_on_vnic") is not True
        ):
            problems.append("podsieć private: prohibit_public_ip_on_vnic musi być true")
    if not any(kind == "oci_core_default_security_list" for kind, _, _ in found):
        problems.append(
            "brak oci_core_default_security_list: domyślna lista VCN (SSH 22 z internetu) "
            "musi być zarządzana i pusta"
        )
    if not any(kind == "oci_core_subnet" and name == "private" for kind, name, _ in found):
        problems.append("brak podsieci private")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:  # noqa: PLR2004
        print("Użycie: python scripts/iac_policy.py KATALOG_MODUŁU")
        return 2
    problems = check(Path(argv[1]))
    for problem in problems:
        print(f"  NARUSZENIE {problem}")
    print(f"polityka sieci {argv[1]}: {'OK' if not problems else f'{len(problems)} naruszeń'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
