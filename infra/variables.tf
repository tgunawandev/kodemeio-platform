# =============================================================================
# Root Variables — passed through to cloudflare and hetzner modules
# =============================================================================

# =============================================================================
# Shared
# =============================================================================

variable "environment" {
  description = "Environment name (prod, staging, dev)"
  type        = string
  default     = "prod"
}

# =============================================================================
# Cloudflare Credentials
# =============================================================================

variable "cloudflare_api_token" {
  description = "Cloudflare API Token with zone:edit and account:read permissions"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_name" {
  description = "Cloudflare account name (as shown in the dashboard)"
  type        = string
}

# =============================================================================
# Hetzner Cloud Credentials
# =============================================================================

variable "hcloud_token" {
  description = "Hetzner Cloud API token (read/write)"
  type        = string
  sensitive   = true
}

# =============================================================================
# Hetzner — Server Defaults
# =============================================================================

variable "location" {
  description = "Default Hetzner datacenter location (fsn1, nbg1, hel1, ash, hil)"
  type        = string
  default     = "fsn1"
}

variable "resource_prefix" {
  description = "Prefix applied to all Hetzner resource names"
  type        = string
  default     = "kodemeio"
}

variable "domain" {
  description = "Primary domain used in cloud-init and server labels"
  type        = string
  default     = "kodeme.io"
}

variable "timezone" {
  description = "Server timezone (timedatectl format)"
  type        = string
  default     = "Asia/Jakarta"
}

variable "swap_size_mb" {
  description = "Swap file size in MB applied by cloud-init"
  type        = number
  default     = 4096
}

variable "ssh_port" {
  description = "SSH port configured by cloud-init (change from 22 for security)"
  type        = number
  default     = 22
}

# =============================================================================
# Hetzner — SSH Keys
# =============================================================================

variable "ssh_keys" {
  description = "Map of SSH public keys to upload to Hetzner"
  type = map(object({
    public_key = string
  }))
  default = {}
}

# =============================================================================
# Hetzner — Networks
# =============================================================================

variable "networks" {
  description = "Private networks for inter-server communication"
  type = map(object({
    ip_range = string
    subnets = list(object({
      ip_range     = string
      type         = string
      network_zone = string
    }))
  }))
  default = {}
}

# =============================================================================
# Hetzner — Servers
# =============================================================================

variable "servers" {
  description = "Map of Hetzner servers to create"
  type = map(object({
    server_type       = string
    image             = string
    location          = optional(string)
    ssh_keys          = optional(list(string), [])
    labels            = optional(map(string), {})
    firewall_ids      = optional(list(string), [])
    network           = optional(string)
    user_data         = optional(string)
    backups           = optional(bool, false)
    delete_protection = optional(bool, false)
    volumes = optional(list(object({
      name   = string
      size   = number
      format = optional(string, "ext4")
    })), [])
  }))
  default = {}
}

# =============================================================================
# Hetzner — Firewalls
# =============================================================================

variable "firewalls" {
  description = "Hetzner firewall rule sets"
  type = map(object({
    labels = optional(map(string), {})
    rules = list(object({
      direction       = string
      protocol        = string
      port            = optional(string)
      description     = optional(string)
      source_ips      = optional(list(string), [])
      destination_ips = optional(list(string), [])
    }))
  }))
  default = {}
}

# =============================================================================
# Hetzner — Load Balancers
# =============================================================================

variable "load_balancers" {
  description = "Hetzner Load Balancers (optional — for multi-server or HA setups)"
  type = map(object({
    type      = string
    location  = optional(string)
    algorithm = optional(string, "round_robin")
    labels    = optional(map(string), {})
    targets = optional(list(object({
      type           = string
      server_name    = string
      use_private_ip = optional(bool, false)
    })), [])
    services = optional(list(object({
      protocol         = string
      listen_port      = number
      destination_port = number
      health_check = optional(object({
        protocol = string
        port     = number
        interval = optional(number, 15)
        timeout  = optional(number, 10)
        retries  = optional(number, 3)
        http = optional(object({
          path         = optional(string, "/")
          status_codes = optional(list(string), ["2??", "3??"])
        }))
      }))
    })), [])
  }))
  default = {}
}

# =============================================================================
# Hetzner — Placement Groups
# =============================================================================

variable "placement_groups" {
  description = "Placement groups to spread servers across physical hosts"
  type = map(object({
    type   = optional(string, "spread")
    labels = optional(map(string), {})
  }))
  default = {}
}

# =============================================================================
# Cloudflare — Zones
# =============================================================================

variable "zones" {
  description = "Cloudflare DNS zones to manage"
  type = map(object({
    plan       = string
    jump_start = optional(bool, false)
    paused     = optional(bool, false)
    type       = optional(string, "full")
  }))
  default = {}
}

# =============================================================================
# Cloudflare — DNS Records
# =============================================================================

variable "dns_records" {
  description = "DNS records to create within managed zones"
  type = map(object({
    zone_name = string
    name      = string
    type      = string
    value     = string
    ttl       = optional(number, 1)
    proxied   = optional(bool, true)
    priority  = optional(number)
    comment   = optional(string)
  }))
  default = {}
}

# =============================================================================
# Cloudflare — Tunnels
# =============================================================================

variable "tunnels" {
  description = "Cloudflare Tunnels (Argo) to create"
  type = map(object({
    secret = string
    config = object({
      ingress_rules = list(object({
        hostname = optional(string)
        path     = optional(string)
        service  = string
      }))
    })
  }))
  default   = {}
  sensitive = true
}

# =============================================================================
# Cloudflare — SSL/TLS
# =============================================================================

variable "origin_certificates" {
  description = "Cloudflare Origin CA certificates"
  type = map(object({
    zone_name          = string
    csr                = string
    hostnames          = list(string)
    request_type       = optional(string, "origin-rsa")
    requested_validity = optional(number, 5475)
  }))
  default = {}
}

variable "authenticated_origin_pulls" {
  description = "Zone names to enable Authenticated Origin Pulls on"
  type        = set(string)
  default     = []
}

# =============================================================================
# Cloudflare — Firewall
# =============================================================================

variable "firewall_rules" {
  description = "Cloudflare WAF custom firewall rules"
  type = map(object({
    zone_name   = string
    description = string
    expression  = string
    action      = string
    priority    = optional(number)
    enabled     = optional(bool, true)
  }))
  default = {}
}

variable "ip_access_rules" {
  description = "IP-level allow/block/challenge rules"
  type = map(object({
    zone_name = string
    mode      = string
    ip        = string
    notes     = optional(string)
  }))
  default = {}
}

variable "rate_limits" {
  description = "Rate limiting rules per zone"
  type = map(object({
    zone_name   = string
    threshold   = number
    period      = number
    action_mode = string
    match_url   = string
    description = optional(string)
  }))
  default = {}
}

# =============================================================================
# Cloudflare — Caching
# =============================================================================

variable "cache_rules" {
  description = "Cache rules (edge TTL, browser TTL overrides)"
  type = map(object({
    zone_name   = string
    description = string
    expression  = string
    action      = string
    edge_ttl    = optional(number)
    browser_ttl = optional(number)
  }))
  default = {}
}

variable "page_rules" {
  description = "Cloudflare Page Rules (legacy)"
  type = map(object({
    zone_name = string
    target    = string
    actions   = map(string)
    priority  = optional(number)
    status    = optional(string, "active")
  }))
  default = {}
}

# =============================================================================
# Cloudflare — Workers
# =============================================================================

variable "workers" {
  description = "Cloudflare Worker scripts"
  type = map(object({
    content = string
    module  = optional(bool, false)
    logpush = optional(bool, false)
    bindings = optional(list(object({
      name = string
      type = string
      text = optional(string)
    })), [])
  }))
  default = {}
}

variable "worker_routes" {
  description = "Route patterns that trigger Workers"
  type = map(object({
    zone_name   = string
    pattern     = string
    worker_name = string
  }))
  default = {}
}

variable "kv_namespaces" {
  description = "Workers KV namespaces"
  type = map(object({
    title = string
  }))
  default = {}
}

# =============================================================================
# Cloudflare — R2 Storage
# =============================================================================

variable "r2_buckets" {
  description = "Cloudflare R2 object storage buckets"
  type = map(object({
    name     = string
    location = optional(string, "WEUR")
  }))
  default = {}
}

# =============================================================================
# Cloudflare — Email Routing
# =============================================================================

variable "email_routing_enabled" {
  description = "Zone names to enable Cloudflare Email Routing on"
  type        = set(string)
  default     = []
}

variable "email_routing_rules" {
  description = "Email forwarding rules"
  type = map(object({
    zone_name    = string
    name         = string
    enabled      = optional(bool, true)
    match_type   = string
    match_value  = string
    action_type  = string
    action_value = list(string)
  }))
  default = {}
}

variable "email_routing_catch_all" {
  description = "Catch-all email routing rules (one per zone)"
  type = map(object({
    zone_name    = string
    enabled      = optional(bool, true)
    action_type  = string
    action_value = list(string)
  }))
  default = {}
}

# =============================================================================
# Cloudflare — Redirect Rules
# =============================================================================

variable "redirect_lists" {
  description = "Bulk redirect lists (source → target URL mappings)"
  type = map(object({
    name        = string
    description = optional(string)
    items = list(object({
      source_url            = string
      target_url            = string
      status_code           = optional(number, 301)
      include_subdomains    = optional(bool, false)
      subpath_matching      = optional(bool, false)
      preserve_query_string = optional(bool, false)
      preserve_path_suffix  = optional(bool, false)
    }))
  }))
  default = {}
}

variable "redirect_rules" {
  description = "Bulk redirect ruleset entries that reference redirect_lists"
  type = map(object({
    name     = string
    list_key = string
    enabled  = optional(bool, true)
  }))
  default = {}
}
