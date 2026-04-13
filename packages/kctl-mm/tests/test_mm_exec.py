from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from kctl_lib.exceptions import CommandError
from kctl_lib.ssh import SSHResult
from kctl_mm.core.mm_exec import MMExec


@pytest.fixture
def mm() -> MMExec:
    return MMExec(
        ssh_host="kod-prod-02",
        ssh_user="root",
        compose_path="/etc/dokploy/compose/kod-mattermost/code/docker-compose.prod.yml",
        compose_service="mattermost",
    )


def test_mmctl_json_success(mm: MMExec) -> None:
    payload = [{"id": "u1", "username": "admin"}]
    with patch("kctl_mm.core.mm_exec.ssh_run") as m:
        m.return_value = SSHResult(returncode=0, stdout=json.dumps(payload), stderr="")
        assert mm.mmctl_json(["user", "list"]) == payload
        cmd = m.call_args.kwargs["command"]
        assert "docker compose -f" in cmd
        assert "exec -T mattermost mmctl --local --format json user list" in cmd


def test_mmctl_nonzero_raises(mm: MMExec) -> None:
    with patch("kctl_mm.core.mm_exec.ssh_run") as m:
        m.return_value = SSHResult(returncode=2, stdout="", stderr="boom")
        with pytest.raises(CommandError, match="boom"):
            mm.mmctl_json(["user", "list"])


def test_docker_compose_calls_ssh(mm: MMExec) -> None:
    with patch("kctl_mm.core.mm_exec.ssh_run") as m:
        m.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
        result = mm.docker_compose(["ps"])
        assert result.stdout == "ok"
        assert "docker compose -f" in m.call_args.kwargs["command"]
        assert " ps" in m.call_args.kwargs["command"]
