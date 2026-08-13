"""Đọc dữ liệu thật từ các file trong data/ và parse thành JSON cho dashboard.

Không có "AI" chạy ngầm ở đây — toàn bộ dữ liệu hiển thị là parse trực tiếp từ
các file .md/.json do pipeline agent (agent/cli.py) đã tạo ra thật. Phần phân
loại "pillar" ở Cân đối danh mục là gán tay dựa trên nội dung đã đọc kỹ từng
kịch bản (xem data/content_map.json), không phải suy luận tự động.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from webapp.persistent_storage import PERSISTENT_DIR

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"
# Data ĐỘNG — trỏ vào persistent disk trên Render (PERSISTENT_DATA_DIR env var),
# local dev không set thì PERSISTENT_DIR = DATA_DIR như cũ. Xem persistent_storage.py.
STATE_FILE = PERSISTENT_DIR / "web_state.json"
UPLOADS_DIR = PERSISTENT_DIR / "video_uploads"

PUBLISH_PLATFORMS = ["Facebook", "YouTube", "TikTok", "Zalo OA", "Blog", "Email"]

# Ngưỡng cảnh báo cho Ads Autopilot (báo cáo — KHÔNG tự động tắt chiến dịch thật).
CPL_WARN_THRESHOLD_VND = 150_000

# --- Hệ thống Content Pillar mới (10 pillar, khớp với data/content_pillars.md) ---
# Mapping Pillar/Topic → Script đọc từ content_map.json (source of truth) — data
# ĐỘNG (bị select_script() ghi thêm), nên cũng nằm trên persistent disk, KHÔNG
# hard-code trong .py. Xem CONTENT_MAP_FILE bên dưới.
CONTENT_MAP_FILE = PERSISTENT_DIR / "content_map.json"


def _load_content_map() -> dict:
    raw = _read(CONTENT_MAP_FILE)
    if not raw:
        return {"script_pillar": {}, "topic_script": {}}
    return json.loads(raw)


def script_pillar_map() -> dict[str, int]:
    """script_id -> số pillar (1-10)."""
    return _load_content_map().get("script_pillar", {})


def topic_script_map() -> dict[str, str]:
    """'{pillar_num}_{topic_num}' -> script_id."""
    return _load_content_map().get("topic_script", {})


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_md_tables(text: str) -> list[list[dict]]:
    """Tìm tất cả bảng markdown trong text, trả về list các bảng (mỗi bảng là list dict)."""
    tables: list[list[dict]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            headers = [h.strip() for h in line.strip("|").split("|")]
            j = i + 2
            rows: list[dict] = []
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip("|").split("|")]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
                j += 1
            tables.append(rows)
            i = j
        else:
            i += 1
    return tables


def read_overview() -> dict:
    raw = _read(DATA_DIR / "raw_research.json")
    research_count = len(json.loads(raw)) if raw else 0

    voc_tables = parse_md_tables(_read(DATA_DIR / "voice_of_customer.md"))
    voc_count = sum(len(t) for t in voc_tables)

    insights_tables = parse_md_tables(_read(DATA_DIR / "priority_insights.md"))
    insights_count = len(insights_tables[0]) if insights_tables else 0

    scripts_count = len(list(SCRIPTS_DIR.glob("script_*.md"))) if SCRIPTS_DIR.exists() else 0

    ad_perf_path = DATA_DIR / "ad_performance.csv"
    ads_synced = ad_perf_path.exists() and ad_perf_path.stat().st_size > 0

    bank_tables = parse_md_tables(_read(DATA_DIR / "insight_bank.md"))
    bank_count = sum(len(t) for t in bank_tables)

    pillars_count = len(re.findall(r"^## Pillar \d+:", _read(DATA_DIR / "content_pillars.md"), re.MULTILINE))
    pillar_tables = parse_md_tables(_read(DATA_DIR / "content_pillars.md"))
    topics_count = sum(len(t) for t in pillar_tables)

    return {
        "research_records": research_count,
        "voice_of_customer_insights": voc_count,
        "priority_insights": insights_count,
        "scripts": scripts_count,
        "ads_synced": ads_synced,
        "insight_bank": bank_count,
        "content_pillars": pillars_count,
        "content_topics": topics_count,
    }


def read_voice_of_customer() -> list[dict]:
    return _read_grouped_sections(DATA_DIR / "voice_of_customer.md")


def _read_grouped_sections(path: Path) -> list[dict]:
    text = _read(path)
    if not text:
        return []
    sections = re.split(r"^## (\d+\.\s*.+)$", text, flags=re.MULTILINE)
    out: list[dict] = []
    # sections[0] is preamble; then alternating title, body
    for idx in range(1, len(sections), 2):
        title = sections[idx].strip()
        body = sections[idx + 1] if idx + 1 < len(sections) else ""
        tables = parse_md_tables(body)
        rows = tables[0] if tables else []
        out.append({"title": title, "rows": rows})
    return out


def read_insight_bank() -> list[dict]:
    """180 insight (câu hỏi/nỗi đau/nỗi sợ/mong muốn/hiểu lầm/lý do chưa hành động)."""
    return _read_grouped_sections(DATA_DIR / "insight_bank.md")


def read_content_pillars() -> list[dict]:
    """10 pillar, mỗi pillar có mục đích + insight nguồn + bảng 10 chủ đề."""
    text = _read(DATA_DIR / "content_pillars.md")
    if not text:
        return []
    sections = re.split(r"^## (Pillar (\d+): .+)$", text, flags=re.MULTILINE)
    out: list[dict] = []
    for idx in range(1, len(sections), 3):
        title = sections[idx].strip()
        num = int(sections[idx + 1])
        body = sections[idx + 2] if idx + 2 < len(sections) else ""
        purpose = re.search(r"Mục đích:\s*(.+)", body)
        source = re.search(r"Insight nguồn:\s*(.+)", body)
        has_video = re.search(r"Đã có video mẫu:\s*(.+)", body)
        tables = parse_md_tables(body)
        topics = tables[0] if tables else []
        out.append(
            {
                "num": num,
                "title": title,
                "purpose": purpose.group(1).strip() if purpose else "",
                "source": source.group(1).strip() if source else "",
                "has_video": has_video.group(1).strip() if has_video else "",
                "topics": topics,
            }
        )
    return out


def read_content_wave1() -> list[dict]:
    """Chủ đề đã triển khai đầy đủ 60 mục (Hook/Góc nhìn/Hiểu lầm/Sai lầm/Ví dụ/Câu hỏi mở)."""
    text = _read(DATA_DIR / "content_wave1.md")
    if not text:
        return []
    sections = re.split(r"^## (\[.+?\] .+)$", text, flags=re.MULTILINE)
    out: list[dict] = []
    for idx in range(1, len(sections), 2):
        title = sections[idx].strip()
        body = sections[idx + 1] if idx + 1 < len(sections) else ""
        tables = parse_md_tables(body)
        rows = tables[0] if tables else []
        out.append({"title": title, "rows": rows})
    return out


def read_research_summary() -> dict:
    raw = _read(DATA_DIR / "raw_research.json")
    if not raw:
        return {"total": 0, "by_source_type": {}, "by_platform": {}}
    records = json.loads(raw)
    by_type: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    for r in records:
        t = r.get("source_type", "khác")
        p = r.get("platform", "khác")
        by_type[t] = by_type.get(t, 0) + 1
        by_platform[p] = by_platform.get(p, 0) + 1
    return {"total": len(records), "by_source_type": by_type, "by_platform": by_platform}


def read_priority_insights() -> list[dict]:
    text = _read(DATA_DIR / "priority_insights.md")
    if not text:
        return []
    tables = parse_md_tables(text)
    summary = tables[0] if tables else []

    # Lấy phần "Lý do chọn" + trích dẫn cho từng insight từ các mục ### Insight #N
    detail_sections = re.split(r"^### Insight #(\d+):\s*(.+)$", text, flags=re.MULTILINE)
    details: dict[str, dict] = {}
    for idx in range(1, len(detail_sections), 3):
        num = detail_sections[idx].strip()
        name = detail_sections[idx + 1].strip()
        body = detail_sections[idx + 2] if idx + 2 < len(detail_sections) else ""
        reason_match = re.search(r"\*\*Lý do chọn:\*\*\s*(.+?)(?=\n-|\n\Z)", body, re.DOTALL)
        details[num] = {
            "name": name,
            "reason": reason_match.group(1).strip() if reason_match else "",
        }

    state = load_state()
    triage = state.get("insight_triage", {})

    out = []
    for row in summary:
        num = row.get("#", "").strip()
        out.append(
            {
                "num": num,
                "insight": row.get("Insight", ""),
                "freq": row.get("Tần suất", ""),
                "emotion": row.get("Cảm xúc", ""),
                "total": row.get("Tổng", "").replace("*", ""),
                "reason": details.get(num, {}).get("reason", ""),
                "status": triage.get(num, "Mới"),
            }
        )
    return out


def read_scores() -> dict:
    text = _read(DATA_DIR / "scores.md")
    if not text:
        return {"summary": [], "top5": []}
    tables = parse_md_tables(text)
    summary = tables[0] if tables else []
    for row in summary:
        row["Tổng điểm"] = row.get("Tổng điểm", "").replace("*", "")

    top5_sections = re.split(r"^### #(\d+) — (.+?) \(tổng điểm (\d+)/40\)$", text, flags=re.MULTILINE)
    top5 = []
    for idx in range(1, len(top5_sections), 4):
        script_id = top5_sections[idx].strip()
        name = top5_sections[idx + 1].strip()
        score = top5_sections[idx + 2].strip()
        body = top5_sections[idx + 3] if idx + 3 < len(top5_sections) else ""
        reason_match = re.search(r"\*\*Lý do chọn:\*\*\s*(.+?)(?=\n###|\Z)", body, re.DOTALL)
        top5.append(
            {
                "script_id": script_id,
                "name": name,
                "score": score,
                "reason": reason_match.group(1).strip() if reason_match else "",
            }
        )
    return {"summary": summary, "top5": top5}


def read_ideas_today() -> list[dict]:
    """Danh sách 10 kịch bản như 'ý tưởng video' — điểm số + trạng thái đã quay."""
    index_text = _read(SCRIPTS_DIR / "index.md")
    tables = parse_md_tables(index_text)
    idx_rows = tables[0] if tables else []

    scores_tables = parse_md_tables(_read(DATA_DIR / "scores.md"))
    score_by_id = {}
    if scores_tables:
        for row in scores_tables[0]:
            score_by_id[row.get("#", "").strip()] = row.get("Tổng điểm", "").replace("*", "")

    state = load_state()
    quay_status = state.get("quay_status", {})

    out = []
    for row in idx_rows:
        script_id = row.get("#", "").strip()
        hook = row.get("Hook (rút gọn)", "")
        out.append(
            {
                "script_id": script_id,
                "name": row.get("Tên kịch bản", ""),
                "insight": row.get("Insight chính", ""),
                "hook": hook,
                "score": score_by_id.get(script_id, ""),
                "quay_xong": quay_status.get(script_id, False),
                "pillar": pillar_title_by_num().get(script_pillar_map().get(script_id), "Chưa gán"),
            }
        )
    out.sort(key=lambda r: int(r["score"]) if r["score"].isdigit() else -1, reverse=True)
    return out


def pillar_title_by_num() -> dict[int, str]:
    return {p["num"]: p["title"] for p in read_content_pillars()}


def read_portfolio() -> list[dict]:
    """Cân đối danh mục theo 10 Pillar thật (content_pillars.md) — cho mỗi pillar:
    bao nhiêu kịch bản đã viết, và đã khai thác bao nhiêu / tổng số chủ đề."""
    ideas = read_ideas_today()
    total_scripts = len(ideas) or 1
    script_pillar = script_pillar_map()
    topic_script = topic_script_map()
    script_counts: dict[int, int] = {}
    for idea in ideas:
        pillar_num = script_pillar.get(idea["script_id"])
        if pillar_num:
            script_counts[pillar_num] = script_counts.get(pillar_num, 0) + 1

    pillars = read_content_pillars()
    out = []
    for p in pillars:
        num = p["num"]
        topic_total = len(p["topics"]) or 1
        topics_covered = sum(
            1 for t in p["topics"] if f"{num}_{str(t.get('#', '')).strip()}" in topic_script
        )
        count = script_counts.get(num, 0)
        out.append(
            {
                "pillar": p["title"],
                "num": num,
                "count": count,
                "pct": round(100 * count / total_scripts, 1),
                "topics_total": len(p["topics"]),
                "topics_covered": topics_covered,
                "topics_pct": round(100 * topics_covered / topic_total, 1),
            }
        )
    return out


def read_script_detail(script_id: str) -> str:
    path = SCRIPTS_DIR / f"script_{script_id}.md"
    return _read(path)


# ---------------------------------------------------------------------------
# Trạng thái UI (persist tay: đã quay chưa, triage insight) — lưu local JSON
# ---------------------------------------------------------------------------


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"quay_status": {}, "insight_triage": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def toggle_quay(script_id: str) -> bool:
    state = load_state()
    current = state.setdefault("quay_status", {}).get(script_id, False)
    state["quay_status"][script_id] = not current
    save_state(state)
    return not current


def set_insight_triage(num: str, status: str) -> None:
    state = load_state()
    state.setdefault("insight_triage", {})[num] = status
    save_state(state)


# ---------------------------------------------------------------------------
# 1. Não Marketing — goal + ý tưởng do AI sinh (gọi thật qua webapp/ai_helper.py)
# ---------------------------------------------------------------------------


def get_goal() -> str:
    return load_state().get("goal", "")


def set_goal(goal: str) -> None:
    state = load_state()
    state["goal"] = goal
    save_state(state)


def get_goal_ideas() -> list[str]:
    return load_state().get("goal_ideas", [])


def set_goal_ideas(ideas: list[str]) -> None:
    state = load_state()
    state["goal_ideas"] = ideas
    save_state(state)


# ---------------------------------------------------------------------------
# 3. Customer Belief Map — remap 6 nhóm voice_of_customer.md thành 4 nhóm niềm tin
# ---------------------------------------------------------------------------

# Mục trong voice_of_customer.md (theo số thứ tự heading) -> nhóm belief map.
# Đây là remap tay dựa trên ý nghĩa từng mục, không phải phân loại AI tự động.
_VOC_TO_BELIEF = {
    "2": "ĐANG TIN",  # Điều khách hàng hiểu đúng
    "6": "ĐANG TIN",  # Niềm tin hiện có (phần lớn là tin tưởng có căn cứ)
    "3": "HIỂU SAI",  # Điều khách hàng hiểu sai (ngộ nhận)
    "1": "NGHI NGỜ",  # Câu hỏi thường gặp — thể hiện sự chưa chắc chắn
    "4": "NGĂN MUA",  # Nỗi lo lớn nhất — rào cản hành động
}


def read_belief_map() -> list[dict]:
    voc = read_voice_of_customer()
    groups: dict[str, list[str]] = {"ĐANG TIN": [], "HIỂU SAI": [], "NGHI NGỜ": [], "NGĂN MUA": []}
    for section in voc:
        num = section["title"].split(".")[0].strip()
        bucket = _VOC_TO_BELIEF.get(num)
        if not bucket:
            continue
        for row in section["rows"]:
            text = row.get("Insight", "")
            if text:
                groups[bucket].append(text)
    return [{"bucket": b, "items": items} for b, items in groups.items()]


# ---------------------------------------------------------------------------
# 6. Kiến tạo 1.000 video — bung 1 insight thành 10 góc nhìn (cache trong state)
# ---------------------------------------------------------------------------


def get_cached_angles(insight_num: str) -> list[str] | None:
    return load_state().get("insight_angles", {}).get(insight_num)


def set_cached_angles(insight_num: str, angles: list[str]) -> None:
    state = load_state()
    state.setdefault("insight_angles", {})[insight_num] = angles
    save_state(state)


# ---------------------------------------------------------------------------
# 7. Bản đồ nội dung — nhóm kịch bản theo insight (dùng lại dữ liệu đã có)
# ---------------------------------------------------------------------------


def read_content_map() -> list[dict]:
    """Bản đồ nội dung theo 10 Pillar thật: mỗi pillar → từng chủ đề → đã có kịch bản
    khai thác chưa. Cho thấy rõ pillar nào còn trống hoàn toàn (chưa có video nào)."""
    pillars = read_content_pillars()
    ideas_by_id = {i["script_id"]: i for i in read_ideas_today()}
    topic_script = topic_script_map()
    out = []
    for p in pillars:
        num = p["num"]
        topics = []
        for t in p["topics"]:
            topic_num = str(t.get("#", "")).strip()
            script_id = topic_script.get(f"{num}_{topic_num}")
            idea = ideas_by_id.get(script_id) if script_id else None
            topics.append(
                {
                    "topic_num": topic_num,
                    "topic": t.get("Chủ đề", ""),
                    "script": (
                        {"script_id": idea["script_id"], "name": idea["name"]} if idea else None
                    ),
                }
            )
        covered = sum(1 for t in topics if t["script"])
        out.append(
            {
                "num": num,
                "title": p["title"],
                "topics_total": len(topics),
                "topics_covered": covered,
                "topics": topics,
            }
        )
    return out


# ---------------------------------------------------------------------------
# 10-11. Upload video + Hàng đợi video (theo dõi thủ công — KHÔNG tự động edit
# hay tự động đăng lên nền tảng nào; chỉ lưu file + trạng thái do bạn tự tick)
# ---------------------------------------------------------------------------


def list_video_queue() -> list[dict]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    publish_state = state.get("publish_status", {})
    out = []
    for f in sorted(UPLOADS_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            statuses = publish_state.get(f.name, {})
            out.append(
                {
                    "filename": f.name,
                    "size_mb": round(f.stat().st_size / 1_000_000, 1),
                    "platforms": {p: statuses.get(p, False) for p in PUBLISH_PLATFORMS},
                }
            )
    return out


def toggle_publish_status(filename: str, platform: str) -> bool:
    state = load_state()
    ps = state.setdefault("publish_status", {}).setdefault(filename, {})
    ps[platform] = not ps.get(platform, False)
    save_state(state)
    return ps[platform]


# ---------------------------------------------------------------------------
# 12. Ads Autopilot — BÁO CÁO số liệu thật từ ad_performance.csv, đề xuất tạm
# dừng khi vượt ngưỡng. KHÔNG tự động gọi Facebook API để bật/tắt chiến dịch —
# quyết định chi tiền quảng cáo luôn cần bạn xác nhận thủ công.
# ---------------------------------------------------------------------------


def read_ads_autopilot() -> list[dict]:
    import csv as _csv

    path = DATA_DIR / "ad_performance.csv"
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            try:
                cost = float(row.get("cost") or 0)
                conversions = float(row.get("conversions") or 0)
                cpl = cost / conversions if conversions else None
            except ValueError:
                cpl = None
            warn = cpl is not None and cpl > CPL_WARN_THRESHOLD_VND
            out.append(
                {
                    "script_id": row.get("script_id", ""),
                    "hook_summary": row.get("hook_summary", ""),
                    "cost": row.get("cost", ""),
                    "conversions": row.get("conversions", ""),
                    "cpl": round(cpl) if cpl is not None else None,
                    "suggest_pause": warn,
                }
            )
    return out
