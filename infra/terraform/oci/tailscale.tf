# Jednorazowe klucze Tailscale dla serwerów (ADR-0007 punkt 3). Provider uwierzytelnia się
# klientem OAuth `goatcash-terraform` (Auth Keys: Write, tagi serwerów) ze zmiennych
# TAILSCALE_OAUTH_CLIENT_ID i TAILSCALE_OAUTH_CLIENT_SECRET (.env.local właściciela).
# Dzięki temu odtworzenie od zera (F-01) nie wymaga ręcznego tworzenia kluczy.
provider "tailscale" {
  scopes = ["auth_keys"]
}

resource "tailscale_tailnet_key" "platform" {
  reusable      = false
  ephemeral     = false
  preauthorized = true
  expiry        = 3600
  tags          = ["tag:goatcash-server"]
  description   = "goatcash-staging cloud-init"
}

resource "tailscale_tailnet_key" "executor" {
  reusable      = false
  ephemeral     = false
  preauthorized = true
  expiry        = 3600
  tags          = ["tag:goatcash-executor"]
  description   = "goatcash-executor cloud-init"
}
