# Shell Completions for kctl-zulip

kctl-zulip supports tab-completion for commands, options, and arguments
in zsh, bash, and fish shells.

## Quick Install

```bash
kctl-zulip completions zsh --install
kctl-zulip completions bash --install
kctl-zulip completions fish --install
```

After installing, restart your shell or source the relevant config file.

## Manual Setup

### Zsh

Generate the completion script and place it in your fpath:

```bash
kctl-zulip completions zsh > ~/.zfunc/_kctl-zulip
```

Ensure `~/.zfunc` is in your fpath. Add to `~/.zshrc` if not already present:

```bash
fpath=(~/.zfunc $fpath)
autoload -Uz compinit && compinit
```

### Bash

Generate and source the completion script:

```bash
kctl-zulip completions bash > ~/.local/share/bash-completion/completions/kctl-zulip
```

Or source it directly in `~/.bashrc`:

```bash
eval "$(kctl-zulip completions bash)"
```

### Fish

Generate and place the completion file:

```bash
kctl-zulip completions fish > ~/.config/fish/completions/kctl-zulip.fish
```

Fish picks up completions automatically from this directory.

## Verifying

After installation, open a new terminal and type:

```bash
kctl-zulip <TAB>
```

You should see a list of available commands (config, users, streams, messages, etc.).

## Troubleshooting

- **Zsh completions not working**: Run `compinit` or delete `~/.zcompdump` and restart.
- **Bash completions not loading**: Ensure `bash-completion` is installed (`apt install bash-completion`).
- **Fish completions stale**: Delete the generated file and regenerate.
