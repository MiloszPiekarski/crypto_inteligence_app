# Zakresy IPv4 Cloudflare: jedyne źródła ruchu na 443 do serwera platformy (roadmapa E3,
# ADR-0007: „tylko 443 z adresów Cloudflare”). Źródło: https://api.cloudflare.com/client/v4/ips
# (stan z 23.11.2026, etag 38f79d050aa027e3be3865e495dcc9bc). Zgodność z bieżącą listą
# sprawdza make iac-lint (scripts/check_cloudflare_ips.py); zmiana listy = PR.
locals {
  cloudflare_ipv4 = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
  ]
}
