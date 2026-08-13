"""Persistent storage cho data ĐỘNG (Daily Content Production + video upload).

Vấn đề: Render free/ephemeral filesystem mất hết thay đổi mỗi lần service
restart/redeploy/spin-down. Giải pháp: gắn Render Persistent Disk, trỏ
PERSISTENT_DATA_DIR (env var) vào mount path đó — chỉ cho ĐÚNG 5 mục data
động, KHÔNG bao giờ đụng tới file tĩnh git-managed (content_pillars.md,
insight_bank.md, 24 script...) — những file đó tiếp tục deploy qua git
bình thường.

Local dev (không set PERSISTENT_DATA_DIR): PERSISTENT_DIR = DATA_DIR như cũ,
hành vi không đổi gì — chỉ trên Render (sau khi set env var) mới thực sự
tách ra dùng disk riêng.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DATA_DIR") or DATA_DIR)

MARKER_FILE = PERSISTENT_DIR / ".migrated"

# Đúng 5 mục data động — KHÔNG thêm bất kỳ file tĩnh nào khác vào đây.
_SEED_FILES = ["content_calendar.json", "web_state.json", "content_map.json"]
_SEED_DIRS = ["daily_production", "video_uploads"]

VN_TZ = timezone(timedelta(hours=7))


def bootstrap_persistent_data() -> None:
    """Chạy 1 lần lúc app khởi động. KHÔNG BAO GIỜ ghi đè nếu disk đã có
    dữ liệu (đánh dấu bằng file .migrated) — chỉ seed đúng 1 lần duy nhất
    trong vòng đời của disk, từ bản git hiện tại."""
    if PERSISTENT_DIR == DATA_DIR:
        print("[persistent_storage] PERSISTENT_DATA_DIR chưa set — dùng data/ như cũ (local dev).")
        return

    PERSISTENT_DIR.mkdir(parents=True, exist_ok=True)

    if MARKER_FILE.exists():
        marker_info = MARKER_FILE.read_text(encoding="utf-8").strip()
        print(
            f"[persistent_storage] Persistent storage đã có dữ liệu ({marker_info}) "
            f"— dùng nguyên trạng, KHÔNG ghi đè gì cả."
        )
        return

    print(
        f"[persistent_storage] Persistent storage TRỐNG (chưa có {MARKER_FILE}) "
        f"— bắt đầu seed 1 lần từ data/ hiện tại trong git."
    )

    for name in _SEED_FILES:
        src = DATA_DIR / name
        dst = PERSISTENT_DIR / name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"[persistent_storage]   seeded file: {name}")
        else:
            print(f"[persistent_storage]   CẢNH BÁO: {name} không tồn tại trong git, bỏ qua")

    for name in _SEED_DIRS:
        src_dir = DATA_DIR / name
        dst_dir = PERSISTENT_DIR / name
        if src_dir.exists():
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            n = sum(1 for _ in dst_dir.rglob("*") if _.is_file())
            print(f"[persistent_storage]   seeded dir: {name}/ ({n} file)")
        else:
            dst_dir.mkdir(parents=True, exist_ok=True)
            print(f"[persistent_storage]   tạo dir rỗng: {name}/ (không có gì để seed từ git)")

    MARKER_FILE.write_text(
        f"migrated_at={datetime.now(VN_TZ).isoformat()}\n", encoding="utf-8"
    )
    print(f"[persistent_storage] Migration hoàn tất — đã ghi {MARKER_FILE}")
