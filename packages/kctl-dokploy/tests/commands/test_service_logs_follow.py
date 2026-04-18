"""Unit tests for the --follow addition to `kctl-dokploy compose service-logs`."""

from __future__ import annotations

from kctl_dokploy.commands.compose import _build_docker_logs_cmd


class TestBuildDockerLogsCmd:
    """The helper must produce the correct argv for local vs remote, follow vs snapshot."""

    def test_local_snapshot(self) -> None:
        cmd = _build_docker_logs_cmd("my-container", tail=200, server_ip="", follow=False)
        assert cmd == ["docker", "logs", "--tail", "200", "my-container"]

    def test_local_follow(self) -> None:
        cmd = _build_docker_logs_cmd("my-container", tail=100, server_ip="", follow=True)
        # -f must appear, and the container name must stay at the end.
        assert cmd[0] == "docker"
        assert "-f" in cmd
        assert cmd[-1] == "my-container"
        assert "--tail" in cmd and "100" in cmd

    def test_remote_snapshot(self) -> None:
        cmd = _build_docker_logs_cmd("web-1", tail=50, server_ip="10.0.0.2", follow=False)
        assert cmd[0] == "ssh"
        assert "root@10.0.0.2" in cmd
        # Remote command is a single shell-quoted arg at the end.
        remote = cmd[-1]
        assert "docker logs --tail 50 web-1" in remote
        assert "-f" not in remote

    def test_remote_follow(self) -> None:
        cmd = _build_docker_logs_cmd("web-1", tail=200, server_ip="10.0.0.2", follow=True)
        assert cmd[0] == "ssh"
        remote = cmd[-1]
        assert "docker logs --tail 200 -f web-1" in remote

    def test_remote_has_ssh_safety_flags(self) -> None:
        cmd = _build_docker_logs_cmd("web-1", tail=50, server_ip="10.0.0.2", follow=False)
        # SSH robustness: bounded connect timeout + accept-new so first connection works.
        assert "ConnectTimeout=10" in cmd
        assert "StrictHostKeyChecking=accept-new" in cmd
