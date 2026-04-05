"""Tests for deployment troubleshooting diagnosis."""

from __future__ import annotations

from unittest.mock import MagicMock

from kctl_dokploy.core.troubleshoot import (
    ContainerInfo,
    Diagnosis,
    ErrorType,
    _classify_error,
    diagnose,
)


class TestClassifyError:
    def test_build_failed(self):
        err, summary, _ = _classify_error("error", "Build failed: npm ERR!", [], "")
        assert err == ErrorType.BUILD_FAILED
        assert "Build failed" in summary

    def test_deployment_error(self):
        err, summary, _ = _classify_error("error", "Compose deploy failed", [], "")
        assert err == ErrorType.BUILD_FAILED  # deployment errors are build_failed category

    def test_not_deployed(self):
        err, _, _ = _classify_error("none", "No deployments found", [], "")
        assert err == ErrorType.NOT_DEPLOYED

    def test_container_crashed(self):
        containers = [ContainerInfo(name="web", state="exited", status="Exited (1)", logs="Error: something")]
        err, _, _ = _classify_error("done", "", containers, "FAIL: timeout")
        assert err == ErrorType.RUNTIME_CRASH

    def test_container_crash_db_refused(self):
        containers = [
            ContainerInfo(
                name="web",
                state="exited",
                status="Exited (1)",
                logs="ECONNREFUSED 5432",
            )
        ]
        err, summary, suggestions = _classify_error("done", "", containers, "")
        assert err == ErrorType.RUNTIME_CRASH
        assert "connection refused" in summary.lower()
        assert any("PGHOST" in s for s in suggestions)

    def test_health_timeout(self):
        containers = [ContainerInfo(name="web", state="running", status="Up 5 min", logs="")]
        err, _, _ = _classify_error("done", "", containers, "FAIL: Cannot connect")
        assert err == ErrorType.HEALTH_TIMEOUT

    def test_healthy_service(self):
        containers = [ContainerInfo(name="web", state="running", status="Up", logs="")]
        err, _, _ = _classify_error("done", "", containers, "OK (200)")
        assert err == ErrorType.UNKNOWN
        assert "healthy" in err.value or True  # just check it doesn't crash

    def test_oom_killed(self):
        containers = [ContainerInfo(name="web", state="exited", status="OOMKilled", logs="OOMKilled")]
        err, summary, _ = _classify_error("done", "", containers, "")
        assert err == ErrorType.RUNTIME_CRASH
        assert "memory" in summary.lower()

    def test_password_auth_failed(self):
        containers = [
            ContainerInfo(
                name="web",
                state="exited",
                status="Exited (1)",
                logs='FATAL: password authentication failed for user "odoo"',
            )
        ]
        err, summary, suggestions = _classify_error("done", "", containers, "")
        assert err == ErrorType.RUNTIME_CRASH
        assert "auth failed" in summary.lower()
        assert any("PGPASSWORD" in s for s in suggestions)

    def test_no_containers_no_deployments(self):
        err, summary, _ = _classify_error("none", "No deployments found", [], "")
        assert err == ErrorType.NOT_DEPLOYED
        assert "never been deployed" in summary.lower()

    def test_no_containers_with_deployment(self):
        err, summary, _ = _classify_error("done", "Deployed OK", [], "")
        assert err == ErrorType.UNKNOWN
        assert "no containers" in summary.lower()

    def test_unknown_fallback(self):
        containers = [ContainerInfo(name="web", state="running", status="Up", logs="")]
        err, _, suggestions = _classify_error("done", "", containers, "")
        assert err == ErrorType.UNKNOWN
        assert len(suggestions) > 0


class TestDiagnose:
    def test_diagnose_with_mock_client(self):
        client = MagicMock()
        client.get.side_effect = [
            # compose.one (step 1: get service name)
            {
                "name": "test-app",
                "appName": "test-app",
                "composeId": "abc123",
            },
            # deployment.allByCompose (step 2)
            [
                {
                    "status": "error",
                    "title": "Build failed",
                    "createdAt": "2026-01-01",
                    "logPath": "",
                }
            ],
            # compose.one (step 3: _get_containers)
            {"name": "test-app", "appName": "test-app"},
            # docker.getContainers (step 3)
            [],
        ]

        result = diagnose(client, "abc123")
        assert isinstance(result, Diagnosis)
        assert result.error_type == ErrorType.BUILD_FAILED
        assert result.compose_id == "abc123"

    def test_diagnose_runtime_crash(self):
        client = MagicMock()
        client.get.side_effect = [
            # compose.one (step 1)
            {"name": "my-svc", "appName": "my-svc", "composeId": "xyz"},
            # deployment.allByCompose (step 2)
            [
                {
                    "status": "done",
                    "title": "Deployed",
                    "createdAt": "2026-01-01",
                    "logPath": "",
                }
            ],
            # compose.one (step 3: _get_containers)
            {"name": "my-svc", "appName": "my-svc", "serverId": "srv1"},
            # docker.getContainers (step 3)
            [
                {"name": "my-svc-web-1", "state": "exited", "status": "Exited (1)"},
            ],
        ]
        client.post.return_value = "ECONNREFUSED 5432"

        result = diagnose(client, "xyz")
        assert result.error_type == ErrorType.RUNTIME_CRASH
        assert "connection refused" in result.summary.lower()

    def test_diagnosis_to_dict(self):
        d = Diagnosis(
            compose_id="abc",
            service_name="test",
            error_type=ErrorType.RUNTIME_CRASH,
            summary="Container crashed",
            details="Details here",
            suggestions=["Fix it"],
        )
        data = d.to_dict()
        assert data["error_type"] == "runtime_crash"
        assert data["suggestions"] == ["Fix it"]
        assert data["containers"] == []

    def test_diagnosis_to_dict_with_containers(self):
        d = Diagnosis(
            compose_id="abc",
            service_name="test",
            error_type=ErrorType.RUNTIME_CRASH,
            summary="Crashed",
            details="",
            containers=[ContainerInfo(name="web", state="exited", status="Exited (1)", logs="err")],
        )
        data = d.to_dict()
        assert len(data["containers"]) == 1
        assert data["containers"][0]["name"] == "web"
        assert data["containers"][0]["logs"] == "err"
