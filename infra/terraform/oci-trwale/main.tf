# Trwała warstwa Oracle (ADR-0007): OCI Vault z kluczem głównym dla executora (ADR-0006).
# Osobny stan, NIE niszczony przy odtwarzaniu środowiska od zera (F-01): usunięcie Vault
# w OCI trwa co najmniej 7 dni, a każda nowa wersja klucza zużywa darmowy limit (20 wersji
# kluczy HSM, typ DEFAULT; „Virtual Private Vault” jest płatny).
terraform {
  required_version = ">= 1.17"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "= 9.12.1"
    }
  }

  backend "oci" {
    bucket = "goatcash-tfstate"
    key    = "staging/oci-trwale.tfstate"
    region = "eu-amsterdam-1"
  }
}

variable "region" {
  description = "Region OCI (region domowy tenancy)."
  type        = string
  default     = "eu-amsterdam-1"
}

variable "oci_profile" {
  description = "Profil w pliku konfiguracji OCI CLI (użytkownik IAM terraform)."
  type        = string
  default     = "DEFAULT"
}

variable "compartment_ocid" {
  description = "OCID compartmentu goatcash."
  type        = string

  validation {
    condition     = startswith(var.compartment_ocid, "ocid1.compartment.")
    error_message = "compartment_ocid musi być OCID compartmentu (ocid1.compartment...)."
  }
}

resource "oci_kms_vault" "goatcash" {
  compartment_id = var.compartment_ocid
  display_name   = "goatcash-staging"
  vault_type     = "DEFAULT"

  lifecycle {
    prevent_destroy = true
  }
}

resource "oci_kms_key" "executor_master" {
  compartment_id      = var.compartment_ocid
  display_name        = "goatcash-executor-master"
  management_endpoint = oci_kms_vault.goatcash.management_endpoint
  protection_mode     = "HSM"

  key_shape {
    algorithm = "AES"
    length    = 32
  }

  lifecycle {
    prevent_destroy = true
  }
}

output "vault_id" {
  description = "OCID Vault (dla executora w E14)."
  value       = oci_kms_vault.goatcash.id
}

output "executor_master_key_id" {
  description = "OCID klucza głównego executora (szyfrowanie kopertowe, ADR-0006)."
  value       = oci_kms_key.executor_master.id
}
