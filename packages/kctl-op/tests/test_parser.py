"""Tests for kctl_op.core.parser module."""

import pytest
from collections import OrderedDict
from pathlib import Path

from kctl_op.core.parser import parse_env_file, serialize_env_vars


class TestParseEnvFile:
    """Tests for parse_env_file."""

    def test_simple_key_value(self, tmp_env_file):
        """Simple KEY=value pairs are parsed correctly."""
        path = tmp_env_file("FOO=bar\nBAZ=qux\n")
        result = parse_env_file(path)
        assert result == OrderedDict([("FOO", "bar"), ("BAZ", "qux")])

    def test_double_quoted_values(self, tmp_env_file):
        """Double-quoted values have quotes stripped."""
        path = tmp_env_file('MY_VAR="hello world"\n')
        result = parse_env_file(path)
        assert result["MY_VAR"] == "hello world"

    def test_single_quoted_values(self, tmp_env_file):
        """Single-quoted values have quotes stripped."""
        path = tmp_env_file("MY_VAR='hello world'\n")
        result = parse_env_file(path)
        assert result["MY_VAR"] == "hello world"

    def test_comments_are_skipped(self, tmp_env_file):
        """Lines starting with # are ignored."""
        path = tmp_env_file("# This is a comment\nKEY=value\n# Another comment\n")
        result = parse_env_file(path)
        assert len(result) == 1
        assert result["KEY"] == "value"

    def test_empty_lines_are_skipped(self, tmp_env_file):
        """Empty and whitespace-only lines are ignored."""
        path = tmp_env_file("KEY1=val1\n\n\n   \nKEY2=val2\n")
        result = parse_env_file(path)
        assert len(result) == 2
        assert result["KEY1"] == "val1"
        assert result["KEY2"] == "val2"

    def test_export_prefix(self, tmp_env_file):
        """Lines with 'export ' prefix have the prefix stripped."""
        path = tmp_env_file("export MY_VAR=hello\nexport OTHER=world\n")
        result = parse_env_file(path)
        assert result["MY_VAR"] == "hello"
        assert result["OTHER"] == "world"

    def test_empty_value(self, tmp_env_file):
        """KEY= with no value produces an empty string."""
        path = tmp_env_file("EMPTY_VAR=\n")
        result = parse_env_file(path)
        assert result["EMPTY_VAR"] == ""

    def test_value_with_hash(self, tmp_env_file):
        """Unquoted values with # include everything after the equals sign."""
        path = tmp_env_file('CHANNEL="general#chat"\n')
        result = parse_env_file(path)
        assert result["CHANNEL"] == "general#chat"

    def test_value_with_spaces_in_quotes(self, tmp_env_file):
        """Quoted values preserve internal spaces."""
        path = tmp_env_file('GREETING="hello beautiful world"\n')
        result = parse_env_file(path)
        assert result["GREETING"] == "hello beautiful world"

    def test_multiline_double_quoted_value(self, tmp_env_file):
        """Multiline values spanning multiple lines are captured."""
        content = 'MULTI="line one\nline two\nline three"\n'
        path = tmp_env_file(content)
        result = parse_env_file(path)
        assert "line one" in result["MULTI"]
        assert "line two" in result["MULTI"]
        assert "line three" in result["MULTI"]

    def test_escape_sequences_unescaped(self, tmp_env_file):
        """Escape sequences \\n and \\t are converted to actual characters."""
        path = tmp_env_file("MSG=hello\\\\nworld\n")
        result = parse_env_file(path)
        assert "\n" in result["MSG"]

    def test_nonexistent_file_returns_empty(self, tmp_path):
        """Parsing a file that does not exist returns an empty OrderedDict."""
        path = tmp_path / "does_not_exist.env"
        result = parse_env_file(path)
        assert result == OrderedDict()
        assert isinstance(result, OrderedDict)

    def test_preserves_order(self, tmp_env_file):
        """Keys are returned in the order they appear in the file."""
        path = tmp_env_file("ZEBRA=1\nAPPLE=2\nMANGO=3\n")
        result = parse_env_file(path)
        assert list(result.keys()) == ["ZEBRA", "APPLE", "MANGO"]

    def test_sample_env_content(self, tmp_env_file, sample_env_content, sample_env_vars):
        """The sample .env content fixture parses to the expected variables."""
        path = tmp_env_file(sample_env_content)
        result = parse_env_file(path)
        assert result == sample_env_vars


class TestSerializeEnvVars:
    """Tests for serialize_env_vars."""

    def test_simple_values(self):
        """Simple values are serialized as KEY=value."""
        env = OrderedDict([("FOO", "bar"), ("BAZ", "qux")])
        result = serialize_env_vars(env)
        assert "FOO=bar\n" in result
        assert "BAZ=qux\n" in result

    def test_values_with_spaces_are_quoted(self):
        """Values containing spaces are wrapped in double quotes."""
        env = OrderedDict([("MSG", "hello world")])
        result = serialize_env_vars(env)
        assert 'MSG="hello world"' in result

    def test_values_with_hash_are_quoted(self):
        """Values containing # are wrapped in double quotes."""
        env = OrderedDict([("CHANNEL", "general#chat")])
        result = serialize_env_vars(env)
        assert 'CHANNEL="general#chat"' in result

    def test_values_with_newlines_are_quoted_and_escaped(self):
        """Values containing newlines are escaped and quoted."""
        env = OrderedDict([("MULTI", "line1\nline2")])
        result = serialize_env_vars(env)
        assert 'MULTI="line1\\nline2"' in result

    def test_values_with_tabs_are_quoted_and_escaped(self):
        """Values containing tabs are escaped and quoted."""
        env = OrderedDict([("TABBED", "col1\tcol2")])
        result = serialize_env_vars(env)
        assert 'TABBED="col1\\tcol2"' in result

    def test_empty_dict_returns_empty_string(self):
        """An empty OrderedDict produces an empty string."""
        result = serialize_env_vars(OrderedDict())
        assert result == ""

    def test_empty_value_no_quotes(self):
        """An empty string value is serialized without quotes."""
        env = OrderedDict([("EMPTY", "")])
        result = serialize_env_vars(env)
        assert "EMPTY=\n" in result

    def test_preserves_key_order(self):
        """Keys are serialized in insertion order."""
        env = OrderedDict([("ZEBRA", "1"), ("APPLE", "2"), ("MANGO", "3")])
        result = serialize_env_vars(env)
        lines = result.strip().split("\n")
        assert lines[0] == "ZEBRA=1"
        assert lines[1] == "APPLE=2"
        assert lines[2] == "MANGO=3"

    def test_trailing_newline(self):
        """Serialized output ends with a newline."""
        env = OrderedDict([("KEY", "value")])
        result = serialize_env_vars(env)
        assert result.endswith("\n")


class TestRoundTrip:
    """Test parse -> serialize -> parse round-trip consistency."""

    def test_round_trip_simple(self, tmp_env_file):
        """Parsing, serializing, and re-parsing produces the same result."""
        original_content = "DB_HOST=localhost\nDB_PORT=5432\nAPI_KEY=abc123\n"
        path = tmp_env_file(original_content)

        # Parse
        parsed = parse_env_file(path)

        # Serialize
        serialized = serialize_env_vars(parsed)

        # Write serialized back and re-parse
        round_trip_path = path.parent / ".env.roundtrip"
        round_trip_path.write_text(serialized)
        reparsed = parse_env_file(round_trip_path)

        assert parsed == reparsed

    def test_round_trip_with_special_chars(self, tmp_env_file):
        """Round-trip works for values that require quoting."""
        env = OrderedDict([
            ("SIMPLE", "value"),
            ("SPACED", "hello world"),
            ("HASHED", "test#value"),
        ])
        serialized = serialize_env_vars(env)
        path = tmp_env_file(serialized)
        reparsed = parse_env_file(path)
        assert reparsed == env
