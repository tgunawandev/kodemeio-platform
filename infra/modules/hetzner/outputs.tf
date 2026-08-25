# =============================================================================
# Outputs
# =============================================================================

# Locations
output "locations" {
  description = "Available Hetzner locations"
  value       = { for loc in data.hcloud_locations.all.locations : loc.name => loc.description }
}

# Server Types
output "server_types" {
  description = "Available server types"
  value = {
    for st in data.hcloud_server_types.all.server_types : st.name => {
      cores       = st.cores
      memory      = st.memory
      disk        = st.disk
      description = st.description
    }
  }
}

# Servers
output "servers" {
  description = "Created servers"
  value = {
    for key, srv in hcloud_server.servers : key => {
      id       = srv.id
      name     = srv.name
      ipv4     = srv.ipv4_address
      ipv6     = srv.ipv6_address
      status   = srv.status
      type     = srv.server_type
      location = srv.location
      labels   = srv.labels
    }
  }
}

# Networks
output "networks" {
  description = "Created networks"
  value = {
    for key, net in hcloud_network.networks : key => {
      id       = net.id
      name     = net.name
      ip_range = net.ip_range
    }
  }
}

# Firewalls
output "firewalls" {
  description = "Created firewalls"
  value = {
    for key, fw in hcloud_firewall.firewalls : key => {
      id   = fw.id
      name = fw.name
    }
  }
}

# SSH Keys
output "ssh_keys" {
  description = "Created SSH keys"
  value = {
    for key, sk in hcloud_ssh_key.keys : key => {
      id          = sk.id
      name        = sk.name
      fingerprint = sk.fingerprint
    }
  }
}

# Load Balancers
output "load_balancers" {
  description = "Created load balancers"
  value = {
    for key, lb in hcloud_load_balancer.lbs : key => {
      id   = lb.id
      name = lb.name
      ipv4 = lb.ipv4
      ipv6 = lb.ipv6
      type = lb.load_balancer_type
    }
  }
}

# Volumes
output "volumes" {
  description = "Created volumes"
  value = {
    for key, vol in hcloud_volume.volumes : key => {
      id       = vol.id
      name     = vol.name
      size     = vol.size
      location = vol.location
    }
  }
}

# Placement Groups
output "placement_groups" {
  description = "Created placement groups"
  value = {
    for key, pg in hcloud_placement_group.groups : key => {
      id   = pg.id
      name = pg.name
      type = pg.type
    }
  }
}
