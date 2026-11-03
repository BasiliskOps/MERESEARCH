"""Append-only provenance ledger: one JSONL record per model call, hash-chained.

Every verdict in the note traces to a record here. Records hold content
hashes of the transcript and prompt, never their text, so the ledger can be
committed without reproducing benchmark data.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

GENESIS = "0" * 64


def sha256(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass
class CallRecord:
    arm: str
    attack_id: str
    kind: str  # attack | benign | synthetic-benign
    model: str
    transcript_hash: str
    prompt_hash: str
    trial: int
    score: float | None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    extra: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    prev: str = GENESIS
    hash: str = ""


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._tip = self._read_tip()

    def _read_tip(self) -> str:
        if not self.path.exists():
            return GENESIS
        tip = GENESIS
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    tip = json.loads(line)["hash"]
        return tip

    def append(self, rec: CallRecord) -> CallRecord:
        rec.prev = self._tip
        rec.hash = ""
        body = json.dumps(asdict(rec), sort_keys=True, separators=(",", ":"))
        rec.hash = sha256(body)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(rec), sort_keys=True) + "\n")
        self._tip = rec.hash
        return rec

    def total_cost(self) -> float:
        return sum(r["cost_usd"] for r in self.records())

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


def verify_chain(path: Path) -> bool:
    """Recompute every hash and link. False if any record was edited, dropped or reordered."""
    prev = GENESIS
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            claimed = rec["hash"]
            if rec["prev"] != prev:
                return False
            rec["hash"] = ""
            body = json.dumps(rec, sort_keys=True, separators=(",", ":"))
            if sha256(body) != claimed:
                return False
            prev = claimed
    return True


class BudgetExceededError(RuntimeError):
    pass


def check_budget(ledger: Ledger, ceiling_usd: float) -> None:
    """Hard stop before the next call once spend reaches the ceiling. Ceiling 0 blocks all calls."""
    spent = ledger.total_cost()
    if spent >= ceiling_usd:
        raise BudgetExceededError(f"spent ${spent:.2f} of ${ceiling_usd:.2f} ceiling")
