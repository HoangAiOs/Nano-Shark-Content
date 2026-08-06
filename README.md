# Nano Shark Cartilage — Content Research & Ad Script Agent

Agent tự động hóa quy trình nghiên cứu insight khách hàng và viết kịch bản video
quảng cáo Facebook cho sản phẩm **Nano Premium Shark Cartilage** (thực phẩm bảo vệ
sức khỏe xương khớp), dành cho nhóm khách hàng **trên 30 tuổi đang gặp vấn đề đau
nhức xương khớp**.

Xây dựng trên [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)
(Python) — agent có sẵn các tool `web_search`, `web_fetch`, `Read`, `Write` để tự
nghiên cứu và ghi file, không cần bạn tự cào dữ liệu web.

Toàn bộ quy trình gồm 7 bước, chạy độc lập từng bước qua command line để bạn kiểm
tra kết quả trước khi đi tiếp.

---

## 1. Giới hạn quan trọng cần biết trước

Agent **không tự đăng nhập được vào Facebook cá nhân/page** (Meta chặn truy cập tự
động). Vì vậy:

- **Google/YouTube/Facebook Group công khai**: agent tự tìm kiếm và đọc nội dung
  công khai — làm được trực tiếp. Với Facebook Group, agent chỉ lấy được phần nội
  dung xuất hiện công khai trong kết quả tìm kiếm hoặc trang không yêu cầu đăng
  nhập — bài viết trong group kín/yêu cầu đăng nhập sẽ tự động bị bỏ qua.
- **Inbox/comment trên page của bạn**: hiện đang **tạm bỏ qua** theo yêu cầu — khi
  nào có, xuất dữ liệu (từ Meta Business Suite, hoặc Facebook Graph API) ra file
  CSV theo đúng schema ở mục 3, đặt vào `data/inbox_comments.csv`, agent sẽ tự
  động dùng thêm nguồn này ở lần chạy `research` tiếp theo (không cần sửa code).
- **Số liệu quảng cáo (CTR, retention, chi phí...)**: tương tự, bạn xuất từ Meta Ads
  Manager ra CSV theo schema ở mục 3, dùng cho bước `analyze-feedback`.

---

## 2. Cài đặt

Yêu cầu: **Python 3.10+** (Claude Agent SDK không chạy được trên 3.9 trở xuống).

> ⚠️ Máy Mac dùng để dựng project này chỉ có sẵn Python 3.9.6 (bản đi kèm Command
> Line Tools) và chưa cài Homebrew. Nếu máy bạn cũng đang ở tình trạng tương tự,
> kiểm tra bằng `python3 --version` trước — nếu dưới 3.10, cài thêm bằng 1 trong 2
> cách sau trước khi chạy các lệnh bên dưới:
>
> - **Cách nhanh nhất — dùng [uv](https://docs.astral.sh/uv/):**
>   ```bash
>   curl -LsSf https://astral.sh/uv/install.sh | sh
>   cd "Hoang Ai Os/agents/nano-shark-content-agent"
>   uv python install 3.12
>   uv venv --python 3.12 .venv
>   source .venv/bin/activate
>   ```
>   (uv tự tải Python 3.12 về, không cần Homebrew hay quyền admin)
> - **Hoặc cài Python trực tiếp** từ [python.org/downloads](https://www.python.org/downloads/)
>   rồi dùng đúng bản đó thay cho `python3` ở bước tạo venv bên dưới (vd `python3.12 -m venv .venv`).

```bash
cd "Hoang Ai Os/agents/nano-shark-content-agent"
python3 -m venv .venv          # đảm bảo python3 ở đây là bản 3.10+
source .venv/bin/activate
pip install -r requirements.txt
```

> Claude Agent SDK đã gói sẵn binary Claude Code cần thiết bên trong package Python
> — bạn **không cần** cài thêm Node.js hay Claude Code CLI riêng.

### Cấu hình API key

Lấy API key tại [Claude Console](https://platform.claude.com/), sau đó:

```bash
cp .env.example .env
# rồi mở .env và điền key thật vào ANTHROPIC_API_KEY=
```

Hoặc export trực tiếp trong terminal (không cần file `.env`):

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxx...
```

---

## 3. Chuẩn bị dữ liệu input

### a. File inbox/comment (dùng ở bước `research`)

Xuất dữ liệu inbox và comment trên page thành file CSV, lưu tại:
`data/inbox_comments.csv`

Schema bắt buộc (đúng tên cột):

| Cột | Mô tả |
|---|---|
| `source` | Nguồn dữ liệu, vd: "Facebook Page", "Inbox" |
| `author` | Tên người bình luận/nhắn tin (có thể để "Ẩn danh" nếu không muốn lưu tên thật) |
| `content` | Nội dung nguyên văn — quan trọng nhất |
| `date` | Ngày, định dạng `YYYY-MM-DD` |
| `type` | `comment` hoặc `inbox` |
| `post_url` | Link bài viết nếu có (để trống nếu là inbox) |

Xem file mẫu tại `data/inbox_comments.sample.csv` để biết định dạng chính xác.
**Nếu chưa có file `data/inbox_comments.csv`, agent sẽ tự động bỏ qua nguồn này**
(không dùng file mẫu để giả làm dữ liệu thật) — chỉ nghiên cứu từ Google, YouTube,
Facebook Group công khai. Khi nào bạn có dữ liệu thật, thêm file này vào và chạy
lại `research` là agent sẽ tự dùng thêm, không cần sửa code.

### b. File số liệu quảng cáo (dùng ở bước `analyze-feedback`)

Sau khi quay và chạy quảng cáo cho các kịch bản, xuất số liệu ra file CSV, lưu tại:
`data/ad_performance.csv`

Schema bắt buộc:

| Cột | Mô tả |
|---|---|
| `script_id` | Mã kịch bản, khớp với tên file — vd `01` ứng với `script_01.md` |
| `hook_summary` | Tóm tắt hook đã dùng (giúp bạn tự đối chiếu khi đọc bảng) |
| `ctr` | Click-through rate (%) |
| `retention_3s` | % người xem còn lại tại giây thứ 3 |
| `retention_25` | % người xem còn lại tại mốc 25% video |
| `retention_50` | % người xem còn lại tại mốc 50% video |
| `retention_75` | % người xem còn lại tại mốc 75% video |
| `retention_100` | % người xem xem hết video |
| `comments` | Số lượng comment |
| `inbox` | Số lượng inbox nhận được |
| `cost` | Chi phí quảng cáo (VNĐ) |
| `conversions` | Số đơn hàng/chuyển đổi |

Xem file mẫu tại `data/ad_performance.sample.csv`.

### c. Tự động lấy dữ liệu qua Facebook Graph API (khuyên dùng lâu dài)

Thay vì export tay 2 file CSV ở trên, có thể kết nối trực tiếp Facebook Graph
API để agent tự động lấy comment công khai + số liệu quảng cáo. Xem hướng dẫn
đầy đủ tại [`docs/facebook-graph-api-setup.md`](docs/facebook-graph-api-setup.md).

Sau khi đã có `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`, `FB_USER_ACCESS_TOKEN`,
`FB_AD_ACCOUNT_ID` trong `.env`, chạy:

```bash
python -m agent.cli sync-facebook
```

Lệnh này ghi đè `data/inbox_comments.csv` và `data/ad_performance.csv` bằng dữ
liệu thật mới nhất từ Facebook. Giới hạn cần biết:

- **Đọc comment cần quyền `pages_read_user_content`** — quyền này thường cần
  nộp App Review cho Meta mới dùng ở mức Advanced Access (xem mục "Bước 4.5"
  trong file hướng dẫn). Trước khi được duyệt, lệnh `sync-facebook` sẽ báo lỗi
  ở phần comment nhưng vẫn chạy được phần ads bình thường.
- **Không lấy được tin nhắn Messenger (inbox)** qua API — giới hạn chính sách
  của Meta, vẫn cần export tay định kỳ nếu cần dữ liệu này.
- **Ghép `script_id` cho ads** dựa trên tên quảng cáo trong Ads Manager — đặt
  tên ad chứa `script_01`, `kich_ban_02`... thì mới ghép đúng; ads không đúng
  quy ước sẽ để trống `script_id` (không đoán bừa).
- **`FB_USER_ACCESS_TOKEN` sống ~60 ngày**, không vĩnh viễn như page token —
  cần làm mới định kỳ, xem `refresh_user_token_hint()` trong
  `agent/lib/meta_client.py`.

---

## 4. Cách chạy

Luôn chạy từ thư mục gốc project (`nano-shark-content-agent/`), với venv đã activate.

```bash
# (Tùy chọn) Đồng bộ dữ liệu thật từ Facebook trước — xem mục 3c
python -m agent.cli sync-facebook

# Bước 1 — Research: thu thập dữ liệu thô (Google/YouTube + file inbox/comment)
python -m agent.cli research

# Bước 2 — Synthesize: tổng hợp Voice of Customer
python -m agent.cli synthesize

# Bước 3 — Filter insights: lọc 5-7 insight ưu tiên
python -m agent.cli filter-insights

# Bước 4 — Write scripts: viết 10 kịch bản video (fetch trang sản phẩm để lấy đúng thông tin)
python -m agent.cli write-scripts

# Bước 5 — Score: chấm điểm và chọn top 5 kịch bản
python -m agent.cli score
```

Hoặc chạy liền 5 bước trên bằng một lệnh:

```bash
python -m agent.cli all
```

Sau khi quay video và chạy quảng cáo thực tế, nhập số liệu vào `data/ad_performance.csv`
rồi chạy:

```bash
# Bước 6 — Analyze feedback: đối chiếu số liệu thực tế với từng kịch bản
python -m agent.cli analyze-feedback

# Bước 7 — Optimize: đề xuất chỉnh sửa/kịch bản mới dựa trên feedback
python -m agent.cli optimize
```

**Hai bước này chạy lại được nhiều lần** — mỗi khi có thêm số liệu quảng cáo mới,
cập nhật `data/ad_performance.csv` rồi chạy lại `analyze-feedback` và `optimize`.
Bước `optimize` sẽ nối thêm mục mới vào `data/optimized_scripts.md` (giữ lại lịch
sử các vòng tối ưu trước, không xóa).

---

## 4b. Web Dashboard (Nano Shark Content OS)

Ngoài CLI, project có 1 dashboard web trực quan hóa toàn bộ dữ liệu trên —
12 module lấy cảm hứng từ mô hình "AI Business OS", 5 module đầu dùng lại dữ
liệu CLI đã có, các module còn lại theo dõi thủ công hoặc gọi Claude Haiku
(giá rẻ) cho việc gợi ý ý tưởng.

```bash
python -m webapp.main
# hoặc: ./run_webapp.sh
```

Mở `http://127.0.0.1:8811`.

| Module | Loại | Ghi chú |
|---|---|---|
| Não Marketing | Gọi AI thật (Haiku) | Nhập goal → sinh 10 ý tưởng bám insight |
| Research | Đọc dữ liệu | Từ `raw_research.json` |
| Tiếng nói khách hàng | Đọc dữ liệu | Từ `voice_of_customer.md` |
| Belief Map | Đọc dữ liệu (remap tay) | Từ 6 nhóm VoC → 4 nhóm niềm tin |
| Ngân hàng Insight | Đọc + ghi trạng thái | Tick trạng thái khai thác từng insight |
| Ý tưởng hôm nay | Đọc + ghi trạng thái | Tick đã quay/chưa quay từng kịch bản |
| Cân đối danh mục | Đọc dữ liệu (gán tay pillar) | Phân bố 10 kịch bản theo 4 nhóm mục tiêu |
| Bản đồ nội dung | Đọc dữ liệu | Insight → kịch bản đã khai thác |
| Kiến tạo 1.000 video | Gọi AI thật (Haiku) | Bung 1 insight → 10 góc nhìn, có cache |
| Upload video | Lưu file | **Chưa có auto-edit thật** — chỉ lưu vào `data/video_uploads/` |
| Hàng đợi video | Theo dõi thủ công | Tick tay từng kênh đã đăng — **không tự động đăng** |
| Ads Autopilot | Báo cáo (đọc `ad_performance.csv`) | Chỉ **đề xuất** tạm dừng khi CPL cao — **không tự bật/tắt chi tiêu thật** |

Toàn bộ trạng thái UI (goal, tick đã quay, triage insight, cache góc nhìn) lưu
tại `data/web_state.json`.

---

## 5. Kết quả từng bước nằm ở đâu

| Bước | File output |
|---|---|
| research | `data/raw_research.json` |
| synthesize | `data/voice_of_customer.md` |
| filter-insights | `data/priority_insights.md` |
| write-scripts | `data/scripts/script_01.md` → `script_10.md` + `data/scripts/index.md` |
| score | `data/scores.md` |
| analyze-feedback | `data/feedback_analysis.md` |
| optimize | `data/optimized_scripts.md` |

Tất cả đều là file JSON/Markdown thuần — mở trực tiếp bằng bất kỳ trình soạn thảo
nào để xem, chỉnh sửa tay nếu cần trước khi chạy bước tiếp theo. Các file trong
`data/scripts/` viết theo định dạng chuẩn, có thể copy trực tiếp cho đội quay
video dùng.

---

## 6. Cấu trúc code (để bạn dễ chỉnh sửa từng phần)

```
nano-shark-content-agent/
├── agent/
│   ├── cli.py              # Entry point — định nghĩa các command
│   ├── config.py           # Đường dẫn file, tên sản phẩm, system prompt chung
│   ├── lib/
│   │   └── claude_client.py  # Wrapper gọi Claude Agent SDK
│   └── phases/
│       ├── research.py           # Bước 1
│       ├── voice_of_customer.py  # Bước 2
│       ├── insight_filter.py     # Bước 3
│       ├── scripts_writer.py     # Bước 4
│       ├── scorer.py             # Bước 5
│       ├── feedback_analyzer.py  # Bước 6
│       └── optimizer.py          # Bước 7
├── data/                    # Toàn bộ input/output — không commit dữ liệu thật lên git
├── requirements.txt
└── .env.example
```

Mỗi phase là 1 file độc lập trong `agent/phases/` — chỉnh sửa prompt hoặc logic
của bước nào, chỉ cần sửa đúng file đó, không ảnh hưởng các bước khác. Prompt gốc
dùng chung (persona, nguyên tắc viết) nằm ở `BASE_SYSTEM_PROMPT` trong `agent/config.py`.

Muốn đổi model (vd dùng Sonnet để tiết kiệm chi phí thay vì Opus), sửa biến `MODEL`
trong `agent/config.py`.

---

## 7. Xử lý sự cố thường gặp

- **"API key not found"** — SDK không tự đọc file `.env`, cần export
  `ANTHROPIC_API_KEY` trong terminal đang chạy lệnh, hoặc cài `python-dotenv`
  (đã có trong `requirements.txt`) và tạo file `.env` từ `.env.example`.
- **Agent chạy nhưng không thấy file output** — kiểm tra lại log in ra màn hình,
  agent có thể dừng giữa chừng nếu hết `max_turns`. Chạy lại lệnh, hoặc tách nhỏ
  yêu cầu hơn nếu vẫn lặp lại.
- **Muốn kiểm tra kết quả từng bước trước khi tốn thêm chi phí API** — luôn chạy
  từng bước riêng lẻ (không dùng `all`) và đọc kỹ file output trước khi qua bước
  tiếp theo, đặc biệt là `priority_insights.md` trước khi chạy `write-scripts`
  (bước tốn nhiều token nhất).
