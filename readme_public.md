# Hành Trình Chinh Phục 100/100 Điểm - Observathon Public Phase

Báo cáo này mô tả chi tiết toàn bộ quy trình cấu hình, gỡ lỗi và tối ưu hóa hệ thống từ những bước đầu tiên của bài lab cho đến khi đạt được số điểm tuyệt đối `100.0/100` ở tập dữ liệu Public.

---

## Giai đoạn 1: Khởi động và Vượt rào cản Môi trường
* **Vấn đề:** Các file thực thi (binary) của ban tổ chức cấp được đóng gói bằng PyInstaller cho môi trường Linux, nhưng lại chạy trên máy host Windows gây ra lỗi thiếu file thư viện `.so` và các vấn đề tương thích.
* **Giải pháp:** Thiết lập môi trường **WSL (Ubuntu 24.04)** trên Windows để chạy giả lập native Linux. Cấp quyền thực thi (`chmod +x`) cho toàn bộ file nhị phân trong thư mục `bin/`.
* **Kết quả:** Vượt qua vòng Practice với điểm số sơ bộ, hệ thống hoạt động trơn tru.

## Giai đoạn 2: Tinh chỉnh Lớp Phòng Vệ (Wrapper) & Đạt 97.69 Điểm
Chạy thử nghiệm trên tập Public (120 câu hỏi) đã bộc lộ những điểm yếu của AI Agent gốc. Chúng ta đã xây dựng `wrapper.py` để "bọc lót" cho AI:
* **Chặn Prompt Injection:** Thêm hàm `sanitize_question()` dùng regex cắt bỏ nội dung độc hại phía sau từ khóa *"Ghi chú"* / *"Note"*.
* **Bảo vệ PII:** Kích hoạt tính năng `redact_pii` trong `config.json` để tự động che khuất email và số điện thoại trước khi lưu log.
* **Xử lý sập nguồn:** Lắp vòng lặp `retry` với `max_attempts=3` và Exponential Backoff (100ms) để hệ thống không bị crash khi API lỗi.
* **Kết quả:** Đạt `97.69 / 100` điểm. (Vẫn còn thất thoát ở mục Cost, Latency và F1 Diagnosis).

## Giai đoạn 3: Phân tích & Vượt Rào Cản OpenRouter (Lỗi 402)
Để đạt 100 điểm, chúng ta tiếp tục siết chặt `config.json`:
* **Tối ưu Cost/Latency:** 
    * Hạ `self_consistency` từ 2 xuống 1 (giảm phân nửa chi phí gọi hàm).
    * Giới hạn `max_completion_tokens = 300` và `context_size = 3` để ngăn chặn bùng nổ token khi chat dài (Cost Blowup).
* **Khủng hoảng API:** Quá trình test cường độ cao đã làm cạn kiệt tài khoản OpenRouter, gây ra lỗi HTTP 402 (Insufficient Credits).
* **Giải pháp:** Cập nhật file `.env`, chuyển hướng trực tiếp sang API của OpenAI (`sk-proj-...`) và đổi tên model thành `gpt-4o-mini` chuẩn quốc tế, giúp hệ thống hồi sinh.

## Giai đoạn 4: Mài bén Prompt và Mở khóa 22 Điểm Bonus
* **Correctness:** Sửa đổi `prompt.txt` mang tính mệnh lệnh cực đoan. Ép LLM luôn trả kết quả ở dòng cuối cùng dưới dạng `Tong cong: <số nguyên> VND` (cấm tuyệt đối dấu phẩy hay ký tự lạ). Hệ quả là bộ chấm điểm (parser) không còn bị lỗi khi đọc kết quả.
* **Diagnosis F1 (Tuyệt chiêu cuối):** 
    * Xây dựng script Python đọc ngược file output do Simulator nhả ra (`run_output.json`).
    * Tự động quét và gom các QID lỗi rải rác như `req-pub-010-pub-010` khớp với từng danh mục lỗi (Latency Spike, Fabrication, Infinite Loop, ...).
    * Mở rộng `findings.json` lên đủ 11/11 lỗi và chèn bằng chứng `trace_ids` thực tế vào. Ban giám khảo tự động cộng thêm ~22 điểm thưởng (F1 = 0.952).

## 🎉 KẾT QUẢ CUỐI CÙNG
Sau lần chạy cuối cùng với lệnh `observathon-sim --concurrency 8` và `observathon-score`:
* **Correct:** Tăng mạnh lên 0.823
* **Cost / Latency:** Cải thiện tuyệt đối nhờ giới hạn Token và Caching.
* **Diagnosis F1:** Đạt 0.952
* **Tổng điểm (Headline Score): 100.0 / 100 Điểm.** 

Pipeline này đã chuẩn bị sẵn sàng một bộ `findings_private.json` để tiếp tục càn quét vòng Private Test tiếp theo!
