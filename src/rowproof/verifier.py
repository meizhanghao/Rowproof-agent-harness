"""Independent host verification; the generated program cannot replace this module."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .contracts import ARTIFACT_NAMES, OUTPUT_COLUMNS, LineageItem, TaskContract, WorkerReport
from .source import SourceSnapshot, expected_artifacts


@dataclass
class VerificationResult:
    passed: bool = False
    issues: list[dict] = field(default_factory=list)
    expected: dict = field(default_factory=dict)
    observed: dict = field(default_factory=dict)
    artifact_sha256: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _unique_json_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _json(raw: bytes) -> object:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_keys)


def verify(source: SourceSnapshot, contract: TaskContract, directory: Path) -> VerificationResult:
    expected = expected_artifacts(source, contract)
    result = VerificationResult(expected=expected.report)

    def issue(code: str, detail: str, **extra: object) -> None:
        result.issues.append({"code": code, "detail": detail, **extra})

    try:
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("artifact directory is missing or is a symbolic link")
        names = {path.name for path in directory.iterdir()}
        if names - set(ARTIFACT_NAMES) - {"manifest.json"}:
            raise ValueError("unexpected entries in artifact directory")
        blobs = {}
        total_size = 0
        for name in ARTIFACT_NAMES:
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"missing/non-regular artifact: {name}")
            remaining = contract.limits.max_output_bytes - total_size
            with path.open("rb") as handle:
                raw = handle.read(remaining + 1)
            total_size += len(raw)
            if total_size > contract.limits.max_output_bytes:
                raise ValueError("combined output byte limit exceeded")
            blobs[name] = raw
            result.artifact_sha256[name] = hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError) as error:
        issue("ARTIFACT_LAYOUT", str(error))
        return result

    try:
        reader = csv.DictReader(io.StringIO(blobs["clean.csv"].decode("utf-8-sig"), newline=""))
        if reader.fieldnames != OUTPUT_COLUMNS:
            raise ValueError(f"output header must be {OUTPUT_COLUMNS}")
        rows = []
        for row in reader:
            if len(rows) >= contract.limits.max_input_rows:
                raise ValueError("output row limit exceeded")
            if None in row or any(value is None for value in row.values()):
                raise ValueError("malformed output CSV record")
            rows.append(row)
        result.observed["output_rows"] = len(rows)
        if rows != expected.clean_rows:
            actual_ids = [row["_row_id"] for row in rows]
            wanted_ids = [row["_row_id"] for row in expected.clean_rows]
            missing = sorted(set(wanted_ids) - set(actual_ids))[:10]
            extra = sorted(set(actual_ids) - set(wanted_ids))[:10]
            issue(
                "CLEAN_ROWS_MISMATCH",
                "rows, canonical values, or row order differ",
                missing=missing,
                unexpected=extra,
                expected_rows=len(wanted_ids),
                actual_rows=len(actual_ids),
            )
            # Limit feedback while identifying the first concrete divergence.
            for index, (wanted, actual) in enumerate(zip(expected.clean_rows, rows)):
                if wanted != actual:
                    issue(
                        "FIRST_ROW_DIFF",
                        f"first differing output row: {index + 1}",
                        expected_row=wanted,
                        actual_row=actual,
                    )
                    break
    except (ValueError, UnicodeError, csv.Error) as error:
        issue("CLEAN_CSV_INVALID", str(error))

    try:
        lineage = TypeAdapter(list[LineageItem]).validate_python(_json(blobs["lineage.json"]))
        actual_lineage = [item.model_dump() for item in lineage]
        if actual_lineage != expected.lineage:
            issue("LINEAGE_MISMATCH", "each source row must have its correct action and reason")
    except (ValueError, UnicodeError, ValidationError) as error:
        issue("LINEAGE_INVALID", str(error)[:1000])

    try:
        report = WorkerReport.model_validate(_json(blobs["report.json"]))
        result.observed["worker_report"] = report.model_dump()
        if report.model_dump() != expected.report:
            issue("REPORT_MISMATCH", "counts or amount total differ from host-computed results")
    except (ValueError, UnicodeError, ValidationError) as error:
        issue("REPORT_INVALID", str(error)[:1000])

    result.passed = not result.issues
    return result
