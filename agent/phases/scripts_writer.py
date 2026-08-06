"""Bước 4 — Viết 10 kịch bản video quảng cáo (2-5 phút)."""

from agent.config import (
    BASE_SYSTEM_PROMPT,
    PRIORITY_INSIGHTS_FILE,
    PRODUCT_NAME,
    PRODUCT_REFERENCE_FILE,
    PRODUCT_URL,
    SCRIPTS_DIR,
)
from agent.lib.claude_client import run_agent_task


def run() -> None:
    if not PRIORITY_INSIGHTS_FILE.exists():
        print(f"⚠️  Chưa có {PRIORITY_INSIGHTS_FILE}. Hãy chạy `agent filter-insights` trước.")
        return

    has_reference = PRODUCT_REFERENCE_FILE.exists()

    product_info_section = (
        f"""
Bước 1 — Lấy thông tin sản phẩm CHUẨN (bắt buộc, ưu tiên cao nhất):
Dùng tool Read đọc file `data/{PRODUCT_REFERENCE_FILE.name}`. File này tổng hợp
từ hồ sơ pháp lý thật (Giấy công bố sản phẩm, Giấy xác nhận nội dung quảng cáo
của Cục An Toàn Thực Phẩm, Certificate of Analysis, GMP) — đây là nguồn CHUẨN
XÁC NHẤT, ưu tiên tuyệt đối so với bất kỳ nguồn nào khác.

**Ràng buộc pháp lý BẮT BUỘC tuân thủ (không có ngoại lệ):**
- Câu công dụng CHỈ được nói đúng như mục 1 của file — không nói vượt quá,
  không cam kết "chữa khỏi", "hết đau ngay", "thay thế thuốc chữa bệnh".
- MỌI kịch bản đều phải có câu cảnh báo bắt buộc ở mục 2 của file (ít nhất câu
  "không phải là thuốc...") xuất hiện ở cuối kịch bản (voice-over hoặc chữ chạy).
- Chỉ dùng đúng thành phần/hàm lượng ở mục 3, và câu chuyện cơ chế/nguồn gốc ở
  mục 4 — không bịa thêm.
"""
        if has_reference
        else f"""
Bước 1 — Lấy thông tin sản phẩm thật:
Dùng tool web_fetch để lấy nội dung trang sản phẩm: {PRODUCT_URL}
Ghi chú lại chính xác: thành phần, công nghệ nano hấp thu, sụn vi cá mập,
collagen type II, các thành phần hỗ trợ khác, công dụng, giá, chính sách —
CHỈ dùng thông tin thật lấy được từ trang này, tuyệt đối không bịa thêm công dụng
hay thành phần không có trên trang. (Chưa có file product_reference.md — nếu có
hồ sơ pháp lý/kỹ thuật thật của sản phẩm, đưa cho tôi để lưu vào file này, sẽ
chuẩn xác hơn nhiều so với chỉ fetch website.)
"""
    )

    prompt = f"""\
Nhiệm vụ: Viết 10 kịch bản video quảng cáo Facebook (dài 2-5 phút) cho sản phẩm
{PRODUCT_NAME}, dựa trên insight đã lọc.
{product_info_section}
Bước 2 — Đọc insight đã lọc:
Dùng tool Read đọc file `data/priority_insights.md`.

Bước 3 — Viết 10 kịch bản:
Mỗi kịch bản chạm vào 1 (hoặc kết hợp) insight đã lọc — cố gắng dùng đa dạng
insight khác nhau qua 10 kịch bản, không lặp lại cùng 1 insight cho tất cả.
Mỗi kịch bản gồm đầy đủ các phần sau, viết bằng tiếng Việt tự nhiên gần gũi
(không dùng thuật ngữ marketing trong nội dung kịch bản):

**Hook (3-5 giây đầu):** Câu mở đầu phải chạm đúng 1 insight đã lọc, đủ gây tò mò
hoặc đồng cảm ngay lập tức.

**Vấn đề:** Kể chuyện/đồng cảm với nỗi đau của khách hàng, dùng lại ngôn ngữ
khách hàng thật đã nói (trích từ insight) thay vì ngôn ngữ marketing.

**Giải pháp:** Giải thích cơ chế {PRODUCT_NAME} hoạt động như thế nào — dùng
câu chuyện cơ chế/nguồn gốc thật ở mục 4 của tài liệu tham chiếu (bằng sáng chế
sụn cá mập, glucosamine từ cua tuyết quý hiếm, collagen hấp thụ nhanh...), CHỈ
được mô tả là "hỗ trợ tốt cho khớp" đúng câu công dụng đã duyệt — không suy diễn
thành "chữa được" hay "trị dứt điểm".

**Bằng chứng:** Thành phần/hàm lượng thật, chứng nhận GMP Nhật Bản, kết quả kiểm
định (Certificate of Analysis), feedback khách hàng nếu có dữ liệu thật hỗ trợ
(không bịa feedback giả).

**CTA cụ thể:** Kêu gọi hành động rõ ràng (nhắn tin/inbox/mua ngay), có thể gợi ý
ưu đãi nếu phù hợp với ngữ cảnh kịch bản.

**Cảnh báo bắt buộc:** Nguyên văn câu "Thực phẩm này không phải là thuốc và
không có tác dụng thay thế thuốc chữa bệnh." — đọc bằng giọng đọc nhanh/chữ chạy
ở cuối video, đúng thông lệ quảng cáo TPBVSK.

**Ghi chú dàn dựng:** Bối cảnh quay, nhân vật xuất hiện (KOL/khách hàng thật/bác sĩ),
tông giọng khi quay.

Bước 4 — Ghi file:
Với mỗi kịch bản, dùng tool Write để lưu vào file riêng:
`data/scripts/script_01.md`, `data/scripts/script_02.md`, ... `data/scripts/script_10.md`

Mỗi file bắt đầu bằng:
# Kịch bản [số] — [tên ngắn mô tả góc tiếp cận]
**Insight chính:** [tên insight đã dùng]

Sau đó là các phần Hook / Vấn đề / Giải pháp / Bằng chứng / CTA / Cảnh báo bắt
buộc / Ghi chú dàn dựng theo đúng heading `## Hook`, `## Vấn đề`, `## Giải pháp`,
`## Bằng chứng`, `## CTA`, `## Cảnh báo bắt buộc`, `## Ghi chú dàn dựng`.

Cuối cùng, dùng tool Write tạo thêm file `data/scripts/index.md` liệt kê cả 10
kịch bản dạng bảng: số thứ tự, tên kịch bản, insight chính, câu hook (rút gọn),
link tới file (vd: `script_01.md`).

Sau khi ghi xong toàn bộ, chỉ cần xác nhận ngắn gọn số lượng file đã tạo.
"""

    run_agent_task(
        prompt,
        allowed_tools=["WebFetch", "Read", "Write"],
        system_prompt=BASE_SYSTEM_PROMPT,
        max_turns=40,
    )

    created = list(SCRIPTS_DIR.glob("script_*.md"))
    print(f"\n✅ Đã tạo {len(created)} file kịch bản trong: {SCRIPTS_DIR}")
