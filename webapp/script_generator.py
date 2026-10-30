"""Sinh kịch bản hoàn chỉnh từ 1 insight Inbox bằng Claude API — NGOẠI LỆ có chủ đích
so với nguyên tắc "dashboard không gọi AI": chỉ riêng tính năng này, gọi từ server.

- Key lấy từ biến môi trường ANTHROPIC_API_KEY (Render → Environment). Không hardcode.
- Chỉ dùng knowledge base data/knowledge/nano_sun_ca_map.md + tin nhắn khách + giọng văn mẫu.
- Sau khi sinh: quét từ cấm + con số lạ (check_script). Vi phạm → tự sinh lại 1 lần kèm
  danh sách lỗi; vẫn còn thì lưu kèm cờ đỏ để người duyệt sửa tay.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata

import anthropic

from webapp.persistent_storage import DATA_DIR

MODEL = "claude-opus-5-5"
KB_PATH = DATA_DIR / "knowledge" / "nano_sun_ca_map.md"
DISCLAIMER = "Thực phẩm này không phải là thuốc và không có tác dụng thay thế thuốc chữa bệnh."
APPROVED_CLAIM = "Bổ sung glucosamin và bột chiết xuất sụn cá mập hỗ trợ tốt cho khớp"
MISSING_RE = re.compile(r"\[THIẾU THÔNG TIN:[^\]]*\]")

NO_KEY_MESSAGE = (
    "Chưa có ANTHROPIC_API_KEY trên server nên chưa sinh được kịch bản. Cách thêm: vào "
    "dashboard.render.com → service nano-shark-content-os → Environment → Add Environment "
    "Variable: Key = ANTHROPIC_API_KEY, Value = key lấy ở platform.claude.com → API Keys → "
    "Save Changes (Render tự deploy lại, ~2–3 phút) rồi bấm lại nút."
)

# Từ/cụm cấm trong kịch bản (so khớp không phân biệt hoa thường, bỏ qua câu cảnh báo bắt buộc).
FORBIDDEN = [
    "chữa khỏi", "chữa trị", "chữa bệnh", "trị bệnh", "trị dứt", "đặc trị", "điều trị", "dứt điểm",
    "hết hẳn", "khỏi hẳn", "khỏi bệnh", "hết bệnh", "khỏi đau", "hết đau", "hết tê", "hết chèn ép",
    "hết thoát vị", "đảm bảo", "cam kết", "thay thế thuốc", "thay thuốc", "không cần mổ", "khỏi mổ",
    "tránh mổ", "thay cho mổ", "thay mổ", "thần dược", "100%",
]
# Cụm hợp lệ có chứa từ cấm — gỡ ra trước khi quét (khuyến cáo trên nhãn).
FORBIDDEN_EXEMPT = ["đang điều trị bệnh"]
# Vượt ngoài câu công dụng đã duyệt nhưng có trong vai trò thành phần của knowledge base →
# không chặn, chỉ đánh dấu vàng để người duyệt cân nhắc trước khi quay quảng cáo.
CAUTION = ["tái tạo", "sửa chữa sụn", "giảm đau", "kháng viêm", "chống viêm", "phục hồi"]

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "ten_kich_ban": {"type": "string", "description": "Tên ngắn cho kịch bản (dưới 15 chữ)"},
        "insight_chinh": {"type": "string"},
        "hook": {"type": "string"},
        "van_de": {"type": "string"},
        "giai_phap": {"type": "string"},
        "cta": {"type": "string"},
        "thieu_thong_tin": {
            "type": "array", "items": {"type": "string"},
            "description": "Mỗi mục thiếu dữ liệu đã đánh dấu [THIẾU THÔNG TIN: ...] trong kịch bản",
        },
    },
    "required": ["ten_kich_ban", "insight_chinh", "hook", "van_de", "giai_phap", "cta", "thieu_thong_tin"],
    "additionalProperties": False,
}

HARD_RULES = f"""QUY TẮC CỨNG (vi phạm bất kỳ điều nào là kịch bản bị loại):
1. Chỉ nói đúng công dụng đã được duyệt: "{APPROVED_CLAIM}". Mỗi thành phần chỉ được mô tả theo vai trò ghi trong KNOWLEDGE BASE.
2. Tuyệt đối không nói sản phẩm chữa/điều trị/làm hết/khỏi bệnh; không hứa kết quả; không nói thay thế thuốc, thay mổ hay thay y tế; không nói giúp hết tê bì, hết chèn ép thần kinh, hết thoát vị.
3. Khách thoát vị đĩa đệm hoặc đau thần kinh toạ: chỉ nói sản phẩm hỗ trợ khớp/sụn, và khuyên cô chú/anh chị tiếp tục theo dõi với bác sĩ.
4. Không bịa số liệu, bằng chứng, tên khách khác, hay kết quả mà khách chưa từng nói. Không trích phản hồi của khách hàng nào khác.
5. Câu hỏi khách hỏi mà KNOWLEDGE BASE không có dữ liệu (ví dụ "có tăng cân không", tác dụng phụ, tương tác thuốc, liệu trình theo bệnh lý, chính sách giao hàng/thanh toán chưa ghi): KHÔNG trả lời đoán. Chèn đúng dấu [THIẾU THÔNG TIN: <mô tả ngắn>] vào chỗ đó trong kịch bản, và liệt kê mỗi mục vào trường thieu_thong_tin.
6. Không dùng các từ: {", ".join(FORBIDDEN)}. Muốn khuyên đi khám thì viết "tiếp tục theo dõi với bác sĩ". Chỉ nhắc "người đang điều trị bệnh nên tham khảo ý kiến trước khi dùng" khi cần, đúng như khuyến cáo trên nhãn.
7. Chỉ dùng con số có trong KNOWLEDGE BASE hoặc trong tin nhắn/hồ sơ của khách.
8. Không tự viết câu cảnh báo bắt buộc — hệ thống tự gắn câu "{DISCLAIMER}" vào cuối kịch bản."""

TASK = """VIỆC CẦN LÀM: viết 1 kịch bản video ngắn để BS Sơn quay, đọc lên quay được ngay, dựa trên đúng một khách đã đồng ý cho dùng tên và câu chuyện.
- ten_kich_ban: tên ngắn gọn cho kịch bản.
- insight_chinh: 1 câu nêu nỗi đau/băn khoăn thật của khách này.
- hook: 2–3 câu mở đầu, dùng chính hoàn cảnh khách: tên, tuổi, tình trạng, câu hỏi họ đã hỏi.
- van_de: kể lại hành trình của khách bằng chính chi tiết trong tin nhắn: đã chẩn đoán gì, đã thử cách gì, còn lo gì. Không thêm chi tiết khách không nói.
- giai_phap: đi từng thành phần của sản phẩm; mỗi thành phần 1–2 câu nói rõ NÓ HỖ TRỢ GÌ cho đúng vấn đề của khách này (theo vai trò trong KNOWLEDGE BASE). Chỉ nêu thành phần liên quan. Trả lời thẳng các câu hỏi khách đã hỏi nếu KNOWLEDGE BASE có dữ liệu (ví dụ nơi sản xuất); không có thì dùng [THIẾU THÔNG TIN: ...]. Trình bày thành gạch đầu dòng cho dễ nhấn nhá.
- cta: kêu gọi nhắn tin/để lại thông tin. Chỉ nhắc "nhận hàng rồi mới thanh toán" nếu KNOWLEDGE BASE có ghi chính sách đó; nếu không có thì chèn [THIẾU THÔNG TIN: chính sách nhận hàng rồi thanh toán].
GIỌNG VĂN: giọng BS Sơn — gần gũi, xưng "con" hoặc "Sơn", gọi người xem là "cô chú anh chị", câu ngắn, kể chuyện, nói như đang trò chuyện thật; học giọng từ các MẪU bên dưới nhưng KHÔNG lấy tên, câu chuyện, con số hay lời hứa nào trong mẫu."""


class GeneratorError(RuntimeError):
    pass


class MissingKeyError(GeneratorError):
    pass


def _voice_samples() -> str:
    """Vài kịch bản mẫu để bắt giọng: 2 bài trong Thư viện + 2 video BS Sơn tự nói (Kịch bản gốc, bản đã hiệu đính)."""
    parts = []
    for sid in ("03", "28"):
        p = DATA_DIR / "scripts" / f"script_{sid}.md"
        if p.exists():
            parts.append(f"--- MẪU Thư viện kịch bản #{sid} ---\n{p.read_text(encoding='utf-8')}")
    orig = DATA_DIR / "original_scripts_segments.json"
    if orig.exists():
        rows = [r for r in json.loads(orig.read_text(encoding="utf-8"))
                if r.get("title", "").upper().startswith("BS") and r.get("clean")]
        for r in rows[:2]:
            c = r["clean"]
            text = "\n".join(f"[{k}] {c[k]}" for k in ("hook", "van_de", "giai_phap", "cta") if c.get(k))
            text = re.sub(r"\[\?(.*?)\?\]", r"\1", text)
            parts.append(f"--- MẪU lời BS Sơn nói trong video thật ({r['title']}) ---\n{text}")
    return "\n\n".join(parts)


def _system_prompt() -> str:
    if not KB_PATH.exists():
        raise GeneratorError(f"Không tìm thấy knowledge base {KB_PATH}")
    kb = KB_PATH.read_text(encoding="utf-8")
    return (f"Bạn viết kịch bản video cho thực phẩm bảo vệ sức khỏe Nano Sụn Cá Mập Nhật Bản Premium "
            f"của DiLiM, do BS Sơn đứng quay.\n\n{HARD_RULES}\n\n{TASK}\n\n"
            f"<knowledge_base>\n{kb}\n</knowledge_base>\n\n<mau_giong_van>\n{_voice_samples()}\n</mau_giong_van>")


def _customer_block(rec: dict) -> str:
    return (f"<khach_hang>\nTên: {rec['ten_khach']}\nTuổi: {rec.get('tuoi') or '(không rõ)'}\n"
            f"Tỉnh/thành: {rec.get('tinh_thanh') or '(không rõ)'}\nNhóm insight: {rec.get('nhom_insight') or '(chưa phân nhóm)'}\n"
            f"Tin nhắn gốc (nguyên văn):\n{rec['tin_nhan_goc']}\n</khach_hang>")


def to_markdown(script_no: str, rec: dict, data: dict) -> str:
    missing = data.get("thieu_thong_tin") or []
    head = ""
    if missing:
        head = "> ⚠️ THIẾU THÔNG TIN — bổ sung vào data/knowledge/nano_sun_ca_map.md rồi bấm \"Sinh lại\":\n" + \
               "\n".join(f"> - {m}" for m in missing) + "\n\n"
    return (f"# Kịch bản {script_no} — \"{data['ten_kich_ban'].strip()}\"\n"
            f"**Nguồn:** Insight từ Inbox {rec['id']} — {rec['ten_khach']} (khách đã đồng ý: "
            f"{rec.get('ghi_chu_xac_nhan') or 'chưa ghi cách xác nhận'})\n"
            f"**Insight chính:** {data['insight_chinh'].strip()}\n\n{head}"
            f"## Hook\n{data['hook'].strip()}\n\n## Vấn đề\n{data['van_de'].strip()}\n\n"
            f"## Giải pháp\n{data['giai_phap'].strip()}\n\n## CTA\n{data['cta'].strip()}\n\n"
            f"## Cảnh báo bắt buộc\n\"{DISCLAIMER}\"\n")


def _norm_num(s: str) -> str:
    return re.sub(r"[.,]", "", s)


def _numbers(text: str) -> set[str]:
    out = set()
    for m in re.findall(r"\d+(?:[.,]\d+)*", text):
        out.add(_norm_num(m))
        out.update(re.findall(r"\d+", m))
    return out


def check_script(markdown: str, rec: dict) -> dict:
    """Trả về {'vi_pham': [...], 'can_nhac': [...], 'so_la': [...], 'thieu_thong_tin': [...]}."""
    body = markdown.split("## Cảnh báo bắt buộc")[0]
    body = re.sub(r"^\*\*Nguồn:\*\*.*$", "", body, flags=re.M)
    body = MISSING_RE.sub(" ", body)
    low = unicodedata.normalize("NFC", body).lower()
    for ex in FORBIDDEN_EXEMPT:
        low = low.replace(ex, " ")

    def found(terms):
        return [t for t in terms if re.search(r"(?<![\wÀ-ỹ])" + re.escape(t) + r"(?![\wÀ-ỹ])", low)]

    allowed = _numbers(KB_PATH.read_text(encoding="utf-8")) | _numbers(
        " ".join(str(rec.get(k, "")) for k in ("ten_khach", "tuoi", "tinh_thanh", "tin_nhan_goc", "nhom_insight")))
    title_line = markdown.split("\n", 1)[0]  # "# Kịch bản 35" — số thứ tự của chính kịch bản
    allowed |= _numbers(title_line)
    so_la = sorted({m for m in re.findall(r"\d+(?:[.,]\d+)*", body) if _norm_num(m) not in allowed},
                   key=lambda x: (len(x), x))
    return {"vi_pham": found(FORBIDDEN), "can_nhac": found(CAUTION), "so_la": so_la,
            "thieu_thong_tin": sorted(set(MISSING_RE.findall(markdown)))}


async def _call(client: anthropic.AsyncAnthropic, system: str, user: str) -> dict:
    try:
        resp = await client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA}},
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError as e:
        raise GeneratorError("ANTHROPIC_API_KEY trên server bị sai hoặc đã thu hồi — kiểm tra lại trong Render → Environment.") from e
    except anthropic.PermissionDeniedError as e:
        raise GeneratorError(f"API key không có quyền gọi model {MODEL}: {e.message}") from e
    except anthropic.RateLimitError as e:
        raise GeneratorError("Đang bị giới hạn tốc độ gọi Claude API — đợi 1 phút rồi bấm lại.") from e
    except anthropic.BadRequestError as e:
        if "credit" in e.message.lower():
            raise GeneratorError("Tài khoản Claude API hết credit — nạp thêm ở platform.claude.com → Billing.") from e
        raise GeneratorError(f"Claude API từ chối yêu cầu: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise GeneratorError(f"Claude API lỗi {e.status_code} — thử lại sau ít phút.") from e
    except anthropic.APIConnectionError as e:
        raise GeneratorError("Server không kết nối được Claude API — thử lại sau.") from e
    if resp.stop_reason == "refusal":
        raise GeneratorError("Claude từ chối viết kịch bản này (bộ lọc an toàn) — thử sửa nhóm insight hoặc bấm lại.")
    if resp.stop_reason == "max_tokens":
        raise GeneratorError("Kịch bản sinh ra bị cắt ngang (quá dài) — bấm Sinh lại.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise GeneratorError("Kết quả Claude trả về không đúng định dạng — bấm Sinh lại.") from e


async def generate(rec: dict, script_no: str) -> dict:
    """Sinh + kiểm tra (+ tự sinh lại 1 lần nếu vi phạm). Trả về {'markdown', 'check', 'attempts'}."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise MissingKeyError(NO_KEY_MESSAGE)
    client = anthropic.AsyncAnthropic(timeout=600.0)
    system = _system_prompt()
    user = _customer_block(rec)
    data = await _call(client, system, user)
    md = to_markdown(script_no, rec, data)
    check = check_script(md, rec)
    attempts = 1
    if check["vi_pham"] or check["so_la"]:
        problems = []
        if check["vi_pham"]:
            problems.append("dùng từ cấm: " + ", ".join(f'"{w}"' for w in check["vi_pham"]))
        if check["so_la"]:
            problems.append("có con số không nằm trong KNOWLEDGE BASE hay tin nhắn khách: " + ", ".join(check["so_la"]))
        fix = (f"{user}\n\n<ban_nhap_truoc>\n{md}\n</ban_nhap_truoc>\n\nBản nháp trước vi phạm quy tắc cứng — "
               f"{'; '.join(problems)}. Viết lại toàn bộ kịch bản, giữ nội dung đúng, bỏ hẳn các vi phạm trên.")
        data = await _call(client, system, fix)
        md = to_markdown(script_no, rec, data)
        check = check_script(md, rec)
        attempts = 2
    return {"markdown": md, "check": check, "attempts": attempts, "model": MODEL,
            "ten_kich_ban": data["ten_kich_ban"].strip(), "insight_chinh": data["insight_chinh"].strip(),
            "hook": data["hook"].strip()}
