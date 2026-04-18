"""Parse .env files into key-value pairs."""

import re
from pathlib import Path
from typing import OrderedDict


def parse_env_file(file_path: Path) -> OrderedDict[str, str]:
    """Parse a .env file and return ordered key-value pairs.

    Handles:
    - Comments (lines starting with #)
    - Empty lines
    - Quoted values (single and double quotes)
    - Multiline values with quotes
    - Export prefix (export VAR=value)
    """
    env_vars: OrderedDict[str, str] = OrderedDict()

    if not file_path.exists():
        return env_vars

    content = file_path.read_text()
    lines = content.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            i += 1
            continue

        # Remove export prefix
        if line.startswith("export "):
            line = line[7:]

        # Parse key=value
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not match:
            i += 1
            continue

        key = match.group(1)
        value = match.group(2)

        # Handle quoted values
        if value.startswith('"') or value.startswith("'"):
            quote_char = value[0]
            # Check if it's a complete quoted string
            if len(value) > 1 and value.endswith(quote_char) and not value.endswith(f"\\{quote_char}"):
                # Single line quoted value
                value = value[1:-1]
            else:
                # Multiline quoted value
                multiline_value = value[1:]  # Remove opening quote
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.rstrip().endswith(quote_char) and not next_line.rstrip().endswith(f"\\{quote_char}"):
                        multiline_value += "\n" + next_line.rstrip()[:-1]  # Remove closing quote
                        break
                    multiline_value += "\n" + next_line
                    i += 1
                value = multiline_value

        # Unescape common escape sequences
        value = value.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\'", "'")

        env_vars[key] = value
        i += 1

    return env_vars


def serialize_env_vars(env_vars: OrderedDict[str, str]) -> str:
    """Serialize key-value pairs back to .env format."""
    lines = []

    for key, value in env_vars.items():
        # Check if value needs quoting
        needs_quotes = (
            "\n" in value
            or "\t" in value
            or " " in value
            or '"' in value
            or "'" in value
            or "#" in value
            or value.startswith(" ")
            or value.endswith(" ")
        )

        if needs_quotes:
            # Escape special characters and wrap in double quotes
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
            lines.append(f'{key}="{escaped}"')
        else:
            lines.append(f"{key}={value}")

    return "\n".join(lines) + "\n" if lines else ""
