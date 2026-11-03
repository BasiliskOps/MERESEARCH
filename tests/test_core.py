import json

import pytest

from meresearch.calibration import (
    PAPER_CLASSES,
    catch_rate_at_fpr,
    category_split,
    max_aggregate,
    threshold_at_fpr,
)
from meresearch.harness.dataset import Transcript, parse_jsonl
from meresearch.harness.upstream import response_module, transcript_module
from meresearch.jev.client import _extract_probability
from meresearch.jev.ledger import StateLedger
from meresearch.jev.questions import KEYS
from meresearch.monitors.pricing import cost_usd
from meresearch.provenance import (
    BudgetExceededError,
    CallRecord,
    Ledger,
    check_budget,
    verify_chain,
)


def test_threshold_matches_paper_convention():
    benign = list(range(100))  # 0..99
    thr, fpr, rate = catch_rate_at_fpr(benign, [98.5, 99.5, 50], 0.01)
    assert thr == 99.0  # percentile(method="higher")
    assert fpr == 0.0  # strict >
    assert rate == pytest.approx(1 / 3)


def test_threshold_rejects_empty():
    with pytest.raises(ValueError):
        threshold_at_fpr([])


def test_split_is_deterministic_and_disjoint():
    a, b = category_split(7)
    assert (a, b) == category_split(7)
    assert set(a).isdisjoint(b) and set(a) | set(b) == set(PAPER_CLASSES)
    assert len(a) == 5 and len(b) == 6


def test_max_aggregate():
    assert max_aggregate([[1, 5], [3, 2]]) == [3, 5]


def test_ledger_accumulates_state(synthetic_transcript, tmp_path):
    t = Transcript(
        "x", "c", "attack", tmp_path, synthetic_transcript, parse_jsonl(synthetic_transcript)
    )
    led = StateLedger("x")
    for a in t.actions():
        probs = dict.fromkeys(KEYS, 0.1)
        probs["credential_read"] = 0.9
        if a.step == 2:
            probs["prior_artifact_reused"] = 0.8
        led.add(a, probs)
    assert led.counts["credential_read"] == 2
    assert led.counts["prior_artifact_reused"] == 1
    assert led.touched[0] == "/w/.env"
    assert "<state_ledger>" in led.render_for_monitor()
    assert len(led.compact_state()) < 2000


def test_ledger_rejects_bad_probabilities(synthetic_transcript, tmp_path):
    t = Transcript(
        "x", "c", "attack", tmp_path, synthetic_transcript, parse_jsonl(synthetic_transcript)
    )
    a = next(t.actions())
    with pytest.raises(ValueError):
        StateLedger("x").add(a, dict.fromkeys(KEYS, 1.5))
    with pytest.raises(ValueError):
        StateLedger("x").add(a, {"credential_read": 0.2})


def test_provenance_chain_detects_tampering(tmp_path):
    p = tmp_path / "calls.jsonl"
    led = Ledger(p)
    for i in range(3):
        led.append(CallRecord("A", "x", "attack", "m", "th", "ph", i, 10.0 * i, cost_usd=0.5))
    assert verify_chain(p)
    assert Ledger(p).total_cost() == pytest.approx(1.5)
    lines = p.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["score"] = 99.0
    lines[1] = json.dumps(rec, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    assert not verify_chain(p)


def test_budget_ceiling(tmp_path):
    led = Ledger(tmp_path / "c.jsonl")
    with pytest.raises(BudgetExceededError):
        check_budget(led, 0.0)
    check_budget(led, 1.0)


def test_cost():
    assert cost_usd("claude-opus-5-5", 1_000_000, 0) == pytest.approx(4.0)


def test_jev_probability_extraction():
    assert _extract_probability({"probability": 0.3}) == 0.3
    assert _extract_probability({"probabilities": {"yes": 0.7}}) == 0.7
    with pytest.raises(ValueError):
        _extract_probability({"label": "yes"})


def test_upstream_stripping_and_parsing(synthetic_transcript):
    stripped = transcript_module().strip_assistant_text(synthetic_transcript)
    assert "Reading." not in stripped and "toolu_01a" in stripped
    assert response_module().parse_response("<score>42</score>")["numeric_score"] == 42
