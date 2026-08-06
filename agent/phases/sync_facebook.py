"""Đồng bộ dữ liệu thật từ Facebook: comment công khai + số liệu quảng cáo."""

from agent.config import AD_PERFORMANCE_FILE, INBOX_COMMENTS_FILE
from agent.lib import meta_client
from agent.lib.meta_client import MetaClientError


def run() -> None:
    print("=== Đồng bộ comment công khai từ Facebook Page ===")
    try:
        comments = meta_client.fetch_page_comments()
        meta_client.write_inbox_comments_csv(comments)
        print(f"✅ Lấy được {len(comments)} comment, đã ghi vào {INBOX_COMMENTS_FILE}")
    except MetaClientError as exc:
        print(f"❌ Lỗi khi lấy comment: {exc}")

    print("\n=== Đồng bộ số liệu quảng cáo từ Facebook Ads ===")
    try:
        ads = meta_client.fetch_ad_insights()
        meta_client.write_ad_performance_csv(ads)
        unmatched = sum(1 for a in ads if not a["script_id"])
        print(f"✅ Lấy được {len(ads)} ad, đã ghi vào {AD_PERFORMANCE_FILE}")
        if unmatched:
            print(
                f"⚠️  {unmatched}/{len(ads)} ad không ghép được script_id (tên ad không chứa "
                f"số thứ tự kịch bản, vd '01', 'script_02'...) — cột script_id để trống, "
                f"bạn tự đối chiếu tay trong file CSV."
            )
    except MetaClientError as exc:
        print(f"❌ Lỗi khi lấy số liệu quảng cáo: {exc}")
        print(f"   Gợi ý: {meta_client.refresh_user_token_hint()}")
