"""Thin bridge to SLEIGHT-Bench's own code so results read directly against the paper.

Modules are loaded by file path from the pinned submodule. Importing the
`evaluate` package normally would pull its BigQuery and GCP dependencies,
which this study replaces with the JSONL provenance ledger. Only modules
with stdlib-only imports are loaded here.
"""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path
from types import ModuleType

from meresearch.config import SLEIGHT_ROOT


def _load(name: str, rel_path: str, root: Path = SLEIGHT_ROOT) -> ModuleType:
    path = (root / rel_path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"refusing to load module outside submodule: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{path} missing; run `git submodule update --init` first")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@cache
def transcript_module() -> ModuleType:
    """`strip_assistant_text` and `render_prompt`, exactly as the paper used them."""
    return _load("sleight_transcript", "evaluate/core/transcript.py")


@cache
def response_module() -> ModuleType:
    """`parse_response`: the paper's `<score>NN</score>` parser."""
    return _load("sleight_response", "evaluate/core/response.py")
