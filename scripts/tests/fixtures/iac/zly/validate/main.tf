terraform {
  required_version = ">= 1.17"
}

output "x" {
  description = "Odwołanie do niezadeklarowanej zmiennej."
  value       = var.brak
}
