# =============================================================================
# Root Outputs
# =============================================================================
# Key values surfaced after apply. Sensitive outputs (tokens, certs) are
# marked sensitive=true — retrieve them with:
#   terraform output -raw <name>
# =============================================================================

# =============================================================================
# Hetzner — Servers
# =============================================================================

output "server_ips" {
  description = "Public IPv4 addresses of all Hetzner servers (key = server name)"
  value = {
    for name, srv in module.hetzner.servers : name => srv.ipv4
  }
}

output "server_ipv6" {
  description = "Public IPv6 addresses of all Hetzner servers (key = server name)"
  value = {
    for name, srv in module.hetzner.servers : name => srv.ipv6
  }
}

output "servers" {
  description = "Full server details from the Hetzner module"
  value       = module.hetzner.servers
}

# =============================================================================
# Hetzner — Networks
# =============================================================================

output "network_ids" {
  description = "Private network IDs (key = network name)"
  value = {
    for name, net in module.hetzner.networks : name => net.id
  }
}

output "networks" {
  description = "Full network details from the Hetzner module"
  value       = module.hetzner.networks
}

# =============================================================================
# Hetzner — Firewalls
# =============================================================================

output "firewall_ids" {
  description = "Hetzner firewall IDs (key = firewall name)"
  value = {
    for name, fw in module.hetzner.firewalls : name => fw.id
  }
}

# =============================================================================
# Hetzner — Load Balancers
# =============================================================================

output "load_balancer_ips" {
  description = "Load balancer public IPs (key = lb name)"
  value = {
    for name, lb in module.hetzner.load_balancers : name => lb.ipv4
  }
}

# =============================================================================
# Hetzner — SSH Keys
# =============================================================================

output "ssh_key_fingerprints" {
  description = "Fingerprints of uploaded SSH keys (key = key name)"
  value = {
    for name, sk in module.hetzner.ssh_keys : name => sk.fingerprint
  }
}

# =============================================================================
# Cloudflare — Zones
# =============================================================================

output "zone_ids" {
  description = "Cloudflare zone IDs (key = zone name, e.g. 'kodeme.io')"
  value       = module.cloudflare.zone_ids
}

output "zone_name_servers" {
  description = "Nameservers assigned to each Cloudflare zone"
  value       = module.cloudflare.zone_name_servers
}

output "cloudflare_account_id" {
  description = "Cloudflare account ID resolved from account name"
  value       = module.cloudflare.account_id
}

# =============================================================================
# Cloudflare — DNS Records
# =============================================================================

output "dns_records" {
  description = "Created DNS records with hostname and proxied status"
  value       = module.cloudflare.dns_records
}

# =============================================================================
# Cloudflare — R2 Storage
# =============================================================================

output "r2_buckets" {
  description = "R2 bucket names and locations"
  value       = module.cloudflare.r2_buckets
}

# =============================================================================
# Cloudflare — Workers & KV
# =============================================================================

output "worker_scripts" {
  description = "Deployed Cloudflare Worker script names"
  value       = module.cloudflare.worker_scripts
}

output "kv_namespace_ids" {
  description = "Workers KV namespace IDs (key = namespace key)"
  value       = module.cloudflare.kv_namespaces
}

# =============================================================================
# Cloudflare — Tunnels (sensitive)
# =============================================================================

output "tunnels" {
  description = "Cloudflare Tunnel IDs and CNAME records (sensitive — contains tokens)"
  value       = module.cloudflare.tunnels
  sensitive   = true
}

# =============================================================================
# Cloudflare — SSL Certificates (sensitive)
# =============================================================================

output "origin_certificates" {
  description = "Cloudflare Origin CA certificate details (sensitive — contains private key material)"
  value       = module.cloudflare.origin_certificates
  sensitive   = true
}

# =============================================================================
# Cross-module — Redirect List IDs
# =============================================================================

output "redirect_lists" {
  description = "Cloudflare bulk redirect list IDs"
  value       = module.cloudflare.redirect_lists
}

# =============================================================================
# Environment
# =============================================================================

output "environment" {
  description = "Active environment (prod / staging / dev)"
  value       = var.environment
}
