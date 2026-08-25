# =============================================================================
# Cloud-Init Templates
# =============================================================================

locals {
  # Base cloud-init for all servers
  cloud_init_base = templatefile("${path.module}/templates/cloud-init-base.yml", {
    timezone     = var.timezone
    swap_size_mb = var.swap_size_mb
    ssh_port     = var.ssh_port
  })

  # Dokploy server cloud-init
  cloud_init_dokploy = templatefile("${path.module}/templates/cloud-init-dokploy.yml", {
    timezone     = var.timezone
    swap_size_mb = var.swap_size_mb
    ssh_port     = var.ssh_port
    domain       = var.domain
  })

  # Database server cloud-init
  cloud_init_database = templatefile("${path.module}/templates/cloud-init-database.yml", {
    timezone     = var.timezone
    swap_size_mb = var.swap_size_mb
    ssh_port     = var.ssh_port
  })
}
