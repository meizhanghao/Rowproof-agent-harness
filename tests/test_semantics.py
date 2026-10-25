import csv
import json
from importlib.resources import files
from pathlib import Path

from pydantic import ValidationError

from rowproof.contracts import TaskContract
from rowproof.source import expected_artifacts, read_source
from tests.support import ProjectCase


class SemanticsTests(ProjectCase):
    def test_repository_examples_match_packaged_assets(self):
        directory = Path(__file__).resolve().parents[1] / "examples" / "orders"
        for repository_name, asset_name in [
            ("input.csv", "orders.csv"),
            ("contract.json", "orders.contract.json"),
        ]:
            self.assertEqual(
                (directory / repository_name).read_bytes(),
                files("rowproof").joinpath("assets/" + asset_name).read_bytes(),
            )

    def test_hand_authored_golden_is_the_oracle(self):
        golden = Path(__file__).resolve().parents[1] / "examples" / "orders" / "expected"
        expected = expected_artifacts(self.source(), self.contract)
        with (golden / "clean.csv").open(encoding="utf-8", newline="") as handle:
            self.assertEqual(expected.clean_rows, list(csv.DictReader(handle)))
        self.assertEqual(
            expected.lineage, json.loads((golden / "lineage.json").read_text(encoding="utf-8"))
        )
        self.assertEqual(
            expected.report, json.loads((golden / "report.json").read_text(encoding="utf-8"))
        )

    def test_first_valid_not_first_seen(self):
        source = self.source(
            [
                [" A1 ", "Bob", "NaN", "2026-10-01"],
                ["A1", " Bob ", "1.005", "2026/10/01"],
                ["A1", "Bob", "10", "2026-10-01"],
            ]
        )
        expected = expected_artifacts(source, self.contract)
        self.assertEqual([row["_row_id"] for row in expected.clean_rows], ["r000002"])
        self.assertEqual(
            [row["reason"] for row in expected.lineage],
            ["invalid_amount", "accepted", "duplicate_order_id"],
        )

    def test_round_each_row_before_sum_and_normalize_negative_zero(self):
        source = self.source(
            [
                ["A1", "Bob", "1.005", "2026-10-01"],
                ["A2", "Bob", "1.005", "2026-10-01"],
                ["A3", "Bob", "-0", "2026-10-01"],
            ]
        )
        result = expected_artifacts(source, self.contract)
        self.assertEqual(result.report["total_amount"], "2.02")
        self.assertEqual(result.clean_rows[-1]["amount"], "0.00")

    def test_reject_nonfinite_impossible_and_noncanonical_dates(self):
        source = self.source(
            [
                ["A1", "Bob", "Infinity", "2026-10-01"],
                ["A2", "Bob", "1", "2026-02-30"],
                ["A3", "Bob", "1", "2026-1-01"],
            ]
        )
        result = expected_artifacts(source, self.contract)
        self.assertEqual(result.report["kept_rows"], 0)
        self.assertEqual(
            [row["reason"] for row in result.lineage],
            ["invalid_amount", "invalid_date", "invalid_date"],
        )

    def test_validation_precedence_is_stable(self):
        result = expected_artifacts(self.source([["", "", "NaN", "bad"]]), self.contract)
        self.assertEqual(result.lineage[0]["reason"], "missing_order_id")

    def test_contract_controls_amount_bounds_and_date_formats(self):
        changed = TaskContract.model_validate(
            {
                "task_id": "narrow",
                "rules": {"amount_min": "2", "date_formats": ["%Y-%m-%d"]},
            }
        )
        source = self.source(
            [
                ["A1", "Bob", "1.999", "2026-10-01"],
                ["A2", "Bob", "2", "2026/10/01"],
                ["A3", "Bob", "2", "2026-10-01"],
            ]
        )
        result = expected_artifacts(source, changed)
        self.assertEqual(
            [row["reason"] for row in result.lineage],
            ["invalid_amount", "invalid_date", "accepted"],
        )

    def test_invalid_contracts_are_rejected(self):
        for payload in [
            {"task_id": "bad", "unexpected": True},
            {"task_id": "bad", "limits": {"max_attempts": 0}},
            {"task_id": "bad", "rules": {"amount_min": "10", "amount_max": "1"}},
            {"task_id": "bad", "rules": {"date_formats": ["%Y-%m-%d", "%Y-%m-%d"]}},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                TaskContract.model_validate(payload)

    def test_reject_bad_header_and_oversized_input(self):
        self.input_path.write_text(
            "order_id,customer,amount,order_date,_row_id\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "header"):
            self.source()
        self.contract.limits.max_input_bytes = 1
        with self.assertRaisesRegex(ValueError, "byte limit"):
            read_source(self.input_path, self.contract)

    def test_reject_malformed_record_and_empty_dataset(self):
        for text in [
            "order_id,customer,amount,order_date\nA,B,1\n",
            "order_id,customer,amount,order_date\n",
        ]:
            self.input_path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                self.source()
