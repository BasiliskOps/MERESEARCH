"""Decrypt and load SLEIGHT-Bench attacks and their paired benign transcripts."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet

from meresearch.config import SLEIGHT_ROOT

ALLOWED_FILES = frozenset(
    {"transcript.jsonl", "benign.jsonl", "metadata.json", "description.md", "verifiers.json"}
)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

# Upstream grading rules (scripts/paper/taxonomy.py): this attack is excluded from
# grading, and the refusal_forcing directory sits outside the paper's 11 classes.
EXCLUDE_FROM_GRADING = frozenset({"refusal-poisoning-credential-exfil"})


def decrypt_dataset(key: str, root: Path = SLEIGHT_ROOT) -> int:
    """Decrypt every attack in place inside the submodule. Returns files written.

    Same Fernet scheme as upstream decrypt.py, but validates each payload
    filename before writing, since upstream writes whatever names it carries.
    """
    fernet = Fernet(key.encode())
    attacks = (root / "attacks").resolve()
    written = 0
    for enc in sorted(attacks.rglob("encrypted.bin")):
        payload = json.loads(fernet.decrypt(enc.read_bytes()))
        for name, b64 in payload.items():
            content = base64.b64decode(b64)
            if not _SAFE_NAME.match(name) or name not in ALLOWED_FILES:
                raise ValueError(f"unexpected file in payload {enc}: {name!r}")
            target = (enc.parent / name).resolve()
            if not target.is_relative_to(attacks):
                raise ValueError(f"payload path escapes attacks/: {target}")
            target.write_bytes(content)
            written += 1
    return written


@dataclass(frozen=True)
class Block:
    """One line of a transcript: a single content block."""

    index: int  # 1-based line number, matching metadata `mechanism` keys
    role: str
    content: dict


@dataclass(frozen=True)
class Action:
    """One agent tool call paired with its result."""

    step: int
    tool: str
    input: dict
    result: str | None
    line: int


@dataclass
class Transcript:
    attack_id: str
    category: str
    kind: str  # "attack" or "benign"
    path: Path
    raw: str
    blocks: list[Block] = field(default_factory=list)

    def actions(self) -> Iterator[Action]:
        results: dict[str, str] = {}
        for b in self.blocks:
            if b.content.get("type") == "tool_result":
                c = b.content.get("content")
                results[b.content.get("tool_use_id", "")] = (
                    c if isinstance(c, str) else json.dumps(c)
                )
        step = 0
        for b in self.blocks:
            if b.role == "assistant" and b.content.get("type") == "tool_use":
                step += 1
                yield Action(
                    step=step,
                    tool=b.content.get("name", ""),
                    input=b.content.get("input", {}),
                    result=results.get(b.content.get("id", "")),
                    line=b.index,
                )


def parse_jsonl(text: str) -> list[Block]:
    """Parse single-block-per-line JSONL, skipping canary lines per FORMAT.md."""
    blocks = []
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        obj = json.loads(line)
        if "canary" in obj and "role" not in obj:
            continue
        content = obj.get("content")
        if isinstance(content, str):
            content = {"type": "text", "text": content}
        blocks.append(Block(index=i, role=obj.get("role", ""), content=content or {}))
    return blocks


def load_transcript(path: Path, attack_id: str, category: str, kind: str) -> Transcript:
    raw = path.read_text(encoding="utf-8")
    return Transcript(attack_id, category, kind, path, raw, parse_jsonl(raw))


def iter_dataset(root: Path = SLEIGHT_ROOT, graded_only: bool = True) -> Iterator[Transcript]:
    """Yield attack and benign transcripts. Category comes from metadata tags when present."""
    attacks = root / "attacks"
    for meta_path in sorted(attacks.glob("*/*/metadata.json")):
        attack_dir = meta_path.parent
        attack_id = attack_dir.name
        if graded_only and attack_id in EXCLUDE_FROM_GRADING:
            continue
        category = attack_dir.parent.name.replace("_", "-")
        if graded_only and category == "refusal-forcing":
            continue
        for kind, fname in (("attack", "transcript.jsonl"), ("benign", "benign.jsonl")):
            p = attack_dir / fname
            if p.is_file():
                yield load_transcript(p, attack_id, category, kind)
