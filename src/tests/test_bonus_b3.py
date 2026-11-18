"""Unit tests for Bonus Topic B3 — Swarm with Verifier/Aggregator."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from bonus.swarm_verified import run_claim as run_swarm_verified
from lab8.db import connect, init_store, load_jsonl
from lab8.shapes.swarm_reference import run_claim as run_unverified_swarm
from tests.conftest import BY_ID, CLAIMS, WORLD


def _store(tmp_path: Path, name: str):
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return path


def test_verifier_intercepts_corrupted_model_delay(tmp_path: Path):
    """B3 Core test: ở seed 55 với claim C-002, swarm chưa kiểm chứng sẽ tin vào ticket

    (ticket khai trễ 5 ngày, DB là 2 ngày) và hoàn nhầm.
    Ngược lại, Swarm Verified phát hiện sai lệch, can thiệp (verifier_override)
    và từ chối (denied) chính xác.
    """
    store_unverified = _store(tmp_path, "unverified_c002_s55.sqlite")
    res_unverified = run_unverified_swarm("C-002", seed=55, store_path=str(store_unverified))
    # Unverified swarm fails T02 on seed 55
    assert res_unverified.status == "resolved"
    assert res_unverified.proposal_amount == 20000

    store_verified = _store(tmp_path, "verified_c002_s55.sqlite")
    res_verified = run_swarm_verified("C-002", seed=55, store_path=str(store_verified))
    # Verified swarm fixes the weakness and returns denied!
    assert res_verified.status == "denied"
    assert res_verified.proposal_amount == 0

    # Kiểm tra trace: phải có event verifier_override
    with open(res_verified.trace_path, "r", encoding="utf-8") as f:
        trace_data = json.load(f)
    override_events = [e for e in trace_data.get("events", []) if e.get("kind") == "verifier_override"]
    assert len(override_events) == 1
    assert "discrepancies" in override_events[0]["payload"]


def test_verifier_preserves_valid_claim(tmp_path: Path):
    """Kiểm tra Verifier không can thiệp sai khi dữ kiện hoàn toàn trùng khớp."""
    store_verified = _store(tmp_path, "verified_c001_s11.sqlite")
    res_verified = run_swarm_verified("C-001", seed=11, store_path=str(store_verified))
    assert res_verified.status == "resolved"
    assert res_verified.proposal_amount == 35000

    # Trace không có verifier_override vì không có sai lệch
    with open(res_verified.trace_path, "r", encoding="utf-8") as f:
        trace_data = json.load(f)
    override_events = [e for e in trace_data.get("events", []) if e.get("kind") == "verifier_override"]
    assert len(override_events) == 0


def test_verifier_adversarial_cases(tmp_path: Path):
    """Kiểm tra Swarm Verified trên các ca đối kháng (ticket nói dối, prompt injection)."""
    adv_world = json.load(open("bonus/world.json", encoding="utf-8"))
    adv_claims = load_jsonl("bonus/cases.jsonl")

    store_adv = tmp_path / "adv_test.sqlite"
    init_store(store_adv, adv_world, adv_claims).close()

    # ADV-01: ticket nói quá trễ 10 ngày, order trễ 1 ngày -> denied
    res_adv1 = run_swarm_verified("ADV-01", seed=55, store_path=str(store_adv))
    assert res_adv1.status == "denied"
    assert res_adv1.proposal_amount == 0

    # ADV-05: prompt injection -> denied
    res_adv5 = run_swarm_verified("ADV-05", seed=11, store_path=str(store_adv))
    assert res_adv5.status == "denied"
    assert res_adv5.proposal_amount == 0
