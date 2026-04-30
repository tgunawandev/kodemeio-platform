"""OutputSink — file output for module list/get commands.

Supports three formats based on file extension:

* ``.jsonl`` / ``.ndjson`` — one JSON object per line, written immediately
  as each record arrives (streaming, low-memory).
* ``.json`` — buffered.  ``mode="array"`` writes a JSON array on close;
  ``mode="object"`` writes the single dict.
* ``.csv`` — header from curated *columns* (or all keys of the first
  record when *full=True*).  Non-scalar cell values are coerced to JSON
  strings so nested objects/arrays do not cause csv.DictWriter to raise.

Unknown extensions raise :class:`kctl_lib.exceptions.ConfigError` (exit 2)
— wrong file path is a config-shaped error, not an API error.

.. note::
    The SDK's ``paginate_list`` function returns a fully-materialised
    ``list[dict]``, not a generator.  This means we cannot stream
    individual HTTP pages — the full dataset is in memory before the first
    ``write_record`` call.  JSONL streaming here still provides a benefit:
    records are written to disk one-by-one as they come out of the
    (in-memory) list, so the *peak* memory needed for serialisation is
    O(record) rather than O(dataset).  A future SDK refactor that turns
    ``paginate_list`` into a page-by-page generator would make JSONL truly
    constant-memory.
"""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from typing import IO, Mapping, Sequence

from kctl_lib.exceptions import ConfigError

UNSUPPORTED_EXT_MESSAGE = "Unsupported output extension. Use .jsonl, .ndjson, .json, or .csv"

_JSONL_EXTS = {".jsonl", ".ndjson"}
_JSON_EXT = ".json"
_CSV_EXT = ".csv"


def _coerce(value: object) -> str | int | float | bool | None:
    """Coerce a value to a CSV-safe scalar.

    Strings, ints, floats, bools, and None pass through unchanged.
    Everything else (dicts, lists, …) is serialised as a JSON string so
    nested Accurate objects (e.g. invoice line-items) are not silently
    dropped.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


class OutputSink:
    """Single-file output sink that picks JSONL / JSON / CSV based on extension.

    Usage::

        with OutputSink(Path("out.jsonl"), columns=spec.columns) as sink:
            for row in rows:
                sink.write_record(row)
        print(f"Wrote {sink.record_count} records")

    Args:
        path:    Destination file path.  Extension determines format.
        columns: Curated column list.  Used as the CSV header (unless
                 *full* is True) and ignored for JSON/JSONL.
        full:    When True, CSV header is taken from the first record's
                 keys rather than *columns*.
        mode:    ``"array"`` (default) — JSON output is a list;
                 ``"object"`` — JSON output is a single dict.  Ignored
                 for JSONL and CSV.

    Raises:
        ConfigError: If the extension is not ``.jsonl``, ``.ndjson``,
                     ``.json``, or ``.csv``.
    """

    def __init__(
        self,
        path: Path,
        columns: Sequence[str] | None = None,
        full: bool = False,
        mode: str = "array",
    ) -> None:
        ext = path.suffix.lower()
        if ext not in (_JSON_EXT, _CSV_EXT) and ext not in _JSONL_EXTS:
            raise ConfigError(UNSUPPORTED_EXT_MESSAGE)

        self._path = path
        self._columns = list(columns) if columns else []
        self._full = full
        self._mode = mode
        self._ext = ext

        # Runtime state
        self._fh: IO[str] | None = None
        self._buffer: list[dict] = []  # JSON array mode
        self._csv_writer: csv.DictWriter | None = None  # type: ignore[type-arg]
        self._csv_fieldnames: list[str] = []
        self._record_count: int = 0

    # ── context manager ────────────────────────────────────────────────────

    def __enter__(self) -> "OutputSink":
        self._fh = self._path.open("w", encoding="utf-8", newline="")
        return self

    def __exit__(self, *exc: object) -> None:
        try:
            if self._fh is not None:
                # Flush buffered formats on clean exit (not on exception —
                # writing a partial JSON array is worse than no file).
                if exc[0] is None:
                    if self._ext == _JSON_EXT:
                        if self._mode == "object":
                            obj = self._buffer[0] if self._buffer else {}
                            self._fh.write(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
                        else:
                            self._fh.write(json.dumps(self._buffer, indent=2, ensure_ascii=False, default=str))
        finally:
            if self._fh is not None:
                self._fh.close()
                self._fh = None

    # ── write ──────────────────────────────────────────────────────────────

    def write_record(self, record: Mapping) -> None:  # type: ignore[type-arg]
        """Write one record to the sink.

        For JSONL: immediately flushes to disk (streaming).
        For JSON: appends to an in-memory buffer; flushed on ``__exit__``.
        For CSV: writes header on first call, then one data row.
        """
        if self._fh is None:
            raise RuntimeError("OutputSink must be used as a context manager")

        rec = dict(record)
        self._record_count += 1

        if self._ext in _JSONL_EXTS:
            self._fh.write(json.dumps(rec, ensure_ascii=False, default=str))
            self._fh.write("\n")
            self._fh.flush()

        elif self._ext == _JSON_EXT:
            self._buffer.append(rec)

        elif self._ext == _CSV_EXT:
            # Determine column headers on first record
            if self._csv_writer is None:
                if self._full or not self._columns:
                    self._csv_fieldnames = list(rec.keys())
                else:
                    self._csv_fieldnames = list(self._columns)

                self._csv_writer = csv.DictWriter(
                    self._fh,
                    fieldnames=self._csv_fieldnames,
                    extrasaction="ignore",
                    lineterminator="\n",
                )
                self._csv_writer.writeheader()

            # Coerce non-scalar values so DictWriter doesn't choke
            coerced = {k: _coerce(rec.get(k)) for k in self._csv_fieldnames}
            self._csv_writer.writerow(coerced)

    # ── helpers ────────────────────────────────────────────────────────────

    @property
    def record_count(self) -> int:
        """Number of records written so far."""
        return self._record_count

    @staticmethod
    def supports(path: Path) -> bool:
        """Return True if the file extension is supported."""
        ext = path.suffix.lower()
        return ext in _JSONL_EXTS or ext in (_JSON_EXT, _CSV_EXT)
