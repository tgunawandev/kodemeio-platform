# =============================================================================
# Variables
# =============================================================================

variable "hcloud_token" {
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Environment name (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Default Hetzner location"
  type        = string
  default     = "fsn1"
}

variable "resource_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "kodemeio"
}

# =============================================================================
# SSH Keys
# =============================================================================

variable "ssh_keys" {
  description = "Map of SSH keys to manage"
  type = map(object({
    public_key = string
  }))
  default = {}
}

# =============================================================================
# Networks
# =============================================================================

variable "networks" {
  description = "Map of private networks"
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
# Servers
# =============================================================================

variable "servers" {
  description = "Map of servers to create"
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
# Firewalls
# =============================================================================

variable "firewalls" {
  description = "Map of firewalls"
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
# Load Balancers
# =============================================================================

variable "load_balancers" {
  description = "Map of load balancers"
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
# Placement Groups
# =============================================================================

variable "placement_groups" {
  description = "Map of placement groups"
  type = map(object({
    type   = optional(string, "spread")
    labels = optional(map(string), {})
  }))
  default = {}
}

# =============================================================================
# Cloud-Init & Server Defaults
# =============================================================================

variable "domain" {
  description = "Primary domain"
  type        = string
  default     = "kodeme.io"
}

variable "timezone" {
  description = "Server timezone"
  type        = string
  default     = "Asia/Jakarta"
}

variable "swap_size_mb" {
  description = "Swap file size in MB"
  type        = number
  default     = 4096
}

variable "ssh_port" {
  description = "SSH port (changed from 22 for security)"
  type        = number
  default     = 22
}
