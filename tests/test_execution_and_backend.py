import json
from unittest.mock import MagicMock, patch

from rowproof.backends import BackendError, OllamaBackend, ProposalContext
from rowproof.contracts import Limits
from rowproof.executors import ProcessExecutor
from tests.support import ProjectCase


class ExecutionTests(ProjectCase):
    def execute(self, script: str, limits: Limits):
        program = self.root / "test_program.py"
        program.write_text(script, encoding="utf-8")
        input_dir, output_dir = self.root / "input", self.root / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        return ProcessExecutor().execute(program, input_dir, output_dir, limits)

    def test_timeout_is_not_success(self):
        result = self.execute(
            "import time\ntime.sleep(30)\n", Limits(execution_timeout_seconds=0.1)
        )
        self.assertTrue(result.timed_out)
        self.assertFalse(result.succeeded)

    def test_exit_zero_with_excessive_logs_is_not_success(self):
        result = self.execute("print('x' * 10000)\n", Limits(max_log_bytes=1024))
        self.assertTrue(result.log_limit_exceeded)
        self.assertFalse(result.succeeded)
        self.assertLessEqual(len(result.log_excerpt), 1024)


class OllamaAdapterTests(ProjectCase):
    def response(self, envelope):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(envelope).encode()
        return response

    @patch("rowproof.backends.urlopen")
    def test_structured_code_proposal_and_feedback_request(self, mocked):
        mocked.return_value = self.response(
            {
                "done": True,
                "response": json.dumps({"summary": "candidate", "python_code": "print('ok')"}),
                "prompt_eval_count": 20,
                "eval_count": 10,
            }
        )
        context = ProposalContext(
            self.contract.as_dict(), [], 2, "old code", {"kind": "verification"}
        )
        generated = OllamaBackend("local-test").propose(context)
        self.assertEqual(generated.proposal.python_code, "print('ok')")
        body = json.loads(mocked.call_args.args[0].data)
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"]["type"], "object")
        self.assertIn("old code", body["prompt"])
        self.assertEqual(generated.usage["eval_count"], 10)

    @patch("rowproof.backends.urlopen")
    def test_incomplete_or_malformed_generation_fails(self, mocked):
        context = ProposalContext(self.contract.as_dict(), [], 1)
        for envelope in [{"done": False, "response": "{}"}, {"done": True, "response": "not JSON"}]:
            mocked.return_value = self.response(envelope)
            with self.assertRaises(BackendError):
                OllamaBackend("local-test").propose(context)

    @patch("rowproof.backends.urlopen")
    def test_response_size_limit(self, mocked):
        mocked.return_value.__enter__.return_value.read.return_value = b"x" * 101
        with self.assertRaisesRegex(BackendError, "byte limit"):
            OllamaBackend("local-test", max_response_bytes=100).propose(
                ProposalContext(self.contract.as_dict(), [], 1)
            )
