#!/usr/bin/env bash
# Fail if any test file references the real user config without isolation.
# Part of Stage C hardening for kctl-* profile standardization.

set -eu

# Pattern matches references to the real config file path or assignments to
# CONFIG_FILE. Tests that touch these MUST use tmp_path / monkeypatch /
# real_config marker for isolation.
pattern='(~/\.config/kodemeio|CONFIG_FILE *=)'

offenders=$(grep -rlE --include='*.py' "$pattern" packages/*/tests/ 2>/dev/null || true)

bad=""
for f in $offenders; do
    if ! grep -qE "monkeypatch|tmp_path|real_config" "$f"; then
        bad="$bad$f"$'\n'
    fi
done

if [ -n "$bad" ]; then
    printf '::error::Test files touching real user config without isolation:\n'
    printf '%s' "$bad"
    exit 1
fi

echo "OK — all test files mentioning CONFIG_FILE use tmp_path / monkeypatch / real_config."
