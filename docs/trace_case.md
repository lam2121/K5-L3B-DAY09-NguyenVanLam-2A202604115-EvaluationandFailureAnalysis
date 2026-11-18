# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID: `E-seeded_regression-20261118-34cb` |
| Triệu chứng | `lab8.metrics.trial_pass` fail (`status resolved != denied`), `refund_amount_correct` fail (ledger=20000, label=0); reply thông báo: *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* |
| Bước sai đầu tiên | Event 3: `model_override` payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 (`handoff`) và Event 2 (`investigator`) hoàn toàn đúng sự thật trong database (DB lưu `delay_days: 2`, `status: delivered`). Đến Event 3, agent tự ý tin số ngày khách hàng tự khai trong ticket ("trễ 5 ngày") và ghi đè sự thật khách quan của DB. |
| Failure mode | Mã `FM-03` (`ticket_trust — tin ticket hơn DB`) |
| Đối chứng | Trên shape `fixed` (cùng `C-002@11`), không có event `model_override`. Event 3 là `quote {"amount_vnd": 0, "reason": "no_entitlement"}`, dẫn tới từ chối hoàn tiền đúng quy định (`status: denied`, refund=0đ). |
| Regression test | Test `test_override_event_breaks_db_fact` (grader `DbFactKept`) và test trial `C-002` trong `test_public_single_run_cases`. Đã xác nhận: fail trên `seeded_regression` và pass trên `fixed`. |
| Chưa chắc chắn | Trace chỉ ghi nhận agent đưa ra quyết định ghi đè, không thể hiện suy nghĩ nội tâm (chain of thought) chi tiết của model nếu không bật log verbose của LLM. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
