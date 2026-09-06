#!/usr/bin/env bash
#
# _boot.sh — repo root, service inventory and shared helpers for a front door.
#
# CANONICAL FILE. Vendored byte-identical into every repo that has a front
# door; the only per-repo file is <service>.yaml. Edit the copy in
# kodemeio-skills/templates/frontdoor/ and run `scripts/frontdoor-sync --write`,
# never the vendored copy — `scripts/frontdoor-sync --check` fails the build
# when a vendored copy has drifted.
#
# Sourced by <service>.sh and by every tool in bin/<service>/. Idempotent.
#
# Derived from kodemeio-odoo/bin/odoo/_boot.sh, which is the reference
# implementation and deliberately NOT replaced by this one: twenty skills
# depend on odoo.sh's exact argv behaviour, and it carries repo-specific
# compensations (the sql invariant refusal) that do not generalise.
#
# The bug the odoo original fixes, inherited here: the old wrappers each set
# SCRIPT_DIR="$(dirname "$0")" and used it AS THE REPO ROOT. That only worked
# while every script sat in the root. "Where I live" and "where the repo is"
# are two different things.

[[ -n "${_FD_BOOT:-}" ]] && return 0
_FD_BOOT=1

# ── Service identity ─────────────────────────────────────────────────────────
# FD_SERVICE is set by <service>.sh from its own filename (odoo.sh -> odoo), so
# this file never needs to know which repo it is in. A tool under
# bin/<service>/ that is executed directly (not through the front door) has no
# FD_SERVICE, so derive it from the directory the tool lives in.
if [[ -z "${FD_SERVICE:-}" ]]; then
  FD_SERVICE="$(basename "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"
fi

# ── Repo root ────────────────────────────────────────────────────────────────
# git first so this is correct inside a worktree; the literal fallback keeps it
# working in a tarball or with git absent.
if [[ -n "${FD_REPO_ROOT_OVERRIDE:-}" ]]; then
  FD_REPO_ROOT="$FD_REPO_ROOT_OVERRIDE"
else
  _fd_boot_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  FD_REPO_ROOT="$(git -C "$_fd_boot_dir" rev-parse --show-toplevel 2>/dev/null)" || FD_REPO_ROOT=""
  [[ -n "$FD_REPO_ROOT" ]] || FD_REPO_ROOT="$(cd "$_fd_boot_dir/../.." && pwd)"
  unset _fd_boot_dir
fi

FD_BIN_DIR="$FD_REPO_ROOT/bin/$FD_SERVICE"
FD_YAML="$FD_REPO_ROOT/$FD_SERVICE.yaml"
export FD_REPO_ROOT FD_BIN_DIR FD_SERVICE

# ── Output ───────────────────────────────────────────────────────────────────
# Everything goes to stderr so a caller can pipe stdout (JSON, a report) without
# catching the banner. NO_COLOR and a non-tty both disable colour.
if [[ -t 2 && "${NO_COLOR:-}" != "1" ]]; then
  c_red()   { printf '\033[1;31m%s\033[0m\n' "$*" >&2; }
  c_green() { printf '\033[1;32m%s\033[0m\n' "$*" >&2; }
  c_dim()   { printf '\033[2m%s\033[0m\n'    "$*" >&2; }
else
  c_red()   { printf '%s\n' "$*" >&2; }
  c_green() { printf '%s\n' "$*" >&2; }
  c_dim()   { printf '%s\n' "$*" >&2; }
fi

# need <binary> [install hint] — refuse early and say how to fix it. Exit 127
# matches the shell's own "command not found", so a caller can tell "the tool
# is missing" apart from "the tool ran and refused" (exit 2).
need() {
  command -v "$1" >/dev/null 2>&1 && return 0
  c_red "Required tool not found on PATH: $1"
  [[ -n "${2:-}" ]] && c_dim "  $2"
  exit 127
}

need yq "yq v4 (mikefarah). See https://github.com/mikefarah/yq"
[[ -f "$FD_YAML" ]] || { c_red "Service inventory missing: $FD_YAML"; exit 1; }

# ── Inventory lookups ────────────────────────────────────────────────────────
# All lookups return an empty string when the key is absent, never an error, so
# a caller can test for "" instead of trapping a yq exit code.
#
# Every lookup that takes user-typed input binds it through strenv() rather
# than interpolating it into the yq expression. A raw ".targets.\"$1\"" lets a
# stray double quote in argv abort the whole front door with a yq lexer error.
# Fail-closed today, but a security lookup must never be string-built.

fd_meta()        { _FD_K="$1" yq -r '.[strenv(_FD_K)] // ""' "$FD_YAML"; }
fd_cli()         { fd_meta cli; }
fd_description() { fd_meta description; }

# The selector is the list of leading words the door consumes before the
# command group: [] (none), [platform], or [tenant, target]. Its length decides
# how many words are joined with "/" to form a target key.
fd_selector_names() { yq -r '.selector // [] | .[]' "$FD_YAML"; }
fd_selector_arity() { yq -r '.selector // [] | length' "$FD_YAML"; }

fd_targets()       { yq -r '.targets // {} | keys | .[]' "$FD_YAML"; }
fd_target_field()  { _FD_T="$1" _FD_F="$2" yq -r '.targets[strenv(_FD_T)][strenv(_FD_F)] // ""' "$FD_YAML"; }
fd_profile_for()   { fd_target_field "$1" profile; }
fd_label_for()     { fd_target_field "$1" label; }
fd_url_for()       { fd_target_field "$1" url; }
fd_is_target()     { _FD_T="$1" yq -e '.targets | has(strenv(_FD_T))' "$FD_YAML" >/dev/null 2>&1; }

# A target listed in safe_targets is exempt from the write guards — it is the
# throwaway one. An EMPTY safe_targets means guards apply everywhere, which is
# the right default for a service with no local instance (authentik has none).
fd_is_safe_target() {
  local s
  while IFS= read -r s; do [[ "$s" == "$1" ]] && return 0; done < <(yq -r '.safe_targets // [] | .[]' "$FD_YAML")
  return 1
}

# fd_guard_verbs <group> [dotted-verb-path] -> space-separated write verbs.
#
# An empty path means the root, spelled `_` in the YAML. NOT "" — yq resolves an
# empty-string key to [], which is a guard that is present, readable, reviewed
# and silently switched off. Verified: `.guards.x."" // []` returns [].
fd_guard_verbs() {
  _FD_G="$1" _FD_P="${2:-_}" \
    yq -r '.guards[strenv(_FD_G)][strenv(_FD_P)] // [] | join(" ")' "$FD_YAML"
}

# Does this EXACT verb own a --yes of its own, so the door must FORWARD the flag
# rather than consume it? Takes the fired guard's key, group[.path].verb.
#
# 🔴 THE DEFAULT IS THE OPPOSITE OF kodemeio-odoo's, on purpose. Measured from
# `<cli> commands tree` on 2026-09-06: kctl-ak, kctl-api, kctl-dokploy, kctl-pg,
# kctl-react and kctl-supa have ZERO --yes options across 251 write-shaped
# verbs between them; only kctl-mm has any (14). odoo.yaml's strip_yes is
# therefore the rule here, not the exception, and forward_yes is the short list.
#
# This inversion is what makes generous guarding safe. odoo could not guard
# freely because forwarding --yes to a verb that has no such option made the
# verb UNREACHABLE off local -- that is the `report build export` incident of
# 2026-08-22. Consuming the flag by default means an over-guarded read costs one
# keystroke and can never make anything unreachable.
#
# 🔴 KEYED TO THE LEAF, NEVER THE GROUP. kctl-mm's `users` group owns --yes on
# `deactivate` but NOT on `users tokens create` or `users tokens enable`. A
# group-level key would forward the flag to those two and break them -- the same
# unreachable-verb bug, arrived at from the opposite direction.
fd_forwards_yes() {
  [[ -n "${1:-}" ]] || return 1
  local k
  while IFS= read -r k; do [[ "$k" == "$1" ]] && return 0; done < <(yq -r '.forward_yes // [] | .[]' "$FD_YAML")
  return 1
}

# Is the GROUP ITSELF the write, with no verb after it?
#
# Needed for a CLI whose top-level command IS the action rather than a namespace:
# `pnpm publish` has no verb for the argv walk below to match, so a guard table
# keyed group->verb cannot express it and `pnpm publish` would go unguarded.
# Listed per repo as `guarded_groups:`.
fd_is_guarded_group() {
  local g
  while IFS= read -r g; do [[ "$g" == "$1" ]] && return 0; done < <(yq -r '.guarded_groups // [] | .[]' "$FD_YAML")
  return 1
}

# Reserved words whose bin/<service>/<name> tool ALSO parses the selector as its
# own leading arguments AND collides with a real CLI group name. Those are the
# only ones ambiguous in the group position -- see _dispatch.sh.
fd_ambiguous_groups() { yq -r '.ambiguous // [] | .[]' "$FD_YAML"; }

# Does the wrapped CLI have a --dry-run of its own? Decides whether the
# --kctl-dry-run escape hatch is advertised.
fd_cli_has_dry_run() { [[ "$(yq -r '.cli_has_dry_run // false' "$FD_YAML")" == "true" ]]; }

fd_global_value_opts() { yq -r '.globals.value // [] | .[]' "$FD_YAML"; }
fd_global_bool_opts()  { yq -r '.globals.bool  // [] | .[]' "$FD_YAML"; }

# ── Shared tool helpers ──────────────────────────────────────────────────────
# Prints a tool's own header block from line 3 on, which is why line 2 of every
# script here must stay a bare `#`. Each bin/<service>/* tool owns its usage
# text this way, so the text cannot live somewhere that drifts from the code.
fd_usage_from_header() {
  awk 'NR>=3 { if ($0 !~ /^#/ && $0 !~ /^[[:space:]]*$/) exit; sub(/^# ?/,""); print }' "${1:-$0}"
}

# fd_resolve <selector-word...> -> sets FD_TARGET and FD_PROFILE, or dies.
# Used by bin/<service>/* tools, which take the selector as their own leading
# arguments rather than going back through the front door.
fd_resolve() {
  local arity; arity="$(fd_selector_arity)"
  local key="" i
  for (( i = 1; i <= arity; i++ )); do
    [[ -n "${!i:-}" ]] || { c_red "Need $(fd_selector_names | tr '\n' ' ')"; exit 1; }
    key="${key:+$key/}${!i}"
  done
  FD_TARGET="$key"
  if [[ -n "$key" ]] && ! fd_is_target "$key"; then
    c_red "Unknown target '$key'. Configured: $(fd_targets | tr '\n' ' ')"
    exit 1
  fi
  FD_PROFILE="$(fd_profile_for "$key")"
  # Exported because the CALLER reads them: fd_resolve is the adapter each
  # bin/<service>/* tool uses instead of going back through the front door.
  # Without the export shellcheck reports them unused (SC2034), which is the
  # kind of warning people silence with a blanket disable and then stop reading.
  export FD_TARGET FD_PROFILE
}
