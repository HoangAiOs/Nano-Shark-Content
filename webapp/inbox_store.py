"""Insight từ Inbox — tin nhắn khách THẬT từ page (tên thật, thông tin sức khoẻ).

Dữ liệu nhạy cảm nên:
- Lưu ở thư mục riêng `inbox/` trên persistent disk (PERSISTENT_DIR), KHÔNG seed từ git,
  KHÔNG commit (data/inbox/ nằm trong .gitignore — repo đang public).
- Chỉ đọc/ghi qua /api/inbox/* (đã nằm sau AuthMiddleware), không xuất hiện ở API khác.
- Kịch bản chỉ sinh được khi khách "Đã đồng ý" — chặn cả ở server, không chỉ ở nút. Sinh bằng
  Claude API (webapp/script_generator.py); file kịch bản lưu ở inbox/scripts/ (cũng không vào git)
  và hiện trong Thư viện kịch bản với số tiếp theo — khách rút đồng ý thì tự ẩn khỏi Thư viện.
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
SCRIPTS_DIR = INBOX_DIR / "scripts"
GENERATION_STALE = timedelta(minutes=15)

CONSENT_VALUES = ("Chưa hỏi", "Đã đồng ý", "Từ chối")
CONSENT_OK = "Đã đồng ý"
DEFAULT_GROUPS = ["đã dùng glucosamine vẫn đau", "sợ mổ", "sợ hàng giả", "ngại giá"]
EVIDENCE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}
EVIDENCE_MAX_BYTES = 10 * 1024 * 1024

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
        if rec.get("kich_ban_so"):
            _script_path(rec["kich_ban_so"]).unlink(missing_ok=True)
        _save([r for r in items if r["id"] != insight_id])


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


# --- Kịch bản sinh bằng Claude API ------------------------------------------------


def _script_path(script_no: str) -> Path:
    return SCRIPTS_DIR / f"script_{script_no}.md"


def _find(items: list[dict], insight_id: str) -> dict:
    rec = next((r for r in items if r["id"] == insight_id), None)
    if rec is None:
        raise KeyError(insight_id)
    return rec


def start_generation(insight_id: str, library_ids: set[str]) -> tuple[dict, str]:
    """Đánh dấu 'đang sinh' và giữ chỗ số kịch bản (giữ số cũ nếu là Sinh lại)."""
    with _lock:
        items = _load()
        rec = _find(items, insight_id)
        if rec.get("dong_y") != CONSENT_OK:
            raise PermissionError("Chưa được khách đồng ý dùng tên và câu chuyện — không đưa vào video")
        sinh = rec.get("sinh") or {}
        if sinh.get("trang_thai") == "dang_sinh" and \
                datetime.now(VN_TZ) - datetime.fromisoformat(sinh["bat_dau"]) < GENERATION_STALE:
            raise InboxError("Kịch bản đang được sinh — đợi xong rồi hãy bấm lại")
        script_no = rec.get("kich_ban_so")
        if not script_no:
            used = {r["kich_ban_so"] for r in items if r.get("kich_ban_so")} | set(library_ids)
            nums = [int(x) for x in used if x.isdigit()]
            script_no = f"{(max(nums) + 1 if nums else 1):02d}"
            rec["kich_ban_so"] = script_no
        rec["sinh"] = {**sinh, "trang_thai": "dang_sinh", "bat_dau": _now(), "loi": ""}
        rec["updated_at"] = _now()
        _save(items)
        return dict(rec), script_no


def finish_generation(insight_id: str, result: dict) -> None:
    with _lock:
        items = _load()
        rec = _find(items, insight_id)
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        _script_path(rec["kich_ban_so"]).write_text(result["markdown"], encoding="utf-8")
        rec["kich_ban_lien_ket"] = _clean_links([*rec.get("kich_ban_lien_ket", []), rec["kich_ban_so"]])
        rec["sinh"] = {"trang_thai": "xong", "bat_dau": rec.get("sinh", {}).get("bat_dau", ""), "luc": _now(),
                       "model": result["model"], "so_lan_goi": result["attempts"], "check": result["check"],
                       "ten_kich_ban": result["ten_kich_ban"], "insight_chinh": result["insight_chinh"],
                       "hook": result["hook"], "sua_tay": "", "loi": ""}
        rec["updated_at"] = _now()
        _save(items)


def fail_generation(insight_id: str, message: str) -> None:
    with _lock:
        items = _load()
        rec = _find(items, insight_id)
        rec["sinh"] = {**(rec.get("sinh") or {}), "trang_thai": "loi", "loi": message, "luc_loi": _now()}
        _save(items)


def read_generated(insight_id: str) -> str:
    rec = _find(_load(), insight_id)
    p = _script_path(rec["kich_ban_so"]) if rec.get("kich_ban_so") else None
    return p.read_text(encoding="utf-8") if p and p.is_file() else ""


def save_manual_edit(insight_id: str, markdown: str, check: dict) -> dict:
    with _lock:
        items = _load()
        rec = _find(items, insight_id)
        if not rec.get("kich_ban_so") or not _script_path(rec["kich_ban_so"]).is_file():
            raise InboxError("Insight này chưa có kịch bản để sửa")
        _script_path(rec["kich_ban_so"]).write_text(markdown, encoding="utf-8")
        rec["sinh"] = {**rec.get("sinh", {}), "check": check, "sua_tay": _now()}
        rec["updated_at"] = _now()
        _save(items)
        return rec


def library_entries() -> list[dict]:
    """Kịch bản sinh từ Inbox để Thư viện kịch bản hiện chung — chỉ khách còn 'Đã đồng ý'."""
    out = []
    for r in _load():
        if r.get("dong_y") == CONSENT_OK and r.get("kich_ban_so") and _script_path(r["kich_ban_so"]).is_file():
            s = r.get("sinh") or {}
            out.append({"script_id": r["kich_ban_so"], "inbox_id": r["id"], "ten_khach": r["ten_khach"],
                        "name": s.get("ten_kich_ban") or f"Kịch bản từ inbox — {r['ten_khach']}",
                        "insight": s.get("insight_chinh", ""), "hook": s.get("hook", "")})
    return out


def library_script(script_no: str) -> str | None:
    for e in library_entries():
        if e["script_id"] == script_no:
            return _script_path(script_no).read_text(encoding="utf-8")
    return None
