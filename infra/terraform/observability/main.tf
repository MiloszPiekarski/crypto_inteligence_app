# Obserwowalność staging (roadmapa E3, zakres prac 6; F-03; ADR-0007): Grafana Cloud
# (punkty kontaktowe e-mail i Telegram, polityka powiadomień, alerty, pulpity, Synthetic
# Monitoring /v1/health co minutę) i Better Stack (/v1/health co 3 min: plan Free nie ma
# 1 min; odstępstwo w ADR-0007, „co minutę” zapewnia Grafana Synthetic Monitoring).
# Dane logowania ze zmiennych środowiska właściciela (.env.local): GRAFANA_URL, GRAFANA_AUTH,
# GRAFANA_SM_URL, GRAFANA_SM_ACCESS_TOKEN; TF_VAR_* dla Telegrama, e-maila i Better Stack.
terraform {
  required_version = ">= 1.17"

  required_providers {
    grafana = {
      source  = "grafana/grafana"
      version = "= 4.53.0"
    }
    betteruptime = {
      source  = "BetterStackHQ/better-uptime"
      version = "= 0.22.4"
    }
  }

  backend "oci" {
    bucket = "goatcash-tfstate"
    key    = "staging/observability.tfstate"
    region = "eu-amsterdam-1"
  }
}

provider "grafana" {}

provider "betteruptime" {
  api_token = var.betterstack_api_token
}

variable "alert_email" {
  description = "Adres e-mail na alerty (TF_VAR_alert_email; nie w repo)."
  type        = string
  sensitive   = true
}

variable "telegram_bot_token" {
  description = "Token bota @goatcash_alerts_bot (TF_VAR_telegram_bot_token)."
  type        = string
  sensitive   = true
}

variable "telegram_chat_id" {
  description = "chat_id właściciela (TF_VAR_telegram_chat_id)."
  type        = string
  sensitive   = true
}

variable "betterstack_api_token" {
  description = "Token Better Stack (Incidents, Read & write; TF_VAR_betterstack_api_token)."
  type        = string
  sensitive   = true
}

variable "prometheus_datasource_uid" {
  description = "UID źródła danych Prometheus w Grafana Cloud."
  type        = string
  default     = "grafanacloud-prom"
}

locals {
  health_url = "https://api.goatcash.app/v1/health"
}

resource "grafana_folder" "staging" {
  title = "GoatCash staging"
}

resource "grafana_contact_point" "owner" {
  name = "goatcash-wlasciciel"

  email {
    addresses = [var.alert_email]
  }

  telegram {
    token   = var.telegram_bot_token
    chat_id = var.telegram_chat_id
  }
}

resource "grafana_notification_policy" "root" {
  contact_point   = grafana_contact_point.owner.name
  group_by        = ["alertname"]
  group_wait      = "30s"
  group_interval  = "1m"
  repeat_interval = "4h"
}

# Alerty (roadmapa E3: dysk > 80%, brak kopii > 26 h, CPU > 90% przez 15 min; F-03:
# zatrzymany kontener). Ocena co 60 s, krótkie „for”, żeby powiadomienie przyszło < 5 min.
resource "grafana_rule_group" "infra" {
  name             = "goatcash-staging-infra"
  folder_uid       = grafana_folder.staging.uid
  interval_seconds = 60

  rule {
    name      = "Dysk zajety > 80%"
    condition = "C"
    for       = "1m"
    annotations = {
      summary = "Na serwerze staging zajęte ponad 80% miejsca na dysku."
    }
    data {
      ref_id         = "A"
      datasource_uid = var.prometheus_datasource_uid
      relative_time_range {
        from = 300
        to   = 0
      }
      model = jsonencode({
        refId   = "A"
        instant = true
        range   = false
        expr    = "max(100 * (1 - node_filesystem_avail_bytes{fstype!~\"tmpfs|overlay|squashfs\"} / node_filesystem_size_bytes{fstype!~\"tmpfs|overlay|squashfs\"}))"
      })
    }
    data {
      ref_id         = "C"
      datasource_uid = "__expr__"
      relative_time_range {
        from = 0
        to   = 0
      }
      model = jsonencode({ refId = "C", type = "threshold", expression = "A", conditions = [{ evaluator = { type = "gt", params = [80] } }] })
    }
  }

  rule {
    name      = "CPU > 90% przez 15 min"
    condition = "C"
    for       = "15m"
    annotations = {
      summary = "CPU serwera staging powyżej 90% od 15 minut."
    }
    data {
      ref_id         = "A"
      datasource_uid = var.prometheus_datasource_uid
      relative_time_range {
        from = 600
        to   = 0
      }
      model = jsonencode({
        refId   = "A"
        instant = true
        range   = false
        expr    = "100 * (1 - avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])))"
      })
    }
    data {
      ref_id         = "C"
      datasource_uid = "__expr__"
      relative_time_range {
        from = 0
        to   = 0
      }
      model = jsonencode({ refId = "C", type = "threshold", expression = "A", conditions = [{ evaluator = { type = "gt", params = [90] } }] })
    }
  }

  rule {
    name           = "Brak kopii > 26 h"
    condition      = "C"
    for            = "0s"
    no_data_state  = "Alerting"
    exec_err_state = "Alerting"
    annotations = {
      summary = "Ostatnia udana kopia pgBackRest starsza niż 26 h (albo brak metryki)."
    }
    data {
      ref_id         = "A"
      datasource_uid = var.prometheus_datasource_uid
      relative_time_range {
        from = 600
        to   = 0
      }
      model = jsonencode({
        refId   = "A"
        instant = true
        range   = false
        expr    = "(time() - max(goatcash_backup_last_success_timestamp_seconds)) / 3600"
      })
    }
    data {
      ref_id         = "C"
      datasource_uid = "__expr__"
      relative_time_range {
        from = 0
        to   = 0
      }
      model = jsonencode({ refId = "C", type = "threshold", expression = "A", conditions = [{ evaluator = { type = "gt", params = [26] } }] })
    }
  }

  # Retencja 30 dni (pgbackrest.conf, repo1-retention-full-type=time): pgBackRest zostawia
  # najnowszą pełną kopię starszą niż 30 dni, a pełne są co tydzień, więc najstarsza kopia
  # ma najwyżej ok. 37 dni. Próg 39 dni: zapas na godzinę kopii i opóźnienie timera.
  rule {
    name           = "Retencja kopii nie dziala"
    condition      = "C"
    for            = "0s"
    no_data_state  = "Alerting"
    exec_err_state = "Alerting"
    annotations = {
      summary = "Najstarsza kopia pgBackRest starsza niż 39 dni (retencja 30 dni nie usuwa kopii) albo brak metryki."
    }
    data {
      ref_id         = "A"
      datasource_uid = var.prometheus_datasource_uid
      relative_time_range {
        from = 600
        to   = 0
      }
      model = jsonencode({
        refId   = "A"
        instant = true
        range   = false
        expr    = "(time() - min(goatcash_backup_oldest_timestamp_seconds)) / 86400"
      })
    }
    data {
      ref_id         = "C"
      datasource_uid = "__expr__"
      relative_time_range {
        from = 0
        to   = 0
      }
      model = jsonencode({ refId = "C", type = "threshold", expression = "A", conditions = [{ evaluator = { type = "gt", params = [39] } }] })
    }
  }

  rule {
    name           = "Kontener bazy lub Valkey niedostepny"
    condition      = "C"
    for            = "1m"
    no_data_state  = "Alerting"
    exec_err_state = "Alerting"
    annotations = {
      summary = "postgres-exporter albo valkey-exporter nie widzi swojej usługi (pg_up/redis_up = 0)."
    }
    data {
      ref_id         = "A"
      datasource_uid = var.prometheus_datasource_uid
      relative_time_range {
        from = 300
        to   = 0
      }
      model = jsonencode({ refId = "A", instant = true, range = false, expr = "(min(pg_up) or vector(0)) * (min(redis_up) or vector(0))" })
    }
    data {
      ref_id         = "C"
      datasource_uid = "__expr__"
      relative_time_range {
        from = 0
        to   = 0
      }
      model = jsonencode({ refId = "C", type = "threshold", expression = "A", conditions = [{ evaluator = { type = "lt", params = [1] } }] })
    }
  }

  rule {
    name           = "API /v1/health niedostepne (Synthetic Monitoring)"
    condition      = "C"
    for            = "2m"
    no_data_state  = "Alerting"
    exec_err_state = "Alerting"
    annotations = {
      summary = "Sprawdzenie Grafana Synthetic Monitoring /v1/health nie przechodzi od 2 minut."
    }
    data {
      ref_id         = "A"
      datasource_uid = var.prometheus_datasource_uid
      relative_time_range {
        from = 300
        to   = 0
      }
      model = jsonencode({ refId = "A", instant = true, range = false, expr = "min(probe_success{job=\"goatcash-staging-health\"})" })
    }
    data {
      ref_id         = "C"
      datasource_uid = "__expr__"
      relative_time_range {
        from = 0
        to   = 0
      }
      model = jsonencode({ refId = "C", type = "threshold", expression = "A", conditions = [{ evaluator = { type = "lt", params = [1] } }] })
    }
  }
}

# Pulpity (roadmapa E3: serwer, Postgres, Valkey).
resource "grafana_dashboard" "staging" {
  for_each    = toset(["serwer", "postgres", "valkey"])
  folder      = grafana_folder.staging.uid
  config_json = file("${path.module}/dashboards/${each.key}.json")
}

# /v1/health co minutę z jednej lokalizacji (ok. 43 200 testów miesięcznie, limit Free: 100 tys.).
data "grafana_synthetic_monitoring_probes" "all" {}

resource "grafana_synthetic_monitoring_check" "health" {
  job       = "goatcash-staging-health"
  target    = local.health_url
  enabled   = true
  frequency = 60000
  timeout   = 10000
  probes    = [data.grafana_synthetic_monitoring_probes.all.probes.Frankfurt]
  labels = {
    environment = "staging"
  }

  settings {
    http {
      method                          = "GET"
      valid_status_codes              = [200]
      fail_if_body_not_matches_regexp = ["\"status\":\"ok\""]
    }
  }
}

# Zewnętrzny, niezależny od Grafany sprawdzacz (plan Free: co 3 min, powiadomienie e-mail).
resource "betteruptime_monitor" "health" {
  url                = local.health_url
  monitor_type       = "status"
  check_frequency    = 180
  email              = true
  pronounceable_name = "GoatCash staging /v1/health"
}
