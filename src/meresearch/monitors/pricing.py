"""USD per million tokens. Verified values are from platform.claude.com model pages (Nov 2026).

Entries marked unverified are confirmed against the live billing of the day-one
single-transcript run before the budget ceiling is set.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_write_5m: float
    cache_read: float
    verified: bool


PRICES: dict[str, Price] = {
    "claude-opus-5-5": Price(4.00, 20.00, 5.00, 0.20, verified=True),
    # Input/output verified; cache rates assumed at Opus 5.5 ratios until day one.
    "claude-fable-5-1": Price(10.00, 50.00, 12.50, 0.50, verified=False),
    "claude-opus-4-6": Price(5.00, 25.00, 6.25, 0.50, verified=False),
    # Workers AI listing, checked 20 Oct 2026: output and cached input free.
    "typesafe/jev": Price(0.042, 0.0, 0.0, 0.0, verified=True),
}


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    p = PRICES[model]
    return (
        input_tokens * p.input
        + output_tokens * p.output
        + cache_write_tokens * p.cache_write_5m
        + cache_read_tokens * p.cache_read
    ) / 1_000_000
