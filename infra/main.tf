# =============================================================================
# kodemeio-dokploy — Root Infrastructure
# =============================================================================
# This is a thin aggregation layer. All resource definitions live in local
# module directories; this file wires them together.
#
# Package source paths (relative to this file):
#   Cloudflare : ./modules/cloudflare/
#   Hetzner    : ./modules/hetzner/
#
# Usage:
#   terraform init
#   terraform plan -var-file="terraform.tfvars"
#   terraform apply -var-file="terraform.tfvars"
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }

  # Remote state — see backend.tf (commented out by default)
}

# =============================================================================
# Cloudflare Module
# =============================================================================
# Manages: zones, DNS records, firewall rules, SSL certificates, R2 buckets,
#          Workers, KV namespaces, email routing, redirect lists, tunnels,
#          cache rules, page rules, IP access rules, rate limits.
# =============================================================================

module "cloudflare" {
  source = "./modules/cloudflare"

  # ── Credentials ─────────────────────────────────────────────────────────────
  cloudflare_api_token    = var.cloudflare_api_token
  cloudflare_account_name = var.cloudflare_account_name

  # ── Shared ──────────────────────────────────────────────────────────────────
  environment = var.environment

  # ── Zones ───────────────────────────────────────────────────────────────────
  zones = var.zones

  # ── DNS Records ─────────────────────────────────────────────────────────────
  dns_records = var.dns_records

  # ── Tunnels ─────────────────────────────────────────────────────────────────
  tunnels = var.tunnels

  # ── SSL/TLS ─────────────────────────────────────────────────────────────────
  origin_certificates        = var.origin_certificates
  authenticated_origin_pulls = var.authenticated_origin_pulls

  # ── Firewall ────────────────────────────────────────────────────────────────
  firewall_rules  = var.firewall_rules
  ip_access_rules = var.ip_access_rules
  rate_limits     = var.rate_limits

  # ── Caching ─────────────────────────────────────────────────────────────────
  cache_rules = var.cache_rules
  page_rules  = var.page_rules

  # ── Workers ─────────────────────────────────────────────────────────────────
  workers       = var.workers
  worker_routes = var.worker_routes
  kv_namespaces = var.kv_namespaces

  # ── R2 Storage ──────────────────────────────────────────────────────────────
  r2_buckets = var.r2_buckets

  # ── Email Routing ────────────────────────────────────────────────────────────
  email_routing_enabled   = var.email_routing_enabled
  email_routing_rules     = var.email_routing_rules
  email_routing_catch_all = var.email_routing_catch_all

  # ── Redirect Rules ───────────────────────────────────────────────────────────
  redirect_lists = var.redirect_lists
  redirect_rules = var.redirect_rules
}

# =============================================================================
# Hetzner Cloud Module
# =============================================================================
# Manages: servers, networks, firewalls, SSH keys, volumes,
#          placement groups, load balancers, cloud-init templates.
# =============================================================================

module "hetzner" {
  source = "./modules/hetzner"

  # ── Credentials ─────────────────────────────────────────────────────────────
  hcloud_token = var.hcloud_token

  # ── Shared ──────────────────────────────────────────────────────────────────
  environment     = var.environment
  location        = var.location
  resource_prefix = var.resource_prefix
  domain          = var.domain
  timezone        = var.timezone
  swap_size_mb    = var.swap_size_mb
  ssh_port        = var.ssh_port

  # ── SSH Keys ────────────────────────────────────────────────────────────────
  ssh_keys = var.ssh_keys

  # ── Networks ────────────────────────────────────────────────────────────────
  networks = var.networks

  # ── Servers ─────────────────────────────────────────────────────────────────
  servers = var.servers

  # ── Firewalls ───────────────────────────────────────────────────────────────
  firewalls = var.firewalls

  # ── Load Balancers ──────────────────────────────────────────────────────────
  load_balancers = var.load_balancers

  # ── Placement Groups ────────────────────────────────────────────────────────
  placement_groups = var.placement_groups
}
