"""Runtime settings, read from the environment (and a local .env) only.

Secrets are held as SecretStr so they never appear in reprs, logs, or the
provenance ledger.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

REPO_ROOT = Path(__file__).resolve().parents[2]
SLEIGHT_ROOT = REPO_ROOT / "ext" / "sleight-bench"
RESULTS_DIR = REPO_ROOT / "results"
PROMPTS_DIR = REPO_ROOT / "prompts"

# Candidate baselines; the stronger is chosen on day one (issue: baseline selection).
BASELINE_CANDIDATES = ("claude-opus-5-5", "claude-fable-5-1")
REPRODUCTION_MODEL = "claude-opus-4-6"

JEV_MODEL = "typesafe/jev"


def _secret(name: str) -> SecretStr | None:
    value = os.environ.get(name, "").strip()
    return SecretStr(value) if value else None


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: SecretStr | None
    cloudflare_account_id: str | None
    cloudflare_api_token: SecretStr | None
    jev_endpoint: str | None
    sleight_fernet_key: SecretStr | None
    budget_usd: float
    seed: int

    @property
    def resolved_jev_endpoint(self) -> str:
        if self.jev_endpoint:
            return self.jev_endpoint
        if not self.cloudflare_account_id:
            raise RuntimeError("CLOUDFLARE_ACCOUNT_ID is not set")
        return (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.cloudflare_account_id}/ai/run/{JEV_MODEL}"
        )


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or REPO_ROOT / ".env", override=False)
    return Settings(
        anthropic_api_key=_secret("ANTHROPIC_API_KEY"),
        cloudflare_account_id=os.environ.get("CLOUDFLARE_ACCOUNT_ID") or None,
        cloudflare_api_token=_secret("CLOUDFLARE_API_TOKEN"),
        jev_endpoint=os.environ.get("JEV_ENDPOINT") or None,
        sleight_fernet_key=_secret("SLEIGHT_FERNET_KEY"),
        budget_usd=float(os.environ.get("MERESEARCH_BUDGET_USD", "0") or 0),
        seed=int(os.environ.get("MERESEARCH_SEED", "20261103")),
    )
