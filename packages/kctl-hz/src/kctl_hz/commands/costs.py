"""Cost estimation commands."""

from __future__ import annotations

import typer

from kctl_hetzner.core.callbacks import AppContext

app = typer.Typer(help="Estimate monthly infrastructure costs.")


def _parse_price(price_str: str | None) -> float:
    """Safely parse a price string to float."""
    if not price_str:
        return 0.0
    try:
        return float(price_str)
    except (ValueError, TypeError):
        return 0.0


@app.command()
def estimate(ctx: typer.Context) -> None:
    """Estimate monthly costs for all Hetzner resources."""
    c: AppContext = ctx.obj

    servers = c.client.get_all("/servers", "servers")
    volumes = c.client.get_all("/volumes", "volumes")
    floating_ips = c.client.get_all("/floating_ips", "floating_ips")
    load_balancers = c.client.get_all("/load_balancers", "load_balancers")

    # Servers cost
    server_cost = 0.0
    server_rows = []
    for s in servers:
        stype = s.get("server_type", {})
        prices = stype.get("prices", [])
        monthly = _parse_price(prices[0].get("price_monthly", {}).get("gross", "0")) if prices else 0.0
        server_cost += monthly
        server_rows.append([s.get("name", ""), stype.get("name", ""), f"{monthly:.2f}"])

    # Volumes cost: EUR 0.0440 per GB/month
    volume_cost = 0.0
    volume_rows = []
    for v in volumes:
        size = v.get("size", 0)
        monthly = size * 0.0440
        volume_cost += monthly
        volume_rows.append([v.get("name", ""), f"{size} GB", f"{monthly:.2f}"])

    # Floating IPs: EUR 4.00/month each
    floating_ip_cost = len(floating_ips) * 4.00

    # Load balancers cost
    lb_cost = 0.0
    lb_rows = []
    for lb in load_balancers:
        lb_type = lb.get("load_balancer_type", {})
        prices = lb_type.get("prices", [])
        monthly = _parse_price(prices[0].get("price_monthly", {}).get("gross", "0")) if prices else 0.0
        lb_cost += monthly
        lb_rows.append([lb.get("name", ""), lb_type.get("name", ""), f"{monthly:.2f}"])

    total = server_cost + volume_cost + floating_ip_cost + lb_cost

    cost_data = {
        "servers": {"count": len(servers), "monthly_eur": round(server_cost, 2)},
        "volumes": {"count": len(volumes), "monthly_eur": round(volume_cost, 2)},
        "floating_ips": {"count": len(floating_ips), "monthly_eur": round(floating_ip_cost, 2)},
        "load_balancers": {"count": len(load_balancers), "monthly_eur": round(lb_cost, 2)},
        "total_monthly_eur": round(total, 2),
    }

    sections = [
        (
            "Summary",
            [
                ("Servers", f"{len(servers)} = EUR {server_cost:.2f}/mo"),
                ("Volumes", f"{len(volumes)} = EUR {volume_cost:.2f}/mo"),
                ("Floating IPs", f"{len(floating_ips)} = EUR {floating_ip_cost:.2f}/mo"),
                ("Load Balancers", f"{len(load_balancers)} = EUR {lb_cost:.2f}/mo"),
                ("TOTAL", f"EUR {total:.2f}/mo"),
            ],
        )
    ]

    if server_rows:
        sections.append(
            (
                "Server Breakdown",
                [(row[0], f"{row[1]} = EUR {row[2]}/mo") for row in server_rows],
            )
        )

    if volume_rows:
        sections.append(
            (
                "Volume Breakdown",
                [(row[0], f"{row[1]} = EUR {row[2]}/mo") for row in volume_rows],
            )
        )

    if lb_rows:
        sections.append(
            (
                "Load Balancer Breakdown",
                [(row[0], f"{row[1]} = EUR {row[2]}/mo") for row in lb_rows],
            )
        )

    c.output.detail("Cost Estimate (Monthly)", sections, data_for_json=cost_data)
