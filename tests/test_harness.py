import json
import os
import shutil
import unittest

from rowproof.backends import FixtureBackend, Generation, OllamaBackend
from rowproof.contracts import CodeProposal
from rowproof.executors import DockerExecutor, ProcessExecutor
from rowproof.harness import Harness
from tests.support import ProjectCase


class HarnessTests(ProjectCase):
    def test_bad_candidate_is_repaired_then_published(self):
        original = self.input_path.read_bytes()
        result = Harness(FixtureBackend(), ProcessExecutor()).run(
            self.input_path,
            self.contract,
            self.root / "run",
        )
        self.assertEqual((result.status, result.attempts), ("passed", 2))
        self.assertEqual(self.input_path.read_bytes(), original)
        manifest = json.loads(
            (self.root / "run/published/manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["verified_summary"]["total_amount"], "52.53")
        events = [
            json.loads(line)
            for line in (self.root / "run/events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertIn("REPAIRING", [item.get("state") for item in events])
        self.assertEqual(events[-1]["status"], "passed")
        self.assertEqual([item["sequence"] for item in events], list(range(1, len(events) + 1)))

    def test_budget_exhaustion_never_publishes(self):
        self.contract.limits.max_attempts = 2
        result = Harness(FixtureBackend("always-broken"), ProcessExecutor()).run(
            self.input_path,
            self.contract,
            self.root / "run",
        )
        self.assertEqual((result.status, result.attempts), ("failed", 2))
        self.assertFalse((self.root / "run/published").exists())
        self.assertIsNone(result.published_directory)

    def test_syntax_error_is_fed_back_before_execution(self):
        class SyntaxThenCorrect(FixtureBackend):
            def propose(self, context):
                if context.feedback is None:
                    return Generation(CodeProposal(summary="invalid syntax", python_code="def :"))
                return super().propose(context)

        result = Harness(SyntaxThenCorrect("always-correct"), ProcessExecutor()).run(
            self.input_path,
            self.contract,
            self.root / "run",
        )
        self.assertEqual((result.status, result.attempts), ("passed", 2))
        first = self.root / "run/attempts/001"
        self.assertTrue((first / "feedback.json").exists())
        self.assertFalse((first / "execution.json").exists())

    def test_model_code_cannot_use_fixture_executor(self):
        with self.assertRaisesRegex(ValueError, "requires the Docker executor"):
            Harness(OllamaBackend("test-model"), ProcessExecutor())

    def test_existing_run_is_not_overwritten(self):
        path = self.root / "run"
        path.mkdir()
        marker = path / "marker.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            Harness(FixtureBackend(), ProcessExecutor()).run(self.input_path, self.contract, path)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


@unittest.skipUnless(
    os.environ.get("ROWPROOF_TEST_DOCKER") == "1" and shutil.which("docker"),
    "set ROWPROOF_TEST_DOCKER=1 after pulling the Docker image",
)
class DockerIntegrationTests(ProjectCase):
    def test_fixture_in_real_container(self):
        result = Harness(FixtureBackend(), DockerExecutor()).run(
            self.input_path,
            self.contract,
            self.root / "container-run",
        )
        self.assertEqual((result.status, result.attempts), ("passed", 2))
