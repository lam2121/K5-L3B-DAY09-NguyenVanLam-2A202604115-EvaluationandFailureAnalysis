"""Custom tests for Shape C (Orchestrator)."""

import pytest
from lab8.db import init_store, connect
from lab8.shapes.orchestrator import run_claim
from tests.conftest import BY_ID, CLAIMS, WORLD


def test_orchestrator_handoff_safety_and_readonly(tmp_path):
    """Kiểm tra Orchestrator chạy đúng và chỉ cấp quyền đọc an toàn cho investigator."""
    store_file = tmp_path / "test_orch_custom.sqlite"
    init_store(store_file, WORLD, CLAIMS).close()

    # Chạy thử với claim hợp lệ C-001
    result = run_claim("C-001", seed=11, store_path=str(store_file))
    
    assert result.status == "resolved"
    assert result.proposal_amount == 35000
    assert result.shape == "orchestrator"
    assert result.trace_path is not None

    # Kiểm tra trace: không được chứa chuỗi cấm
    with open(result.trace_path, "r", encoding="utf-8") as f:
        trace_content = f.read()
        assert "CANARY_SECRET" not in trace_content
        assert "internal_note" not in trace_content


def test_orchestrator_missing_order_id(tmp_path):
    """Kiểm tra Orchestrator dừng sớm và trả về needs_info khi claim thiếu order_id."""
    store_file = tmp_path / "test_orch_missing.sqlite"
    init_store(store_file, WORLD, CLAIMS).close()

    # C-004 là claim thiếu order_id
    result = run_claim("C-004", seed=11, store_path=str(store_file))
    assert result.status == "needs_info"
    assert result.proposal_amount == 0