"""Small reproducible CLI; failed verification is a nonzero process exit."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from importlib.resources import as_file, files
from pathlib import Path

from .backends import FixtureBackend, OllamaBackend
from .benchmark import benchmark
from .contracts import TaskContract, write_json
from .executors import DockerExecutor, ProcessExecutor
from .harness import Harness
from .source import read_source
from .verifier import verify


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="RowProof contract-driven data agent harness")
    sub = root.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="run the bundled scripted data-loss/repair demonstration")
    demo.add_argument("--output", type=Path)
    demo.add_argument(
        "--fixture",
        choices=["broken-then-fixed", "always-correct", "always-broken"],
        default="broken-then-fixed",
    )
    demo.add_argument("--executor", choices=["process", "docker"], default="process")
    demo.add_argument("--image", default="python:3.12-slim")
    run = sub.add_parser("run", help="run your CSV against an orders.v1 contract")
    run.add_argument("--input", required=True, type=Path)
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--backend", choices=["fixture", "ollama"], default="fixture")
    run.add_argument("--executor", choices=["process", "docker"], default="process")
    run.add_argument("--model", default=os.environ.get("ROWPROOF_OLLAMA_MODEL", ""))
    run.add_argument(
        "--ollama-url", default=os.environ.get("ROWPROOF_OLLAMA_URL", "http://127.0.0.1:11434")
    )
    run.add_argument("--image", default="python:3.12-slim")
    validate = sub.add_parser("validate", help="independently recheck an artifact directory")
    validate.add_argument("--input", required=True, type=Path)
    validate.add_argument("--contract", required=True, type=Path)
    validate.add_argument("--artifacts", required=True, type=Path)
    bench = sub.add_parser("benchmark", help="scripted control-flow ablation, without an LLM")
    bench.add_argument("--output", required=True, type=Path)
    bench.add_argument("--repetitions", type=int, default=3)
    schema = sub.add_parser("schema", help="export the contract JSON Schema")
    schema.add_argument("--output", required=True, type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "schema":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, TaskContract.model_json_schema())
            print(str(args.output))
            return 0
        if args.command == "benchmark":
            print(
                json.dumps(benchmark(args.output, args.repetitions), ensure_ascii=False, indent=2)
            )
            return 0
        if args.command == "validate":
            contract = TaskContract.load(args.contract)
            result = verify(read_source(args.input, contract), contract, args.artifacts)
            print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            return 0 if result.passed else 1
        executor = DockerExecutor(args.image) if args.executor == "docker" else ProcessExecutor()
        if args.command == "demo":
            output = args.output or Path("runs") / datetime.now().strftime("demo-%Y%m%d-%H%M%S-%f")
            harness = Harness(FixtureBackend(args.fixture), executor)
            with as_file(files("rowproof").joinpath("assets/orders.csv")) as source:
                with as_file(files("rowproof").joinpath("assets/orders.contract.json")) as contract:
                    result = harness.run(source, TaskContract.load(contract), output)
        else:
            backend = (
                OllamaBackend(args.model, args.ollama_url)
                if args.backend == "ollama"
                else FixtureBackend()
            )
            result = Harness(backend, executor).run(
                args.input, TaskContract.load(args.contract), args.output
            )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status == "passed" else 1
    except (OSError, ValueError, csv.Error, subprocess.SubprocessError) as error:
        print(f"rowproof: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
