"""Trusted fixture subprocesses and Docker-isolated model-produced programs."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .contracts import Limits


@dataclass
class ExecutionResult:
    returncode: int
    elapsed_seconds: float
    timed_out: bool = False
    log_limit_exceeded: bool = False
    log_excerpt: str = ""

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.log_limit_exceeded

    def as_dict(self) -> dict:
        return asdict(self)


def _execute(command: list[str], cwd: Path, log_path: Path, limits: Limits) -> ExecutionResult:
    start = time.monotonic()
    timed_out = log_limit = False
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, shell=False
        )
        try:
            while process.poll() is None:
                if time.monotonic() - start > limits.execution_timeout_seconds:
                    timed_out = True
                    break
                if log_path.stat().st_size > limits.max_log_bytes:
                    log_limit = True
                    break
                try:
                    process.wait(timeout=0.03)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
    log_limit = log_limit or log_path.stat().st_size > limits.max_log_bytes
    with log_path.open("rb") as handle:
        excerpt = handle.read(min(limits.max_log_bytes, 16000)).decode("utf-8", errors="replace")
    return ExecutionResult(
        process.returncode, round(time.monotonic() - start, 6), timed_out, log_limit, excerpt
    )


class ProcessExecutor:
    """Not a sandbox. The harness only permits trusted fixture backends here."""

    name = "process"
    isolated = False

    def preflight(self) -> None:
        pass

    def execute(
        self, program: Path, input_dir: Path, output_dir: Path, limits: Limits
    ) -> ExecutionResult:
        command = [
            sys.executable,
            "-I",
            str(program.resolve()),
            "--input",
            str((input_dir / "source.csv").resolve()),
            "--contract",
            str((input_dir / "contract.json").resolve()),
            "--output",
            str(output_dir.resolve()),
        ]
        return _execute(command, program.parent, program.parent / "execution.log", limits)


class DockerExecutor:
    """A practical local isolation boundary, not a hostile-code security certification."""

    name = "docker"
    isolated = True

    def __init__(self, image: str = "python:3.12-slim"):
        self.image = image

    def preflight(self) -> None:
        if not shutil.which("docker"):
            raise ValueError("Docker CLI not found; install/start Docker and pre-pull the image")
        try:
            check = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError(f"Docker preflight failed: {error}") from error
        if check.returncode:
            raise ValueError(f"Docker image unavailable; run: docker pull {self.image}")

    def execute(
        self, program: Path, input_dir: Path, output_dir: Path, limits: Limits
    ) -> ExecutionResult:
        # Avoid a mount-spec separator being interpreted as another mount option.
        if any("," in str(path.resolve()) for path in (program, input_dir, output_dir)):
            raise ValueError("Docker bind-mount paths must not contain commas")
        output_dir.chmod(0o777)
        container = "rowproof-" + uuid.uuid4().hex
        command = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            container,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            "--memory=256m",
            "--cpus=1",
            "--user=65534:65534",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--workdir=/output",
            "--env=PYTHONDONTWRITEBYTECODE=1",
            "--env=PYTHONUNBUFFERED=1",
            "--mount",
            f"type=bind,src={program.resolve()},dst=/program.py,readonly",
            "--mount",
            f"type=bind,src={input_dir.resolve()},dst=/input,readonly",
            "--mount",
            f"type=bind,src={output_dir.resolve()},dst=/output",
            self.image,
            "python",
            "-I",
            "/program.py",
            "--input",
            "/input/source.csv",
            "--contract",
            "/input/contract.json",
            "--output",
            "/output",
        ]
        try:
            return _execute(command, program.parent, program.parent / "execution.log", limits)
        finally:
            # Killing the docker CLI does not reliably stop its container.
            subprocess.run(
                ["docker", "rm", "--force", container], capture_output=True, timeout=15, check=False
            )
