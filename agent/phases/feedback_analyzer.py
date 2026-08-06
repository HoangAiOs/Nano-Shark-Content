"""Bước 6 — Feedback loop: đối chiếu số liệu quảng cáo thực tế với kịch bản."""

from agent.config import (
    AD_PERFORMANCE_FILE,
    AD_PERFORMANCE_SAMPLE_FILE,
    BASE_SYSTEM_PROMPT,
    FEEDBACK_ANALYSIS_FILE,
    SCRIPTS_DIR,
)
from agent.lib.claude_client import run_agent_task


def run() -> None:
    perf_file = AD_PERFORMANCE_FILE if AD_PERFORMANCE_FILE.exists() else AD_PERFORMANCE_SAMPLE_FILE

    if not AD_PERFORMANCE_FILE.exists():
        print(
            f"ℹ️  Chưa có {AD_PERFORMANCE_FILE.name} — đang dùng file mẫu "
            f"{AD_PERFORMANCE_SAMPLE_FILE.name} để bạn xem định dạng.\n"
            f"   Khi có số liệu thật, lưu vào: {AD_PERFORMANCE_FILE}\n"
        )

    if not any(SCRIPTS_DIR.glob("script_*.md")):
        print(f"⚠️  Chưa có kịch bản nào trong {SCRIPTS_DIR}. Hãy chạy `agent write-scripts` trước.")
        return

    prompt = f"""\
Nhiệm vụ: Đọc số liệu quảng cáo thực tế và đối chiếu với nội dung từng kịch bản
để phân tích hiệu quả, sau đó ghi kết quả vào `data/feedback_analysis.md`.

Bước 1 — Đọc dữ liệu:
- Dùng tool Read đọc file `{perf_file.relative_to(perf_file.parent.parent)}`.
  Schema CSV: script_id, hook_summary, ctr, retention_3s, retention_25,
  retention_50, retention_75, retention_100, comments, inbox, cost, conversions
- Dùng tool Read đọc từng file kịch bản tương ứng trong `data/scripts/`
  (script_id khớp với tên file, vd script_id "01" → `data/scripts/script_01.md`)

Bước 2 — Phân tích:
Với mỗi kịch bản có số liệu, phân tích:
- Kịch bản này hiệu quả hay không (dựa trên CTR, retention các mốc, conversions
  so với chi phí)
- Insight nào được dùng, insight đó có thực sự "ăn" với khách hàng không (dựa
  vào retention_3s và retention_25 — nếu rớt mạnh ngay từ đầu, hook/insight có
  vấn đề)
- Độ dài kịch bản có ảnh hưởng đến retention không (so sánh giữa các kịch bản)
- CTA có tạo ra inbox/conversion tương xứng với lượng người xem hết video không

Bước 3 — Kết luận:
Rút ra:
- Nhóm kịch bản hiệu quả nhất và điểm chung của chúng (loại hook, loại insight,
  độ dài, loại CTA)
- Nhóm kịch bản kém hiệu quả nhất và lý do cụ thể (dựa trên số liệu, không suy
  đoán chung chung)

Ghi file `data/feedback_analysis.md` với cấu trúc:

# Phân tích hiệu quả quảng cáo

## Bảng số liệu tóm tắt
(bảng: script_id, CTR, retention 3s/25/50/75/100, inbox, conversions, đánh giá
nhanh Tốt/Trung bình/Kém)

## Phân tích chi tiết từng kịch bản
### Kịch bản [id] — [tên]
- Kết quả: ...
- Phân tích: tại sao hiệu quả/không hiệu quả (dựa trên hook, insight, độ dài, CTA)

## Kết luận & bài học
- Điều gì đang hiệu quả (pattern chung)
- Điều gì không hiệu quả (pattern chung)

Dùng tool Write để lưu vào `data/feedback_analysis.md`, ghi đè toàn bộ file
(nếu file đã tồn tại từ lần chạy trước, viết lại hoàn toàn dựa trên dữ liệu mới
nhất, không cần giữ nội dung cũ). Sau khi ghi xong, chỉ cần xác nhận ngắn gọn.
"""

    run_agent_task(
        prompt,
        allowed_tools=["Read", "Write"],
        system_prompt=BASE_SYSTEM_PROMPT,
        max_turns=25,
    )

    if FEEDBACK_ANALYSIS_FILE.exists():
        print(f"\n✅ Đã lưu phân tích tại: {FEEDBACK_ANALYSIS_FILE}")
    else:
        print("\n⚠️  Không tìm thấy file feedback_analysis.md — kiểm tra lại log phía trên.")
