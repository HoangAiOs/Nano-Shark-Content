"""Xử lý video feedback khách hàng thật (tải từ Google Drive) — kiểm kê, đo
thời lượng và transcribe local bằng faster-whisper (không tốn phí API).

Cấu trúc nguồn: data/raw_videos/<năm>/[<tháng>/]<file>.mp4
Cấu trúc đích:  data/customer_testimonials/<năm>/[<tháng>/]<file>.txt
                data/customer_testimonials/index.json (metadata toàn bộ)
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from agent.config import (
    CUSTOMER_TESTIMONIALS_DIR,
    RAW_VIDEOS_DIR,
    TESTIMONIALS_INDEX_FILE,
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}

# Mồi từ vựng domain cho Whisper — khách hàng thật nói giọng địa phương/miền Nam,
# model dễ nhầm các thuật ngữ y khoa thành từ đồng âm (vd "khớp gối" -> "khắp gói").
# initial_prompt giúp model thiên về đúng chính tả các từ này khi nghe âm gần giống.
TRANSCRIBE_INITIAL_PROMPT = (
    "Xương khớp, khớp gối, thoái hóa khớp, viêm khớp, tràn dịch khớp gối, gai cột sống, "
    "thoát vị đĩa đệm, sụn cá mập, Nano Premium Shark Cartilage, glucosamine, canxi, "
    "collagen, thuốc giảm đau, vật lý trị liệu, đi lại, cứng khớp, sưng đau."
)


@dataclass
class VideoEntry:
    path: Path
    year: str
    month: str | None
    size_bytes: int


def discover_videos(years: list[str] | None = None) -> list[VideoEntry]:
    """Quét data/raw_videos/<năm>/[<tháng>/]*.mp4, trả về danh sách có cấu trúc."""
    entries: list[VideoEntry] = []
    if not RAW_VIDEOS_DIR.exists():
        return entries

    for year_dir in sorted(RAW_VIDEOS_DIR.iterdir()):
        if not year_dir.is_dir():
            continue
        year = year_dir.name
        if years and year not in years:
            continue
        for path in sorted(year_dir.rglob("*")):
            if path.is_dir() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            if path.name.endswith(".part") or ".part" in path.suffixes[-1:]:
                continue
            rel = path.relative_to(year_dir)
            month = rel.parts[0] if len(rel.parts) > 1 else None
            entries.append(
                VideoEntry(path=path, year=year, month=month, size_bytes=path.stat().st_size)
            )
    return entries


def probe_duration_seconds(path: Path) -> float | None:
    """Đo thời lượng video bằng PyAV (đã cài kèm faster-whisper, không cần ffmpeg riêng)."""
    try:
        import av
    except ImportError:
        return None
    try:
        with av.open(str(path)) as container:
            if container.duration:
                return float(container.duration) / 1_000_000
            for stream in container.streams:
                if stream.duration and stream.time_base:
                    return float(stream.duration * stream.time_base)
    except Exception:
        return None
    return None


def _fmt_size(num_bytes: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f}TB"


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m{s:02d}s"


def print_inventory_report(sample_probe: bool = True) -> dict:
    """In báo cáo kiểm kê: tổng số video, dung lượng, chia theo năm/tháng,
    và ước tính thời gian transcribe dựa trên benchmark thực tế trên 1 video mẫu."""
    entries = discover_videos()
    total_size = sum(e.size_bytes for e in entries)

    by_year: dict[str, list[VideoEntry]] = {}
    for e in entries:
        by_year.setdefault(e.year, []).append(e)

    print(f"\n📦 Kiểm kê data/raw_videos/: {len(entries)} video, tổng {_fmt_size(total_size)}\n")
    for year in sorted(by_year):
        yr_entries = by_year[year]
        yr_size = sum(e.size_bytes for e in yr_entries)
        print(f"  {year}: {len(yr_entries)} video, {_fmt_size(yr_size)}")
        by_month: dict[str, list[VideoEntry]] = {}
        for e in yr_entries:
            by_month.setdefault(e.month or "(gốc)", []).append(e)
        for month in sorted(by_month):
            m_entries = by_month[month]
            m_size = sum(e.size_bytes for e in m_entries)
            print(f"    - {month}: {len(m_entries)} video, {_fmt_size(m_size)}")

    total_duration = None
    benchmark_rtf = None  # real-time factor: giây xử lý / giây audio
    if sample_probe and entries:
        print("\n⏱  Đo thời lượng thực tế của từng video (dùng PyAV)...")
        durations = []
        for e in entries:
            d = probe_duration_seconds(e.path)
            durations.append(d)
            if d is None:
                print(f"    ⚠️  Không đo được thời lượng: {e.path.name}")
        known = [d for d in durations if d]
        if known:
            total_duration = sum(known)
            print(f"  Tổng thời lượng đo được: {_fmt_duration(total_duration)} "
                  f"({len(known)}/{len(entries)} video đo thành công)")

        # Benchmark tốc độ transcribe thật trên video ngắn nhất để ước tính chính xác
        probeable = [(e, d) for e, d in zip(entries, durations) if d]
        if probeable:
            sample_entry, sample_duration = min(probeable, key=lambda x: x[1])
            print(f"\n🔬 Benchmark tốc độ transcribe trên video mẫu ngắn nhất "
                  f"({sample_entry.path.name}, {_fmt_duration(sample_duration)})...")
            try:
                from faster_whisper import WhisperModel

                model = WhisperModel("small", device="cpu", compute_type="int8")
                t0 = time.time()
                segments, _ = model.transcribe(
                    str(sample_entry.path), language="vi", beam_size=1,
                    initial_prompt=TRANSCRIBE_INITIAL_PROMPT,
                )
                list(segments)  # ép chạy hết generator để đo thời gian thực
                elapsed = time.time() - t0
                benchmark_rtf = elapsed / sample_duration
                print(f"  → {elapsed:.1f}s xử lý cho {sample_duration:.1f}s audio "
                      f"(hệ số {benchmark_rtf:.2f}x thời gian thực)")
            except Exception as exc:
                print(f"  ⚠️  Benchmark lỗi: {exc}")

    if total_duration and benchmark_rtf:
        est_seconds = total_duration * benchmark_rtf
        print(f"\n⏳ Ước tính tổng thời gian transcribe (model 'small', CPU): "
              f"~{_fmt_duration(est_seconds)}")
    elif total_duration:
        print("\n⏳ Không benchmark được tốc độ thực tế — ước tính dựa trên kinh nghiệm "
              "faster-whisper 'small' trên CPU (~0.3-0.8x thời gian thực): "
              f"~{_fmt_duration(total_duration * 0.3)} đến ~{_fmt_duration(total_duration * 0.8)}")

    return {
        "total_videos": len(entries),
        "total_size_bytes": total_size,
        "total_duration_seconds": total_duration,
        "estimated_transcribe_seconds": (
            total_duration * benchmark_rtf if total_duration and benchmark_rtf else None
        ),
    }


_NAME_LOCATION_RE = re.compile(r"^(?:PH\s*[-–]?\s*)?(.+?)\.(?:mp4|mov|m4v|avi|mkv)$", re.IGNORECASE)


def _guess_customer_label(filename: str) -> str:
    """Rút gọn tên file thành nhãn khách hàng dễ đọc, vd 'SỤN - CÔ HÀ' -> 'Cô Hà'."""
    stem = Path(filename).stem
    stem = re.sub(r"^PH\s*[-–]?\s*", "", stem, flags=re.IGNORECASE)
    return stem.strip(" -–")


def load_index() -> list[dict]:
    if TESTIMONIALS_INDEX_FILE.exists():
        return json.loads(TESTIMONIALS_INDEX_FILE.read_text(encoding="utf-8"))
    return []


def save_index(records: list[dict]) -> None:
    CUSTOMER_TESTIMONIALS_DIR.mkdir(parents=True, exist_ok=True)
    TESTIMONIALS_INDEX_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def transcribe_all(
    years: list[str] | None = None,
    model_size: str = "small",
) -> dict:
    """Transcribe toàn bộ (hoặc phạm vi năm được chỉ định) video chưa xử lý.
    Resumable: bỏ qua video đã có trong index.json với status 'ok'."""
    from faster_whisper import WhisperModel

    entries = discover_videos(years=years)
    if not entries:
        print("⚠️  Không tìm thấy video nào trong data/raw_videos/.")
        return {"processed": 0, "skipped": 0, "errors": []}

    existing = {r["source_file"]: r for r in load_index()}
    print(f"\n🎙  Bắt đầu transcribe {len(entries)} video (model faster-whisper '{model_size}', CPU)...\n")

    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    records = list(load_index())
    errors: list[dict] = []
    processed = 0
    skipped = 0

    for i, e in enumerate(entries, 1):
        key = str(e.path.relative_to(RAW_VIDEOS_DIR))
        if key in existing and existing[key].get("status") == "ok":
            skipped += 1
            continue

        print(f"[{i}/{len(entries)}] {key} ({_fmt_size(e.size_bytes)}) ...", end=" ", flush=True)
        t0 = time.time()
        try:
            duration = probe_duration_seconds(e.path)
            segments, info = model.transcribe(
                str(e.path), language="vi", beam_size=5, initial_prompt=TRANSCRIBE_INITIAL_PROMPT
            )
            text_parts = [seg.text.strip() for seg in segments]
            transcript = "\n".join(p for p in text_parts if p)

            out_dir = CUSTOMER_TESTIMONIALS_DIR / e.year / (e.month or "")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / (e.path.stem + ".txt")
            out_path.write_text(transcript, encoding="utf-8")

            record = {
                "source_file": key,
                "original_filename": e.path.name,
                "customer_label": _guess_customer_label(e.path.name),
                "year": e.year,
                "month": e.month,
                "transcript_path": str(out_path.relative_to(RAW_VIDEOS_DIR.parent.parent)),
                "duration_seconds": duration,
                "source_type": "real_customer_testimonial",
                "status": "ok",
                "char_count": len(transcript),
                "error": None,
            }
            elapsed = time.time() - t0
            print(f"xong ({elapsed:.0f}s, {len(transcript)} ký tự)")
            processed += 1
        except Exception as exc:
            record = {
                "source_file": key,
                "original_filename": e.path.name,
                "customer_label": _guess_customer_label(e.path.name),
                "year": e.year,
                "month": e.month,
                "transcript_path": None,
                "duration_seconds": None,
                "source_type": "real_customer_testimonial",
                "status": "error",
                "char_count": 0,
                "error": str(exc),
            }
            errors.append(record)
            print(f"LỖI: {exc}")

        records = [r for r in records if r["source_file"] != key] + [record]
        save_index(records)  # ghi ngay sau mỗi video để resumable nếu bị ngắt giữa chừng

    print(f"\n✅ Hoàn tất: {processed} video mới xử lý, {skipped} video đã có sẵn (bỏ qua), "
          f"{len(errors)} lỗi.")
    if errors:
        print("⚠️  Các video lỗi:")
        for e in errors:
            print(f"   - {e['source_file']}: {e['error']}")

    return {"processed": processed, "skipped": skipped, "errors": errors}
