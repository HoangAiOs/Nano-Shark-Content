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

from agent.config import PRODUCT_NAME, TARGET_AUDIENCE

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
    """Gọi Claude 1 lần, parse JSON nghiêm ngặt. Nếu AI bị cắt giữa chừng vì
    chạm max_tokens, raise lỗi RÕ RÀNG ngay tại đây thay vì để lộ ra ngoài
    dưới dạng lỗi parse JSON khó hiểu (vd "Unterminated string...")."""
    response = _client().messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            f"AI bị cắt giữa chừng vì vượt giới hạn max_tokens={max_tokens} "
            f"(model={model}) — nội dung yêu cầu quá dài so với giới hạn hiện tại. "
            f"Cần tăng max_tokens trong ai_helper.py hoặc giảm khối lượng nội dung/lần gọi."
        )
    return _extract_json_strict(response.content[0].text)


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


def generate_daily_scripts(topic_title: str, ideas: list[dict]) -> list[dict]:
    """Viết 10 script video 2-6 phút, mỗi script dựa trên đúng 1 ý tưởng đầu vào."""
    ideas_text = json.dumps(ideas, ensure_ascii=False, indent=2)
    prompt = f"""\
Sản phẩm: {PRODUCT_NAME}. Khách hàng mục tiêu: {TARGET_AUDIENCE}.
Topic: {topic_title}

10 ý tưởng đã chọn (viết script đúng theo thứ tự, 1 script/1 ý tưởng, giữ nguyên "idea_idx"):
{ideas_text}

Với MỖI ý tưởng, viết 1 script video quảng cáo Facebook dài 2-6 phút, tiếng Việt tự
nhiên gần gũi (không dùng thuật ngữ marketing trong nội dung). Mỗi script là 1 object
JSON với đúng các field:
- "idea_idx": trùng với idea_idx của ý tưởng tương ứng
- "hook": hook 3-10 giây đầu
- "problem": vấn đề
- "agitate": đào sâu vấn đề
- "insight": insight dùng trong script (phải khớp insight_used của ý tưởng)
- "explanation": giải thích cơ chế
- "solution": giải pháp — CHỈ được mô tả công dụng đúng câu: "{MANDATORY_CLAIM}", không cam kết "chữa khỏi" hay vượt quá công dụng này
- "product_intro": giới thiệu sản phẩm
- "cta": kêu gọi hành động
- "camera_notes": gợi ý cảnh quay
- "text_overlay": chữ chạy/overlay nếu cần (có thể để chuỗi rỗng nếu không cần)

Ràng buộc bắt buộc:
- Không tự tạo claim y khoa hoặc claim sản phẩm ngoài câu công dụng đã duyệt ở trên.
- Không bịa thêm insight/nỗi đau khách hàng ngoài insight đã cho trong từng ý tưởng.
- Câu cảnh báo bắt buộc "{MANDATORY_WARNING}" sẽ được hệ thống tự thêm vào cuối, KHÔNG cần viết lại trong "cta" hay "text_overlay".

Trả lời CHỈ bằng JSON: một mảng đúng {len(ideas)} object theo cấu trúc trên, không có text nào khác."""

    # 10 script đầy đủ (~10 field/script) cần nhiều token hơn nhiều so với bước ý
    # tưởng — 8192 từng bị cắt giữa chừng (lỗi "Unterminated string"), tăng lên 16384.
    return _call_and_extract_json(model=DAILY_SCRIPT_MODEL, max_tokens=16384, prompt=prompt)


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
