"""Replaceable code-proposal backends. Fixtures are explicitly not LLM evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .contracts import CodeProposal
from .prompts import SYSTEM_PROMPT, build_prompt


class BackendError(RuntimeError):
    pass


@dataclass
class ProposalContext:
    contract: dict
    sample: list[dict]
    attempt: int
    previous_code: str | None = None
    feedback: dict | None = None


@dataclass
class Generation:
    proposal: CodeProposal
    usage: dict = field(default_factory=dict)


class CodeBackend(Protocol):
    name: str
    untrusted_code: bool

    def propose(self, context: ProposalContext) -> Generation: ...


class FixtureBackend:
    """Trusted scripts for reproducible integration tests; not a reasoning agent."""

    untrusted_code = False

    def __init__(self, mode: str = "broken-then-fixed"):
        if mode not in {"broken-then-fixed", "always-correct", "always-broken"}:
            raise ValueError("unknown fixture mode")
        self.mode = mode
        self.name = f"fixture:{mode}"

    def propose(self, context: ProposalContext) -> Generation:
        script = files("rowproof").joinpath("assets/worker.py.txt").read_text(encoding="utf-8")
        broken = self.mode == "always-broken" or (
            self.mode == "broken-then-fixed" and context.feedback is None
        )
        if broken:
            script = script.replace(
                "# DEMO_MUTATION", "clean = clean[:-1]  # seeded silent data loss"
            )
        return Generation(
            CodeProposal(
                summary="Scripted broken candidate" if broken else "Scripted corrected candidate",
                python_code=script,
            )
        )


class OllamaBackend:
    untrusted_code = True

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120,
        max_response_bytes: int = 1_000_000,
    ):
        if not model.strip():
            raise ValueError("a local Ollama model tag is required")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Ollama URL must use http or https")
        self.model, self.base_url = model, base_url.rstrip("/")
        self.timeout, self.max_response_bytes = timeout, max_response_bytes
        self.name = f"ollama:{model}"

    def propose(self, context: ProposalContext) -> Generation:
        body = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": build_prompt(
                context.contract, context.sample, context.previous_code, context.feedback
            ),
            "stream": False,
            "format": CodeProposal.model_json_schema(),
            "options": {"temperature": 0, "num_predict": 4096},
        }
        request = Request(
            self.base_url + "/api/generate",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raise BackendError("Ollama response byte limit exceeded")
            envelope = json.loads(raw)
            if envelope.get("error"):
                raise BackendError(str(envelope["error"])[:500])
            if envelope.get("done") is not True:
                raise BackendError("Ollama returned an incomplete generation")
            proposal = CodeProposal.model_validate_json(envelope["response"])
            usage = {
                key: envelope[key] for key in ("prompt_eval_count", "eval_count") if key in envelope
            }
            return Generation(proposal, usage)
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            raise BackendError(f"Ollama generation failed: {str(error)[:1000]}") from error
