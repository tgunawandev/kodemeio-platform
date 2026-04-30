"""Unit tests for OutputSink (core/streaming.py).

Covers the six scenarios called out in the spec:
  1. JSONL — line-per-record, no array brackets, parses as N JSON objects.
  2. JSON array mode — single JSON array on close.
  3. JSON object mode — single JSON dict on close.
  4. CSV curated columns — header matches spec.columns, extra keys excluded.
  5. CSV --full mode — header taken from first record's keys.
  6. Unknown extension — raises ConfigError.
  7. File is closed even if write_record raises (finally guarantee).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kctl_accurate.core.streaming import UNSUPPORTED_EXT_MESSAGE, OutputSink
from kctl_lib.exceptions import ConfigError

# ── fixtures ────────────────────────────────────────────────────────────────

_COLUMNS = ["id", "name", "email"]

_ROW1 = {"id": 1, "name": "PT Alpha", "email": "alpha@example.com", "extra": "ignored"}
_ROW2 = {"id": 2, "name": "PT Beta", "email": "beta@example.com", "extra": "also ignored"}


# ── 1. JSONL ─────────────────────────────────────────────────────────────────


def test_jsonl_writes_one_line_per_record(tmp_path: Path) -> None:
    """Each write_record produces exactly one JSON object on its own line."""
    out = tmp_path / "out.jsonl"
    with OutputSink(out, columns=_COLUMNS) as sink:
        sink.write_record(_ROW1)
        sink.write_record(_ROW2)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}: {lines}"

    obj1 = json.loads(lines[0])
    obj2 = json.loads(lines[1])
    assert obj1["id"] == 1
    assert obj2["name"] == "PT Beta"


def test_jsonl_no_array_brackets(tmp_path: Path) -> None:
    """JSONL output must NOT start with '[' — it is not a JSON array."""
    out = tmp_path / "out.jsonl"
    with OutputSink(out, columns=_COLUMNS) as sink:
        sink.write_record(_ROW1)

    content = out.read_text(encoding="utf-8")
    assert not content.startswith("["), "JSONL must not start with '['"


def test_ndjson_extension_accepted(tmp_path: Path) -> None:
    """.ndjson extension is treated identically to .jsonl."""
    out = tmp_path / "out.ndjson"
    with OutputSink(out) as sink:
        sink.write_record(_ROW1)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == 1


# ── 2. JSON array mode ────────────────────────────────────────────────────────


def test_json_array_mode_writes_list(tmp_path: Path) -> None:
    """JSON array mode produces a single JSON array containing all records."""
    out = tmp_path / "out.json"
    with OutputSink(out, columns=_COLUMNS, mode="array") as sink:
        sink.write_record(_ROW1)
        sink.write_record(_ROW2)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) == 2
    assert payload[0]["id"] == 1
    assert payload[1]["name"] == "PT Beta"


# ── 3. JSON object mode ───────────────────────────────────────────────────────


def test_json_object_mode_writes_dict(tmp_path: Path) -> None:
    """JSON object mode writes a single dict (not a list)."""
    out = tmp_path / "out.json"
    with OutputSink(out, columns=_COLUMNS, mode="object") as sink:
        sink.write_record(_ROW1)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert payload["id"] == 1
    assert payload["name"] == "PT Alpha"


# ── 4. CSV curated columns ────────────────────────────────────────────────────


def test_csv_curated_columns_header_and_rows(tmp_path: Path) -> None:
    """CSV projects to spec.columns; extra keys are excluded."""
    out = tmp_path / "out.csv"
    with OutputSink(out, columns=_COLUMNS) as sink:
        sink.write_record(_ROW1)
        sink.write_record(_ROW2)

    lines = out.read_text(encoding="utf-8").splitlines()
    # Header + 2 data rows
    assert len(lines) == 3, lines
    assert lines[0] == "id,name,email"
    assert "PT Alpha" in lines[1]
    assert "extra" not in lines[1]


# ── 5. CSV --full mode ────────────────────────────────────────────────────────


def test_csv_full_mode_uses_all_keys_from_first_record(tmp_path: Path) -> None:
    """--full mode derives header from the first record's keys."""
    out = tmp_path / "out.csv"
    with OutputSink(out, columns=_COLUMNS, full=True) as sink:
        sink.write_record(_ROW1)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    # All keys from _ROW1 must appear in the header
    header_cols = lines[0].split(",")
    for key in _ROW1:
        assert key in header_cols, f"Key {key!r} missing from header: {header_cols}"


# ── 6. Unknown extension raises ConfigError ───────────────────────────────────


def test_unknown_extension_raises_config_error(tmp_path: Path) -> None:
    """Unsupported extension raises ConfigError before entering context."""
    bad_path = tmp_path / "out.xlsx"
    with pytest.raises(ConfigError, match="Unsupported"):
        OutputSink(bad_path)


def test_unsupported_ext_message_is_accurate(tmp_path: Path) -> None:
    """The error message mentions the supported extensions."""
    bad_path = tmp_path / "out.parquet"
    with pytest.raises(ConfigError) as exc_info:
        OutputSink(bad_path)
    assert ".jsonl" in str(exc_info.value)
    assert ".csv" in str(exc_info.value)


# ── 7. File is closed even if write_record raises ─────────────────────────────


def test_file_closed_on_write_error(tmp_path: Path) -> None:
    """__exit__ closes the file handle even if write_record raises."""
    out = tmp_path / "out.jsonl"
    sink = OutputSink(out, columns=_COLUMNS)
    fh_ref = None

    class _Boom(Exception):
        pass

    try:
        with sink:
            fh_ref = sink._fh
            raise _Boom("simulated write failure")
    except _Boom:
        pass

    # The file handle must be closed
    assert fh_ref is not None
    assert fh_ref.closed


# ── helpers ───────────────────────────────────────────────────────────────────


def test_supports_returns_true_for_valid_extensions(tmp_path: Path) -> None:
    for ext in (".jsonl", ".ndjson", ".json", ".csv"):
        assert OutputSink.supports(tmp_path / f"file{ext}"), f"{ext} should be supported"


def test_supports_returns_false_for_unknown_extension(tmp_path: Path) -> None:
    assert not OutputSink.supports(tmp_path / "file.xlsx")
    assert not OutputSink.supports(tmp_path / "file.parquet")


def test_record_count_tracks_writes(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    with OutputSink(out) as sink:
        assert sink.record_count == 0
        sink.write_record(_ROW1)
        assert sink.record_count == 1
        sink.write_record(_ROW2)
        assert sink.record_count == 2
