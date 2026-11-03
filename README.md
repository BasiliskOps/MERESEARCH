# MERESEARCH: Monitor Ensemble Study

This repository measures whether a state-augmented monitoring architecture catches more covert sabotage on [SLEIGHT-Bench](https://arxiv.org/abs/2605.16626) at a 1% false-positive rate than a single frontier monitor reading the raw transcript. The work is defense-side: every attack comes from the published SLEIGHT-Bench release by Najt, Toft, Tracy, Roger and Benton (Anthropic Fellows Program, May 2026), no new evasion technique is created or published, and any attack the architecture still misses is reported as a mapped weakness for monitor builders to patch. Benchmark transcripts stay encrypted at rest and are never reproduced here.

## Design

Five arms score the same transcripts. Arm A is the strongest current Claude monitor reading the raw transcript with extended thinking (the control). Arm B adds a per-action state ledger built by TypeSafe's Jev on Cloudflare Workers AI. Arm C splits judgment across four to six blind-spot specialists that each read the ledger, aggregated by max and recalibrated. Arm D scores the ledger with Jev alone and makes no frontier call. Arm E runs Opus 4.6 to anchor the reproduction against the paper. Every threshold is set on benign transcripts to 1% FPR using the paper's convention, ledger questions and specialist prompts are tuned on a seeded half of the eleven categories and then frozen, and the held-out catch rate is the headline number. A held-out result within five points of arm A is reported as null.

## Layout

`src/meresearch/harness` loads the pinned `ext/sleight-bench` submodule and reuses its transcript stripping, prompt rendering and score parsing so results read directly against the paper. `jev` holds the question set, the Workers AI client and the running state ledger. `monitors` holds the Claude monitor and the pricing table. `calibration.py` holds thresholds, catch rates and the category split. `provenance.py` writes a hash-chained JSONL record for every model call, holding content hashes and cost but never transcript text. Results land in `results/`; the static viewer lives in `viewer/`.

## Setup

```bash
git clone --recurse-submodules https://github.com/BasiliskOps/MERESEARCH
cd MERESEARCH
uv sync --all-groups
cp .env.example .env        # fill in keys; .env is gitignored
uv run pre-commit install
uv run meresearch decrypt   # decrypts into the submodule, where outputs are gitignored
uv run meresearch inventory
uv run pytest
```

## Provenance

`uv run meresearch verify-ledger results/<run>/calls.jsonl` recomputes every hash in a run's call ledger and fails if any record was edited, dropped or reordered. Every number in the research note cites the ledger records it was computed from.

## License

MIT. SLEIGHT-Bench is MIT-licensed by its authors and included as an unmodified submodule.
