"""Bước 7 — Optimization: đề xuất chỉnh sửa/kịch bản mới dựa trên feedback."""

from agent.config import BASE_SYSTEM_PROMPT, FEEDBACK_ANALYSIS_FILE, OPTIMIZED_SCRIPTS_FILE, SCRIPTS_DIR
from agent.lib.claude_client import run_agent_task


def run() -> None:
    if not FEEDBACK_ANALYSIS_FILE.exists():
        print(f"⚠️  Chưa có {FEEDBACK_ANALYSIS_FILE}. Hãy chạy `agent analyze-feedback` trước.")
        return

    prompt = """\
Nhiệm vụ: Dựa trên phân tích feedback thực tế, đề xuất phiên bản chỉnh sửa cho
các kịch bản yếu và/hoặc kịch bản mới theo hướng đã chứng minh hiệu quả. Ghi kết
quả vào `data/optimized_scripts.md`.

Bước 1 — Đọc dữ liệu:
Dùng tool Read đọc `data/feedback_analysis.md` và các file kịch bản gốc liên quan
trong `data/scripts/` (đọc file nào cần thiết dựa trên kết luận trong phân tích
feedback).

Bước 2 — Đề xuất tối ưu:
Với mỗi kịch bản được đánh giá là kém hiệu quả trong feedback_analysis.md, đề xuất:
- Hook mới — dựa trên insight/pattern đã chứng minh hiệu quả ở các kịch bản khác
- Cấu trúc mới nếu cần (vd: rút ngắn phần vấn đề, đổi vị trí CTA...)
- Giữ nguyên phần nào của kịch bản gốc vẫn ổn, chỉ sửa phần có vấn đề

Nếu phân tích feedback cho thấy một hướng insight/hook/CTA rõ ràng hiệu quả,
đề xuất thêm 1-2 kịch bản HOÀN TOÀN MỚI khai thác sâu hơn hướng đó.

Với mỗi đề xuất, giải thích rõ: dựa trên số liệu/insight nào mà đề xuất thay đổi
này, kỳ vọng cải thiện điều gì (vd: retention 3s, CTR, tỷ lệ inbox...).

Bước 3 — Ghi file:
Ghi vào `data/optimized_scripts.md` với cấu trúc:

# Đề xuất tối ưu kịch bản — [ngày chạy]

## Kịch bản cần chỉnh sửa
### [id/tên kịch bản gốc] → Phiên bản tối ưu
**Vấn đề của bản gốc:** ...
**Thay đổi đề xuất:** ...
**Kịch bản đầy đủ sau khi sửa:** (viết đầy đủ Hook/Vấn đề/Giải pháp/Bằng chứng/CTA/
Ghi chú dàn dựng như định dạng kịch bản gốc)

## Kịch bản mới đề xuất (nếu có)
(cùng định dạng như kịch bản gốc: Hook/Vấn đề/Giải pháp/Bằng chứng/CTA/Ghi chú dàn dựng)

Dùng tool Write để lưu vào `data/optimized_scripts.md`. Nếu file đã tồn tại từ
lần chạy tối ưu trước, GHI THÊM (không xóa nội dung cũ) một mục mới với heading
`# Vòng tối ưu [ngày giờ chạy]` để giữ lại lịch sử các vòng tối ưu — dùng tool
Read để kiểm tra nội dung hiện có trước, sau đó Write lại toàn bộ file với nội
dung cũ + mục mới nối tiếp phía dưới.

Sau khi ghi xong, chỉ cần xác nhận ngắn gọn.
"""

    run_agent_task(
        prompt,
        allowed_tools=["Read", "Write"],
        system_prompt=BASE_SYSTEM_PROMPT,
        max_turns=25,
    )

    if OPTIMIZED_SCRIPTS_FILE.exists():
        print(f"\n✅ Đã lưu đề xuất tối ưu tại: {OPTIMIZED_SCRIPTS_FILE}")
    else:
        print("\n⚠️  Không tìm thấy file optimized_scripts.md — kiểm tra lại log phía trên.")
