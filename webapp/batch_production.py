"""Batch Content Production — "quay 1 lần, đủ content cả tháng".

Khác với Daily Content Production (1 ngày = 1 topic = tối đa 1 script được
chọn), Batch Production: 1 batch = N insight (20-30) = N script, TẤT CẢ đều
"sống" song song, không có khái niệm chọn 1/N — người dùng quay lần lượt hết
cả batch trong 1 buổi.

Không đụng gì tới daily_production.py / content_calendar.json / content_map.json
— đây là module hoàn toàn song song, độc lập.

State lưu 2 nơi (đều dùng PERSISTENT_DIR — sống sót qua Render restart/redeploy,
xem persistent_storage.py; local dev không set env var thì vẫn nằm trong data/):
  - batches_index.json      — index nhẹ, 1 record/batch
  - batches/{batch_id}.json — chi tiết đầy đủ 1 batch (toàn bộ script)

Đây là data HOÀN TOÀN MỚI (chưa từng tồn tại trong git trước đây) — không cần
seed từ đâu cả, chỉ cần tạo mới trực tiếp trên PERSISTENT_DIR khi dùng lần đầu.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from webapp.persistent_storage import PERSISTENT_DIR

INDEX_FILE = PERSISTENT_DIR / "batches_index.json"
BATCHES_DIR = PERSISTENT_DIR / "batches"

VN_TZ = timezone(timedelta(hours=7))

STATUSES = ["chua_quay", "da_quay", "da_dung", "da_dang"]
_NEXT_STATUS = {"chua_quay": "da_quay", "da_quay": "da_dung", "da_dung": "da_dang"}


def _now_iso() -> str:
    return datetime.now(VN_TZ).isoformat()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "batch"


# ---------------------------------------------------------------------------
# Index (nhẹ — 1 record/batch)
# ---------------------------------------------------------------------------


def load_index() -> list[dict]:
    if not INDEX_FILE.exists():
        return []
    raw = INDEX_FILE.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else []


def save_index(records: list[dict]) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _status_counts(scripts: list[dict]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for s in scripts:
        st = s.get("status", "chua_quay")
        counts[st] = counts.get(st, 0) + 1
    return counts


def _update_index_entry(batch_id: str, **fields) -> None:
    records = load_index()
    for r in records:
        if r["id"] == batch_id:
            r.update(fields)
            r["updated_at"] = _now_iso()
            save_index(records)
            return
    raise ValueError(f"Không tìm thấy batch '{batch_id}' trong index")


def list_batches() -> list[dict]:
    return sorted(load_index(), key=lambda r: r["created_at"], reverse=True)


# ---------------------------------------------------------------------------
# Batch detail
# ---------------------------------------------------------------------------


def load_batch(batch_id: str) -> dict | None:
    path = BATCHES_DIR / f"{batch_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_batch(batch_id: str, data: dict) -> None:
    BATCHES_DIR.mkdir(parents=True, exist_ok=True)
    path = BATCHES_DIR / f"{batch_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_batch(name: str) -> dict:
    date_key = datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
    batch_id = f"batch_{date_key}_{_slugify(name)}"

    record = {
        "id": batch_id,
        "name": name,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "script_count": 0,
        "status_counts": _status_counts([]),
    }
    records = load_index()
    records.append(record)
    save_index(records)

    save_batch(batch_id, {"id": batch_id, "name": name, "scripts": []})
    return record


def add_scripts(batch_id: str, insights: list[str], raw_scripts: list[dict], mandatory_warning: str) -> dict:
    """Gắn thêm script mới sinh (1 đợt, vd 10 insight/lần) vào batch đã có.
    Không bao giờ xoá script cũ trong batch — chỉ nối thêm."""
    batch = load_batch(batch_id)
    if batch is None:
        raise ValueError(f"Không tìm thấy batch '{batch_id}'")

    start_idx = len(batch["scripts"]) + 1
    for i, (insight, raw) in enumerate(zip(insights, raw_scripts), start=start_idx):
        script = dict(raw)
        script["script_id"] = f"{batch_id}_{i:02d}"
        script["insight"] = insight
        script["mandatory_warning"] = mandatory_warning
        script["status"] = "chua_quay"
        batch["scripts"].append(script)

    save_batch(batch_id, batch)
    _update_index_entry(
        batch_id,
        script_count=len(batch["scripts"]),
        status_counts=_status_counts(batch["scripts"]),
    )
    return batch


def set_script_status(batch_id: str, script_id: str, status: str | None = None) -> dict:
    """Không truyền status -> tự chuyển sang trạng thái KẾ TIẾP (chua_quay -> da_quay
    -> da_dung -> da_dang), đúng thao tác "bấm là chuyển ngay" trong UI."""
    batch = load_batch(batch_id)
    if batch is None:
        raise ValueError(f"Không tìm thấy batch '{batch_id}'")

    script = next((s for s in batch["scripts"] if s["script_id"] == script_id), None)
    if script is None:
        raise ValueError(f"Không tìm thấy script '{script_id}' trong batch '{batch_id}'")

    if status is None:
        status = _NEXT_STATUS.get(script.get("status", "chua_quay"))
        if status is None:
            return batch  # đã ở trạng thái cuối (da_dang), không còn "kế tiếp"
    elif status not in STATUSES:
        raise ValueError(f"status '{status}' không hợp lệ — chỉ nhận: {STATUSES}")

    script["status"] = status
    save_batch(batch_id, batch)
    _update_index_entry(batch_id, status_counts=_status_counts(batch["scripts"]))
    return batch
