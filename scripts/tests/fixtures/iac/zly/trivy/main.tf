# Celowo błędna konfiguracja: SSH (22) otwarty dla całego internetu.
# Wzorzec dla autotestu trivy config w make iac-lint (musi zostać odrzucony).
resource "aws_security_group_rule" "ssh_z_internetu" {
  type              = "ingress"
  description       = "SSH z dowolnego adresu"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = "sg-00000000"
}
