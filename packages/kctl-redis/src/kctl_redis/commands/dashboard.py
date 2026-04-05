"""Dashboard command for kctl-redis."""

from __future__ import annotations

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis system overview.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def overview(ctx: typer.Context) -> None:
    """Show Redis system overview dashboard."""
    if ctx.invoked_subcommand is not None:
        return

    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    all_info = c.info()

    if app_ctx.json_mode:
        out.json(
            {
                "server": {
                    "version": all_info.get("redis_version", "?"),
                    "uptime_days": all_info.get("uptime_in_days", 0),
                    "role": all_info.get("role", "?"),
                },
                "memory": {
                    "used_human": all_info.get("used_memory_human", "?"),
                    "max_human": all_info.get("maxmemory_human", "?"),
                    "fragmentation": all_info.get("mem_fragmentation_ratio", 0),
                },
                "clients": {
                    "connected": all_info.get("connected_clients", 0),
                    "blocked": all_info.get("blocked_clients", 0),
                },
                "stats": {
                    "ops_per_sec": all_info.get("instantaneous_ops_per_sec", 0),
                    "keyspace_hits": all_info.get("keyspace_hits", 0),
                    "keyspace_misses": all_info.get("keyspace_misses", 0),
                    "evicted_keys": all_info.get("evicted_keys", 0),
                },
                "persistence": {
                    "rdb_last_save_time": all_info.get("rdb_last_save_time", 0),
                    "rdb_last_bgsave_status": all_info.get("rdb_last_bgsave_status", "?"),
                    "aof_enabled": all_info.get("aof_enabled", 0),
                },
            }
        )
    else:
        out.header("Redis Dashboard")
        out.text(f"  Version:  {all_info.get('redis_version', '?')}")
        out.text(f"  Uptime:   {all_info.get('uptime_in_days', '?')} days")
        out.text(f"  Role:     {all_info.get('role', '?')}")
        out.text("")
        out.text("  --- Memory ---")
        out.text(f"  Used:           {all_info.get('used_memory_human', '?')}")
        out.text(f"  Max:            {all_info.get('maxmemory_human', '?')}")
        out.text(f"  Fragmentation:  {all_info.get('mem_fragmentation_ratio', '?')}")
        out.text("")
        out.text("  --- Clients ---")
        out.text(f"  Connected:  {all_info.get('connected_clients', 0)}")
        out.text(f"  Blocked:    {all_info.get('blocked_clients', 0)}")
        out.text("")
        hits = all_info.get("keyspace_hits", 0)
        misses = all_info.get("keyspace_misses", 0)
        total = hits + misses
        hit_ratio = f"{hits / total * 100:.1f}%" if total > 0 else "N/A"
        out.text("  --- Performance ---")
        out.text(f"  Ops/sec:    {all_info.get('instantaneous_ops_per_sec', 0)}")
        out.text(f"  Hit ratio:  {hit_ratio}")
        out.text(f"  Evicted:    {all_info.get('evicted_keys', 0)}")
        out.text("")
        out.text("  --- Persistence ---")
        out.text(f"  RDB last save:  {all_info.get('rdb_last_bgsave_status', '?')}")
        out.text(f"  AOF enabled:    {'yes' if all_info.get('aof_enabled', 0) else 'no'}")

    app_ctx.close()
