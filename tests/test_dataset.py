import json

import pytest

from meresearch.harness.dataset import Transcript, decrypt_dataset, parse_jsonl


def test_canary_skipped_and_line_numbers_kept(synthetic_transcript):
    blocks = parse_jsonl(synthetic_transcript)
    assert blocks[0].index == 2  # canary on line 1 skipped
    assert all(b.role in {"user", "assistant"} for b in blocks)


def test_actions_pair_tool_use_with_result(synthetic_transcript, tmp_path):
    t = Transcript(
        "x", "cat", "attack", tmp_path, synthetic_transcript, parse_jsonl(synthetic_transcript)
    )
    acts = list(t.actions())
    assert [a.step for a in acts] == [1, 2]
    assert acts[0].tool == "Read" and acts[0].result.endswith("KEY=x")
    assert acts[1].line == 6


def test_decrypt_rejects_path_traversal(tmp_path):
    from base64 import b64encode

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    attack = tmp_path / "attacks" / "c" / "a"
    attack.mkdir(parents=True)
    payload = {"../../evil.py": b64encode(b"x").decode()}
    (attack / "encrypted.bin").write_bytes(Fernet(key).encrypt(json.dumps(payload).encode()))
    with pytest.raises(ValueError):
        decrypt_dataset(key.decode(), root=tmp_path)
    assert not (tmp_path / "evil.py").exists()
