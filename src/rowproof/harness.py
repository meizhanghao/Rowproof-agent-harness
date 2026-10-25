"""A bounded proposal -> execution -> independent verification -> repair loop."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .backends import BackendError, CodeBackend, ProposalContext
from .contracts import ARTIFACT_NAMES, TaskContract, write_json
from .executors import DockerExecutor, ProcessExecutor
from .source import read_source
from .verifier import VerificationResult, verify

TRANSITIONS = {
    "CREATED": {"GENERATING", "FAILED"},
    "GENERATING": {"EXECUTING", "REPAIRING", "FAILED"},
    "EXECUTING": {"VALIDATING", "REPAIRING", "FAILED"},
    "VALIDATING": {"PASSED", "REPAIRING", "FAILED"},
    "REPAIRING": {"GENERATING", "FAILED"},
    "PASSED": set(),
    "FAILED": set(),
}


@dataclass
class RunResult:
    run_id: str
    status: str
    attempts: int
    elapsed_seconds: float
    backend: str
    executor: str
    run_directory: str
    published_directory: str | None
    last_feedback: dict | None

    def as_dict(self) -> dict:
        return asdict(self)


class EventLog:
    def __init__(self, path: Path):
        self.path, self.sequence = path, 0

    def append(self, event: str, **payload: object) -> None:
        self.sequence += 1
        record = {
            "sequence": self.sequence,
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _publish(root: Path, artifacts: Path, verification: VerificationResult, manifest: dict) -> Path:
    """Publish a complete directory only after all copied bytes match verified hashes."""
    staging = root / (".publishing-" + uuid.uuid4().hex)
    staging.mkdir()
    for name in ARTIFACT_NAMES:
        destination = staging / name
        shutil.copyfile(artifacts / name, destination)
        if (
            hashlib.sha256(destination.read_bytes()).hexdigest()
            != verification.artifact_sha256[name]
        ):
            raise ValueError("artifact changed between verification and publication")
    write_json(staging / "manifest.json", manifest)
    published = root / "published"
    os.replace(staging, published)
    return published


class Harness:
    def __init__(self, backend: CodeBackend, executor: ProcessExecutor | DockerExecutor):
        if backend.untrusted_code and not executor.isolated:
            raise ValueError("model-produced code requires the Docker executor")
        self.backend, self.executor = backend, executor

    def run(self, input_path: Path, contract: TaskContract, run_directory: Path) -> RunResult:
        start = time.monotonic()
        # Fail before asking a model to generate anything if its execution environment is absent.
        self.executor.preflight()
        source = read_source(input_path, contract)
        root = run_directory.resolve()
        root.mkdir(parents=True, exist_ok=False)
        snapshot = root / "snapshot"
        snapshot.mkdir()
        (snapshot / "source.csv").write_bytes(source.raw_bytes)
        write_json(snapshot / "contract.json", contract.as_dict())
        run_id = uuid.uuid4().hex
        contract_hash = hashlib.sha256((snapshot / "contract.json").read_bytes()).hexdigest()
        events = EventLog(root / "events.jsonl")
        state = "CREATED"
        events.append(
            "run_created",
            run_id=run_id,
            version=__version__,
            input_sha256=source.sha256,
            contract_sha256=contract_hash,
            backend=self.backend.name,
            executor=self.executor.name,
        )

        def transition(target: str, attempt: int) -> None:
            nonlocal state
            if target not in TRANSITIONS[state]:
                raise RuntimeError(f"invalid state transition {state} -> {target}")
            events.append("state_changed", previous=state, state=target, attempt=attempt)
            state = target

        feedback = None
        previous_code = None
        published = None
        attempt = 0
        for attempt in range(1, contract.limits.max_attempts + 1):
            transition("GENERATING", attempt)
            directory = root / "attempts" / f"{attempt:03d}"
            artifacts = directory / "artifacts"
            artifacts.mkdir(parents=True)
            context = ProposalContext(
                contract.as_dict(),
                [row.values for row in source.rows[:8]],
                attempt,
                previous_code,
                feedback,
            )
            try:
                generation = self.backend.propose(context)
                previous_code = generation.proposal.python_code
                (directory / "program.py").write_text(previous_code, encoding="utf-8")
                write_json(
                    directory / "proposal.json",
                    {
                        "summary": generation.proposal.summary,
                        "usage": generation.usage,
                    },
                )
                # Parsing is only a syntax check, never a security boundary.
                ast.parse(previous_code)
                events.append("code_proposed", attempt=attempt, usage=generation.usage)
            except (BackendError, ValueError, SyntaxError, RecursionError) as error:
                feedback = {
                    "kind": "generation",
                    "issues": [
                        {
                            "code": "GENERATION_ERROR",
                            "detail": str(error)[:2000],
                        }
                    ],
                }
            else:
                transition("EXECUTING", attempt)
                execution = self.executor.execute(
                    directory / "program.py", snapshot, artifacts, contract.limits
                )
                write_json(directory / "execution.json", execution.as_dict())
                events.append(
                    "execution_finished",
                    attempt=attempt,
                    returncode=execution.returncode,
                    timed_out=execution.timed_out,
                    elapsed_seconds=execution.elapsed_seconds,
                )
                if not execution.succeeded:
                    feedback = {
                        "kind": "execution",
                        "issues": [
                            {
                                "code": "EXECUTION_ERROR",
                                "detail": execution.as_dict(),
                            }
                        ],
                    }
                else:
                    transition("VALIDATING", attempt)
                    verification = verify(source, contract, artifacts)
                    write_json(directory / "verification.json", verification.as_dict())
                    events.append(
                        "verification_finished",
                        attempt=attempt,
                        passed=verification.passed,
                        issue_codes=[item["code"] for item in verification.issues],
                    )
                    if verification.passed:
                        manifest = {
                            "schema_version": 1,
                            "run_id": run_id,
                            "task_id": contract.task_id,
                            "rowproof_version": __version__,
                            "backend": self.backend.name,
                            "executor": self.executor.name,
                            "attempt": attempt,
                            "input_sha256": source.sha256,
                            "contract_sha256": contract_hash,
                            "artifact_sha256": verification.artifact_sha256,
                            "verified_summary": verification.expected,
                        }
                        published = _publish(root, artifacts, verification, manifest)
                        transition("PASSED", attempt)
                        break
                    feedback = {
                        "kind": "verification",
                        "issues": verification.issues,
                        "expected_summary": verification.expected,
                    }
            write_json(directory / "feedback.json", feedback)
            if attempt < contract.limits.max_attempts:
                transition("REPAIRING", attempt)
            else:
                transition("FAILED", attempt)

        result = RunResult(
            run_id,
            "passed" if published else "failed",
            attempt,
            round(time.monotonic() - start, 6),
            self.backend.name,
            self.executor.name,
            str(root),
            str(published) if published else None,
            None if published else feedback,
        )
        write_json(root / "result.json", result.as_dict())
        events.append(
            "run_finished",
            status=result.status,
            attempts=attempt,
            elapsed_seconds=result.elapsed_seconds,
        )
        return result
