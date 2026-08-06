"""Cấu hình dùng chung cho toàn bộ agent."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"

PRODUCT_NAME = "Nano Premium Shark Cartilage"
PRODUCT_URL = "https://nichieiasia.com/products/thuc-pham-bao-ve-suc-khoe-nano-premium-shark-cartilage"
TARGET_AUDIENCE = "Người trên 30 tuổi đang gặp vấn đề đau nhức xương khớp"

# Model mặc định cho toàn bộ pipeline. Có thể đổi sang model khác nếu cần tiết kiệm chi phí.
MODEL = "claude-opus-5"

PRODUCT_REFERENCE_FILE = DATA_DIR / "product_reference.md"

# Nguồn video feedback khách hàng thật (Google Drive) — độ tin cậy cao nhất,
# ưu tiên hơn dữ liệu tìm kiếm công khai (Google/YouTube/Facebook Group).
RAW_VIDEOS_DIR = DATA_DIR / "raw_videos"
CUSTOMER_TESTIMONIALS_DIR = DATA_DIR / "customer_testimonials"
TESTIMONIALS_INDEX_FILE = CUSTOMER_TESTIMONIALS_DIR / "index.json"

RAW_RESEARCH_FILE = DATA_DIR / "raw_research.json"
VOICE_OF_CUSTOMER_FILE = DATA_DIR / "voice_of_customer.md"
PRIORITY_INSIGHTS_FILE = DATA_DIR / "priority_insights.md"
SCORES_FILE = DATA_DIR / "scores.md"
FEEDBACK_ANALYSIS_FILE = DATA_DIR / "feedback_analysis.md"
OPTIMIZED_SCRIPTS_FILE = DATA_DIR / "optimized_scripts.md"

INBOX_COMMENTS_SAMPLE_FILE = DATA_DIR / "inbox_comments.sample.csv"
INBOX_COMMENTS_FILE = DATA_DIR / "inbox_comments.csv"

AD_PERFORMANCE_SAMPLE_FILE = DATA_DIR / "ad_performance.sample.csv"
AD_PERFORMANCE_FILE = DATA_DIR / "ad_performance.csv"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


BASE_SYSTEM_PROMPT = f"""\
Bạn là chuyên gia nghiên cứu insight khách hàng và copywriter quảng cáo Facebook,
chuyên về ngành thực phẩm bảo vệ sức khỏe xương khớp tại Việt Nam.

Sản phẩm đang làm: {PRODUCT_NAME} ({PRODUCT_URL})
Khách hàng mục tiêu: {TARGET_AUDIENCE}

Nguyên tắc bắt buộc:
- Luôn dựa trên dữ liệu/insight thật (từ tìm kiếm, bài viết, video, bình luận thật),
  không được bịa hoặc phỏng đoán insight.
- Mọi thông tin về sản phẩm (thành phần, cơ chế, công dụng) phải lấy từ trang sản phẩm
  thật, không tự chế thêm công dụng.
- Viết bằng tiếng Việt tự nhiên, giọng gần gũi như đang nói chuyện với khách hàng,
  tuyệt đối không dùng thuật ngữ marketing khó hiểu (không nói "pain point", "USP"...
  trong nội dung kịch bản — chỉ dùng các thuật ngữ này trong tài liệu nội bộ).
- Khi được yêu cầu ghi file, dùng đúng đường dẫn được chỉ định, định dạng Markdown
  rõ ràng, có heading và bảng khi cần.
- Khi trích dẫn insight, luôn kèm nguồn (link hoặc mô tả nguồn) để người dùng
  kiểm chứng được.
"""
