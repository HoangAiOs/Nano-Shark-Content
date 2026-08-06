"""Bước 5 — Đánh giá & lọc top 5 kịch bản."""

from agent.config import BASE_SYSTEM_PROMPT, SCORES_FILE, SCRIPTS_DIR
from agent.lib.claude_client import run_agent_task


def run() -> None:
    scripts = sorted(SCRIPTS_DIR.glob("script_*.md"))
    if not scripts:
        print(f"⚠️  Chưa có kịch bản nào trong {SCRIPTS_DIR}. Hãy chạy `agent write-scripts` trước.")
        return

    prompt = """\
Nhiệm vụ: Đọc toàn bộ 10 file kịch bản trong thư mục `data/scripts/` (dùng tool
Read cho từng file `script_01.md` đến `script_10.md`), chấm điểm và chọn ra 5
kịch bản tốt nhất, sau đó ghi kết quả vào `data/scores.md`.

Chấm điểm mỗi kịch bản theo 4 tiêu chí, thang điểm 1-10:
1. Mức độ chạm insight — hook và nội dung có thực sự chạm đúng nỗi đau/mong muốn
   khách hàng hay không
2. Tính mới/khác biệt — so với các kịch bản quảng cáo xương khớp phổ biến trên
   thị trường và so với 9 kịch bản còn lại
3. Khả năng giữ chân người xem — cấu trúc có đủ hấp dẫn để xem hết 2-5 phút không
4. Độ rõ ràng của CTA — lời kêu gọi hành động có cụ thể, dễ hành động không

Ghi file `data/scores.md` với cấu trúc:

# Bảng điểm kịch bản

## Bảng tổng hợp
| # | Tên kịch bản | Chạm insight | Mới/khác biệt | Giữ chân người xem | CTA rõ ràng | Tổng điểm |
|---|---|---|---|---|---|---|
(10 dòng, tổng điểm = tổng 4 tiêu chí, thang tối đa 40)

## Top 5 kịch bản được chọn
Với mỗi kịch bản trong top 5, viết:
### #[số] — [tên kịch bản] (tổng điểm x/40)
**Lý do chọn:** giải thích 2-3 câu tại sao kịch bản này thuộc top 5, nêu rõ điểm
mạnh cụ thể.

Dùng tool Write để lưu vào `data/scores.md`, ghi đè toàn bộ file. Sau khi ghi
xong, chỉ cần xác nhận ngắn gọn.
"""

    run_agent_task(
        prompt,
        allowed_tools=["Read", "Write"],
        system_prompt=BASE_SYSTEM_PROMPT,
        max_turns=20,
    )

    if SCORES_FILE.exists():
        print(f"\n✅ Đã lưu bảng điểm tại: {SCORES_FILE}")
    else:
        print("\n⚠️  Không tìm thấy file scores.md — kiểm tra lại log phía trên.")
