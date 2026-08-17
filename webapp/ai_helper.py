"""Gọi Claude cho 2 tính năng sinh ý tưởng nhẹ trong dashboard (Não Marketing,
Kiến tạo 1.000 video). Đây là lệnh gọi API đơn giản (1 request, không dùng tool,
không phải agent loop) — khác với agent/lib/claude_client.py vốn chạy full Claude
Agent SDK cho pipeline nghiên cứu/viết kịch bản.

Dùng model rẻ (Haiku) vì đây chỉ là gợi ý ý tưởng ngắn, không cần suy luận sâu —
tránh lặp lại tình huống tốn credit đã gặp ở pipeline chính.
"""

from __future__ import annotations

import json
import os

import anthropic

from agent.config import PRODUCT_NAME, PRODUCT_REFERENCE_FILE, TARGET_AUDIENCE

_MODEL = "claude-haiku-4-5"

# Daily Content Production — model cấu hình riêng qua env var, KHÔNG hard-code.
# Nếu env var không set thì dùng _MODEL (mặc định hiện tại của ai_helper.py).
DAILY_IDEA_MODEL = os.environ.get("DAILY_IDEA_MODEL") or _MODEL
DAILY_SCRIPT_MODEL = os.environ.get("DAILY_SCRIPT_MODEL") or _MODEL
DAILY_SCORE_MODEL = os.environ.get("DAILY_SCORE_MODEL") or _MODEL

MANDATORY_CLAIM = "Bổ sung glucosamin và bột chiết xuất sụn cá mập hỗ trợ tốt cho khớp"
MANDATORY_WARNING = "Thực phẩm này không phải là thuốc và không có tác dụng thay thế thuốc chữa bệnh."


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _call_and_extract_json(*, model: str, max_tokens: int, prompt: str):
    """Gọi Claude qua streaming — bắt buộc khi max_tokens đủ lớn để SDK ước tính
    request có thể chạy quá 10 phút (SDK chặn hẳn non-streaming trong trường hợp
    này). Gom lại thành response đầy đủ rồi parse JSON nghiêm ngặt. Nếu AI bị cắt
    giữa chừng vì chạm max_tokens, raise lỗi RÕ RÀNG ngay tại đây thay vì để lộ ra
    ngoài dưới dạng lỗi parse JSON khó hiểu (vd "Unterminated string...")."""
    with _client().messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        final_message = stream.get_final_message()

    if final_message.stop_reason == "max_tokens":
        raise RuntimeError(
            f"AI bị cắt giữa chừng vì vượt giới hạn max_tokens={max_tokens} "
            f"(model={model}) — nội dung yêu cầu quá dài so với giới hạn hiện tại. "
            f"Cần tăng max_tokens trong ai_helper.py hoặc giảm khối lượng nội dung/lần gọi."
        )
    return _extract_json_strict(final_message.content[0].text)


def generate_ideas_from_goal(goal: str, top_insights: list[str]) -> list[str]:
    """Sinh 10 ý tưởng chủ đề video từ 1 goal + danh sách insight ưu tiên."""
    insights_text = "\n".join(f"- {i}" for i in top_insights[:7]) or "(chưa có insight)"
    prompt = f"""\
Sản phẩm: {PRODUCT_NAME}. Khách hàng mục tiêu: {TARGET_AUDIENCE}.

Mục tiêu kinh doanh hiện tại: {goal or "(chưa nhập goal)"}

Insight ưu tiên đã có:
{insights_text}

Hãy đề xuất đúng 10 chủ đề video ngắn (mỗi chủ đề 1 dòng, không đánh số, không giải
thích thêm) bám sát mục tiêu và insight ở trên. Trả lời CHỈ bằng JSON: một mảng
10 chuỗi."""

    response = _client().messages.create(
        model=_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json_array(response.content[0].text)


def expand_insight_angles(insight_text: str) -> list[str]:
    """Bung 1 insight thành 10 góc nhìn/ý tưởng video khác nhau."""
    prompt = f"""\
Sản phẩm: {PRODUCT_NAME}. Khách hàng mục tiêu: {TARGET_AUDIENCE}.

Insight: {insight_text}

Hãy bung insight này thành đúng 10 góc nhìn/ý tưởng video khác nhau (mỗi góc 1
dòng ngắn gọn, không đánh số, không trùng nhau, không giải thích thêm). Trả lời
CHỈ bằng JSON: một mảng 10 chuỗi."""

    response = _client().messages.create(
        model=_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json_array(response.content[0].text)


# ---------------------------------------------------------------------------
# Daily Content Production — 3 bước AI (Ý tưởng / Script / Chấm điểm)
# ---------------------------------------------------------------------------


def generate_daily_ideas(
    pillar_title: str, topic_title: str, insight_refs: list[str]
) -> list[dict]:
    """Sinh 10 ý tưởng video (chưa phải script đầy đủ) cho 1 topic đã chọn."""
    insights_text = "\n".join(f"- {i}" for i in insight_refs) or "(chưa chọn insight cụ thể)"
    prompt = f"""\
Sản phẩm: {PRODUCT_NAME}. Khách hàng mục tiêu: {TARGET_AUDIENCE}.

Pillar: {pillar_title}
Topic: {topic_title}

Insight khách hàng thật liên quan (đã chọn tay, không được suy diễn thêm insight khác):
{insights_text}

Hãy tạo đúng 10 Ý TƯỞNG VIDEO khác nhau cho topic này (KHÔNG viết script dài).
Mỗi ý tưởng là 1 object JSON với đúng các field:
- "name": tên ý tưởng ngắn gọn
- "insight_used": insight nào trong danh sách trên được dùng
- "problem": nỗi đau/vấn đề cụ thể
- "angle": góc tiếp cận
- "hook": câu hook 1 dòng
- "big_idea": ý tưởng lớn/thông điệp chính
- "why": vì sao góc này đáng thử
- "cta": gợi ý CTA

Ràng buộc bắt buộc: chỉ dùng insight có trong danh sách trên, không bịa thêm nỗi đau/insight khách hàng không có nguồn.

Trả lời CHỈ bằng JSON: một mảng đúng 10 object theo cấu trúc trên, không có text nào khác."""

    return _call_and_extract_json(model=DAILY_IDEA_MODEL, max_tokens=4096, prompt=prompt)


def _read_product_reference() -> str:
    if not PRODUCT_REFERENCE_FILE.exists():
        raise RuntimeError(
            f"Không tìm thấy {PRODUCT_REFERENCE_FILE} — cần file này để AI viết đúng "
            f"thành phần/cơ chế thật, không tự bịa. Kiểm tra lại đường dẫn."
        )
    text = PRODUCT_REFERENCE_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"{PRODUCT_REFERENCE_FILE} rỗng — không có dữ liệu để AI dùng.")
    return text


def generate_daily_scripts(topic_title: str, ideas: list[dict]) -> list[dict]:
    """Viết lời thoại vlog hoàn chỉnh cho từng ý tưởng — KHÔNG phải kịch bản quảng
    cáo có shot list. Người dùng chỉ cần đọc lời thoại và bật camera quay. Cơ chế/
    thành phần nhắc tới PHẢI lấy đúng từ product_reference.md, không suy diễn."""
    ideas_text = json.dumps(ideas, ensure_ascii=False, indent=2)
    product_reference = _read_product_reference()
    prompt = f"""\
Sản phẩm: {PRODUCT_NAME}. Khách hàng mục tiêu: {TARGET_AUDIENCE}.
Topic: {topic_title}

Tài liệu tham chiếu sản phẩm (NGUỒN DUY NHẤT được phép dùng cho thành phần/cơ chế —
không được lấy thông tin thành phần/cơ chế từ đâu khác, kể cả kiến thức chung):
---
{product_reference}
---

10 ý tưởng đã chọn (viết đúng theo thứ tự, 1 lời thoại/1 ý tưởng, giữ nguyên "idea_idx"):
{ideas_text}

Với MỖI ý tưởng, viết 1 ĐOẠN LỜI THOẠI HOÀN CHỈNH để 1 người tự quay vlog trước
camera — KHÔNG PHẢI kịch bản quảng cáo có shot list. Nội dung phải giúp người xem
hiểu được: khách hàng đang gặp vấn đề gì → vấn đề đó liên quan cơ chế nào → (các)
thành phần liên quan có vai trò gì → vì sao thành phần đó liên quan tới vấn đề đang
nói → sản phẩm hướng tới hỗ trợ mục tiêu gì.

Cách dựng nội dung (đây là DÀN Ý TƯ DUY nội bộ — bài nói cuối cùng phải là 1 đoạn
văn liền mạch tự nhiên, KHÔNG được chia thành từng đoạn có tiêu đề như dàn ý này):
1. Hook — nêu đúng tình trạng/nỗi đau khách hàng, tự nhiên, không sáo rỗng.
2. Giải thích ngắn gọn vì sao tình trạng này đáng quan tâm.
3. Giải thích cơ chế liên quan — CHỈ dùng đúng 1 trong 5 cơ chế ở mục 4 tài liệu trên.
4. Với TỪNG thành phần được nhắc tới: nêu tên → vai trò/chức năng → vì sao vai trò
   đó liên quan tới vấn đề đang nói. Nếu nhắc từ 2 thành phần trở lên, giải thích
   thêm vì sao chúng bổ trợ nhau cho mục tiêu hỗ trợ.
5. Giới thiệu sản phẩm tự nhiên.
6. CTA tìm hiểu/tư vấn thêm, nếu phù hợp.

RÀNG BUỘC BẮT BUỘC VỀ THÀNH PHẦN/CƠ CHẾ (quan trọng nhất):
- Tài liệu tham chiếu ở trên chỉ mô tả VAI TRÒ/CƠ CHẾ CỤ THỂ cho 3 thành phần:
  Glucosamine (cua tuyết), Bột chiết xuất sụn cá mập (bằng sáng chế, hấp thụ canxi),
  Collagen (tuýp 2, phân tử nhỏ, hấp thụ nhanh). CHỈ được giải thích sâu vai trò/cơ
  chế cho thành phần nào NẰM TRONG 3 thành phần này.
- Các thành phần khác trong bảng mục 3 (Calcium vỏ sò, bột nano vi khuẩn acid
  lactic, MSM, CPP, cây móng mèo, BCAA, Vitamin D3, chiết xuất thịt gà, Elastin,
  Hyaluronic acid...) CHỈ có hàm lượng, KHÔNG có mô tả cơ chế trong tài liệu —
  TUYỆT ĐỐI KHÔNG được tự suy diễn vai trò/cơ chế cho các thành phần này. Nếu
  không phù hợp để nhắc tới, đơn giản là BỎ QUA, không cần nhồi vào cho đủ.
- KHÔNG bắt buộc phải nhắc đủ 2 thành phần. Chỉ chọn (các) thành phần thực sự phù
  hợp với topic/insight đang viết VÀ có dữ liệu vai trò/cơ chế thật trong tài liệu.
  Nếu chỉ 1 thành phần phù hợp, chỉ giải thích đúng 1 thành phần đó — không cố
  nhồi thêm thành phần thứ 2 cho đủ.
- Nếu không có thành phần nào trong 3 thành phần trên thực sự phù hợp với topic,
  có thể nói ở mức khái quát theo đúng câu công dụng đã duyệt, không ép nhắc thành phần.
- TUYỆT ĐỐI KHÔNG được tự thêm BẤT KỲ câu giải thích sinh lý học/cơ chế nào —
  kể cả câu giải thích "vì sao triệu chứng xảy ra", "vì sao buổi sáng/ban đêm khác
  nhau", hay bất kỳ mô tả nào nghe có vẻ hợp lý theo kiến thức phổ thông — NẾU câu
  đó không xuất hiện trong đúng 5 cơ chế ở mục 4 hoặc mô tả 3 thành phần ở trên.
  Ví dụ CẤM tự bịa (không có trong tài liệu): "đệm sụn không còn êm", "dịch khớp
  không lưu thông khi ngủ", "ban đêm không cử động nên khớp cứng lại", hoặc bất kỳ
  cách giải thích sinh lý học nào khác không trích được nguyên do từ tài liệu trên.
  Nếu không tìm được cơ chế nào trong tài liệu giải thích đúng lý do triệu chứng
  xảy ra, KHÔNG giải thích lý do đó — chỉ nêu triệu chứng (đúng insight đã cho) rồi
  chuyển thẳng sang cơ chế/thành phần sản phẩm có trong tài liệu.

RÀNG BUỘC BẮT BUỘC VỀ NGÔN TỪ:
- Câu công dụng CHỈ được nói đúng: "{MANDATORY_CLAIM}".
- TUYỆT ĐỐI KHÔNG dùng: "chữa", "điều trị", "đánh tan bệnh", "khỏi hoàn toàn",
  "phục hồi chắc chắn", "thay thế thuốc", "cam kết hết đau", tỷ lệ % hiệu quả cụ
  thể, thời gian khỏi bệnh cụ thể, hoặc bất kỳ tác động sinh học nào ngoài tài liệu.
- TUYỆT ĐỐI KHÔNG dùng các câu khẳng định chắc chắn tình trạng SẼ cải thiện —
  ví dụ cấm: "sẽ giảm dần", "sẽ đỡ hơn", "sẽ hết", "sẽ khỏe lại", "chắc chắn cải
  thiện". Đây là dạng cam kết kết quả trá hình, không được phép dù không dùng từ
  "chữa"/"khỏi" trực tiếp.
- KHÔNG tự viết câu kiểu "đây không phải là thuốc chữa bệnh" hay bất kỳ cách diễn
  đạt nào gần giống câu cảnh báo bắt buộc — hệ thống tự thêm nguyên văn câu cảnh
  báo vào cuối, lời thoại không cần và không được tự ý paraphrase trước.
- Ưu tiên dùng: "hỗ trợ", "góp phần", "cung cấp", "bổ sung", "hỗ trợ duy trì",
  "hướng tới mục tiêu...". Nếu tài liệu không đủ chi tiết để giải thích sâu 1 thành
  phần, dùng câu an toàn kiểu "thành phần này được dùng với mục tiêu hỗ trợ..."
  thay vì bịa cơ chế.
- Không bịa thêm insight/nỗi đau khách hàng ngoài insight đã cho trong từng ý tưởng.

CHẤT LƯỢNG LỜI THOẠI:
- Tự nhiên, dễ nói, câu ngắn, giống 1 người thật đang giải thích cho khách hàng —
  KHÔNG giống bài viết AI, KHÔNG đọc như quảng cáo truyền hình.
- Độ dài BẮT BUỘC đạt khoảng 300-450 chữ (phù hợp video vlog 2-3 phút) — đây là
  mục tiêu CẦN ĐẠT, không phải gợi ý mềm. TUYỆT ĐỐI KHÔNG đạt độ dài bằng cách lặp
  lại ý đã nói dưới dạng khác. Nếu cần thêm chữ để đạt độ dài, ưu tiên: giải thích
  SÂU HƠN cơ chế/thành phần (vẫn trong phạm vi tài liệu) và liên hệ RÕ HƠN, cụ thể
  hơn tới vấn đề khách hàng đang gặp trong insight — không thêm câu thừa/lặp ý.
- KHÔNG cần viết câu cảnh báo bắt buộc trong lời thoại — hệ thống tự thêm vào cuối.

Mỗi script là 1 object JSON với đúng các field:
- "idea_idx": trùng với idea_idx của ý tưởng tương ứng
- "loi_thoai": toàn bộ lời thoại, 1 đoạn văn liền mạch (string)
- "footage": mảng 3-5 gợi ý bối cảnh quay CỰC ĐƠN GIẢN (vd "Nói trực tiếp trước camera", "Đi bộ", "Cầm sản phẩm", "Ngồi làm việc", "Sinh hoạt đời thường") — chỉ là gợi ý cho AI dựng video sau này, KHÔNG phải yêu cầu bắt buộc người quay phải làm đúng từng shot
- "mechanism": mảng các object {{"ingredient": tên thành phần, "role": vai trò/chức năng theo đúng tài liệu, "relation_to_problem": vì sao liên quan tới vấn đề đang nói}} — 1 object cho MỖI thành phần thực sự được nhắc trong loi_thoai (có thể là mảng rỗng [] nếu không nhắc thành phần nào cụ thể). Đây là metadata để kiểm tra chất lượng, KHÔNG hiển thị cho người dùng.

Trả lời CHỈ bằng JSON: một mảng đúng {len(ideas)} object theo cấu trúc trên, không có text nào khác."""

    # Lời thoại 2-3 phút (~300-450 chữ) dài hơn ~2-2.5 lần bản 45-90s trước đó, cộng
    # thêm field "mechanism" mới — tăng max_tokens để không lặp lại lỗi cắt giữa chừng.
    return _call_and_extract_json(model=DAILY_SCRIPT_MODEL, max_tokens=24000, prompt=prompt)


_SCORE_CRITERIA = [
    "insight_strength",
    "hook_strength",
    "problem_relevance",
    "emotional_relevance",
    "clarity",
    "product_relevance",
    "differentiation",
    "facebook_ads_potential",
    "compliance",
    "curiosity_likelihood",
]


def score_daily_scripts(scripts: list[dict]) -> list[dict]:
    """Chấm điểm 10 script theo 10 tiêu chí (0-10 mỗi tiêu chí, tổng /100)."""
    scripts_text = json.dumps(scripts, ensure_ascii=False, indent=2)
    criteria_list = "\n".join(f"- {c}" for c in _SCORE_CRITERIA)
    prompt = f"""\
Sản phẩm: {PRODUCT_NAME}. Khách hàng mục tiêu: {TARGET_AUDIENCE}.

Chấm điểm {len(scripts)} script quảng cáo sau đây (mỗi script có "script_id"):
{scripts_text}

Chấm theo đúng 10 tiêu chí sau, mỗi tiêu chí thang điểm 0-10:
{criteria_list}

Với MỖI script, trả về 1 object JSON với đúng các field:
- "script_id": trùng script_id của script được chấm
- "criteria": object gồm đúng 10 key ở trên, mỗi key là số nguyên 0-10
- "total": tổng 10 tiêu chí (0-100)
- "reason": lý do chấm điểm, ngắn gọn 1-2 câu

Trả lời CHỈ bằng JSON: một mảng đúng {len(scripts)} object theo cấu trúc trên, không có text nào khác."""

    return _call_and_extract_json(model=DAILY_SCORE_MODEL, max_tokens=4096, prompt=prompt)


def _extract_json_strict(text: str):
    """Parse JSON nghiêm ngặt — KHÔNG fallback bịa dữ liệu nếu AI trả sai định dạng.
    Lỗi được raise lên để route trả về error rõ ràng cho UI (không giả vờ có data)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    return json.loads(text)


def _extract_json_array(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(x) for x in data]
    except json.JSONDecodeError:
        pass
    # fallback: mỗi dòng không rỗng là 1 ý tưởng
    return [line.strip("- ").strip() for line in text.splitlines() if line.strip()][:10]
