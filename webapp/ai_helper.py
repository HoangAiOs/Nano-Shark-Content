"""Gọi Claude cho 2 tính năng sinh ý tưởng nhẹ trong dashboard (Não Marketing,
Kiến tạo 1.000 video). Đây là lệnh gọi API đơn giản (1 request, không dùng tool,
không phải agent loop) — khác với agent/lib/claude_client.py vốn chạy full Claude
Agent SDK cho pipeline nghiên cứu/viết kịch bản.

Dùng model rẻ (Haiku) vì đây chỉ là gợi ý ý tưởng ngắn, không cần suy luận sâu —
tránh lặp lại tình huống tốn credit đã gặp ở pipeline chính.
"""

from __future__ import annotations

import json

import anthropic

from agent.config import PRODUCT_NAME, TARGET_AUDIENCE

_MODEL = "claude-haiku-4-5"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


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
