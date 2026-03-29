"""Tests for kctl_common.doctor_base."""

from __future__ import annotations

from kctl_common.doctor_base import CheckResult, DockerCheck, GitCheck, PythonVersionCheck, UvCheck, run_doctor
from kctl_common.output import Output


class FakePassCheck:
    name = "fake-pass"

    def run(self) -> CheckResult:
        return CheckResult(name=self.name, status="ok", message="All good")


class FakeFailCheck:
    name = "fake-fail"

    def run(self) -> CheckResult:
        return CheckResult(name=self.name, status="fail", message="Broken", fix_command="fix-it")


class FakeWarnCheck:
    name = "fake-warn"

    def run(self) -> CheckResult:
        return CheckResult(name=self.name, status="warn", message="Hmm")


class TestCheckResult:
    def test_ok(self) -> None:
        r = CheckResult(name="test", status="ok", message="fine")
        assert r.status == "ok" and r.fix_command is None

    def test_fail_with_fix(self) -> None:
        r = CheckResult(name="test", status="fail", message="broken", fix_command="fix-it")
        assert r.fix_command == "fix-it"


class TestRunDoctor:
    def test_all_pass(self) -> None:
        assert run_doctor([FakePassCheck()], Output(json_mode=True)) is True

    def test_fail_returns_false(self) -> None:
        assert run_doctor([FakePassCheck(), FakeFailCheck()], Output(json_mode=True)) is False

    def test_warn_still_passes(self) -> None:
        assert run_doctor([FakeWarnCheck()], Output(json_mode=True)) is True

    def test_mixed(self) -> None:
        assert run_doctor([FakePassCheck(), FakeWarnCheck(), FakeFailCheck()], Output(json_mode=True)) is False


class TestBuiltInChecks:
    def test_python_version(self) -> None:
        r = PythonVersionCheck().run()
        assert r.status == "ok" and "3." in r.message

    def test_git(self) -> None:
        assert GitCheck().run().status in ("ok", "fail")

    def test_uv(self) -> None:
        assert UvCheck().run().status in ("ok", "fail")

    def test_docker(self) -> None:
        assert DockerCheck().run().status in ("ok", "fail")
