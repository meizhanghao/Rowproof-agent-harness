"""Bounded source ingestion and a host-owned, deterministic business oracle."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from .contracts import SOURCE_COLUMNS, TaskContract


@dataclass(frozen=True)
class SourceRow:
    row_id: str
    values: dict[str, str]


@dataclass(frozen=True)
class SourceSnapshot:
    raw_bytes: bytes
    sha256: str
    rows: tuple[SourceRow, ...]


@dataclass(frozen=True)
class ExpectedArtifacts:
    clean_rows: list[dict[str, str]]
    lineage: list[dict[str, str]]
    report: dict[str, int | str]


def read_source(path: Path, contract: TaskContract) -> SourceSnapshot:
    with path.open("rb") as handle:
        raw = handle.read(contract.limits.max_input_bytes + 1)
    if len(raw) > contract.limits.max_input_bytes:
        raise ValueError("input byte limit exceeded")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != SOURCE_COLUMNS:
        raise ValueError(f"input header must be exactly {SOURCE_COLUMNS}")
    rows = []
    for index, row in enumerate(reader, start=1):
        if index > contract.limits.max_input_rows:
            raise ValueError("input row limit exceeded")
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"malformed CSV record at data row {index}")
        rows.append(SourceRow(f"r{index:06d}", row))
    if not rows:
        raise ValueError("input must contain at least one data row")
    return SourceSnapshot(raw, hashlib.sha256(raw).hexdigest(), tuple(rows))


def parse_amount(text: str, contract: TaskContract) -> str | None:
    try:
        value = Decimal(text.strip())
        if not value.is_finite():
            return None
        if not contract.rules.amount_min <= value <= contract.rules.amount_max:
            return None
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Canonicalize negative zero, if supplied as '-0'.
        return format(abs(value) if value == 0 else value, ".2f")
    except (InvalidOperation, ValueError):
        return None


def parse_date(text: str, contract: TaskContract) -> str | None:
    text = text.strip()
    for fmt in contract.rules.date_formats:
        separator = "/" if "/" in fmt else "-"
        if not re.fullmatch(rf"\d{{4}}{separator}\d{{2}}{separator}\d{{2}}", text):
            continue
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def expected_artifacts(source: SourceSnapshot, contract: TaskContract) -> ExpectedArtifacts:
    """Compute expected outcomes from source and contract, never from agent claims.

    Rule precedence is part of orders.v1: required ID, customer, amount, date,
    then duplicate detection. An invalid earlier row does not reserve its ID.
    """
    seen: set[str] = set()
    clean: list[dict[str, str]] = []
    lineage: list[dict[str, str]] = []
    for source_row in source.rows:
        row = {key: value.strip() for key, value in source_row.values.items()}
        amount = parse_amount(row["amount"], contract)
        date = parse_date(row["order_date"], contract)
        if not row["order_id"]:
            reason = "missing_order_id"
        elif not row["customer"]:
            reason = "missing_customer"
        elif amount is None:
            reason = "invalid_amount"
        elif date is None:
            reason = "invalid_date"
        elif row["order_id"] in seen:
            reason = "duplicate_order_id"
        else:
            reason = "accepted"
            seen.add(row["order_id"])
            clean.append(
                {
                    "_row_id": source_row.row_id,
                    "order_id": row["order_id"],
                    "customer": row["customer"],
                    "amount": amount,
                    "order_date": date,
                }
            )
        lineage.append(
            {
                "row_id": source_row.row_id,
                "action": "keep" if reason == "accepted" else "reject",
                "reason": reason,
            }
        )
    total = sum((Decimal(row["amount"]) for row in clean), Decimal("0"))
    return ExpectedArtifacts(
        clean,
        lineage,
        {
            "input_rows": len(source.rows),
            "kept_rows": len(clean),
            "rejected_rows": len(source.rows) - len(clean),
            "total_amount": format(total, ".2f"),
        },
    )
