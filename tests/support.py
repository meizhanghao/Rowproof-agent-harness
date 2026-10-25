from __future__ import annotations

import csv
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from rowproof.backends import FixtureBackend, ProposalContext
from rowproof.contracts import SOURCE_COLUMNS, TaskContract, write_json
from rowproof.executors import ProcessExecutor
from rowproof.source import read_source


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rowproof-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.contract = TaskContract.model_validate_json(
            files("rowproof").joinpath("assets/orders.contract.json").read_text(encoding="utf-8")
        )
        self.input_path = self.root / "source.csv"
        self.input_path.write_text(
            files("rowproof").joinpath("assets/orders.csv").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def source(self, rows: list[list[str]] | None = None):
        if rows is not None:
            with self.input_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(SOURCE_COLUMNS)
                writer.writerows(rows)
        return read_source(self.input_path, self.contract)

    def correct_artifacts(self):
        snapshot = self.root / "snapshot"
        snapshot.mkdir()
        source = self.source()
        (snapshot / "source.csv").write_bytes(source.raw_bytes)
        write_json(snapshot / "contract.json", self.contract.as_dict())
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        program = self.root / "program.py"
        code = FixtureBackend("always-correct").propose(
            ProposalContext(self.contract.as_dict(), [], 1)
        )
        program.write_text(code.proposal.python_code, encoding="utf-8")
        result = ProcessExecutor().execute(program, snapshot, artifacts, self.contract.limits)
        self.assertTrue(result.succeeded, result.log_excerpt)
        return source, artifacts
