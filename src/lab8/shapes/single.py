"""Shape B - Single Agent (ReAct), vi du co chu thich de hoc luong.

Chep file nay vao: src/lab8/shapes/single.py
Chay lenh trong thu muc src/:
    python -m lab8.run --shape single --claim-id C-001 --seed 11 --db data/run.sqlite

Khong de agent ghi refund. Chi host (issue_refund) duoc ghi tien.
"""

from __future__ import annotations

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Mot yeu cau hoan phi: doc -> quyet dinh -> de xuat -> host duyet."""
    conn = connect(store_path)
    try:
        budget = Budget()  # Dem so lan goi model, tool va chi phi mo phong
        trace = Trace(make_run_id("single", claim_id, seed))  # Luu nhat ky an toan
        memory = {}  # Nho order va quote; run_react chi dua last_result moi nhat

        def decide(observation: dict) -> dict:
            """Moi lan duoc goi, chon 1 tool DOC hoac tra ve ket qua cuoi."""
            last_tool = observation.get("last_tool")
            result = observation.get("last_result") or {}

            # MockLLM chi MO PHONG model va tinh cost; khong sinh lenh tool.
            # Khong dua ticket cua khach vao prompt vi ticket co the chua lenh gia/secret.
            complete(
                budget,
                seed=seed,
                purpose="single_decide",
                prompt=f"claim={claim_id}; last_tool={last_tool or 'start'}",
            )

            # 1. Chua co du lieu -> doc claim.
            if last_tool is None:
                action = {"tool": "get_claim_view", "args": {"claim_id": claim_id}}

            # 2. Da doc claim -> xem co ma don khong.
            elif last_tool == "get_claim_view":
                if not result.get("found"):
                    action = {"final": {"status": "failed", "error_reason": "unknown_claim"}}
                elif not result.get("order_id"):
                    action = {"final": {"status": "needs_info", "error_reason": "missing_order_id"}}
                else:
                    memory["order_id"] = result["order_id"]
                    memory["principal_id"] = result["principal_id"]
                    action = {"tool": "lookup_order", "args": {
                        "order_id": memory["order_id"],
                        "principal_id": memory["principal_id"],
                    }}

            # 3. Don co ton tai va thuoc dung khach khong?
            elif last_tool == "lookup_order":
                if not result.get("visible"):
                    action = {"final": {
                        "status": "escalated", "error_reason": result.get("reason", "order_not_visible")
                    }}
                else:
                    memory["order"] = result["order"]  # Lay su that tu DB, khong tu ticket
                    action = {"tool": "lookup_policy", "args": {}}

            # 4. Da doc policy hien hanh -> cho CODE tinh tien (khong hoi LLM).
            elif last_tool == "lookup_policy":
                action = {"tool": "compute_compensation", "args": {
                    "order": memory["order"]
                }}

            # 5. So tien = 0 thi tu choi; > 0 thi kiem tra lich su hoan.
            elif last_tool == "compute_compensation":
                memory["quote"] = int(result["amount_vnd"])
                if memory["quote"] <= 0:
                    action = {"final": {
                        "status": "denied", "proposal_amount": 0,
                        "error_reason": result.get("reason"),
                    }}
                else:
                    action = {"tool": "lookup_refund_history", "args": {
                        "order_id": memory["order_id"],
                        "principal_id": memory["principal_id"],
                    }}

            # 6. Du du lieu -> ket thuc ReAct, chi DE XUAT so tien day du.
            elif last_tool == "lookup_refund_history":
                action = {"final": {"status": "quoted", "proposal_amount": memory["quote"]}}

            else:
                action = {"final": {"status": "failed", "error_reason": "unexpected_tool"}}

            # Chi ghi ten buoc, khong ghi ticket/raw DB/PII/secret vao trace.
            final = action.get("final", {})
            trace.add("react", {
                "after": last_tool or "start",
                "next": action.get("tool", "final"),
                "status": final.get("status"),
            })
            return action

        # ReAct lien tuc hoi decide(); toi da 8 lan.
        # worker=True: cam agent goi tool GHI trong vong lap.
        loop = run_react(
            conn, budget,
            observation={"claim": {"claim_id": claim_id}},
            decide=decide,
            max_steps=8,
            worker=True,
        )

        final = loop["final"]
        status = final.get("status", "failed")
        proposal = int(final.get("proposal_amount", 0))
        reason = final.get("error_reason")

        # CHI sau vong ReAct, code cua shape moi goi host ghi tien.
        if status == "quoted" and proposal > 0:
            trace.add("host_request", {"proposal_amount": proposal})
            try:
                outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
            finally:
                # Neu InjectedCrash xay ra, van ghi trace nhung KHONG nuot loi.
                trace.write()

            status = "resolved" if outcome["ok"] else (
                "failed" if outcome["conflict"] else "denied"
            )
            reason = None if outcome["ok"] else outcome["reason"]
            trace.add("host_result", {"status": status, "reason": reason})

        elif status == "quoted":
            status, reason = "failed", "missing_positive_quote"

        # finish() lay refund tu ledger, ghi trace, dong goi RunResult.
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )
    finally:
        conn.close()
