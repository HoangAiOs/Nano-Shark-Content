"""Bước 2 — Tổng hợp Voice of Customer từ dữ liệu thô."""

from agent.config import BASE_SYSTEM_PROMPT, RAW_RESEARCH_FILE, VOICE_OF_CUSTOMER_FILE
from agent.lib.claude_client import run_agent_task


def run() -> None:
    if not RAW_RESEARCH_FILE.exists():
        print(f"⚠️  Chưa có {RAW_RESEARCH_FILE}. Hãy chạy `agent research` trước.")
        return

    prompt = f"""\
Nhiệm vụ: Đọc file `data/raw_research.json` (dùng tool Read), phân tích và tổng
hợp thành Voice of Customer, sau đó ghi ra file `data/voice_of_customer.md`.

QUAN TRỌNG — CHỈ dùng dữ liệu khách hàng thật, bỏ qua tìm kiếm công khai:
File raw_research.json có 2 loại bản ghi phân biệt bằng trường `credibility`:
`"real_customer_testimonial"` (21 bản ghi — video feedback khách hàng THẬT đã
dùng sản phẩm) và `"public_discussion"` (bản ghi từ tìm kiếm công khai). Cho
lần tổng hợp này, CHỈ sử dụng các bản ghi `"real_customer_testimonial"` — bỏ
qua hoàn toàn mọi bản ghi `"public_discussion"`, không đưa vào bất kỳ bảng nào.
Mục tiêu là phản ánh đúng trải nghiệm thật của khách đã dùng sản phẩm, không
pha trộn với ý kiến của người chưa dùng.

Với mỗi insight, cột "Nguồn / câu gốc" PHẢI trích dẫn theo mẫu: "[Tên khách
hàng], phản hồi tháng [tháng]/[năm]: "[câu nói nguyên văn]"" — để sau này dùng
làm bằng chứng thật trong kịch bản quảng cáo.

Nếu một nhóm (vd nỗi lo/ngộ nhận) không có đủ dữ liệu từ 21 testimonial thật để
kết luận, để bảng ngắn hơn hoặc ghi chú "chưa đủ dữ liệu" — không bịa và không
lấy bù từ public_discussion.

Phân loại toàn bộ insight thành 6 nhóm sau, mỗi nhóm trình bày dưới dạng bảng
Markdown với 2 cột: "Insight" và "Nguồn / câu gốc" (dẫn link nếu có, hoặc trích
nguyên văn câu nói kèm mô tả nguồn nếu không có link — để người dùng kiểm chứng
được từng dòng):

1. Câu hỏi thường gặp — những câu hỏi khách hàng hay đặt ra
2. Điều khách hàng hiểu đúng — về bệnh xương khớp hoặc về nhóm sản phẩm này
3. Điều khách hàng hiểu sai (ngộ nhận cần đính chính)
4. Nỗi lo lớn nhất — vd: sợ phải mổ, sợ liệt, sợ phụ thuộc thuốc giảm đau, sợ tốn kém...
5. Mong muốn lớn nhất — vd: hết đau, đi lại bình thường, không phiền con cháu, ngủ ngon...
6. Niềm tin hiện có — vd: tin Đông y/mẹo dân gian, nghi ngờ quảng cáo, sợ tác dụng phụ
   Tây y...

Mỗi nhóm nên có ít nhất 5 dòng nếu dữ liệu cho phép. Không bịa insight — nếu dữ liệu
thô không đủ để kết luận điều gì đó, không đưa vào.

Ghi file theo cấu trúc:
# Voice of Customer — [tên sản phẩm]

## 1. Câu hỏi thường gặp
(bảng)

## 2. Điều khách hàng hiểu đúng
(bảng)

## 3. Điều khách hàng hiểu sai (ngộ nhận)
(bảng)

## 4. Nỗi lo lớn nhất
(bảng)

## 5. Mong muốn lớn nhất
(bảng)

## 6. Niềm tin hiện có
(bảng)

Dùng tool Write để lưu vào đúng đường dẫn `data/voice_of_customer.md`, ghi đè
toàn bộ file. Sau khi ghi xong, chỉ cần xác nhận ngắn gọn.
"""

    run_agent_task(
        prompt,
        allowed_tools=["Read", "Write"],
        system_prompt=BASE_SYSTEM_PROMPT,
        max_turns=20,
    )

    if VOICE_OF_CUSTOMER_FILE.exists():
        print(f"\n✅ Đã lưu Voice of Customer tại: {VOICE_OF_CUSTOMER_FILE}")
    else:
        print("\n⚠️  Không tìm thấy file voice_of_customer.md — kiểm tra lại log phía trên.")
