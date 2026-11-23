terraform {
  required_version = ">= 1.17"
}

variable "nieuzywana" {
  description = "Zadeklarowana i nieużywana."
  type        = string
  default     = "x"
}
