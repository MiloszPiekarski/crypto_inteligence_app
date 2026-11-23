output "vcn_id" {
  description = "OCID sieci VCN staging."
  value       = oci_core_vcn.staging.id
}

output "public_subnet_id" {
  description = "OCID podsieci publicznej (platforma, executor)."
  value       = oci_core_subnet.public.id
}

output "private_subnet_id" {
  description = "OCID podsieci prywatnej (bez dostępu do internetu)."
  value       = oci_core_subnet.private.id
}

output "nsg_platform_id" {
  description = "OCID grupy NSG platformy (443 tylko z Cloudflare)."
  value       = oci_core_network_security_group.platform.id
}

output "nsg_executor_id" {
  description = "OCID grupy NSG executora (bez ruchu przychodzącego)."
  value       = oci_core_network_security_group.executor.id
}
