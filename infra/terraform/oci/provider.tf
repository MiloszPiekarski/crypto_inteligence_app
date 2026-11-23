# Uwierzytelnienie: profil z pliku konfiguracji OCI CLI właściciela (użytkownik IAM
# `terraform`, polityka ograniczona do compartmentu goatcash). Żadnych kluczy w repo.
provider "oci" {
  region              = var.region
  config_file_profile = var.oci_profile
}
