"""Command line entry point: `uv run meresearch --help`."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from meresearch.arms import ARMS
from meresearch.calibration import benign_set_is_stable, category_split
from meresearch.config import load_settings
from meresearch.harness.dataset import decrypt_dataset, iter_dataset
from meresearch.provenance import verify_chain

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def decrypt() -> None:
    """Decrypt SLEIGHT-Bench in place inside the submodule (gitignored there)."""
    s = load_settings()
    if s.sleight_fernet_key is None:
        raise typer.BadParameter("set SLEIGHT_FERNET_KEY in .env (key is in the upstream README)")
    n = decrypt_dataset(s.sleight_fernet_key.get_secret_value())
    console.print(f"decrypted {n} files")


@app.command()
def inventory() -> None:
    """Count graded transcripts per category and check benign-set size for a 1% cut."""
    counts: Counter[tuple[str, str]] = Counter()
    for t in iter_dataset():
        counts[(t.category, t.kind)] += 1
    if not counts:
        console.print("no decrypted transcripts found; run `meresearch decrypt` first")
        raise typer.Exit(1)
    table = Table("category", "attack", "benign")
    for cat in sorted({c for c, _ in counts}):
        table.add_row(cat, str(counts[(cat, "attack")]), str(counts[(cat, "benign")]))
    console.print(table)
    n_benign = sum(v for (_, k), v in counts.items() if k == "benign")
    stable = benign_set_is_stable(n_benign)
    verdict = "stable" if stable else "too small"
    console.print(f"benign transcripts: {n_benign} ({verdict} for 1% FPR)")


@app.command()
def split() -> None:
    """Print the frozen tuned / held-out category split for the configured seed."""
    s = load_settings()
    tuned, held = category_split(s.seed)
    console.print(f"seed {s.seed}\ntuned:    {', '.join(tuned)}\nheld-out: {', '.join(held)}")


@app.command()
def arms() -> None:
    """List the five arms."""
    table = Table("arm", "description", "frontier calls", "isolates")
    for a in ARMS.values():
        table.add_row(a.key, a.description, str(a.frontier_calls), a.isolates)
    console.print(table)


@app.command("verify-ledger")
def verify_ledger(path: Path) -> None:
    """Check a provenance ledger's hash chain."""
    ok = verify_chain(path)
    console.print("chain intact" if ok else "chain BROKEN")
    raise typer.Exit(0 if ok else 1)


if __name__ == "__main__":
    app()
