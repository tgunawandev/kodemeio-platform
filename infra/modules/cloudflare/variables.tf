# Cloudflare Variables

variable "cloudflare_api_token" {
  description = "Cloudflare API Token with appropriate permissions"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_name" {
  description = "Cloudflare account name"
  type        = string
}

variable "environment" {
  description = "Environment name (prod, staging)"
  type        = string
  default     = "prod"
}

# ─── Zones ────────────────────────────────────────────────────────────────────

variable "zones" {
  description = "Map of DNS zones to manage"
  type = map(object({
    plan       = string
    jump_start = optional(bool, false)
    paused     = optional(bool, false)
    type       = optional(string, "full")
  }))
  default = {}
}

# ─── DNS Records ──────────────────────────────────────────────────────────────

variable "dns_records" {
  description = "Map of DNS records"
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

# ─── Tunnels ──────────────────────────────────────────────────────────────────

variable "tunnels" {
  description = "Cloudflare Tunnels to create"
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

# ─── SSL/TLS ──────────────────────────────────────────────────────────────────

variable "origin_certificates" {
  description = "Origin CA certificates to create"
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
  description = "Zones to enable authenticated origin pulls"
  type        = set(string)
  default     = []
}

# ─── Firewall ─────────────────────────────────────────────────────────────────

variable "firewall_rules" {
  description = "Custom firewall rules"
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
  description = "IP-level access rules"
  type = map(object({
    zone_name = string
    mode      = string
    ip        = string
    notes     = optional(string)
  }))
  default = {}
}

variable "rate_limits" {
  description = "Rate limiting rules"
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

# ─── Caching ──────────────────────────────────────────────────────────────────

variable "cache_rules" {
  description = "Cache rules"
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
  description = "Page rules"
  type = map(object({
    zone_name = string
    target    = string
    actions   = map(string)
    priority  = optional(number)
    status    = optional(string, "active")
  }))
  default = {}
}

# ─── Workers ──────────────────────────────────────────────────────────────────

variable "workers" {
  description = "Worker scripts"
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
  description = "Worker routes"
  type = map(object({
    zone_name   = string
    pattern     = string
    worker_name = string
  }))
  default = {}
}

variable "kv_namespaces" {
  description = "KV namespaces"
  type = map(object({
    title = string
  }))
  default = {}
}

# ─── R2 Storage ───────────────────────────────────────────────────────────────

variable "r2_buckets" {
  description = "R2 storage buckets"
  type = map(object({
    name     = string
    location = optional(string, "WEUR")
  }))
  default = {}
}

# ─── Email Routing ────────────────────────────────────────────────────────────

variable "email_routing_enabled" {
  description = "Zones to enable email routing on"
  type        = set(string)
  default     = []
}

variable "email_routing_rules" {
  description = "Email routing rules"
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
  description = "Catch-all email routing rules"
  type = map(object({
    zone_name    = string
    enabled      = optional(bool, true)
    action_type  = string
    action_value = list(string)
  }))
  default = {}
}

# ─── Redirect Rules ──────────────────────────────────────────────────────────

variable "redirect_lists" {
  description = "Bulk redirect lists"
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
  description = "Bulk redirect rules"
  type = map(object({
    name     = string
    list_key = string
    enabled  = optional(bool, true)
  }))
  default = {}
}
