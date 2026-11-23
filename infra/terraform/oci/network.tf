# Sieć staging (roadmapa E3, zakres prac 1; ADR-0007 punkt 3):
# - podsieć publiczna: serwer platformy (A1) i executor (mikro-VM z zarezerwowanym IP);
# - podsieć prywatna: bez publicznych IP i bez trasy do internetu (usługi wewnętrzne);
# - Security List podsieci publicznej: przychodzący tylko ICMP „fragmentation needed” (MTU);
#   ruch aplikacji dopuszczają grupy NSG przypięte do maszyn:
#     platform: TCP 443 wyłącznie z zakresów Cloudflare,
#     executor: brak jakiegokolwiek ruchu przychodzącego (ADR-0006);
# - port 22 nie jest otwarty nigdzie: administracja przez Tailscale (decyzja D5).

resource "oci_core_vcn" "staging" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "goatcash-staging"
  dns_label      = "goatcash"
}

# OCI tworzy dla każdej VCN domyślną Security List z SSH 22 z internetu. Nasze podsieci
# jej nie używają, ale przejmujemy ją i zostawiamy bez reguł (obrona w głąb).
resource "oci_core_default_security_list" "staging" {
  manage_default_resource_id = oci_core_vcn.staging.default_security_list_id
  display_name               = "goatcash-staging-default-pusta"
}

resource "oci_core_internet_gateway" "staging" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.staging.id
  display_name   = "goatcash-staging-igw"
  enabled        = true
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.staging.id
  display_name   = "goatcash-staging-public"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.staging.id
  }
}

resource "oci_core_route_table" "private" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.staging.id
  display_name   = "goatcash-staging-private"
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.staging.id
  display_name   = "goatcash-staging-public"

  egress_security_rules {
    description = "Ruch wychodzący (aktualizacje, GHCR, R2, Grafana, Tailscale)"
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    description = "ICMP 3/4 (Path MTU Discovery); bez tego połączenia TCP mogą się zawieszać"
    source      = "0.0.0.0/0"
    protocol    = "1"

    icmp_options {
      type = 3
      code = 4
    }
  }
}

resource "oci_core_security_list" "private" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.staging.id
  display_name   = "goatcash-staging-private"

  egress_security_rules {
    description = "Ruch tylko wewnątrz VCN"
    destination = var.vcn_cidr
    protocol    = "all"
  }

  ingress_security_rules {
    description = "Ruch tylko z wnętrza VCN"
    source      = var.vcn_cidr
    protocol    = "all"
  }
}

resource "oci_core_subnet" "public" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.staging.id
  cidr_block        = cidrsubnet(var.vcn_cidr, 8, 1)
  display_name      = "goatcash-staging-public"
  dns_label         = "public"
  route_table_id    = oci_core_route_table.public.id
  security_list_ids = [oci_core_security_list.public.id]
}

resource "oci_core_subnet" "private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.staging.id
  cidr_block                 = cidrsubnet(var.vcn_cidr, 8, 2)
  display_name               = "goatcash-staging-private"
  dns_label                  = "private"
  prohibit_public_ip_on_vnic = true
  route_table_id             = oci_core_route_table.private.id
  security_list_ids          = [oci_core_security_list.private.id]
}

resource "oci_core_network_security_group" "platform" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.staging.id
  display_name   = "goatcash-staging-platform"
}

resource "oci_core_network_security_group_security_rule" "platform_https_from_cloudflare" {
  for_each = toset(local.cloudflare_ipv4)

  network_security_group_id = oci_core_network_security_group.platform.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source_type               = "CIDR_BLOCK"
  source                    = each.value
  description               = "HTTPS tylko z Cloudflare (${each.value})"

  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}

resource "oci_core_network_security_group_security_rule" "platform_egress" {
  network_security_group_id = oci_core_network_security_group.platform.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"
  description               = "Ruch wychodzący platformy"
}

# Executor: bez reguł przychodzących (ADR-0006). Tylko ruch wychodzący (giełdy, Tailscale).
resource "oci_core_network_security_group" "executor" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.staging.id
  display_name   = "goatcash-staging-executor"
}

resource "oci_core_network_security_group_security_rule" "executor_egress" {
  network_security_group_id = oci_core_network_security_group.executor.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"
  description               = "Ruch wychodzący executora"
}
