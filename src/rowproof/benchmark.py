"""A small, scripted control-flow experiment. This is not a real-model benchmark."""

from __future__ import annotations

import csv
import json
import time
from importlib.resources import as_file, files
from pathlib import Path

from .backends import FixtureBackend, ProposalContext
from .contracts import TaskContract, write_json
from .executors import ProcessExecutor
from .harness import Harness
from .source import read_source
from .verifier import verify


def benchmark(output: Path, repetitions: int = 3) -> dict:
    if not 1 <= repetitions <= 20:
        raise ValueError("repetitions must be between 1 and 20")
    output.mkdir(parents=True, exist_ok=False)
    records = []
    with as_file(files("rowproof").joinpath("assets/orders.csv")) as source_path:
        with as_file(files("rowproof").joinpath("assets/orders.contract.json")) as contract_path:
            contract = TaskContract.load(contract_path)
            source = read_source(source_path, contract)
            for index in range(repetitions):
                # Baseline reports success using exit code; an offline verifier measures truth.
                root = output / f"exit-code-only-{index}"
                root.mkdir()
                snapshot, artifacts = root / "snapshot", root / "artifacts"
                snapshot.mkdir()
                artifacts.mkdir()
                (snapshot / "source.csv").write_bytes(source.raw_bytes)
                write_json(snapshot / "contract.json", contract.as_dict())
                proposal = FixtureBackend().propose(ProposalContext(contract.as_dict(), [], 1))
                program = root / "program.py"
                program.write_text(proposal.proposal.python_code, encoding="utf-8")
                start = time.monotonic()
                execution = ProcessExecutor().execute(program, snapshot, artifacts, contract.limits)
                offline = verify(source, contract, artifacts)
                records.append(
                    {
                        "policy": "exit-code-only",
                        "repetition": index,
                        "reported_success": execution.succeeded,
                        "artifact_valid": offline.passed,
                        "attempts": 1,
                        "elapsed_seconds": round(time.monotonic() - start, 6),
                    }
                )
                for policy, budget in (("verify-only", 1), ("verify-and-repair", 2)):
                    effective = contract.model_copy(deep=True)
                    effective.limits.max_attempts = budget
                    result = Harness(FixtureBackend(), ProcessExecutor()).run(
                        source_path,
                        effective,
                        output / f"{policy}-{index}",
                    )
                    # Even an unpromoted candidate can be measured by this offline evaluator.
                    candidate = (
                        Path(result.run_directory)
                        / "attempts"
                        / f"{result.attempts:03d}"
                        / "artifacts"
                    )
                    offline = verify(source, effective, candidate)
                    records.append(
                        {
                            "policy": policy,
                            "repetition": index,
                            "reported_success": result.status == "passed",
                            "artifact_valid": offline.passed,
                            "attempts": result.attempts,
                            "elapsed_seconds": result.elapsed_seconds,
                        }
                    )
    with (output / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = {
        "experiment_type": "scripted_fixture_control_flow",
        "limitations": "One seeded data-loss bug; no real LLM calls; not a model-quality estimate.",
        "repetitions_per_policy": repetitions,
        "policies": [],
    }
    for policy in ("exit-code-only", "verify-only", "verify-and-repair"):
        subset = [record for record in records if record["policy"] == policy]
        summary["policies"].append(
            {
                "policy": policy,
                "runs": len(subset),
                "reported_successes": sum(row["reported_success"] for row in subset),
                "valid_artifacts": sum(row["artifact_valid"] for row in subset),
                "false_successes": sum(
                    row["reported_success"] and not row["artifact_valid"] for row in subset
                ),
                "mean_attempts": sum(row["attempts"] for row in subset) / len(subset),
            }
        )
    write_json(output / "summary.json", summary)
    lines = [
        "# Scripted control-flow experiment",
        "",
        summary["limitations"],
        "",
        "| Policy | Runs | Reported success | Valid artifacts | False success |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summary["policies"]:
        lines.append(
            f"| {row['policy']} | {row['runs']} | {row['reported_successes']} | "
            f"{row['valid_artifacts']} | {row['false_successes']} |"
        )
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json.loads(json.dumps(summary))
