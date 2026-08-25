# Cloudflare Outputs

output "account_id" {
  description = "Cloudflare account ID"
  value       = local.account_id
}

output "environment" {
  description = "Current environment"
  value       = var.environment
}

# Zones
output "zone_ids" {
  description = "Map of zone names to zone IDs"
  value = {
    for name, zone in cloudflare_zone.zones : name => zone.id
  }
}

output "zone_name_servers" {
  description = "Nameservers for each zone"
  value = {
    for name, zone in cloudflare_zone.zones : name => zone.name_servers
  }
}

# DNS Records
output "dns_records" {
  description = "Created DNS records"
  value = {
    for key, record in cloudflare_record.records : key => {
      id       = record.id
      hostname = record.hostname
      type     = record.type
      value    = record.value
      proxied  = record.proxied
    }
  }
}

# Tunnels
output "tunnels" {
  description = "Created tunnels"
  value = {
    for name, tunnel in cloudflare_tunnel.tunnels : name => {
      id    = tunnel.id
      name  = tunnel.name
      cname = "${tunnel.id}.cfargotunnel.com"
      token = tunnel.tunnel_token
    }
  }
  sensitive = true
}

# SSL Certificates
output "origin_certificates" {
  description = "Origin CA certificates"
  value = {
    for key, cert in cloudflare_origin_ca_certificate.certs : key => {
      id          = cert.id
      certificate = cert.certificate
      expires_on  = cert.expires_on
    }
  }
  sensitive = true
}

# Workers
output "worker_scripts" {
  description = "Deployed worker scripts"
  value = {
    for name, worker in cloudflare_worker_script.workers : name => {
      name = worker.name
    }
  }
}

output "kv_namespaces" {
  description = "KV namespace IDs"
  value = {
    for key, ns in cloudflare_workers_kv_namespace.namespaces : key => {
      id    = ns.id
      title = ns.title
    }
  }
}

# R2
output "r2_buckets" {
  description = "R2 bucket details"
  value = {
    for key, bucket in cloudflare_r2_bucket.buckets : key => {
      name     = bucket.name
      location = bucket.location
    }
  }
}

# Redirects
output "redirect_lists" {
  description = "Bulk redirect list IDs"
  value = {
    for key, list in cloudflare_list.redirect_lists : key => {
      id   = list.id
      name = list.name
    }
  }
}
