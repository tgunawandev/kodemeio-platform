"""Tests for kctl_lib.docker."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kctl_lib.docker import DockerManager


@pytest.fixture()
def compose_file(tmp_path: Path) -> Path:
    cf = tmp_path / "docker-compose.yml"
    cf.write_text("version: '3'\nservices:\n  web:\n    image: nginx\n")
    return cf


@pytest.fixture()
def manager(compose_file: Path) -> DockerManager:
    return DockerManager(compose_file=compose_file, project_name="test-project")


class TestDockerManagerInit:
    def test_stores_compose_file(self, compose_file: Path) -> None:
        dm = DockerManager(compose_file=compose_file, project_name="myproject")
        assert dm.compose_file == compose_file

    def test_stores_project_name(self, compose_file: Path) -> None:
        dm = DockerManager(compose_file=compose_file, project_name="myproject")
        assert dm.project_name == "myproject"


class TestBaseCmd:
    def test_base_cmd_structure(self, manager: DockerManager, compose_file: Path) -> None:
        cmd = manager._base_cmd()
        assert cmd[0] == "docker"
        assert cmd[1] == "compose"
        assert "-f" in cmd
        assert str(compose_file) in cmd
        assert "-p" in cmd
        assert "test-project" in cmd

    def test_base_cmd_order(self, manager: DockerManager, compose_file: Path) -> None:
        cmd = manager._base_cmd()
        assert cmd == ["docker", "compose", "-f", str(compose_file), "-p", "test-project"]


class TestUp:
    def test_up_default_detached(self, manager: DockerManager, compose_file: Path) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.up()
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "up" in cmd
            assert "-d" in cmd

    def test_up_with_services(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.up(services=["web", "db"])
            cmd = mock_run.call_args[0][0]
            assert "web" in cmd
            assert "db" in cmd

    def test_up_no_detach(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.up(detach=False)
            cmd = mock_run.call_args[0][0]
            assert "-d" not in cmd

    def test_up_uses_compose_parent_as_cwd(self, manager: DockerManager, compose_file: Path) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.up()
            kwargs = mock_run.call_args[1]
            assert kwargs.get("cwd") == compose_file.parent


class TestDown:
    def test_down_basic(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.down()
            cmd = mock_run.call_args[0][0]
            assert "down" in cmd
            assert "-v" not in cmd

    def test_down_with_volumes(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.down(volumes=True)
            cmd = mock_run.call_args[0][0]
            assert "-v" in cmd


class TestPs:
    def test_ps_returns_list_of_dicts(self, manager: DockerManager) -> None:
        container = {"Name": "web", "State": "running"}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(container) + "\n"
        with patch("kctl_lib.docker.run_quiet", return_value=mock_result):
            result = manager.ps()
        assert isinstance(result, list)
        assert result[0] == container

    def test_ps_multiple_containers(self, manager: DockerManager) -> None:
        containers = [{"Name": "web", "State": "running"}, {"Name": "db", "State": "running"}]
        stdout = "\n".join(json.dumps(c) for c in containers) + "\n"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = stdout
        with patch("kctl_lib.docker.run_quiet", return_value=mock_result):
            result = manager.ps()
        assert len(result) == 2
        assert result[0]["Name"] == "web"
        assert result[1]["Name"] == "db"

    def test_ps_returns_empty_on_failure(self, manager: DockerManager) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("kctl_lib.docker.run_quiet", return_value=mock_result):
            result = manager.ps()
        assert result == []

    def test_ps_returns_empty_on_blank_output(self, manager: DockerManager) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "   "
        with patch("kctl_lib.docker.run_quiet", return_value=mock_result):
            result = manager.ps()
        assert result == []

    def test_ps_skips_invalid_json_lines(self, manager: DockerManager) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"Name": "web"}\nnot-json\n{"Name": "db"}\n'
        with patch("kctl_lib.docker.run_quiet", return_value=mock_result):
            result = manager.ps()
        assert len(result) == 2


class TestRestart:
    def test_restart_all(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.restart()
            cmd = mock_run.call_args[0][0]
            assert "restart" in cmd

    def test_restart_specific_service(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.restart(service="web")
            cmd = mock_run.call_args[0][0]
            assert "restart" in cmd
            assert "web" in cmd


class TestLogs:
    def test_logs_default(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.logs()
            cmd = mock_run.call_args[0][0]
            assert "logs" in cmd
            assert "--tail" in cmd
            assert "100" in cmd

    def test_logs_with_service(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.logs(service="web")
            cmd = mock_run.call_args[0][0]
            assert "web" in cmd

    def test_logs_follow(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.logs(follow=True)
            cmd = mock_run.call_args[0][0]
            assert "-f" in cmd

    def test_logs_no_capture(self, manager: DockerManager) -> None:
        with patch("kctl_lib.docker.run") as mock_run:
            manager.logs()
            kwargs = mock_run.call_args[1]
            assert kwargs.get("capture") is False


class TestImageSize:
    def test_image_size_returns_list(self, manager: DockerManager) -> None:
        image = {"Repository": "nginx", "Tag": "latest", "Size": "142MB"}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(image) + "\n"
        with patch("kctl_lib.docker.run_quiet", return_value=mock_result):
            result = manager.image_size()
        assert isinstance(result, list)
        assert result[0] == image

    def test_image_size_empty_on_failure(self, manager: DockerManager) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("kctl_lib.docker.run_quiet", return_value=mock_result):
            result = manager.image_size()
        assert result == []

    def test_image_size_skips_invalid_json(self, manager: DockerManager) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"Repository": "nginx"}\nbad-line\n'
        with patch("kctl_lib.docker.run_quiet", return_value=mock_result):
            result = manager.image_size()
        assert len(result) == 1
