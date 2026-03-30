# Shell Completions

kctl-odoo uses Typer which provides automatic shell completion.

## Installation

### Bash

```bash
kctl-odoo --install-completion bash
```

### Zsh

```bash
kctl-odoo --install-completion zsh
```

### Fish

```bash
kctl-odoo --install-completion fish
```

## Manual Installation

### Bash

```bash
eval "$(_KCTL_ODOO_COMPLETE=bash_source kctl-odoo)"

# Or add to ~/.bashrc for persistence:
echo 'eval "$(_KCTL_ODOO_COMPLETE=bash_source kctl-odoo)"' >> ~/.bashrc
```

### Zsh

```bash
eval "$(_KCTL_ODOO_COMPLETE=zsh_source kctl-odoo)"

# Or add to ~/.zshrc for persistence:
echo 'eval "$(_KCTL_ODOO_COMPLETE=zsh_source kctl-odoo)"' >> ~/.zshrc
```

### Fish

```fish
# Add to ~/.config/fish/completions/kctl-odoo.fish:
eval (env _KCTL_ODOO_COMPLETE=fish_source kctl-odoo)
```

## Verify

After installation, restart your shell and try:

```bash
kctl-odoo <TAB><TAB>     # Shows all command groups
kctl-odoo modules <TAB>   # Shows subcommands (install, upgrade, list, info)
kctl-odoo --<TAB>          # Shows global options (--json, --profile, etc.)
```

## Troubleshooting

If completions are not working:

1. Make sure `kctl-odoo` is on your `$PATH` (installed via `uv tool install`).
2. Restart your shell or source your rc file (`source ~/.zshrc`).
3. For Zsh, ensure `compinit` is called in your `~/.zshrc` before the completion eval.
4. Try the manual installation method above if `--install-completion` does not work.
