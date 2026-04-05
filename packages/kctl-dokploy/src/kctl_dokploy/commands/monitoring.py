"""Monitoring and metrics commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Monitoring, metrics, and resource usage.")


@app.command()
def containers(ctx: typer.Context) -> None:
    """Show Docker container stats (CPU, memory, network)."""
    c: AppContext = ctx.obj
    data = c.client.get("/docker.getContainers")
    container_list = data if isinstance(data, list) else data.get("containers", []) if isinstance(data, dict) else []
    if not isinstance(container_list, list):
        container_list = []
    rows = []
    for ct in container_list:
        name = ct.get("name", ct.get("Names", ""))
        if isinstance(name, list):
            name = name[0] if name else ""
        image = ct.get("image", ct.get("Image", ""))
        state = ct.get("state", ct.get("State", "unknown"))
        status = ct.get("status", ct.get("Status", ""))
        ports = ct.get("ports", ct.get("Ports", ""))
        if isinstance(ports, list):
            ports = ", ".join(str(p) for p in ports[:3])
        rows.append([str(name), str(image), str(state), str(status), str(ports)])
    c.output.table(
        "Docker Containers",
        [
            ("Name", "cyan"),
            ("Image", ""),
            ("State", ""),
            ("Status", "dim"),
            ("Ports", "dim"),
        ],
        rows,
        data_for_json=data if isinstance(data, (list, dict)) else {"containers": container_list},
    )


@app.command()
def resources(ctx: typer.Context) -> None:
    """Show system resource usage (disk, CPU, RAM)."""
    c: AppContext = ctx.obj
    try:
        data = c.client.get("/server.getServerMetrics", params={"serverId": ""})
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    cpu = data.get("cpuUsage", data.get("cpu", "-"))
    memory = data.get("memoryUsage", data.get("memory", "-"))
    disk = data.get("diskUsage", data.get("disk", "-"))
    total_memory = data.get("totalMemory", data.get("memoryTotal", "-"))
    total_disk = data.get("totalDisk", data.get("diskTotal", "-"))
    sections = [
        (
            "System Resources",
            [
                ("CPU Usage", str(cpu)),
                ("Memory Usage", str(memory)),
                ("Total Memory", str(total_memory)),
                ("Disk Usage", str(disk)),
                ("Total Disk", str(total_disk)),
            ],
        ),
    ]
    c.output.detail("System Resources", sections, data_for_json=data)


@app.command("server-stats")
def server_stats(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Option("--server", "-s", help="Server ID (omit for main server)")] = "",
) -> None:
    """Show server monitoring statistics."""
    c: AppContext = ctx.obj
    if server_id:
        data = c.client.get("/server.one", params={"serverId": server_id})
    else:
        servers = c.client.get("/server.all")
        data = servers[0] if isinstance(servers, list) and servers else {}
    if not isinstance(data, dict):
        data = {}
    name = data.get("name", data.get("serverName", "main"))
    docker_version = data.get("dockerVersion", "-")
    os_info = data.get("os", data.get("operatingSystem", "-"))
    uptime = data.get("uptime", "-")
    containers_running = data.get("containersRunning", data.get("runningContainers", "-"))
    sections = [
        (
            f"Server: {name}",
            [
                ("Docker Version", str(docker_version)),
                ("OS", str(os_info)),
                ("Uptime", str(uptime)),
                ("Running Containers", str(containers_running)),
            ],
        ),
    ]
    c.output.detail(f"Server Stats: {name}", sections, data_for_json=data)


@app.command("container-logs")
def container_logs(
    ctx: typer.Context,
    container_name: Annotated[str, typer.Argument(help="Docker container name")],
    tail: Annotated[int, typer.Option("--tail", "-n", help="Number of lines to show")] = 100,
    server: Annotated[str | None, typer.Option("--server", "-s", help="Server name (for remote containers)")] = None,
) -> None:
    """Show logs from a Docker container."""
    c: AppContext = ctx.obj

    # Try API first
    try:
        payload: dict = {"containerId": container_name, "tail": tail}
        if server:
            # Resolve server name to serverId
            servers = c.client.get("/server.all")
            for s in servers if isinstance(servers, list) else []:
                if s.get("name") == server:
                    payload["serverId"] = s.get("serverId", "")
                    break
        data = c.client.post("/docker.getContainerLogs", json=payload)
        if c.json_mode:
            c.output.raw_json(data)
            return
        if isinstance(data, dict):
            logs = data.get("logs", data.get("data", ""))
        elif isinstance(data, str):
            logs = data
        else:
            logs = str(data)
        if isinstance(logs, list):
            logs = "\n".join(str(line) for line in logs)
        c.output.header(f"Logs: {container_name} (tail {tail})")
        c.output.text(str(logs))
    except Exception:
        # API failed — fall back to SSH for remote servers
        if server:
            try:
                servers = c.client.get("/server.all")
            except Exception:
                servers = []
            server_ip = ""
            for s in servers if isinstance(servers, list) else []:
                if s.get("name") == server:
                    server_ip = s.get("ipAddress", "")
                    break
            if server_ip:
                import subprocess

                try:
                    result = subprocess.run(
                        [
                            "ssh",
                            "-o",
                            "ConnectTimeout=5",
                            "-o",
                            "StrictHostKeyChecking=no",
                            f"root@{server_ip}",
                            f"docker logs --tail {tail} {container_name} 2>&1",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    logs = result.stdout if result.returncode == 0 else f"SSH failed: {result.stderr}"
                except (subprocess.TimeoutExpired, Exception) as e:
                    logs = f"SSH failed: {e}"
                c.output.header(f"Logs: {container_name} (tail {tail}, via SSH)")
                c.output.text(logs)
                return
        c.output.error("Failed to fetch container logs (API and SSH both failed)")
        raise typer.Exit(1)
