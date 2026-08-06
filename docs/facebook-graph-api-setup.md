# Hướng dẫn kết nối Facebook Graph API (dùng lâu dài)

Mục tiêu: lấy **Page Access Token không hết hạn** + (tùy chọn) **Ad Account ID**
để agent tự động kéo comment công khai và số liệu quảng cáo, thay vì bạn phải
export CSV thủ công mỗi lần.

Phần này bạn phải tự làm trên giao diện Meta (cần đăng nhập tài khoản Facebook
của bạn — tôi không đăng nhập thay được). Sau khi có token, đưa lại cho tôi để
viết code kết nối.

---

## Giới hạn thật cần biết trước (đọc trước khi làm)

| Loại dữ liệu | Lấy được qua API không? | Điều kiện |
|---|---|---|
| **Comment công khai** trên bài đăng của Page | ✅ Có, ổn định lâu dài | Quyền `pages_read_engagement`, `pages_read_user_content` |
| **Số liệu quảng cáo** (CTR, retention, chi phí...) | ✅ Có, ổn định lâu dài | Quyền `ads_read`, cần Ad Account ID |
| **Inbox/tin nhắn Messenger** | ⚠️ Rất hạn chế | Meta chỉ cho lấy hội thoại khách **chủ động nhắn trong 24-72h gần nhất** (chính sách Messenger Platform), và quyền `pages_messaging` thường cần qua App Review nếu dùng ngoài phạm vi admin/dev test. **Không có cách lấy toàn bộ lịch sử inbox cũ qua API.** |

→ Hướng thực tế: tự động hóa **comment + số liệu quảng cáo**. Với inbox, vẫn nên
định kỳ export tay từ Meta Business Suite (đỡ hơn vì có thể làm 1 lần/tuần thay
vì mỗi lần chạy agent).

---

## Bước 1 — Tạo Meta App

1. Vào [developers.facebook.com](https://developers.facebook.com/) → đăng nhập
   bằng tài khoản Facebook quản lý Page.
2. **My Apps** → **Create App**.
3. Chọn loại app: **Business**.
4. Đặt tên app (vd "Nano Shark Content Agent"), liên kết với Business Portfolio
   của bạn nếu có (Business Manager), hoặc để Meta tự tạo mới.

## Bước 2 — Lấy Page Access Token không hết hạn

Đây là phần quan trọng nhất — làm đúng thứ tự 3 bước sau để token **không tự
hết hạn** (miễn bạn không đổi mật khẩu Facebook hoặc gỡ app):

### 2.1. Lấy short-lived User Access Token
- Vào [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
- Chọn đúng App vừa tạo ở góc trên.
- Nút **Get Token → Get User Access Token**, tick các quyền:
  `pages_show_list`, `pages_read_engagement`, `pages_read_user_content`,
  `ads_read` (nếu cần số liệu quảng cáo), `business_management`.
- Copy token vừa tạo ra (chỉ sống ~1-2 giờ, chưa dùng được lâu dài).

### 2.2. Đổi sang long-lived User Access Token (sống 60 ngày)
Lấy **App ID** và **App Secret** tại App Dashboard → Settings → Basic, rồi gọi:

```
GET https://graph.facebook.com/v21.0/oauth/access_token
    ?grant_type=fb_exchange_token
    &client_id={app-id}
    &client_secret={app-secret}
    &fb_exchange_token={short-lived-token-vừa-lấy}
```

Có thể gọi trực tiếp bằng trình duyệt (dán URL đã điền đủ tham số) hoặc `curl`.
Kết quả trả về 1 access_token mới — đây là long-lived user token.

### 2.3. Đổi sang Page Access Token (không hết hạn)
Dùng long-lived user token ở trên gọi:

```
GET https://graph.facebook.com/v21.0/{page-id}?fields=access_token
    &access_token={long-lived-user-token}
```

`{page-id}` xem tại Page → Settings → About, hoặc từ URL trang. Kết quả trả về
`access_token` — **đây là Page Access Token không hết hạn** (miễn bạn vẫn còn
là admin của Page và không đổi mật khẩu/gỡ app).

## Bước 3 — Lấy Ad Account ID (nếu cần số liệu quảng cáo)

Vào [business.facebook.com/settings](https://business.facebook.com/settings) →
**Ad Accounts** → copy ID (dạng `act_1234567890`).

## Bước 4 — App Review (chỉ cần nếu vướng)

Nếu bạn dùng chính tài khoản admin của Page/Business để lấy token (đúng như
hướng dẫn trên), phần lớn trường hợp **không cần App Review** — Meta cho phép
admin/developer/tester của app dùng các quyền cơ bản (`pages_read_engagement`,
`ads_read`) ở chế độ Development ngay lập tức, miễn app đó và Page đó thuộc
cùng Business Manager của bạn. Chỉ cần App Review nếu bạn muốn mở rộng cho
người khác dùng app này, hoặc dùng cho Page không phải của bạn.

## Bước 4.5 — Xin Advanced Access cho `pages_read_user_content` (nếu bị chặn đọc comment)

Nếu gọi API đọc comment bị lỗi `(#10) This endpoint requires the
'pages_read_user_content' permission...`, nghĩa là quyền này đang ở mức
**Standard Access** (chỉ dùng thử được với chính bạn/tester) và cần nộp **App
Review** để lên **Advanced Access** mới dùng được thật.

1. Vào App Dashboard → sidebar trái → **"Xét duyệt"** → **"Quyền và tính năng"**
   (Permissions and Features).
2. Tìm `pages_read_user_content` → bấm **"Yêu cầu quyền truy cập nâng cao"**
   (Request Advanced Access).
3. Meta thường yêu cầu:
   - **Business Verification** cho Business Manager (nếu chưa xác minh) — làm
     tại business.facebook.com/settings/security, cần giấy tờ doanh nghiệp.
   - **Screencast** quay màn hình demo: gọi API lấy comment và cho thấy dữ liệu
     đó được dùng để làm gì (vd: hiện luồng agent đọc comment → tổng hợp insight).
   - Giải thích bằng văn bản mục đích dùng quyền này.
   - Link Chính sách quyền riêng tư (Privacy Policy) của app/doanh nghiệp.
4. Nộp và chờ Meta duyệt — thường **3-5 ngày làm việc**, có thể lâu hơn.
5. Trong lúc chờ duyệt, dùng tạm `data/inbox_comments.csv` export tay để không
   bị chặn tiến độ.

## Bước 5 — Đưa lại cho tôi

Gửi (dán vào chat hoặc để tôi lưu vào `.env` như đã làm với API key Anthropic):

- `FB_PAGE_ID`
- `FB_PAGE_ACCESS_TOKEN`
- `FB_AD_ACCOUNT_ID` (nếu có, dạng `act_...`)

Sau đó tôi sẽ viết `agent/lib/meta_client.py` gọi Graph API + Marketing API,
tự động ghi ra đúng schema đang dùng (`data/inbox_comments.csv` cho comment,
`data/ad_performance.csv` cho số liệu quảng cáo) — cắm thẳng vào pipeline agent
đã có, không cần sửa gì ở các bước research/analyze-feedback.
