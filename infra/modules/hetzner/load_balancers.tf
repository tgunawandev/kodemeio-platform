# =============================================================================
# Load Balancers
# =============================================================================

resource "hcloud_load_balancer" "lbs" {
  for_each           = var.load_balancers
  name               = "${var.resource_prefix}-${each.key}"
  load_balancer_type = each.value.type
  location           = coalesce(each.value.location, var.location)

  algorithm {
    type = each.value.algorithm
  }

  labels = merge(
    {
      managed_by  = "terraform"
      environment = var.environment
      project     = var.resource_prefix
    },
    each.value.labels
  )
}

# Load Balancer Targets
resource "hcloud_load_balancer_target" "targets" {
  for_each = {
    for item in flatten([
      for lb_key, lb in var.load_balancers : [
        for target in lb.targets : {
          key            = "${lb_key}-${target.server_name}"
          lb_key         = lb_key
          server_name    = target.server_name
          use_private_ip = target.use_private_ip
        }
      ]
    ]) : item.key => item
  }

  type             = "server"
  load_balancer_id = hcloud_load_balancer.lbs[each.value.lb_key].id
  server_id        = hcloud_server.servers[each.value.server_name].id
  use_private_ip   = each.value.use_private_ip
}

# Load Balancer Services
resource "hcloud_load_balancer_service" "services" {
  for_each = {
    for item in flatten([
      for lb_key, lb in var.load_balancers : [
        for svc in lb.services : {
          key              = "${lb_key}-${svc.protocol}-${svc.listen_port}"
          lb_key           = lb_key
          protocol         = svc.protocol
          listen_port      = svc.listen_port
          destination_port = svc.destination_port
          health_check     = svc.health_check
        }
      ]
    ]) : item.key => item
  }

  load_balancer_id = hcloud_load_balancer.lbs[each.value.lb_key].id
  protocol         = each.value.protocol
  listen_port      = each.value.listen_port
  destination_port = each.value.destination_port

  dynamic "health_check" {
    for_each = each.value.health_check != null ? [each.value.health_check] : []
    content {
      protocol = health_check.value.protocol
      port     = health_check.value.port
      interval = health_check.value.interval
      timeout  = health_check.value.timeout
      retries  = health_check.value.retries

      dynamic "http" {
        for_each = health_check.value.http != null ? [health_check.value.http] : []
        content {
          path         = http.value.path
          status_codes = http.value.status_codes
        }
      }
    }
  }
}
