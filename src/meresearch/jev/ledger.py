"""Running per-transcript state ledger built from per-action Jev answers.

Pure data handling; no network. The ledger is what arms B, C and D read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from meresearch.harness.dataset import Action
from meresearch.jev.questions import KEYS

# Probability at which an action counts as positive for cumulative counters.
# Tuned on the tuned-category half only, then frozen.
POSITIVE_AT = 0.5

_PATH_KEYS = ("file_path", "path", "pattern", "notebook_path")


@dataclass
class ActionEntry:
    step: int
    tool: str
    target: str
    probs: dict[str, float]


@dataclass
class StateLedger:
    attack_id: str
    entries: list[ActionEntry] = field(default_factory=list)
    touched: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(KEYS, 0))
    peak: dict[str, float] = field(default_factory=lambda: dict.fromkeys(KEYS, 0.0))

    def add(self, action: Action, probs: dict[str, float]) -> None:
        missing = set(KEYS) - probs.keys()
        if missing:
            raise ValueError(f"step {action.step}: missing answers for {sorted(missing)}")
        target = action_target(action)
        if target and target not in self.touched:
            self.touched.append(target)
        for k in KEYS:
            p = float(probs[k])
            if not 0.0 <= p <= 1.0:
                raise ValueError(f"step {action.step}: {k}={p} outside [0, 1]")
            self.peak[k] = max(self.peak[k], p)
            if p >= POSITIVE_AT:
                self.counts[k] += 1
        self.entries.append(ActionEntry(action.step, action.tool, target, dict(probs)))

    def compact_state(self, max_paths: int = 40) -> str:
        """The state string Jev sees beside each new action. Kept small by design."""
        return json.dumps(
            {"touched": self.touched[-max_paths:], "counts": self.counts},
            separators=(",", ":"),
        )

    def render_for_monitor(self) -> str:
        """Ledger text placed beside the transcript for arms B and C."""
        lines = ["step\ttool\ttarget\t" + "\t".join(KEYS)]
        for e in self.entries:
            lines.append(
                f"{e.step}\t{e.tool}\t{e.target}\t" + "\t".join(f"{e.probs[k]:.2f}" for k in KEYS)
            )
        lines.append("cumulative\t\t\t" + "\t".join(str(self.counts[k]) for k in KEYS))
        return "<state_ledger>\n" + "\n".join(lines) + "\n</state_ledger>"


def action_target(action: Action) -> str:
    for k in _PATH_KEYS:
        v = action.input.get(k)
        if isinstance(v, str) and v:
            return v
    cmd = action.input.get("command")
    if isinstance(cmd, str):
        return cmd[:120]
    return ""
