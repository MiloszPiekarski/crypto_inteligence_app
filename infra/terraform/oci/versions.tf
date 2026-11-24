# Stos Oracle dla staging (E3, ADR-0007). Providery przypięte; sumy w .terraform.lock.hcl
# (platformy darwin_arm64 i linux_amd64: komputer właściciela i CI).
terraform {
  required_version = ">= 1.17"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "= 9.12.1"
    }
    tailscale = {
      source  = "tailscale/tailscale"
      version = "= 0.29.3"
    }
  }
}
