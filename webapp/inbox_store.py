"""Insight từ Inbox — tin nhắn khách THẬT từ page (tên thật, thông tin sức khoẻ).

Dữ liệu nhạy cảm nên:
- Lưu ở thư mục riêng `inbox/` trên persistent disk (PERSISTENT_DIR), KHÔNG seed từ git,
  KHÔNG commit (data/inbox/ nằm trong .gitignore — repo đang public).
- Chỉ đọc/ghi qua /api/inbox/* (đã nằm sau AuthMiddleware), không xuất hiện ở API khác.
- Khung kịch bản chỉ tạo được khi khách "Đã đồng ý" — chặn cả ở server, không chỉ ở nút.
- Không gọi AI: khung kịch bản là template trống, điền sẵn tên + tin nhắn gốc vào Bằng chứng.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from webapp.persistent_storage import PERSISTENT_DIR

INBOX_DIR = PERSISTENT_DIR / "inbox"
INBOX_FILE = INBOX_DIR / "inbox_insights.json"
EVIDENCE_DIR = INBOX_DIR / "evidence"

CONSENT_VALUES = ("Chưa hỏi", "Đã đồng ý", "Từ chối")
CONSENT_OK = "Đã đồng ý"
DEFAULT_GROUPS = ["đã dùng glucosamine vẫn đau", "sợ mổ", "sợ hàng giả", "ngại giá"]
EVIDENCE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}
EVIDENCE_MAX_BYTES = 10 * 1024 * 1024

DISCLAIMER = '"Thực phẩm này không phải là thuốc và không có tác dụng thay thế thuốc chữa bệnh."'
VN_TZ = timezone(timedelta(hours=7))
_lock = threading.Lock()

_TEXT_FIELDS = ("ten_khach", "tuoi", "tinh_thanh", "tin_nhan_goc", "nhom_insight", "ngay_nhan",
                "ghi_chu_xac_nhan", "bang_chung_link")


class InboxError(ValueError):
    pass


def _now() -> str:
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def _load_all() -> dict:
    """File dạng {"next_id": n, "items": [...]} — next_id chỉ tăng, xoá insight không làm dùng lại mã cũ."""
    if not INBOX_FILE.exists():
        return {"next_id": 1, "items": []}
    return json.loads(INBOX_FILE.read_text(encoding="utf-8"))


def _load() -> list[dict]:
    return _load_all()["items"]


def _save(items: list[dict], next_id: int | None = None) -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    if next_id is None:
        next_id = _load_all()["next_id"]
    tmp = INBOX_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"next_id": next_id, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, INBOX_FILE)


def _clean_links(value) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,\s]+", value)
    # Số kịch bản trong Thư viện dạng 2 chữ số ("03") — chuẩn hoá "3"/"#3" về đúng dạng đó.
    ids = {str(v).strip().lstrip("#") for v in (value or [])} - {""}
    ids = {f"{int(i):02d}" if i.isdigit() else i for i in ids}
    return sorted(ids, key=lambda s: (not s.isdigit(), int(s) if s.isdigit() else 0, s))


def _normalize(data: dict, base: dict | None = None) -> dict:
    rec = dict(base or {})
    for f in _TEXT_FIELDS:
        if f in data:
            v = data.get(f)
            v = "" if v is None else str(v)
            # Tin nhắn gốc giữ nguyên văn — chỉ bỏ khoảng trắng thừa ở hai đầu khối dán.
            rec[f] = v.strip("\n\r ") if f == "tin_nhan_goc" else v.strip()
    if "dong_y" in data:
        rec["dong_y"] = data.get("dong_y") or "Chưa hỏi"
    rec.setdefault("dong_y", "Chưa hỏi")
    if rec["dong_y"] not in CONSENT_VALUES:
        raise InboxError(f"Trạng thái đồng ý không hợp lệ: {rec['dong_y']}")
    if "kich_ban_lien_ket" in data:
        rec["kich_ban_lien_ket"] = _clean_links(data.get("kich_ban_lien_ket"))
    rec.setdefault("kich_ban_lien_ket", [])
    rec.setdefault("bang_chung_anh", [])
    if not rec.get("ten_khach"):
        raise InboxError("Thiếu tên khách")
    if not rec.get("tin_nhan_goc"):
        raise InboxError(f"Thiếu nội dung tin nhắn gốc ({rec.get('ten_khach')})")
    if rec.get("ngay_nhan") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", rec["ngay_nhan"]):
        raise InboxError(f"Ngày nhận tin phải dạng YYYY-MM-DD: {rec['ngay_nhan']}")
    return rec


def list_insights() -> dict:
    items = _load()
    groups = sorted({i.get("nhom_insight", "") for i in items if i.get("nhom_insight")} | set(DEFAULT_GROUPS))
    return {"items": items, "groups": groups, "consent_values": list(CONSENT_VALUES)}


def add_insights(entries: list[dict]) -> list[dict]:
    if not entries:
        raise InboxError("Không có tin nhắn nào để lưu")
    with _lock:
        data = _load_all()
        items, next_id = data["items"], data["next_id"]
        added = []
        for e in entries:
            rec = _normalize(e)
            rec["id"] = f"INB-{next_id:04d}"
            next_id += 1
            rec["created_at"] = rec["updated_at"] = _now()
            items.append(rec)
            added.append(rec)
        _save(items, next_id)
    return added


def update_insight(insight_id: str, data: dict) -> dict:
    with _lock:
        items = _load()
        for idx, rec in enumerate(items):
            if rec["id"] == insight_id:
                new = _normalize(data, rec)
                new["updated_at"] = _now()
                items[idx] = new
                _save(items)
                return new
    raise KeyError(insight_id)


def delete_insight(insight_id: str) -> None:
    with _lock:
        items = _load()
        rec = next((r for r in items if r["id"] == insight_id), None)
        if rec is None:
            raise KeyError(insight_id)
        for name in rec.get("bang_chung_anh", []):
            p = EVIDENCE_DIR / name
            if p.is_file():
                p.unlink()
        _save([r for r in items if r["id"] != insight_id])


def build_skeleton(rec: dict) -> str:
    who = ", ".join(x for x in [rec["ten_khach"], f"{rec['tuoi']} tuổi" if rec.get("tuoi") else "",
                                rec.get("tinh_thanh", "")] if x)
    quoted = "\n".join(f"> {line}" if line else ">" for line in rec["tin_nhan_goc"].split("\n"))
    ngay = rec.get("ngay_nhan") or "chưa ghi ngày"
    return f"""# Khung kịch bản từ Inbox — {rec['ten_khach']} ({rec['id']})
**Nguồn insight:** tin nhắn inbox page — {who} — nhận ngày {ngay} — nhóm "{rec.get('nhom_insight') or 'chưa phân nhóm'}"
**Đồng ý sử dụng:** {rec['dong_y']} — {rec.get('ghi_chu_xac_nhan') or '(chưa ghi cách xác nhận)'}
**Insight chính:** (viết tiếp)

> Quy tắc khi viết tiếp (xoá khối này trước khi quay):
> - Giữ nguyên tinh thần lời khách, không bịa thêm bệnh sử / kết quả ngoài tin nhắn gốc.
> - Không dùng "chữa khỏi", "điều trị"; giữ nguyên Cảnh báo bắt buộc bên dưới.
> - Chỉ dùng tên, tuổi, câu chuyện của khách vì khách đã "Đã đồng ý" — nếu khách rút đồng ý thì bỏ khung này.

## Hook
(viết tiếp)

## Vấn đề
(viết tiếp)

## Giải pháp
(viết tiếp)

## Bằng chứng
Khách: {who}
Tin nhắn gốc (nguyên văn, nhận ngày {ngay}):
{quoted}

## CTA
(viết tiếp)

## Cảnh báo bắt buộc
{DISCLAIMER}
Kết quả có thể khác nhau tuỳ cơ địa.

## Ghi chú dàn dựng
(viết tiếp)
"""


def create_skeleton(insight_id: str) -> dict:
    with _lock:
        items = _load()
        for rec in items:
            if rec["id"] == insight_id:
                if rec.get("dong_y") != CONSENT_OK:
                    raise PermissionError(
                        "Chưa được khách đồng ý dùng tên và câu chuyện — không đưa vào video")
                rec["khung_kich_ban"] = build_skeleton(rec)
                rec["khung_tao_luc"] = rec["updated_at"] = _now()
                _save(items)
                return rec
    raise KeyError(insight_id)


def save_evidence(insight_id: str, filename: str, contents: bytes) -> dict:
    ext = Path(filename or "").suffix.lower()
    if ext not in EVIDENCE_EXTS:
        raise InboxError("Chỉ nhận ảnh (jpg, png, webp, gif, heic)")
    if len(contents) > EVIDENCE_MAX_BYTES:
        raise InboxError("Ảnh quá 10 MB")
    with _lock:
        items = _load()
        rec = next((r for r in items if r["id"] == insight_id), None)
        if rec is None:
            raise KeyError(insight_id)
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        name = f"{insight_id}-{uuid.uuid4().hex[:8]}{ext}"
        (EVIDENCE_DIR / name).write_bytes(contents)
        rec.setdefault("bang_chung_anh", []).append(name)
        rec["updated_at"] = _now()
        _save(items)
        return rec


def evidence_path(name: str) -> Path | None:
    if not re.fullmatch(r"INB-\d+-[0-9a-f]{8}\.[a-z]+", name or ""):
        return None
    p = EVIDENCE_DIR / name
    return p if p.is_file() else None
