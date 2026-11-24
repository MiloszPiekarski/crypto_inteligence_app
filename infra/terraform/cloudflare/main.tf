# Cloudflare dla staging (roadmapa E3, zakres prac 2; ADR-0007): rekordy api. i app. przez
# proxy, TLS Full (strict) z certyfikatem Origin CA, reguła WAF, limit zapytań, bucket R2.
# Token: CLOUDFLARE_API_TOKEN (.env.local; strefa goatcash.app: DNS, Zone Settings, Zone WAF,
# SSL and Certificates, Firewall Services; konto: Workers R2 Storage, wszystko Edit).
# Adres serwera z wyjścia stosu oci (ten sam bucket stanu).
terraform {
  required_version = ">= 1.17"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "= 5.28.1"
    }
  }

  backend "oci" {
    bucket = "goatcash-tfstate"
    key    = "staging/cloudflare.tfstate"
    region = "eu-amsterdam-1"
  }
}

provider "cloudflare" {}

variable "account_id" {
  description = "Account ID Cloudflare (CLOUDFLARE_ACCOUNT_ID w .env.local, przez TF_VAR_account_id)."
  type        = string
}

variable "origin_csr_path" {
  description = "Ścieżka do CSR certyfikatu Origin CA (publiczny; klucz prywatny tylko w SOPS i Bitwardenie)."
  type        = string
  default     = "../../tls/origin.csr"
}

variable "state_namespace" {
  description = "Namespace OCI Object Storage z bucketem stanu (oci os ns get)."
  type        = string
}

data "terraform_remote_state" "oci" {
  backend = "oci"
  config = {
    bucket    = "goatcash-tfstate"
    key       = "staging/oci.tfstate"
    region    = "eu-amsterdam-1"
    namespace = var.state_namespace
  }
}

data "cloudflare_zone" "goatcash" {
  filter = {
    name = "goatcash.app"
  }
}

locals {
  zone_id     = data.cloudflare_zone.goatcash.zone_id
  platform_ip = data.terraform_remote_state.oci.outputs.platform_public_ip
}

resource "cloudflare_dns_record" "api" {
  zone_id = local.zone_id
  name    = "api.goatcash.app"
  type    = "A"
  content = local.platform_ip
  proxied = true
  ttl     = 1
  comment = "staging api (E3, Terraform)"
}

resource "cloudflare_dns_record" "app" {
  zone_id = local.zone_id
  name    = "app.goatcash.app"
  type    = "A"
  content = local.platform_ip
  proxied = true
  ttl     = 1
  comment = "staging app (E3, Terraform; interfejs od E12)"
}

# TLS między Cloudflare a serwerem: Full (strict), czyli Cloudflare sprawdza certyfikat
# Origin CA na Caddy; HTTPS wymuszony, TLS co najmniej 1.2.
resource "cloudflare_zone_setting" "ssl" {
  zone_id    = local.zone_id
  setting_id = "ssl"
  value      = "strict"
}

resource "cloudflare_zone_setting" "always_use_https" {
  zone_id    = local.zone_id
  setting_id = "always_use_https"
  value      = "on"
}

resource "cloudflare_zone_setting" "min_tls_version" {
  zone_id    = local.zone_id
  setting_id = "min_tls_version"
  value      = "1.2"
}

# Certyfikat Origin CA (15 lat) z CSR właściciela; klucz prywatny tylko w SOPS (tls.ORIGIN_KEY),
# CSR i certyfikat są publiczne (infra/tls/).
resource "cloudflare_origin_ca_certificate" "staging" {
  csr                = file(var.origin_csr_path)
  hostnames          = ["api.goatcash.app", "app.goatcash.app"]
  request_type       = "origin-ecc"
  requested_validity = 5475
}

# WAF (plan Free): reguły zarządzane Cloudflare działają domyślnie; własna reguła odrzuca
# metody HTTP, których API nie używa.
resource "cloudflare_ruleset" "firewall" {
  zone_id = local.zone_id
  name    = "goatcash: reguly wlasne"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  rules = [{
    description = "Blokada nieuzywanych metod HTTP"
    expression  = "not http.request.method in {\"GET\" \"HEAD\" \"POST\" \"PUT\" \"PATCH\" \"DELETE\" \"OPTIONS\"}"
    action      = "block"
    enabled     = true
  }]
}

# Limit zapytań (plan Free: jedna reguła, okno 10 s): 100 zapytań na 10 s z jednego IP do api.
resource "cloudflare_ruleset" "rate_limit" {
  zone_id = local.zone_id
  name    = "goatcash: limit zapytan"
  kind    = "zone"
  phase   = "http_ratelimit"

  rules = [{
    description = "api: 100 zapytan / 10 s na IP"
    expression  = "(http.host eq \"api.goatcash.app\")"
    action      = "block"
    enabled     = true
    ratelimit = {
      characteristics     = ["cf.colo.id", "ip.src"]
      period              = 10
      requests_per_period = 100
      mitigation_timeout  = 10
    }
  }]
}

# Kopie pgBackRest (roadmapa E3, zakres 5). Darmowy limit R2: 10 GB.
resource "cloudflare_r2_bucket" "backups" {
  account_id = var.account_id
  name       = "goatcash-staging-backups"
  location   = "EEUR"
}

output "origin_certificate" {
  description = "Certyfikat Origin CA (publiczny): zapisz do infra/tls/origin.pem."
  value       = cloudflare_origin_ca_certificate.staging.certificate
}
