
import json
import time
from pathlib import Path

from lab8.db import connect
from lab8.durability import committed_audit_count, get_refund
from lab8.metrics import check_trace
from lab8.shapes.workflow import run_claim


def test_unknown_claim_fails_without_refund_and_writes_clean_trace(public_db):
    started_at = time.time()

    result = run_claim(
        "C-UNKNOWN",
        seed=11,
        store_path=str(public_db),
    )

    # The unknown claim must fail safely.
    assert result.status == "failed"
    assert result.error_reason == "unknown_claim"
    assert result.proposal_amount == 0

    # No model call or refund should occur.
    assert result.model_calls == 0
    assert result.refund_effects == []

    conn = connect(public_db)
    try:
        assert get_refund(conn, "C-UNKNOWN") is None
        assert committed_audit_count(conn, "C-UNKNOWN") == 0
    finally:
        conn.close()

    # A fresh, correctly formatted trace must still exist.
    trace_path = Path(result.trace_path)
    assert trace_path.is_file()

    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    assert trace["run_id"] == result.run_id
    assert isinstance(trace["events"], list)

    # The trace must not expose secrets.
    assert "CANARY_SECRET_" not in str(trace)

    assert check_trace(
        result.as_dict(),
        started_at=started_at,
    ) == (True, "ok")
