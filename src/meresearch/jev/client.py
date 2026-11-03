"""Jev client over Cloudflare Workers AI.

The request body follows the published shape (`state` plus typed `questions`).
The exact REST path and the field names for returned probabilities are not
documented on the Cloudflare listing; both are confirmed on day one against a
live call (issue: Jev client) and `_extract_probability` is adjusted then.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx

from meresearch.config import JEV_MODEL, Settings
from meresearch.harness.dataset import Action
from meresearch.jev.questions import QUESTIONS

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_ACTION_CHARS = 8_000  # one action plus state stays far under the 32K window


@dataclass
class JevResult:
    probs: dict[str, float]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    raw: dict


class JevClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if settings.cloudflare_api_token is None:
            raise RuntimeError("CLOUDFLARE_API_TOKEN is not set")
        self._url = settings.resolved_jev_endpoint
        if not self._url.startswith("https://"):
            raise ValueError("Jev endpoint must be https")
        self._headers = {
            "Authorization": f"Bearer {settings.cloudflare_api_token.get_secret_value()}",
            "Content-Type": "application/json",
        }
        self._http = client or httpx.Client(timeout=TIMEOUT, follow_redirects=False)

    def ask(self, action: Action, compact_state: str) -> JevResult:
        state = {
            "prior_state": compact_state,
            "action": {
                "tool": action.tool,
                "input": action.input,
                "result": (action.result or "")[:MAX_ACTION_CHARS],
            },
        }
        body = {
            "state": json.dumps(state)[: MAX_ACTION_CHARS * 2],
            "questions": [
                {"type": q.type, "instructions": q.instructions, "criteria": q.criteria}
                for q in QUESTIONS
            ],
        }
        t0 = time.monotonic()
        resp = self._http.post(self._url, headers=self._headers, json=body)
        latency = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()
        payload = data.get("result", data)
        answers = payload.get("answers", [])
        if len(answers) != len(QUESTIONS):
            raise ValueError(f"{JEV_MODEL} returned {len(answers)} answers for {len(QUESTIONS)}")
        usage = payload.get("usage", {})
        return JevResult(
            probs={q.key: _extract_probability(a) for q, a in zip(QUESTIONS, answers, strict=True)},
            input_tokens=int(usage.get("input_tokens", usage.get("prompt_tokens", 0))),
            output_tokens=int(usage.get("output_tokens", usage.get("completion_tokens", 0))),
            latency_ms=latency,
            raw=payload,
        )


def _extract_probability(answer: dict | float) -> float:
    """Probability that the answer is yes. Field name confirmed on day one."""
    if isinstance(answer, int | float):
        return float(answer)
    for k in ("probability", "p_yes", "yes", "score", "confidence"):
        if k in answer and isinstance(answer[k], int | float):
            return float(answer[k])
    probs = answer.get("probabilities")
    if isinstance(probs, dict):
        for k in ("yes", "true", "Yes", "True"):
            if k in probs:
                return float(probs[k])
    raise ValueError(f"cannot find probability in Jev answer keys {sorted(answer)}")
