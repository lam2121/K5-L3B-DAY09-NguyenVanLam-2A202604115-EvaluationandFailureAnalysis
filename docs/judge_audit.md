# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | ĐẠT (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | KHÔNG ĐẠT (κ=0.375 < 0.6, R=0.300 < 0.7) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (tone) | PASS | FAIL | Người đúng | Câu văn: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* Văn phong xuề xòa, dùng từ xưng hô "anh - em" và đuôi câu "nha" không đạt chuẩn chuyên nghiệp CSKH. Sửa rubric judge: bổ sung cấm xưng hô thiếu trang trọng và các từ đệm địa phương/thân mật. |
| 2 | `H-029` (tone) | PASS | FAIL | Người đúng | Câu văn: *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* Giọng điệu cộc lốc mang tính mệnh lệnh tiêu cực ("không cần nhắn thêm"). Sửa rubric: cấm các mẫu câu mang tính gạt bỏ hoặc ra lệnh cho khách hàng. |
| 3 | `H-042` (tone) | FAIL | PASS | Người đúng | Câu văn: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* Câu trả lời nhã nhặn, đầy đủ thông tin thời gian. Judge bắt bẻ thái quá (False Positive). Sửa rubric: làm rõ việc nêu thời gian tiền về (3-5 ngày) là chuẩn mực, không vi phạm giọng điệu. |
| 4 | `H-051` (tone) | FAIL | PASS | Người đúng | Câu văn: *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* Dùng từ chèn tiếng Anh "refund". Người chấp nhận vì dễ hiểu, judge bắt lỗi ngoại ngữ. Sửa rubric: cho phép từ mượn phổ biến hoặc yêu cầu chuẩn hóa 100% tiếng Việt nếu có chính sách ngôn ngữ nghiêm ngặt. |
| 5 | `HL-016` (helpful) | PASS | FAIL | Người đúng | Câu văn: *"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của..."* Lời xin lỗi khuôn sáo rỗng (canned apology), không đưa ra giải pháp hay thông tin thực tế nào giải quyết đơn hàng. Judge bị đánh lừa bởi tính lịch sự; Người đánh giá đúng là FAIL hữu ích. Sửa rubric: câu trả lời chỉ xin lỗi mà không có thông tin xử lý đơn thì bắt buộc chấm FAIL. |

## Kết luận
- **Tiêu chí bị loại và lý do**: `judge_helpful` bị loại vì không đạt ngưỡng tin cậy bắt buộc:
  - Chỉ số $\kappa = 0.375$ (thấp hơn nhiều so với ngưỡng sàn 0.6) và Recall chỉ đạt $0.300$ (ngưỡng sàn 0.7).
  - Ma trận nhầm lẫn: `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`. 
  - Tỉ lệ bỏ sót lỗi (False Negative) lên tới $21/30 = 70\%$. Judge bị đánh lừa bởi các câu trả lời lịch sự nhưng rỗng tuếch, để lọt phần lớn câu trả lời vô dụng tới khách hàng. Nếu đưa judge này vào làm CI gate sẽ gây rủi ro nghiêm trọng (báo nhầm an toàn giả tạo).
- **Tiêu chí được chọn**: `judge_tone` đạt toàn bộ các ngưỡng sàn ($\kappa=0.757$, $P=0.857$, $R=0.800$), tỷ lệ phát hiện lỗi tốt và ma trận nhầm lẫn cân bằng `{'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}`, tỉ lệ lỗi quan sát $0.28$ qua hiệu chỉnh Rogan-Gladen phản ánh đúng tỉ lệ lỗi thực tế $0.30$.
- **Rủi ro còn lại**: Cả hai judge hiện chỉ được kiểm tra trên dữ liệu replay đã công khai (public replay dataset); chưa được kiểm định trên dữ liệu tương tác người dùng mới (held-out data) và các tình huống đàm thoại nhiều lượt. Cần gắn thêm luồng gán nhãn con người định kỳ trước khi triển khai sản xuất.
