# Security

Report vulnerabilities privately through GitHub's "Report a vulnerability" button on this repository's Security tab. Do not open a public issue.

Secrets are loaded from a local `.env` file that is gitignored; `.env.example` lists the variables with empty values. Gitleaks runs in pre-commit and CI. All GitHub Actions are pinned to full commit SHAs, workflows run with read-only `contents` permission, and dependencies are locked with `uv.lock` and installed with `--locked`.

SLEIGHT-Bench transcripts stay encrypted at rest in the `ext/sleight-bench` submodule. Plaintext transcripts are blocked from this tree by `.gitignore` and a pre-commit hook, and nothing derived from them that reproduces transcript text is committed. Only scores, ledgers of extracted predicates, and aggregate metrics are written to `results/`.
