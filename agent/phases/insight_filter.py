"""Bước 3 — Lọc insight ưu tiên (5-7 insight mạnh nhất)."""

from agent.config import BASE_SYSTEM_PROMPT, PRIORITY_INSIGHTS_FILE, VOICE_OF_CUSTOMER_FILE
from agent.lib.claude_client import run_agent_task


def run() -> None:
    if not VOICE_OF_CUSTOMER_FILE.exists():
        print(f"⚠️  Chưa có {VOICE_OF_CUSTOMER_FILE}. Hãy chạy `agent synthesize` trước.")
        return

    prompt = """\
Nhiệm vụ: Đọc file `data/voice_of_customer.md` (dùng tool Read), chấm điểm và
chọn ra 5-7 insight mạnh nhất, sau đó ghi ra file `data/priority_insights.md`.

Tiêu chí chấm điểm (thang 1-10 cho mỗi tiêu chí):
- Tần suất xuất hiện: insight này xuất hiện nhiều lần trong dữ liệu hay chỉ 1-2 lần
- Cường độ cảm xúc: mức độ khẩn thiết/bức xúc/lo lắng trong lời khách hàng khi nói
  về điều này (không phải insight nào khách hàng nói bình thản cũng yếu — nhưng
  ưu tiên insight có cảm xúc mạnh vì dễ tạo hook)

Với mỗi insight được chọn, trình bày:
### Insight #[số]: [tên ngắn gọn]
- **Mô tả:** ...
- **Điểm tần suất:** x/10
- **Điểm cường độ cảm xúc:** x/10
- **Tổng điểm:** x/20
- **Lý do chọn:** giải thích ngắn gọn (2-3 câu) tại sao insight này đủ mạnh để
  làm nền cho kịch bản quảng cáo
- **Trích dẫn minh họa:** 1-2 câu trích nguyên văn từ voice_of_customer.md

Sắp xếp theo tổng điểm giảm dần. Ghi file với heading:
# Insight Ưu Tiên — [tên sản phẩm]

Dùng tool Write để lưu vào `data/priority_insights.md`, ghi đè toàn bộ file.
Sau khi ghi xong, chỉ cần xác nhận ngắn gọn.
"""

    run_agent_task(
        prompt,
        allowed_tools=["Read", "Write"],
        system_prompt=BASE_SYSTEM_PROMPT,
        max_turns=15,
    )

    if PRIORITY_INSIGHTS_FILE.exists():
        print(f"\n✅ Đã lưu insight ưu tiên tại: {PRIORITY_INSIGHTS_FILE}")
    else:
        print("\n⚠️  Không tìm thấy file priority_insights.md — kiểm tra lại log phía trên.")
