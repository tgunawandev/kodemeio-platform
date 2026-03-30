"""Tests for exception hierarchy."""

from __future__ import annotations

from kctl_claw.core.exceptions import (
    ConfigError,
    DockerError,
    GatewayError,
    KctlError,
    NotFoundError,
    ValidationError,
)


def test_hierarchy():
    """All exceptions inherit from KctlError."""
    assert issubclass(ConfigError, KctlError)
    assert issubclass(GatewayError, KctlError)
    assert issubclass(DockerError, KctlError)
    assert issubclass(NotFoundError, KctlError)
    assert issubclass(ValidationError, KctlError)


def test_not_found_error_message():
    err = NotFoundError("agent", "foobot", valid_names=["kodemeiodev", "kontenosdev"])
    assert "foobot" in str(err)
    assert "kodemeiodev" in str(err)


def test_gateway_error():
    err = GatewayError(status_code=401, message="Unauthorized")
    assert "401" in str(err)
    assert "Unauthorized" in str(err)


def test_docker_error():
    err = DockerError(command="docker compose ps", returncode=1, stderr="not found")
    assert "docker compose ps" in str(err)
    assert "not found" in str(err)
