"""Tests for kctl_op.core.diff module."""

import pytest
from collections import OrderedDict

from kctl_op.core.diff import (
    ChangeType,
    DiffResult,
    FieldChange,
    _truncate_value,
    compute_diff,
    format_diff,
    normalize_value,
    values_equal,
)


class TestNormalizeValue:
    """Tests for normalize_value."""

    def test_empty_string(self):
        """Empty string normalizes to empty string."""
        assert normalize_value("") == ""

    def test_escape_sequences_newline(self):
        """Literal \\n is converted to actual newline."""
        assert normalize_value("hello\\nworld") == "hello\nworld"

    def test_escape_sequences_tab(self):
        """Literal \\t is converted to actual tab."""
        assert normalize_value("col1\\tcol2") == "col1\tcol2"

    def test_escaped_backslash(self):
        """Double backslash is normalized to single backslash."""
        assert normalize_value("path\\\\file") == "path\\file"

    def test_crlf_normalized_to_lf(self):
        """Windows line endings (\\r\\n) are normalized to Unix (\\n)."""
        assert normalize_value("line1\r\nline2") == "line1\nline2"

    def test_cr_normalized_to_lf(self):
        """Old Mac line endings (\\r) are normalized to Unix (\\n)."""
        assert normalize_value("line1\rline2") == "line1\nline2"

    def test_trailing_whitespace_stripped_per_line(self):
        """Trailing whitespace on each line is removed."""
        assert normalize_value("hello   \nworld  ") == "hello\nworld"

    def test_already_normalized(self):
        """A value with no special sequences is unchanged."""
        assert normalize_value("simple") == "simple"


class TestValuesEqual:
    """Tests for values_equal."""

    def test_identical_values(self):
        """Identical values are equal."""
        assert values_equal("hello", "hello") is True

    def test_equal_after_normalization(self):
        """Values that differ only by line endings are equal after normalization."""
        assert values_equal("line1\nline2", "line1\r\nline2") is True

    def test_equal_after_trailing_whitespace(self):
        """Values that differ only by trailing whitespace are equal."""
        assert values_equal("hello  ", "hello") is True

    def test_not_equal(self):
        """Actually different values are not equal."""
        assert values_equal("hello", "world") is False

    def test_empty_values_equal(self):
        """Two empty strings are equal."""
        assert values_equal("", "") is True


class TestComputeDiff:
    """Tests for compute_diff."""

    def test_identical_dicts_no_changes(self):
        """Identical dicts produce no changes."""
        local = OrderedDict([("A", "1"), ("B", "2")])
        remote = OrderedDict([("A", "1"), ("B", "2")])
        diff = compute_diff(local, remote)
        assert not diff.has_changes
        assert len(diff.unchanged) == 2

    def test_added_keys_detected(self):
        """Keys in local but not remote are ADDED."""
        local = OrderedDict([("A", "1"), ("B", "2"), ("C", "3")])
        remote = OrderedDict([("A", "1")])
        diff = compute_diff(local, remote)
        assert len(diff.added) == 2
        added_keys = {c.key for c in diff.added}
        assert added_keys == {"B", "C"}

    def test_removed_keys_detected(self):
        """Keys in remote but not local are REMOVED."""
        local = OrderedDict([("A", "1")])
        remote = OrderedDict([("A", "1"), ("B", "2"), ("C", "3")])
        diff = compute_diff(local, remote)
        assert len(diff.removed) == 2
        removed_keys = {c.key for c in diff.removed}
        assert removed_keys == {"B", "C"}

    def test_modified_values_detected(self):
        """Keys with different values are MODIFIED."""
        local = OrderedDict([("A", "new_value")])
        remote = OrderedDict([("A", "old_value")])
        diff = compute_diff(local, remote)
        assert len(diff.modified) == 1
        assert diff.modified[0].key == "A"
        assert diff.modified[0].local_value == "new_value"
        assert diff.modified[0].remote_value == "old_value"

    def test_mixed_changes(self):
        """A mix of added, removed, modified, and unchanged keys."""
        local = OrderedDict([
            ("KEEP", "same"),
            ("CHANGE", "new"),
            ("NEW_KEY", "added"),
        ])
        remote = OrderedDict([
            ("KEEP", "same"),
            ("CHANGE", "old"),
            ("OLD_KEY", "removed"),
        ])
        diff = compute_diff(local, remote)
        assert diff.has_changes
        assert len(diff.added) == 1
        assert len(diff.removed) == 1
        assert len(diff.modified) == 1
        assert len(diff.unchanged) == 1

    def test_empty_dicts(self):
        """Two empty dicts produce no changes."""
        diff = compute_diff(OrderedDict(), OrderedDict())
        assert not diff.has_changes
        assert len(diff.changes) == 0

    def test_changes_sorted_by_key(self):
        """Changes are returned sorted by key name."""
        local = OrderedDict([("Z", "1"), ("A", "2"), ("M", "3")])
        remote = OrderedDict()
        diff = compute_diff(local, remote)
        keys = [c.key for c in diff.changes]
        assert keys == sorted(keys)


class TestDiffResult:
    """Tests for DiffResult dataclass properties."""

    def test_has_changes_false_when_all_unchanged(self):
        """has_changes is False when all fields are unchanged."""
        changes = [
            FieldChange(key="A", change_type=ChangeType.UNCHANGED, local_value="1", remote_value="1"),
        ]
        diff = DiffResult(local_fields=OrderedDict(), remote_fields=OrderedDict(), changes=changes)
        assert diff.has_changes is False

    def test_has_changes_true_with_any_change(self):
        """has_changes is True if any field is not UNCHANGED."""
        changes = [
            FieldChange(key="A", change_type=ChangeType.UNCHANGED, local_value="1", remote_value="1"),
            FieldChange(key="B", change_type=ChangeType.ADDED, local_value="2"),
        ]
        diff = DiffResult(local_fields=OrderedDict(), remote_fields=OrderedDict(), changes=changes)
        assert diff.has_changes is True

    def test_added_property_filters_correctly(self):
        """The added property returns only ADDED changes."""
        changes = [
            FieldChange(key="A", change_type=ChangeType.ADDED, local_value="1"),
            FieldChange(key="B", change_type=ChangeType.REMOVED, remote_value="2"),
            FieldChange(key="C", change_type=ChangeType.ADDED, local_value="3"),
        ]
        diff = DiffResult(local_fields=OrderedDict(), remote_fields=OrderedDict(), changes=changes)
        assert len(diff.added) == 2
        assert all(c.change_type == ChangeType.ADDED for c in diff.added)

    def test_removed_property_filters_correctly(self):
        """The removed property returns only REMOVED changes."""
        changes = [
            FieldChange(key="A", change_type=ChangeType.REMOVED, remote_value="1"),
            FieldChange(key="B", change_type=ChangeType.MODIFIED, local_value="new", remote_value="old"),
        ]
        diff = DiffResult(local_fields=OrderedDict(), remote_fields=OrderedDict(), changes=changes)
        assert len(diff.removed) == 1
        assert diff.removed[0].key == "A"

    def test_modified_property_filters_correctly(self):
        """The modified property returns only MODIFIED changes."""
        changes = [
            FieldChange(key="A", change_type=ChangeType.MODIFIED, local_value="new", remote_value="old"),
            FieldChange(key="B", change_type=ChangeType.UNCHANGED, local_value="same", remote_value="same"),
        ]
        diff = DiffResult(local_fields=OrderedDict(), remote_fields=OrderedDict(), changes=changes)
        assert len(diff.modified) == 1
        assert diff.modified[0].key == "A"

    def test_unchanged_property_filters_correctly(self):
        """The unchanged property returns only UNCHANGED changes."""
        changes = [
            FieldChange(key="A", change_type=ChangeType.UNCHANGED, local_value="1", remote_value="1"),
            FieldChange(key="B", change_type=ChangeType.UNCHANGED, local_value="2", remote_value="2"),
            FieldChange(key="C", change_type=ChangeType.ADDED, local_value="3"),
        ]
        diff = DiffResult(local_fields=OrderedDict(), remote_fields=OrderedDict(), changes=changes)
        assert len(diff.unchanged) == 2


class TestFieldChange:
    """Tests for FieldChange dataclass."""

    def test_is_changed_true_for_added(self):
        """is_changed is True for ADDED."""
        fc = FieldChange(key="X", change_type=ChangeType.ADDED, local_value="v")
        assert fc.is_changed is True

    def test_is_changed_false_for_unchanged(self):
        """is_changed is False for UNCHANGED."""
        fc = FieldChange(key="X", change_type=ChangeType.UNCHANGED, local_value="v", remote_value="v")
        assert fc.is_changed is False


class TestFormatDiff:
    """Tests for format_diff."""

    def test_no_changes_message(self):
        """When there are no changes, a 'no changes' message is returned."""
        changes = [
            FieldChange(key="A", change_type=ChangeType.UNCHANGED, local_value="1", remote_value="1"),
        ]
        diff = DiffResult(local_fields=OrderedDict(), remote_fields=OrderedDict(), changes=changes)
        result = format_diff(diff)
        assert result == "No changes detected."

    def test_format_with_added_changes(self):
        """Added changes are displayed with + prefix and correct count."""
        local = OrderedDict([("NEW_KEY", "value")])
        remote = OrderedDict()
        diff = compute_diff(local, remote)
        result = format_diff(diff)
        assert "+1 added" in result
        assert "+ NEW_KEY" in result

    def test_format_with_removed_changes(self):
        """Removed changes are displayed with - prefix."""
        local = OrderedDict()
        remote = OrderedDict([("OLD_KEY", "value")])
        diff = compute_diff(local, remote)
        result = format_diff(diff)
        assert "-1 removed" in result
        assert "- OLD_KEY" in result

    def test_format_with_modified_changes(self):
        """Modified changes are displayed with ~ prefix."""
        local = OrderedDict([("KEY", "new")])
        remote = OrderedDict([("KEY", "old")])
        diff = compute_diff(local, remote)
        result = format_diff(diff)
        assert "~1 modified" in result
        assert "~ KEY" in result

    def test_format_show_values(self):
        """With show_values=True, values are displayed."""
        local = OrderedDict([("NEW_KEY", "the_value")])
        remote = OrderedDict()
        diff = compute_diff(local, remote)
        result = format_diff(diff, show_values=True)
        assert "the_value" in result

    def test_format_mixed_changes_summary(self):
        """Summary line shows counts for all change types."""
        local = OrderedDict([("KEEP", "same"), ("CHANGE", "new"), ("ADD", "added")])
        remote = OrderedDict([("KEEP", "same"), ("CHANGE", "old"), ("DEL", "removed")])
        diff = compute_diff(local, remote)
        result = format_diff(diff)
        assert "+1 added" in result
        assert "-1 removed" in result
        assert "~1 modified" in result


class TestTruncateValue:
    """Tests for _truncate_value."""

    def test_empty_value_returns_empty_quotes(self):
        """An empty value returns double quotes."""
        assert _truncate_value("") == '""'

    def test_short_value_unchanged(self):
        """Short values are returned unchanged."""
        assert _truncate_value("hello") == "hello"

    def test_long_value_truncated(self):
        """Values exceeding max_length are truncated with ellipsis."""
        long_value = "x" * 100
        result = _truncate_value(long_value, max_length=20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_masks_password_like_values(self):
        """Values containing 'password' are partially masked."""
        result = _truncate_value("my_password_is_very_long")
        assert "*" in result
        # First 4 and last 4 characters are visible
        assert result[:4] == "my_p"
        assert result[-4:] == "long"

    def test_masks_secret_like_values(self):
        """Values containing 'secret' are partially masked."""
        result = _truncate_value("this_is_a_secret_value")
        assert "*" in result

    def test_masks_key_like_values(self):
        """Values containing 'key' are partially masked."""
        result = _truncate_value("my_api_key_12345678")
        assert "*" in result

    def test_masks_token_like_values(self):
        """Values containing 'token' are partially masked."""
        result = _truncate_value("bearer_token_abcdef12")
        assert "*" in result

    def test_short_secret_not_masked(self):
        """Secret-like values with 8 or fewer characters are not masked."""
        result = _truncate_value("key12345")
        assert "*" not in result

    def test_custom_max_length(self):
        """Custom max_length parameter is respected."""
        value = "a" * 30
        result = _truncate_value(value, max_length=10)
        assert len(result) == 10
        assert result.endswith("...")
