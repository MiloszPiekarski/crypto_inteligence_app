"""Polityka sieci OCI: moduł repo przechodzi, każde naruszenie jest wykrywane (trivy nie ma
reguł OCI, więc ta kontrola musi sama łapać otwarte porty)."""

import json
import shutil
from pathlib import Path

import check_cloudflare_ips
import iac_policy
import pytest

MODULE = Path(__file__).resolve().parents[2] / "infra" / "terraform" / "oci"

SSH_NSG = """
resource "oci_core_network_security_group_security_rule" "ssh" {
  network_security_group_id = oci_core_network_security_group.platform.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source_type               = "CIDR_BLOCK"
  source                    = "0.0.0.0/0"
  tcp_options {
    destination_port_range {
      min = 22
      max = 22
    }
  }
}
"""
HTTPS_TO_EXECUTOR = """
resource "oci_core_network_security_group_security_rule" "do_executora" {
  for_each                  = toset(local.cloudflare_ipv4)
  network_security_group_id = oci_core_network_security_group.executor.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source_type               = "CIDR_BLOCK"
  source                    = each.value
  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}
"""
HTTPS_FROM_ANYWHERE = """
resource "oci_core_network_security_group_security_rule" "https_z_internetu" {
  network_security_group_id = oci_core_network_security_group.platform.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source_type               = "CIDR_BLOCK"
  source                    = "0.0.0.0/0"
  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}
"""
UDP_RULE = """
resource "oci_core_network_security_group_security_rule" "udp" {
  for_each                  = toset(local.cloudflare_ipv4)
  network_security_group_id = oci_core_network_security_group.platform.id
  direction                 = "INGRESS"
  protocol                  = "17"
  source_type               = "CIDR_BLOCK"
  source                    = each.value
  udp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}
"""
SECLIST_SSH = """
resource "oci_core_security_list" "dziura" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.staging.id
  ingress_security_rules {
    source   = "0.0.0.0/0"
    protocol = "6"
    tcp_options {
      min = 22
      max = 22
    }
  }
}
"""


def module_with(tmp_path: Path, extra: str = "", replace: tuple[str, str] | None = None) -> Path:
    copy = tmp_path / "oci"
    shutil.copytree(MODULE, copy, ignore=shutil.ignore_patterns(".terraform*"))
    network = copy / "network.tf"
    text = network.read_text("utf-8")
    if replace:
        assert text.count(replace[0]) == 1, replace[0]
        text = text.replace(replace[0], replace[1])
    network.write_text(text + extra, "utf-8")
    return copy


def test_repo_module_passes() -> None:
    assert iac_policy.check(MODULE) == []


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (SSH_NSG, "tylko na port 443"),
        (SSH_NSG, "local.cloudflare_ipv4"),
        (HTTPS_TO_EXECUTOR, "tylko do NSG platform"),
        (HTTPS_FROM_ANYWHERE, "local.cloudflare_ipv4"),
        (UDP_RULE, "tylko TCP"),
        (SECLIST_SSH, "Security List dziura"),
    ],
)
def test_violations_are_detected(tmp_path: Path, extra: str, message: str) -> None:
    found = iac_policy.check(module_with(tmp_path, extra))
    assert any(message in p for p in found), found


def test_default_security_list_with_rules_rejected(tmp_path: Path) -> None:
    module = module_with(
        tmp_path,
        replace=(
            '  display_name               = "goatcash-staging-default-pusta"\n',
            '  display_name               = "x"\n'
            "  ingress_security_rules {\n"
            '    source   = "0.0.0.0/0"\n'
            '    protocol = "6"\n'
            "  }\n",
        ),
    )
    assert any("domyślna Security List" in p for p in iac_policy.check(module))


def test_missing_default_security_list_rejected(tmp_path: Path) -> None:
    module = module_with(
        tmp_path,
        replace=(
            'resource "oci_core_default_security_list" "staging" {',
            'resource "oci_core_drg" "zamiast_listy" {',
        ),
    )
    assert any("brak oci_core_default_security_list" in p for p in iac_policy.check(module))


def test_private_subnet_with_public_ips_rejected(tmp_path: Path) -> None:
    module = module_with(
        tmp_path,
        replace=(
            "  prohibit_public_ip_on_vnic = true\n",
            "  prohibit_public_ip_on_vnic = false\n",
        ),
    )
    assert any("prohibit_public_ip_on_vnic" in p for p in iac_policy.check(module))


def test_policy_cli_exit_codes(tmp_path: Path) -> None:
    assert iac_policy.main(["p", str(MODULE)]) == 0
    assert iac_policy.main(["p", str(module_with(tmp_path, SSH_NSG))]) == 1


def test_cloudflare_list_comparison() -> None:
    local = check_cloudflare_ips.local_ranges(MODULE / "cloudflare_ips.tf")
    assert len(local) == len(set(local)) > 0
    same = json.dumps({"success": True, "result": {"ipv4_cidrs": list(reversed(local))}})
    assert check_cloudflare_ips.compare(local, same) == []
    changed = json.dumps({"success": True, "result": {"ipv4_cidrs": [*local[1:], "1.2.3.0/24"]}})
    found = check_cloudflare_ips.compare(local, changed)
    assert any("1.2.3.0/24" in p for p in found)
    assert any(local[0] in p for p in found)
    assert check_cloudflare_ips.compare(local, '{"success": false}') != []
