# Maszyny staging (roadmapa E3, zakres prac 1; ADR-0007 punkt 1: wszystko w Always Free).
# - A1 2 OCPU / 12 GB (jedna naraz: limit 1500 OCPU-h miesięcznie) + dysk startowy 50 GB
#   + wolumen danych 100 GB (Docker i dane na /srv/goatcash, montuje Ansible);
# - mikro-VM AMD (executor, ADR-0006) + dysk startowy 50 GB + zarezerwowany publiczny IP
#   (biała lista IP w kluczach giełd od E14).
# Pierwsze uruchomienie (cloud-init): Tailscale z jednorazowym kluczem (tailscale.tf), dalej
# Ansible przez Tailscale. Portu 22 z internetu nie ma (NSG, D5).

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

locals {
  ad = data.oci_identity_availability_domains.ads.availability_domains[0].name
}

data "oci_core_images" "ubuntu_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

data "oci_core_images" "ubuntu_amd" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.E2.1.Micro"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "platform" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad
  display_name        = "goatcash-staging"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = 2
    memory_in_gbs = 12
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_arm.images[0].id
    boot_volume_size_in_gbs = 50
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
    hostname_label   = "staging"
    nsg_ids          = [oci_core_network_security_group.platform.id]
  }

  metadata = {
    ssh_authorized_keys = trimspace(file("${path.module}/../../ssh/goatcash_staging_ci.pub"))
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
      tailscale_auth_key = tailscale_tailnet_key.platform.key
      hostname           = "goatcash-staging"
      tags               = "tag:goatcash-server"
    }))
  }

  lifecycle {
    # Nowszy obraz Ubuntu w OCI nie może sam wymusić odtworzenia serwera (aktualizacje
    # bezpieczeństwa robi unattended-upgrades); klucz Tailscale jest jednorazowy przy starcie.
    ignore_changes = [source_details[0].source_id, metadata["user_data"]]
  }
}

resource "oci_core_volume" "data" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad
  display_name        = "goatcash-staging-data"
  size_in_gbs         = 100
}

resource "oci_core_volume_attachment" "data" {
  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.platform.id
  volume_id       = oci_core_volume.data.id
  device          = "/dev/oracleoci/oraclevdb"
}

resource "oci_core_instance" "executor" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad
  display_name        = "goatcash-staging-executor"
  shape               = "VM.Standard.E2.1.Micro"

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_amd.images[0].id
    boot_volume_size_in_gbs = 50
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = false
    hostname_label   = "executor"
    nsg_ids          = [oci_core_network_security_group.executor.id]
  }

  metadata = {
    ssh_authorized_keys = trimspace(file("${path.module}/../../ssh/goatcash_staging_ci.pub"))
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
      tailscale_auth_key = tailscale_tailnet_key.executor.key
      hostname           = "goatcash-executor"
      tags               = "tag:goatcash-executor"
    }))
  }

  lifecycle {
    ignore_changes = [source_details[0].source_id, metadata["user_data"]]
  }
}

# Zarezerwowany publiczny IP executora: stały adres do białych list kluczy giełd (ADR-0006).
data "oci_core_vnic_attachments" "executor" {
  compartment_id = var.compartment_ocid
  instance_id    = oci_core_instance.executor.id
}

data "oci_core_private_ips" "executor" {
  vnic_id = data.oci_core_vnic_attachments.executor.vnic_attachments[0].vnic_id
}

resource "oci_core_public_ip" "executor" {
  compartment_id = var.compartment_ocid
  display_name   = "goatcash-staging-executor"
  lifetime       = "RESERVED"
  private_ip_id  = data.oci_core_private_ips.executor.private_ips[0].id
}
