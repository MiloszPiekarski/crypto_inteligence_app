# Konfiguracja tflint dla wszystkich modułów infra/terraform (make iac-lint, bramka G3).
config {
  call_module_type = "none"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
