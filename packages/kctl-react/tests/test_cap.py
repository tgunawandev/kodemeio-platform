"""Tests for Capacitor commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from kctl_react.cli import app

runner = CliRunner()


class TestCapStatus:
    def test_status_no_capacitor(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "status"])
        assert result.exit_code == 0
        assert "0/" in result.output

    def test_status_with_capacitor(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "status"])
        assert result.exit_code == 0
        assert "1/" in result.output

    def test_status_json(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "cap", "status"])
        assert result.exit_code == 0
        for i, ch in enumerate(result.output):
            if ch == "[":
                try:
                    data = json.loads(result.output[i:])
                    sfa = next(d for d in data if d["app"] == "sfa")
                    assert sfa["capacitor"] is True
                    assert sfa["android"] is False
                    return
                except json.JSONDecodeError:
                    continue
        raise AssertionError("No valid JSON found")

    def test_status_with_android(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        (mock_monorepo / "apps" / "sfa" / "android").mkdir()
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "status"])
        assert result.exit_code == 0
        assert "yes" in result.output


class TestCapInit:
    def test_init(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "init", "sfa"])
        assert result.exit_code == 0
        assert (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").exists()
        content = (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").read_text()
        assert "io.kodeme.sfa" in content

    def test_init_custom_app_id(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "init", "sfa", "--app-id", "com.example.sfa"])
        assert result.exit_code == 0
        content = (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").read_text()
        assert "com.example.sfa" in content

    def test_init_already_configured(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "init", "sfa"])
        assert result.exit_code == 0
        assert "already configured" in result.output

    def test_init_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "init", "nonexistent"])
        assert result.exit_code == 1


class TestCapAdd:
    def test_add_no_config(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "add", "sfa", "android"])
        assert result.exit_code == 1
        assert "No capacitor.config.ts" in result.output

    def test_add_invalid_platform(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "add", "sfa", "windows"])
        assert result.exit_code == 1
        assert "android" in result.output or "ios" in result.output

    def test_add_already_exists(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        (mock_monorepo / "apps" / "sfa" / "android").mkdir()
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "add", "sfa", "android"])
        assert result.exit_code == 0
        assert "already exists" in result.output


class TestCapSync:
    def test_sync_no_config(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "sync", "sfa"])
        assert result.exit_code == 1
        assert "No Capacitor config" in result.output

    def test_sync_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "sync", "nonexistent"])
        assert result.exit_code == 1


class TestCapDoctor:
    def test_doctor_general(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "doctor"])
        assert result.exit_code == 0
        assert "node" in result.output

    def test_doctor_with_app(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "doctor", "sfa"])
        assert result.exit_code == 0
        assert "capacitor.config" in result.output

    def test_doctor_checks_java(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "doctor", "--platform", "android"])
        assert result.exit_code == 0
        assert "java" in result.output

    def test_doctor_checks_deps(self, mock_monorepo: Path) -> None:
        """Doctor with app should check @capacitor/* deps."""
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "doctor", "sfa"])
        assert result.exit_code == 0
        assert "@capacitor/core" in result.output

    def test_doctor_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "cap", "doctor"])
        assert result.exit_code == 0
        for i, ch in enumerate(result.output):
            if ch == "[":
                try:
                    data = json.loads(result.output[i:])
                    tools = [d["check"] for d in data]
                    assert "node" in tools
                    return
                except json.JSONDecodeError:
                    continue


class TestCapHelpers:
    def test_has_capacitor(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _has_capacitor

        assert _has_capacitor(mock_monorepo / "apps" / "sfa") is False
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("")
        assert _has_capacitor(mock_monorepo / "apps" / "sfa") is True

    def test_has_platform(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _has_platform

        assert _has_platform(mock_monorepo / "apps" / "sfa", "android") is False
        (mock_monorepo / "apps" / "sfa" / "android").mkdir()
        assert _has_platform(mock_monorepo / "apps" / "sfa", "android") is True

    def test_get_java_major_version(self) -> None:
        from kctl_react.commands.cap import _get_java_major_version

        ver = _get_java_major_version()
        # Should return an int or None (not crash)
        assert ver is None or isinstance(ver, int)

    def test_get_pkg_deps(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _get_pkg_deps

        deps = _get_pkg_deps(mock_monorepo / "apps" / "sfa")
        assert "@kodemeio/core" in deps

    def test_get_pkg_deps_missing(self, tmp_path: Path) -> None:
        from kctl_react.commands.cap import _get_pkg_deps

        assert _get_pkg_deps(tmp_path / "nonexistent") == {}


class TestCapVersionMatch:
    def test_versions_aligned(self) -> None:
        from kctl_react.commands.cap import _check_cap_version_match

        deps = {"@capacitor/core": "^8.0.0", "@capacitor/android": "^8.3.0"}
        ok, detail = _check_cap_version_match(deps)
        assert ok is True

    def test_versions_mismatched(self) -> None:
        from kctl_react.commands.cap import _check_cap_version_match

        deps = {"@capacitor/core": "^6.2.0", "@capacitor/android": "^8.3.0"}
        ok, detail = _check_cap_version_match(deps)
        assert ok is False
        assert "6" in detail and "8" in detail

    def test_no_platform_deps(self) -> None:
        from kctl_react.commands.cap import _check_cap_version_match

        deps = {"@capacitor/core": "^8.0.0"}
        ok, _ = _check_cap_version_match(deps)
        assert ok is True


class TestCapValidation:
    def test_validate_environment_basic(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _validate_environment

        checks = _validate_environment(mock_monorepo, None, None, check_deps=False)
        check_names = [c["check"] for c in checks]
        assert "node" in check_names
        assert "pnpm" in check_names

    def test_validate_with_app(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _validate_environment

        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        app_dir = mock_monorepo / "apps" / "sfa"
        checks = _validate_environment(mock_monorepo, app_dir, "android")
        check_names = [c["check"] for c in checks]
        assert "capacitor.config" in check_names
        assert "@capacitor/core" in check_names

    def test_validate_workbox_warning(self, mock_monorepo: Path) -> None:
        """Should flag missing workbox-window when vite-plugin-pwa is a dep."""
        from kctl_react.commands.cap import _validate_environment

        # Add vite-plugin-pwa to deps
        pkg_file = mock_monorepo / "apps" / "sfa" / "package.json"
        pkg = json.loads(pkg_file.read_text())
        pkg["devDependencies"]["vite-plugin-pwa"] = "^0.21.0"
        pkg_file.write_text(json.dumps(pkg, indent=2))

        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        app_dir = mock_monorepo / "apps" / "sfa"
        checks = _validate_environment(mock_monorepo, app_dir, "android")
        wb_checks = [c for c in checks if c["check"] == "workbox-window"]
        assert len(wb_checks) == 1
        assert wb_checks[0]["status"] == "fail"

    def test_validate_gradle_version(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _validate_environment

        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        android_dir = mock_monorepo / "apps" / "sfa" / "android"
        wrapper_dir = android_dir / "gradle" / "wrapper"
        wrapper_dir.mkdir(parents=True)
        (wrapper_dir / "gradle-wrapper.properties").write_text(
            "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.2.1-all.zip\n"
        )

        app_dir = mock_monorepo / "apps" / "sfa"
        checks = _validate_environment(mock_monorepo, app_dir, "android")
        gradle_checks = [c for c in checks if c["check"] == "gradle"]
        assert len(gradle_checks) == 1
        assert gradle_checks[0]["status"] == "fail"
        assert "8.2.1" in gradle_checks[0]["detail"]

    def test_validate_min_sdk(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _validate_environment

        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        android_dir = mock_monorepo / "apps" / "sfa" / "android"
        android_dir.mkdir(parents=True, exist_ok=True)
        (android_dir / "variables.gradle").write_text("ext {\n    minSdkVersion = 22\n}\n")

        app_dir = mock_monorepo / "apps" / "sfa"
        checks = _validate_environment(mock_monorepo, app_dir, "android")
        sdk_checks = [c for c in checks if c["check"] == "minSdkVersion"]
        assert len(sdk_checks) == 1
        assert sdk_checks[0]["status"] == "fail"


class TestCapFixAndroidProject:
    def test_fix_gradle_version(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _fix_android_project
        from kctl_react.core.output import Output

        android_dir = mock_monorepo / "apps" / "sfa" / "android"
        wrapper_dir = android_dir / "gradle" / "wrapper"
        wrapper_dir.mkdir(parents=True)
        (wrapper_dir / "gradle-wrapper.properties").write_text(
            "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.2.1-all.zip\n"
        )

        out = Output()
        _fix_android_project(out, android_dir)

        text = (wrapper_dir / "gradle-wrapper.properties").read_text()
        assert "8.11.1" in text
        assert "8.2.1" not in text

    def test_fix_min_sdk(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _fix_android_project
        from kctl_react.core.output import Output

        android_dir = mock_monorepo / "apps" / "sfa" / "android"
        android_dir.mkdir(parents=True, exist_ok=True)
        (android_dir / "variables.gradle").write_text(
            "ext {\n    minSdkVersion = 22\n    compileSdkVersion = 34\n    targetSdkVersion = 34\n}\n"
        )

        out = Output()
        _fix_android_project(out, android_dir)

        text = (android_dir / "variables.gradle").read_text()
        assert "minSdkVersion = 23" in text
        assert "compileSdkVersion = 35" in text
        assert "targetSdkVersion = 35" in text

    def test_fix_gradlew_permissions(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _fix_android_project
        from kctl_react.core.output import Output

        android_dir = mock_monorepo / "apps" / "sfa" / "android"
        android_dir.mkdir(parents=True, exist_ok=True)
        gradlew = android_dir / "gradlew"
        gradlew.write_text("#!/bin/bash\n")
        gradlew.chmod(0o644)  # Not executable

        out = Output()
        _fix_android_project(out, android_dir)

        import os

        assert os.access(gradlew, os.X_OK)


class TestCapDev:
    def test_dev_help(self) -> None:
        result = runner.invoke(app, ["cap", "dev", "--help"])
        assert result.exit_code == 0
        assert "live-reload" in result.output.lower()

    def test_dev_no_platform(self, mock_monorepo: Path) -> None:
        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text("export default {};")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "dev", "sfa", "android"])
        assert result.exit_code == 1
        assert "No android/" in result.output


# ── ADB device commands ────────────────────────────────────────────


class TestCapDevices:
    def test_devices_help(self) -> None:
        result = runner.invoke(app, ["cap", "devices", "--help"])
        assert result.exit_code == 0
        assert "ADB" in result.output or "device" in result.output.lower()

    def test_devices_no_adb(self, mock_monorepo: Path) -> None:
        """Should handle missing adb gracefully."""
        with patch("kctl_react.commands.cap.run", side_effect=Exception("adb not found")):
            result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "devices"])
            assert result.exit_code == 0
            assert "No devices" in result.output

    def test_list_devices_parser(self) -> None:
        from kctl_react.commands.cap import _list_devices

        # Just verify it returns a list and doesn't crash
        devs = _list_devices(Path("/tmp"))
        assert isinstance(devs, list)


class TestCapInstall:
    def test_install_no_apk(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "install", "sfa"])
        assert result.exit_code == 1
        assert "No debug APK" in result.output

    def test_install_help(self) -> None:
        result = runner.invoke(app, ["cap", "install", "--help"])
        assert result.exit_code == 0
        assert "device" in result.output.lower()

    def test_find_apk(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _find_apk

        # No APK exists
        assert _find_apk(mock_monorepo / "apps" / "sfa") is None

        # Create fake APK
        apk_dir = mock_monorepo / "apps" / "sfa" / "android" / "app" / "build" / "outputs" / "apk" / "debug"
        apk_dir.mkdir(parents=True)
        (apk_dir / "app-debug.apk").write_text("fake")
        result = _find_apk(mock_monorepo / "apps" / "sfa")
        assert result is not None
        assert result.name == "app-debug.apk"


class TestCapLaunch:
    def test_launch_no_config(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "launch", "sfa"])
        assert result.exit_code == 1
        assert "appId" in result.output or "Cannot read" in result.output

    def test_get_app_id(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _get_app_id

        (mock_monorepo / "apps" / "sfa" / "capacitor.config.ts").write_text(
            'const config = { appId: "io.kodeme.sfa" }; export default config;'
        )
        assert _get_app_id(mock_monorepo / "apps" / "sfa") == "io.kodeme.sfa"

    def test_get_app_id_missing(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _get_app_id

        assert _get_app_id(mock_monorepo / "apps" / "sfa") == ""


class TestCapLogs:
    def test_logs_help(self) -> None:
        result = runner.invoke(app, ["cap", "logs", "--help"])
        assert result.exit_code == 0
        assert "logcat" in result.output.lower()


class TestCapKeystore:
    def test_keystore_help(self) -> None:
        result = runner.invoke(app, ["cap", "keystore", "--help"])
        assert result.exit_code == 0
        assert "keystore" in result.output.lower()

    def test_keystore_creates_file(self, mock_monorepo: Path) -> None:
        """Test keystore generation with mocked keytool."""
        from kctl_react.commands.cap import _keystore_path

        ks = _keystore_path(mock_monorepo, "sfa")
        assert not ks.exists()

        with patch("kctl_react.commands.cap.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""

            # keytool mock — we need the file to be created
            def side_effect(cmd, **kwargs):
                if "keytool" in cmd:
                    ks.parent.mkdir(parents=True, exist_ok=True)
                    ks.write_text("fake-keystore")
                result_obj = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
                return result_obj

            mock_run.side_effect = side_effect
            result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "keystore", "sfa"])
            assert result.exit_code == 0
            assert ks.exists()

    def test_keystore_already_exists(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.cap import _keystore_path

        ks = _keystore_path(mock_monorepo, "sfa")
        ks.parent.mkdir(parents=True, exist_ok=True)
        ks.write_text("existing")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "keystore", "sfa"])
        assert result.exit_code == 0
        assert "already exists" in result.output


class TestCapEmulator:
    def test_emulator_help(self) -> None:
        result = runner.invoke(app, ["cap", "emulator", "--help"])
        assert result.exit_code == 0
        assert "emulator" in result.output.lower()

    def test_emulator_no_android_home(self, mock_monorepo: Path) -> None:
        with patch.dict("os.environ", {"ANDROID_HOME": "", "ANDROID_SDK_ROOT": ""}, clear=False):
            result = runner.invoke(app, ["--root", str(mock_monorepo), "cap", "emulator"])
            assert result.exit_code == 1
            assert "ANDROID_HOME" in result.output
