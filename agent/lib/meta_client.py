"""Client gọi Facebook Graph API để tự động lấy comment công khai trên Page
và số liệu quảng cáo, ghi thẳng vào đúng schema CSV mà pipeline agent đang dùng.

Yêu cầu các biến môi trường trong `.env` (xem docs/facebook-graph-api-setup.md):
    FB_PAGE_ID              - ID của Page
    FB_PAGE_ACCESS_TOKEN    - Page Access Token (không hết hạn, dùng cho việc đọc Page)
    FB_USER_ACCESS_TOKEN    - Long-lived User Access Token (~60 ngày, dùng cho Ads Insights)
    FB_AD_ACCOUNT_ID        - vd act_2074420212746225 (dùng cho Ads Insights)

Giới hạn quan trọng:
- CHỈ lấy được comment công khai trên bài đăng, KHÔNG lấy được tin nhắn Messenger
  (inbox) — Meta giới hạn rất chặt phần này qua API (xem docs/facebook-graph-api-setup.md).
- Số liệu quảng cáo được ghép với `script_id` dựa trên TÊN QUẢNG CÁO trong Ads
  Manager — tên ads cần chứa số thứ tự kịch bản (vd "01", "Script 02", "kich_ban_03")
  thì mới ghép đúng. Ads không ghép được sẽ để trống `script_id` và vẫn được ghi
  ra để bạn tự đối chiếu tay.
- `FB_USER_ACCESS_TOKEN` là long-lived (~60 ngày), KHÔNG vĩnh viễn như page token
  — cần làm mới định kỳ (xem hàm `refresh_user_token_hint` bên dưới).
"""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path

import httpx

from agent.config import AD_PERFORMANCE_FILE, INBOX_COMMENTS_FILE

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

INBOX_CSV_FIELDS = ["source", "author", "content", "date", "type", "post_url"]
AD_PERFORMANCE_CSV_FIELDS = [
    "script_id",
    "hook_summary",
    "ctr",
    "retention_3s",
    "retention_25",
    "retention_50",
    "retention_75",
    "retention_100",
    "comments",
    "inbox",
    "cost",
    "conversions",
]

# Bắt buộc phải có tiền tố "script"/"kich ban"/"kb" thì mới ghép script_id — nếu
# để prefix tùy chọn sẽ khớp nhầm vào số ngẫu nhiên trong tên ad cũ không liên quan
# (vd "Sụn 1115" bị hiểu nhầm thành script "11"). Ad không đúng quy ước đặt tên
# sẽ để trống script_id thay vì đoán bừa.
_SCRIPT_ID_PATTERN = re.compile(r"(?:script|kich[_\s-]?ban|kb)[_\s-]*(\d{2})", re.IGNORECASE)


class MetaClientError(RuntimeError):
    """Lỗi khi gọi Facebook Graph API — thường do thiếu quyền hoặc token hết hạn."""


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MetaClientError(
            f"Thiếu biến môi trường {name} trong .env. Xem docs/facebook-graph-api-setup.md."
        )
    return value


def _get(path: str, *, params: dict) -> dict:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{GRAPH_API_BASE}/{path}", params=params)
    data = response.json()
    if "error" in data:
        err = data["error"]
        raise MetaClientError(
            f"Facebook Graph API lỗi khi gọi {path}: [{err.get('code')}] {err.get('message')}"
        )
    return data


# ---------------------------------------------------------------------------
# Comments (đọc)
# ---------------------------------------------------------------------------


def fetch_page_comments(*, max_posts: int = 25) -> list[dict]:
    """Lấy comment công khai trên các bài đăng gần nhất của Page."""
    page_id = _require_env("FB_PAGE_ID")
    page_token = _require_env("FB_PAGE_ACCESS_TOKEN")

    records: list[dict] = []
    posts = _get(
        f"{page_id}/posts",
        params={
            "fields": "id,permalink_url,created_time,comments.limit(100){message,from,created_time}",
            "limit": max_posts,
            "access_token": page_token,
        },
    )

    for post in posts.get("data", []):
        post_url = post.get("permalink_url", "")
        for c in post.get("comments", {}).get("data", []):
            message = (c.get("message") or "").strip()
            if not message:
                continue
            author = (c.get("from") or {}).get("name") or "Ẩn danh"
            created = c.get("created_time", "")
            records.append(
                {
                    "source": "Facebook Page",
                    "author": author,
                    "content": message,
                    "date": created[:10] if created else "",
                    "type": "comment",
                    "post_url": post_url,
                }
            )

    return records


def write_inbox_comments_csv(records: list[dict]) -> Path:
    INBOX_COMMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with INBOX_COMMENTS_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INBOX_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    return INBOX_COMMENTS_FILE


# ---------------------------------------------------------------------------
# Ads insights
# ---------------------------------------------------------------------------


def _extract_script_id(ad_name: str) -> str:
    match = _SCRIPT_ID_PATTERN.search(ad_name)
    return match.group(1) if match else ""


def _action_value(actions: list[dict] | None, action_type: str) -> float:
    for a in actions or []:
        if a.get("action_type") == action_type:
            try:
                return float(a.get("value", 0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def fetch_ad_insights(*, date_preset: str = "last_30d") -> list[dict]:
    """Lấy số liệu quảng cáo ở cấp độ ad, ghép với script_id qua tên quảng cáo."""
    ad_account_id = _require_env("FB_AD_ACCOUNT_ID")
    user_token = _require_env("FB_USER_ACCESS_TOKEN")

    fields = ",".join(
        [
            "ad_name",
            "ad_id",
            "spend",
            "impressions",
            "clicks",
            "ctr",
            "actions",
            "video_play_actions",
            "video_p25_watched_actions",
            "video_p50_watched_actions",
            "video_p75_watched_actions",
            "video_p100_watched_actions",
        ]
    )

    data = _get(
        f"{ad_account_id}/insights",
        params={
            "level": "ad",
            "fields": fields,
            "date_preset": date_preset,
            "access_token": user_token,
        },
    )

    records: list[dict] = []
    for row in data.get("data", []):
        ad_name = row.get("ad_name", "")
        impressions = float(row.get("impressions", 0) or 0)
        video_plays = _action_value(row.get("video_play_actions"), "video_view")
        base = video_plays or impressions

        def pct(field_name: str) -> float | str:
            watched = _action_value(row.get(field_name), "video_view")
            return round(100 * watched / base, 1) if base else ""

        actions = row.get("actions") or []
        records.append(
            {
                "script_id": _extract_script_id(ad_name),
                "hook_summary": ad_name,
                "ctr": row.get("ctr", ""),
                "retention_3s": round(100 * base / impressions, 1) if impressions and base else "",
                "retention_25": pct("video_p25_watched_actions"),
                "retention_50": pct("video_p50_watched_actions"),
                "retention_75": pct("video_p75_watched_actions"),
                "retention_100": pct("video_p100_watched_actions"),
                "comments": int(_action_value(actions, "comment")),
                "inbox": int(
                    _action_value(actions, "onsite_conversion.messaging_conversation_started_7d")
                ),
                "cost": row.get("spend", ""),
                "conversions": int(
                    _action_value(actions, "omni_purchase")
                    or _action_value(actions, "onsite_conversion.purchase")
                    or _action_value(actions, "onsite_conversion.messaging_order_created_v2")
                ),
            }
        )

    return records


def write_ad_performance_csv(records: list[dict]) -> Path:
    AD_PERFORMANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AD_PERFORMANCE_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AD_PERFORMANCE_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    return AD_PERFORMANCE_FILE


def refresh_user_token_hint() -> str:
    return (
        "FB_USER_ACCESS_TOKEN chỉ sống ~60 ngày. Làm mới bằng cách gọi lại "
        "GET /oauth/access_token?grant_type=fb_exchange_token&client_id={FB_APP_ID}"
        "&client_secret={FB_APP_SECRET}&fb_exchange_token={FB_USER_ACCESS_TOKEN hiện tại} "
        "trước khi token hết hạn, rồi cập nhật lại .env. Xem docs/facebook-graph-api-setup.md."
    )
