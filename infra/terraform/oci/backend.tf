# Stan w OCI Object Storage (ADR-0007, punkt 2): wersjonowanie w buckecie, blokada stanu
# przez If-None-Match (plik .lock obok stanu). Bucket zakłada jednorazowo właściciel
# (runbook). Namespace podaje się przy init (częściowa konfiguracja), nie w repo:
#   terraform init -backend-config="namespace=$(oci os ns get --query data --raw-output)"
terraform {
  backend "oci" {
    bucket = "goatcash-tfstate"
    key    = "staging/oci.tfstate"
    region = "eu-amsterdam-1"
  }
}
