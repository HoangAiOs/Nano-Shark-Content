"""Bước 1 — Research: thu thập dữ liệu thô về insight khách hàng."""

from agent.config import (
    BASE_SYSTEM_PROMPT,
    INBOX_COMMENTS_FILE,
    RAW_RESEARCH_FILE,
    TARGET_AUDIENCE,
    TESTIMONIALS_INDEX_FILE,
)
from agent.lib.claude_client import run_agent_task


def run() -> None:
    has_inbox_file = INBOX_COMMENTS_FILE.exists()
    has_testimonials = TESTIMONIALS_INDEX_FILE.exists()

    inbox_section = (
        f"""
Đọc dữ liệu inbox/comment nội bộ:
Đọc file `data/{INBOX_COMMENTS_FILE.name}` (dùng tool Read).
File này có schema CSV: source, author, content, date, type (comment/inbox), post_url.
Đưa toàn bộ nội dung này vào cùng bộ dữ liệu thô, credibility = "public_discussion".
"""
        if has_inbox_file
        else """
Dữ liệu inbox/comment nội bộ: BỎ QUA — chưa có file `data/inbox_comments.csv`.
"""
    )

    testimonial_section = (
        """
Bước 1 — Nguồn CHÍNH, ưu tiên cao nhất — Video feedback khách hàng THẬT đã dùng sản phẩm:
Đọc file `data/customer_testimonials/index.json` (dùng tool Read) để lấy danh sách
transcript. Với MỖI bản ghi trong index này, đọc file transcript tương ứng
(trường `transcript_path`, dùng tool Read) — đây là lời nói nguyên văn của khách
hàng THẬT đã dùng sản phẩm, quay trải nghiệm thật (không phải diễn/booking), độ
tin cậy cao nhất trong toàn bộ dữ liệu.

Với mỗi transcript, trích ra các câu nói/insight cụ thể (nguyên văn hoặc gần
nguyên văn) về: lý do họ tìm đến sản phẩm, triệu chứng/nỗi đau trước khi dùng,
cảm nhận/thay đổi sau khi dùng, điều khiến họ tin tưởng, điều họ còn băn khoăn.
Với mỗi insight trích ra, LUÔN ghi rõ `customer_label`, `year`, `month` từ index.json
để có thể trích dẫn kiểu "chị Hà, phản hồi tháng 12/2025 nói: ...".

Đây là dữ liệu bắt buộc phải xử lý hết (không bỏ sót transcript nào trong index.json).
"""
        if has_testimonials
        else """
Bước 1 — Nguồn video feedback khách hàng thật: CHƯA CÓ.
Chưa có `data/customer_testimonials/index.json` — bỏ qua bước này, chỉ dùng tìm
kiếm công khai bên dưới.
"""
    )

    public_search_section = f"""
Bước 2 — Nguồn BỔ SUNG (không thay thế) — Tìm kiếm công khai (web_search, web_fetch):
Dữ liệu ở bước này chỉ để hiểu thêm góc nhìn của NGƯỜI CHƯA DÙNG sản phẩm (đang
tìm hiểu/than phiền chung về đau khớp) — KHÔNG dùng để thay thế bằng chứng thật
từ Bước 1. Đánh dấu credibility = "public_discussion" cho toàn bộ dữ liệu ở bước
này. Tìm trên 3 nguồn sau về: nguyên nhân đau nhức xương khớp, triệu chứng họ
đang gặp, cách họ đang chữa/giảm đau, sản phẩm họ đã dùng và phản hồi, nỗi lo/ngộ
nhận chung:

1. **Google** — bài báo, trang sức khỏe, forum, hỏi đáp.
2. **YouTube** — video review, bình luận dưới video.
3. **Facebook Groups công khai** — qua Google `site:facebook.com/groups <từ khóa>`.
   Facebook chặn truy cập tự động vào nội dung yêu cầu đăng nhập — CHỈ lấy phần
   công khai trong snippet/trang fetch được mà không cần đăng nhập; nếu không
   fetch được thì bỏ qua, không suy đoán nội dung.

{"Tìm khoảng 8-12 nguồn (ít hơn bình thường vì đã có nguồn testimonial thật ở trên làm chính)." if has_testimonials else "Tìm ít nhất 15-20 nguồn khác nhau, đa dạng cả 3 kênh trên."}
Với mỗi nguồn, ưu tiên trích dẫn nguyên văn câu nói của khách hàng thay vì diễn giải lại.
{inbox_section}"""

    prompt = f"""\
Nhiệm vụ: Thu thập dữ liệu thô (raw research) về insight khách hàng của
{TARGET_AUDIENCE}, sau đó lưu toàn bộ vào file `data/raw_research.json`.
{testimonial_section}
{public_search_section}
Bước 3 — Ghi kết quả:
Dùng tool Write để lưu TOÀN BỘ dữ liệu thô thu thập được vào `data/raw_research.json`
theo đúng schema JSON sau (một mảng các object):

[
  {{
    "source_type": "web" | "video" | "comment" | "facebook_group" | "inbox",
    "credibility": "real_customer_testimonial" | "public_discussion",
    "platform": "tên nền tảng, vd: Google, YouTube, Facebook, Video testimonial nội bộ...",
    "url": "link nguồn, để rỗng nếu không có",
    "title": "tiêu đề bài viết/video/group nếu có",
    "author": "tên tác giả/người nói, với testimonial dùng đúng customer_label từ index.json",
    "date": "vd '2025-12' lấy từ year/month trong index.json nếu là testimonial, hoặc ngày bài viết nếu có",
    "content": "nội dung/trích dẫn nguyên văn, đây là trường quan trọng nhất"
  }},
  ...
]

Ghi đè toàn bộ file (không cần giữ lại nội dung cũ). Không cần trả lời gì thêm
ngoài việc ghi file — chỉ cần xác nhận ngắn gọn: bao nhiêu bản ghi từ testimonial
thật (real_customer_testimonial) và bao nhiêu từ tìm kiếm công khai (public_discussion),
chia theo từng kênh.
"""

    if not has_inbox_file:
        print(
            "ℹ️  Chưa có data/inbox_comments.csv — bỏ qua dữ liệu inbox/comment nội bộ lần chạy này.\n"
        )
    if has_testimonials:
        print(
            "✅ Đã tìm thấy data/customer_testimonials/index.json — dùng làm nguồn CHÍNH cho research "
            "(video feedback khách hàng thật), tìm kiếm công khai chỉ để bổ sung.\n"
        )
    else:
        print(
            "ℹ️  Chưa có data/customer_testimonials/index.json — chưa transcribe testimonial nào. "
            "Chạy `python -m agent.cli transcribe-testimonials` trước nếu muốn dùng nguồn này.\n"
        )

    run_agent_task(
        prompt,
        allowed_tools=["WebSearch", "WebFetch", "Read", "Write"],
        system_prompt=BASE_SYSTEM_PROMPT,
        max_turns=40 if has_testimonials else 30,
    )

    if RAW_RESEARCH_FILE.exists():
        print(f"\n✅ Đã lưu dữ liệu thô tại: {RAW_RESEARCH_FILE}")
    else:
        print("\n⚠️  Không tìm thấy file raw_research.json — kiểm tra lại log phía trên.")
