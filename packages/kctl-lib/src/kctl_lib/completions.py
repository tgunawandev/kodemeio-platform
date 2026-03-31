"""Shell completion generation for kctl-* CLI tools."""

from __future__ import annotations

from pathlib import Path

from kctl_common.runner import run_quiet


def get_completion_script(app_name: str, shell: str = "zsh") -> str:
    env_var = f"_{app_name.upper().replace('-', '_')}_COMPLETE"
    result = run_quiet([app_name, "--help"], env={env_var: f"complete_{shell}"})
    return result.stdout if result.returncode == 0 else ""


def install_completions(app_name: str, shell: str = "zsh") -> Path | None:
    script = get_completion_script(app_name, shell)
    if not script:
        return None
    if shell == "zsh":
        d = Path.home() / ".zfunc"
        d.mkdir(exist_ok=True)
        target = d / f"_{app_name}"
    elif shell == "bash":
        d = Path.home() / ".local" / "share" / "bash-completion" / "completions"
        d.mkdir(parents=True, exist_ok=True)
        target = d / app_name
    elif shell == "fish":
        d = Path.home() / ".config" / "fish" / "completions"
        d.mkdir(parents=True, exist_ok=True)
        target = d / f"{app_name}.fish"
    else:
        return None
    target.write_text(script)
    return target
