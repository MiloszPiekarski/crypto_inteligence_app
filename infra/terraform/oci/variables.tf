variable "region" {
  description = "Region OCI (region domowy tenancy, ADR-0007)."
  type        = string
  default     = "eu-amsterdam-1"
}

variable "oci_profile" {
  description = "Profil w pliku konfiguracji OCI CLI (użytkownik IAM terraform)."
  type        = string
  default     = "DEFAULT"
}

variable "compartment_ocid" {
  description = "OCID compartmentu goatcash (z konsoli Oracle albo OCI CLI)."
  type        = string

  validation {
    condition     = startswith(var.compartment_ocid, "ocid1.compartment.")
    error_message = "compartment_ocid musi być OCID compartmentu (ocid1.compartment...)."
  }
}

variable "vcn_cidr" {
  description = "Zakres adresów VCN staging."
  type        = string
  default     = "10.30.0.0/16"
}
