"""The host-owned contract. Version 1 deliberately supports one business profile."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SOURCE_COLUMNS = ["order_id", "customer", "amount", "order_date"]
OUTPUT_COLUMNS = ["_row_id", *SOURCE_COLUMNS]
ARTIFACT_NAMES = ("clean.csv", "lineage.json", "report.json")
Reason = Literal[
    "accepted",
    "missing_order_id",
    "missing_customer",
    "invalid_amount",
    "invalid_date",
    "duplicate_order_id",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderRules(StrictModel):
    amount_min: Decimal = Decimal("0")
    amount_max: Decimal = Decimal("1000000000")
    decimal_places: Literal[2] = 2
    rounding: Literal["ROUND_HALF_UP"] = "ROUND_HALF_UP"
    duplicate_policy: Literal["first_valid"] = "first_valid"
    date_formats: Annotated[
        list[Literal["%Y-%m-%d", "%Y/%m/%d"]], Field(min_length=1, max_length=2)
    ] = ["%Y-%m-%d", "%Y/%m/%d"]

    @model_validator(mode="after")
    def valid_bounds(self) -> OrderRules:
        if not self.amount_min.is_finite() or not self.amount_max.is_finite():
            raise ValueError("amount bounds must be finite")
        if not Decimal("0") <= self.amount_min <= self.amount_max <= Decimal("1e12"):
            raise ValueError("require 0 <= amount_min <= amount_max <= 1e12")
        if len(set(self.date_formats)) != len(self.date_formats):
            raise ValueError("date_formats must be unique")
        return self


class Limits(StrictModel):
    max_input_rows: int = Field(default=10000, ge=1, le=100000)
    max_input_bytes: int = Field(default=2_000_000, ge=1, le=20_000_000)
    max_output_bytes: int = Field(default=8_000_000, ge=1, le=50_000_000)
    max_attempts: int = Field(default=3, ge=1, le=5)
    execution_timeout_seconds: float = Field(default=10.0, ge=0.1, le=120)
    max_log_bytes: int = Field(default=64000, ge=1024, le=1_000_000)


class TaskContract(StrictModel):
    schema_version: Literal[1] = 1
    task_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    profile: Literal["orders.v1"] = "orders.v1"
    rules: OrderRules = Field(default_factory=OrderRules)
    limits: Limits = Field(default_factory=Limits)

    @classmethod
    def load(cls, path: Path) -> TaskContract:
        if path.stat().st_size > 100000:
            raise ValueError("contract exceeds 100 KB")
        return cls.model_validate_json(path.read_text(encoding="utf-8-sig"))

    def as_dict(self) -> dict:
        return self.model_dump(mode="json")


class LineageItem(StrictModel):
    row_id: str
    action: Literal["keep", "reject"]
    reason: Reason


class WorkerReport(StrictModel):
    input_rows: int = Field(ge=0, strict=True)
    kept_rows: int = Field(ge=0, strict=True)
    rejected_rows: int = Field(ge=0, strict=True)
    total_amount: str = Field(pattern=r"^\d+\.\d{2}$")


class CodeProposal(StrictModel):
    summary: str = Field(min_length=1, max_length=2000)
    python_code: str = Field(min_length=1, max_length=100000)

    @field_validator("python_code")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("code contains a NUL character")
        return value


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
