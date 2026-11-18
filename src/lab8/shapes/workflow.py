
"""Shape A — deterministic workflow.

Money stays in Python code. The host alone authorizes and commits refunds.
"""

from __future__ import annotations

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import (
    compute_compensation,
    get_claim_view,
    lookup_order,
    tool_cost,
)
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:

    # 1. Initialize the connection, budget and trace.
    conn = connect(store_path)
    try:
        budget = Budget()

        run_id = make_run_id("workflow", claim_id, seed)
        trace = Trace(run_id)

        # 2. Read the claim through the safe tool.
        budget.add_tool(tool_cost())
        claim = get_claim_view(conn, claim_id)

        trace.add(
            "claim_lookup",
            {
                "found": claim["found"],
                "has_order_id": bool(claim.get("order_id")),
            },
        )

        # Unknown claim.
        if not claim["found"]:
            trace.add("decision", {"status": "failed"})

            return finish(
                conn,
                shape="workflow",
                claim_id=claim_id,
                seed=seed,
                status="failed",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="unknown_claim",
            )

        # 3. Ask for more information if order_id is missing.
        order_id = claim.get("order_id")

        if not order_id:
            trace.add("decision", {"status": "needs_info"})

            return finish(
                conn,
                shape="workflow",
                claim_id=claim_id,
                seed=seed,
                status="needs_info",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason="missing_order_id",
            )

        # 4. Look up the order within the customer's ownership scope.
        budget.add_tool(tool_cost())
        order_result = lookup_order(
            conn,
            order_id,
            claim["principal_id"],
        )

        trace.add(
            "order_lookup",
            {
                "visible": order_result["visible"],
                "reason": order_result["reason"],
            },
        )

        # Escalate if the order is inaccessible or does not exist.
        if not order_result["visible"]:
            trace.add("decision", {"status": "escalated"})

            return finish(
                conn,
                shape="workflow",
                claim_id=claim_id,
                seed=seed,
                status="escalated",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason=order_result["reason"],
            )

        order = order_result["order"]

        # 5. Calculate compensation using structured order data.
        # Never use delay numbers or refund amounts from ticket text.
        budget.add_tool(tool_cost())
        quote = compute_compensation(conn, order)

        proposal = int(quote["amount_vnd"])

        trace.add(
            "compensation_quote",
            {
                "amount_vnd": proposal,
                "reason": quote["reason"],
                "clause_ids": quote["clause_ids"],
            },
        )

        # No entitlement: deny without calling the refund host.
        if proposal <= 0:
            trace.add("decision", {"status": "denied"})

            return finish(
                conn,
                shape="workflow",
                claim_id=claim_id,
                seed=seed,
                status="denied",
                proposal_amount=0,
                budget=budget,
                trace=trace,
                error_reason=quote["reason"],
            )

        # 6. Send the FULL quote to the host.
        # The host validates approval, applies per-order caps,
        # enforces idempotency and writes the refund atomically.
        # Forward crash_at and allow InjectedCrash to propagate.
        outcome = issue_refund(
            conn,
            claim_id,
            proposal,
            crash_at=crash_at,
        )

        # 7. Handle authorization failure or amount conflict.
        if not outcome["ok"]:
            status = "failed" if outcome["conflict"] else "denied"

            trace.add(
                "refund_authorization",
                {
                    "ok": False,
                    "reason": outcome["reason"],
                    "conflict": outcome["conflict"],
                },
            )

            trace.add("decision", {"status": status})

            return finish(
                conn,
                shape="workflow",
                claim_id=claim_id,
                seed=seed,
                status=status,
                proposal_amount=proposal,
                budget=budget,
                trace=trace,
                error_reason=outcome["reason"],
            )

        # 8. Refund successfully committed (or safely replayed).
        trace.add(
            "refund_authorization",
            {
                "ok": True,
                "reason": outcome["reason"],
            },
        )

        trace.add("decision", {"status": "resolved"})

        return finish(
            conn,
            shape="workflow",
            claim_id=claim_id,
            seed=seed,
            status="resolved",
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=None,
        )

    finally:
        # Always close the SQLite connection, including after a crash.
        conn.close()
