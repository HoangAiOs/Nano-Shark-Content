"""CLI entrypoint. Chạy từ thư mục gốc project bằng:

    python -m agent.cli <command>

Xem README.md để biết chi tiết từng command.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv chưa cài — vẫn chạy được nếu ANTHROPIC_API_KEY đã export sẵn

from agent.config import ensure_data_dirs
from agent.lib import testimonials
from agent.phases import (
    feedback_analyzer,
    insight_filter,
    optimizer,
    research,
    scorer,
    scripts_writer,
    sync_facebook,
    voice_of_customer,
)

COMMANDS = {
    "sync-facebook": (
        "Đồng bộ dữ liệu thật từ Facebook (comment công khai + số liệu quảng cáo)",
        sync_facebook.run,
    ),
    "research": ("Bước 1 — Thu thập dữ liệu thô về insight khách hàng", research.run),
    "synthesize": ("Bước 2 — Tổng hợp Voice of Customer", voice_of_customer.run),
    "filter-insights": ("Bước 3 — Lọc 5-7 insight ưu tiên", insight_filter.run),
    "write-scripts": ("Bước 4 — Viết 10 kịch bản video", scripts_writer.run),
    "score": ("Bước 5 — Chấm điểm & chọn top 5 kịch bản", scorer.run),
    "analyze-feedback": ("Bước 6 — Phân tích số liệu quảng cáo thực tế", feedback_analyzer.run),
    "optimize": ("Bước 7 — Đề xuất tối ưu dựa trên feedback", optimizer.run),
}

PIPELINE_ORDER = [
    "research",
    "synthesize",
    "filter-insights",
    "write-scripts",
    "score",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="Agent nghiên cứu insight & viết kịch bản quảng cáo Facebook.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, (help_text, _fn) in COMMANDS.items():
        subparsers.add_parser(name, help=help_text)

    subparsers.add_parser(
        "all",
        help=f"Chạy tuần tự các bước {' → '.join(PIPELINE_ORDER)} (không gồm analyze-feedback/optimize)",
    )

    p_inv = subparsers.add_parser(
        "inventory-testimonials",
        help="Kiểm kê video feedback khách hàng thật đã tải (data/raw_videos/) + ước tính thời gian transcribe",
    )
    p_inv.add_argument("--no-benchmark", action="store_true", help="Bỏ qua benchmark tốc độ (nhanh hơn nhưng không ước tính được thời gian)")

    p_tr = subparsers.add_parser(
        "transcribe-testimonials",
        help="Transcribe video feedback khách hàng thật bằng faster-whisper (local, miễn phí)",
    )
    p_tr.add_argument("--years", type=str, default=None, help="Giới hạn năm, vd: 2025,2026 (mặc định: tất cả)")
    p_tr.add_argument("--model", type=str, default="small", help="Kích thước model faster-whisper (tiny/base/small/medium/large-v3), mặc định: small")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ensure_data_dirs()

    if args.command == "all":
        for name in PIPELINE_ORDER:
            _, fn = COMMANDS[name]
            print(f"\n{'=' * 60}\n{name.upper()}\n{'=' * 60}")
            fn()
        return

    if args.command == "inventory-testimonials":
        testimonials.print_inventory_report(sample_probe=not args.no_benchmark)
        return

    if args.command == "transcribe-testimonials":
        years = [y.strip() for y in args.years.split(",")] if args.years else None
        testimonials.transcribe_all(years=years, model_size=args.model)
        return

    _, fn = COMMANDS[args.command]
    fn()


if __name__ == "__main__":
    sys.exit(main() or 0)
