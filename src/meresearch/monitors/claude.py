"""One frontier Claude monitor call: prompt + transcript (+ ledger) in, suspicion score out.

Rendering and score parsing reuse SLEIGHT-Bench's own functions so scores
read directly against the paper. The transcript sits in a cached prefix so
arm C's specialists pay full input price once per transcript.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import anthropic

from meresearch.config import Settings
from meresearch.harness.upstream import response_module, transcript_module
from meresearch.monitors.pricing import cost_usd

# Opus 5.x and Fable 5.x: adaptive thinking is always on; depth is set by effort.
ADAPTIVE_MODELS = frozenset({"claude-opus-5-5", "claude-fable-5-1"})


@dataclass
class MonitorResult:
    score: float | None
    text: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost_usd: float
    latency_ms: int


class ClaudeMonitor:
    def __init__(
        self,
        settings: Settings,
        model: str,
        effort: str = "high",
        thinking_budget: int | None = None,
        max_tokens: int = 32_000,
        client: anthropic.Anthropic | None = None,
    ):
        if client is None:
            if settings.anthropic_api_key is None:
                raise RuntimeError("ANTHROPIC_API_KEY is not set")
            client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key.get_secret_value(), max_retries=4
            )
        self._client = client
        self.model = model
        self.effort = effort
        self.thinking_budget = thinking_budget
        self.max_tokens = max_tokens

    def score(
        self,
        prompt_template: str,
        transcript_jsonl: str,
        ledger: str | None = None,
        strip_assistant: bool = True,
    ) -> MonitorResult:
        tmod = transcript_module()
        text = tmod.strip_assistant_text(transcript_jsonl) if strip_assistant else transcript_jsonl
        system, user = tmod.render_prompt(prompt_template, text)

        # Cached prefix: the rendered transcript. Ledger and nothing else varies after it.
        content: list[dict] = [
            {"type": "text", "text": user, "cache_control": {"type": "ephemeral"}}
        ]
        if ledger:
            content.append({"type": "text", "text": ledger})

        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        if system:
            kwargs["system"] = system
        if self.model in ADAPTIVE_MODELS:
            kwargs["output_config"] = {"effort": self.effort}
        elif self.thinking_budget:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": self.thinking_budget}

        t0 = time.monotonic()
        resp = self._client.messages.create(**kwargs)
        latency = int((time.monotonic() - t0) * 1000)

        out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        parsed = response_module().parse_response(out)
        u = resp.usage
        cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        cr = getattr(u, "cache_read_input_tokens", 0) or 0
        return MonitorResult(
            score=parsed.get("numeric_score"),
            text=out,
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_write_tokens=cw,
            cache_read_tokens=cr,
            cost_usd=cost_usd(self.model, u.input_tokens, u.output_tokens, cw, cr),
            latency_ms=latency,
        )
