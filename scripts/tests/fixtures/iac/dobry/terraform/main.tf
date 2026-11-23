terraform {
  required_version = ">= 1.17"
}

variable "nazwa" {
  description = "Nazwa testowa (wzorzec dla make iac-lint)."
  type        = string
  default     = "goatcash"
}

output "nazwa" {
  description = "Zwraca nazwę."
  value       = var.nazwa
}
