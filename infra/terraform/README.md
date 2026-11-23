# infra/terraform

Terraform: Oracle i Cloudflare (etap E3, ADR-0007).

Moduły główne: `oci/` i `cloudflare/` (osobne stany). Kontrola statyczna: `make iac-lint`
(terraform fmt i validate, tflint z `.tflint.hcl`, trivy config); narzędzia w przypiętych
wersjach instaluje `make tools`. Operacje zmieniające zasoby (apply, destroy) uruchamia
tylko właściciel, po zgodzie (CLAUDE.md, „Prawdziwe zasoby”).
