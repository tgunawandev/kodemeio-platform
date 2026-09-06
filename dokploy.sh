#!/usr/bin/env bash
#
# <service>.sh — this repo's front door.
#
# CANONICAL FILE, vendored byte-identical into every repo. It carries no
# per-repo knowledge at all: the service name comes from this file's OWN
# filename (dokploy.sh -> dokploy), which then resolves ./dokploy.yaml and
# bin/dokploy/. Renaming the door is therefore the whole of "point it at a
# different service", and there is no second place to update.
#
# Everything that differs between repos lives in <service>.yaml: the CLI to
# wrap, the targets and their profiles, the write-guard table, and the global
# options the wrapped CLI recognises.
#
# Run it with no arguments for usage generated from that YAML and from
# bin/<service>/ on disk — never from a hand-typed list that can go stale.
set -euo pipefail

FD_SERVICE="$(basename "${BASH_SOURCE[0]}" .sh)"
_fd_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export FD_SERVICE

# The path is built from this file's own name, so it is not a constant and
# SC1090 cannot follow it. That indirection is the whole design: it is what
# lets one file serve ten repos.
#
# Two traps in the directive below, both hit while writing this: it must be the
# LAST comment line before the source (a trailing comment block is parsed as
# part of it), and no OTHER comment line may begin with the linter's own name,
# or that line is read as a malformed directive too. Both surface as SC1073.
# shellcheck source=/dev/null
source "$_fd_root/bin/$FD_SERVICE/_boot.sh"
# shellcheck source=/dev/null
source "$FD_BIN_DIR/_dispatch.sh"

fd_main "$@"
