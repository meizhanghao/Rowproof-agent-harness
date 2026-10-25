import csv
import json

from rowproof.contracts import OUTPUT_COLUMNS, write_json
from rowproof.verifier import verify
from tests.support import ProjectCase


class VerifierTests(ProjectCase):
    def test_worker_implementation_independently_matches_golden_rules(self):
        source, artifacts = self.correct_artifacts()
        result = verify(source, self.contract, artifacts)
        self.assertTrue(result.passed, result.issues)
        self.assertEqual(result.expected["total_amount"], "52.53")
        self.assertEqual(set(result.artifact_sha256), {"clean.csv", "lineage.json", "report.json"})

    def test_detect_data_loss_even_when_worker_report_is_self_consistent(self):
        source, artifacts = self.correct_artifacts()
        with (artifacts / "clean.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))[:-1]
        with (artifacts / "clean.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        write_json(
            artifacts / "report.json",
            {
                "input_rows": 12,
                "kept_rows": 5,
                "rejected_rows": 7,
                "total_amount": "40.03",
            },
        )
        lineage = json.loads((artifacts / "lineage.json").read_text(encoding="utf-8"))
        lineage[-1] = {"row_id": "r000012", "action": "reject", "reason": "invalid_amount"}
        write_json(artifacts / "lineage.json", lineage)
        result = verify(source, self.contract, artifacts)
        self.assertFalse(result.passed)
        self.assertTrue(
            {"CLEAN_ROWS_MISMATCH", "LINEAGE_MISMATCH", "REPORT_MISMATCH"}
            <= {item["code"] for item in result.issues}
        )

    def test_detect_lineage_spoofing(self):
        source, artifacts = self.correct_artifacts()
        lineage = json.loads((artifacts / "lineage.json").read_text(encoding="utf-8"))
        lineage[0]["row_id"] = lineage[1]["row_id"]
        write_json(artifacts / "lineage.json", lineage)
        self.assertIn(
            "LINEAGE_MISMATCH",
            [item["code"] for item in verify(source, self.contract, artifacts).issues],
        )

    def test_report_rejects_booleans_and_duplicate_keys(self):
        source, artifacts = self.correct_artifacts()
        for raw in [
            '{"input_rows":true,"kept_rows":6,"rejected_rows":6,"total_amount":"52.53"}',
            '{"input_rows":12,"input_rows":12,"kept_rows":6,"rejected_rows":6,"total_amount":"52.53"}',
        ]:
            (artifacts / "report.json").write_text(raw, encoding="utf-8")
            self.assertIn(
                "REPORT_INVALID",
                [item["code"] for item in verify(source, self.contract, artifacts).issues],
            )

    def test_reject_output_over_byte_budget(self):
        source, artifacts = self.correct_artifacts()
        self.contract.limits.max_output_bytes = 10
        result = verify(source, self.contract, artifacts)
        self.assertEqual(result.issues[0]["code"], "ARTIFACT_LAYOUT")

    def test_reject_missing_and_unexpected_artifacts(self):
        source, artifacts = self.correct_artifacts()
        (artifacts / "extra.txt").write_text("unexpected", encoding="utf-8")
        self.assertFalse(verify(source, self.contract, artifacts).passed)

    def test_reject_symbolic_link_artifact(self):
        source, artifacts = self.correct_artifacts()
        original = self.root / "external.csv"
        (artifacts / "clean.csv").rename(original)
        try:
            (artifacts / "clean.csv").symlink_to(original)
        except OSError:
            self.skipTest("creating symlinks requires Windows developer mode or privileges")
        self.assertFalse(verify(source, self.contract, artifacts).passed)
