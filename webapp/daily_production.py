"""Daily Content Production — logic riêng, tách khỏi data_reader.py để không
đụng tới code đang chạy ổn định của 24 script / 10 Pillar / Insight Bank.

State lưu ở 2 nơi (cả 2 đều là data ĐỘNG — nằm trên persistent disk trên Render,
xem webapp/persistent_storage.py; local dev không set env var thì vẫn nằm
trong data/ như trước):
  - content_calendar.json   — index nhẹ, 1 record/ngày
  - daily_production/{date}.json — chi tiết đầy đủ 1 ngày (ideas/scripts/scores)

Không gọi AI ở đây — module này chỉ quản lý dữ liệu + rule chọn topic. AI được
gọi riêng ở webapp/ai_helper.py, kích hoạt từ route trong main.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from webapp import data_reader as dr
from webapp.persistent_storage import PERSISTENT_DIR

CALENDAR_FILE = PERSISTENT_DIR / "content_calendar.json"
DAILY_DIR = PERSISTENT_DIR / "daily_production"
CONTENT_MAP_FILE = PERSISTENT_DIR / "content_map.json"

VN_TZ = timezone(timedelta(hours=7))

STATUSES = [
    "topic_selected",
    "ideas_generated",
    "draft",
    "scored",
    "selected",
    "recorded",
    "published",
    "ads_running",
    "completed",
]


def today_str() -> str:
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now(VN_TZ).isoformat()


# ---------------------------------------------------------------------------
# Calendar (index nhẹ)
# ---------------------------------------------------------------------------


def load_calendar() -> list[dict]:
    if not CALENDAR_FILE.exists():
        return []
    raw = CALENDAR_FILE.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else []


def save_calendar(records: list[dict]) -> None:
    CALENDAR_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def get_record(date: str) -> dict | None:
    for r in load_calendar():
        if r["date"] == date:
            return r
    return None


def _update_record(date: str, **fields) -> dict:
    records = load_calendar()
    for r in records:
        if r["date"] == date:
            r.update(fields)
            r["updated_at"] = _now_iso()
            save_calendar(records)
            return r
    raise ValueError(f"Không tìm thấy record ngày {date} trong content_calendar.json")


# ---------------------------------------------------------------------------
# Daily detail file
# ---------------------------------------------------------------------------


def load_daily(date: str) -> dict | None:
    path = DAILY_DIR / f"{date}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_daily(date: str, data: dict) -> None:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    path = DAILY_DIR / f"{date}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Rule-based chọn topic hôm nay (KHÔNG dùng AI — Phase 1 bắt buộc rule-based)
# ---------------------------------------------------------------------------


def _pillar_coverage(pillar: dict, topic_script: dict) -> tuple[float, int, int]:
    total = len(pillar["topics"]) or 1
    covered = sum(
        1
        for t in pillar["topics"]
        if f"{pillar['num']}_{str(t.get('#', '')).strip()}" in topic_script
    )
    return covered / total, covered, total


def suggest_topic(avoid_last_n: int = 9) -> dict:
    """Gợi ý pillar/topic tiếp theo — KHÔNG tạo record, chỉ gợi ý.

    Rule (đúng thứ tự ưu tiên đã chốt):
    1. Bỏ qua pillar đã phủ 100% topic.
    2. Ưu tiên pillar chưa xuất hiện trong `avoid_last_n` record gần nhất
       (đảm bảo xoay vòng 10 pillar trước khi lặp lại).
    3. Trong các pillar còn lại, chọn pillar có % coverage thấp nhất.
    4. Trong pillar đã chọn, chọn topic có số thứ tự nhỏ nhất còn chưa có script.
    """
    pillars = dr.read_content_pillars()
    topic_script = dr.topic_script_map()
    calendar = load_calendar()
    recent_pillars = {r["pillar_num"] for r in calendar[-avoid_last_n:]} if calendar else set()

    scored_pillars = []
    for p in pillars:
        pct, covered, total = _pillar_coverage(p, topic_script)
        if covered >= total:
            continue
        scored_pillars.append((pct, covered, total, p))

    if not scored_pillars:
        return {"error": "Tất cả 10 Pillar đã phủ đủ 100% topic — không còn topic trống."}

    scored_pillars.sort(key=lambda x: x[0])
    preferred = [row for row in scored_pillars if row[3]["num"] not in recent_pillars]
    candidates = preferred or scored_pillars

    pct, covered, total, chosen_pillar = candidates[0]
    missing_topics = [
        t
        for t in chosen_pillar["topics"]
        if f"{chosen_pillar['num']}_{str(t.get('#', '')).strip()}" not in topic_script
    ]
    missing_topics.sort(
        key=lambda t: int(t["#"]) if str(t.get("#", "")).isdigit() else 999
    )
    chosen_topic = missing_topics[0]

    return {
        "pillar_num": chosen_pillar["num"],
        "pillar_title": chosen_pillar["title"],
        "topic_num": str(chosen_topic.get("#", "")).strip(),
        "topic_title": chosen_topic.get("Chủ đề", ""),
        "reason": (
            f"Pillar {chosen_pillar['num']} ({chosen_pillar['title']}) đang có coverage "
            f"thấp trong nhóm chưa khai thác gần đây: {covered}/{total} chủ đề "
            f"({round(pct * 100, 1)}%) đã có script."
        ),
    }


# ---------------------------------------------------------------------------
# State machine — tạo record, cập nhật từng bước
# ---------------------------------------------------------------------------


def create_today_record(pillar_num: int, topic_num: str) -> dict:
    date = today_str()
    if get_record(date):
        raise ValueError(f"Đã có record cho ngày {date} rồi — không tạo mới đè lên.")

    record = {
        "id": f"d{date.replace('-', '')}",
        "date": date,
        "pillar_num": pillar_num,
        "topic_num": topic_num,
        "insight_refs": [],
        "status": "topic_selected",
        "selected_script_id": None,
        "detail_file": f"daily_production/{date}.json",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    records = load_calendar()
    records.append(record)
    save_calendar(records)

    save_daily(
        date,
        {
            "date": date,
            "pillar_num": pillar_num,
            "topic_num": topic_num,
            "insight_refs": [],
            "ideas": [],
            "scripts": [],
            "scores": [],
            "top5": [],
        },
    )
    return record


def set_insights(date: str, insight_refs: list[str]) -> dict:
    daily = load_daily(date)
    if daily is None:
        raise ValueError(f"Chưa có record ngày {date}")
    daily["insight_refs"] = insight_refs
    save_daily(date, daily)
    return _update_record(date, insight_refs=insight_refs)


def set_ideas(date: str, ideas: list[dict]) -> dict:
    daily = load_daily(date)
    if daily is None:
        raise ValueError(f"Chưa có record ngày {date}")
    daily["ideas"] = ideas
    save_daily(date, daily)
    return _update_record(date, status="ideas_generated")


def set_scripts(date: str, scripts: list[dict]) -> dict:
    daily = load_daily(date)
    if daily is None:
        raise ValueError(f"Chưa có record ngày {date}")
    daily["scripts"] = scripts
    save_daily(date, daily)
    return _update_record(date, status="draft")


def set_scores(date: str, scores: list[dict], top5: list[str]) -> dict:
    daily = load_daily(date)
    if daily is None:
        raise ValueError(f"Chưa có record ngày {date}")
    daily["scores"] = scores
    daily["top5"] = top5
    save_daily(date, daily)
    return _update_record(date, status="scored")


def select_script(date: str, script_id: str) -> dict:
    daily = load_daily(date)
    if daily is None:
        raise ValueError(f"Chưa có record ngày {date}")
    valid_ids = {s["script_id"] for s in daily.get("scripts", [])}
    if script_id not in valid_ids:
        raise ValueError(f"script_id '{script_id}' không thuộc ngày {date}")

    record = _update_record(date, status="selected", selected_script_id=script_id)

    # Cập nhật content_map.json — CHỈ thêm/sửa đúng 1 key của ngày hôm nay,
    # không đụng tới các entry khác (24 script cũ giữ nguyên).
    content_map = json.loads(CONTENT_MAP_FILE.read_text(encoding="utf-8"))
    key = f"{record['pillar_num']}_{record['topic_num']}"
    content_map.setdefault("topic_script", {})[key] = script_id
    content_map.setdefault("script_pillar", {})[script_id] = record["pillar_num"]
    CONTENT_MAP_FILE.write_text(
        json.dumps(content_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


ALLOWED_MANUAL_STATUSES = {"recorded", "published", "ads_running", "completed"}


def set_status(date: str, status: str) -> dict:
    if status not in ALLOWED_MANUAL_STATUSES:
        raise ValueError(
            f"status '{status}' không hợp lệ — chỉ nhận: {sorted(ALLOWED_MANUAL_STATUSES)}"
        )
    return _update_record(date, status=status)


def get_history(days: int = 7) -> list[dict]:
    records = load_calendar()
    records_sorted = sorted(records, key=lambda r: r["date"], reverse=True)
    return records_sorted[:days]
