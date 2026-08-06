# Checklist Deploy Kịch Bản — Nano Premium Shark Cartilage

> Cập nhật tay file này khi từng kịch bản đi qua các bước. Xem chi tiết kịch bản
> tại `data/scripts/script_XX.md`, điểm số/lý do chọn tại `data/scores.md`.
>
> **Quan trọng:** Tên ad trên Ads Manager phải chứa đúng số kịch bản (vd
> `script_09`, `kich_ban_04`) — `sync-facebook` chỉ ghép được số liệu nếu đặt
> tên đúng quy ước này.

---

## Bảng theo dõi tổng quan

| # | Kịch bản | Điểm | Ưu tiên | Quay | Dựng | Duyệt tuân thủ | Đăng Ads | Ad Name đã đặt đúng | Đang chạy |
|---|---|---|---|---|---|---|---|---|---|
| 09 | Cô chú bỏ 2 triệu ra thì có quyền đòi xem giấy tờ | 35 | 🥇 Top 1 | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 04 | Sợ mất tiền, không sợ tốn tiền | 35 | 🥇 Top 1 | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 07 | Đang uống glucosamine rồi, vậy đã đủ chưa? | 34 | 🥈 Top 2 | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 08 | Một ký cua tuyết chỉ lấy ra được 10 gram | 34 | 🥈 Top 2 | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 10 | 39 tuổi đã cứng khớp buổi sáng | 34 | 🥈 Top 2 | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 01 | Uống thuốc 5 năm rồi mà vẫn cứng 10 ngón tay | 32 | Backup | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 02 | Điều cô chú sợ không phải cái đầu gối | 32 | Backup | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 03 | Biết là thoái hóa rồi, giờ uống gì? | 32 | Backup | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 05 | Mổ rồi mà bên kia còn đau hơn | 31 | Backup | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 06 | 3 giờ sáng, chỉ còn mình với cái đầu gối | 30 | Backup | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |

**Gợi ý thứ tự làm:** quay 5 kịch bản Top trước (09, 04, 07, 08, 10) — đã đủ đa
dạng góc tiếp cận (giấy tờ / giá / CTA nhẹ / phóng sự nguyên liệu / nhóm tuổi
trẻ hơn). Chỉ quay thêm nhóm Backup nếu có ngân sách/thời gian dư, hoặc sau khi
có số liệu thật từ `analyze-feedback` cho thấy cần thêm góc tiếp cận khác.

---

## Checklist tuân thủ pháp lý (bắt buộc — áp dụng từng kịch bản trước khi đăng)

Đánh dấu đủ cả 7 mục sau mới được đăng quảng cáo, dựa theo
`data/product_reference.md` và `data/scripts/index.md`:

- [ ] Chỉ đọc đúng **1 câu công dụng đã duyệt**: *"Bổ sung glucosamin và bột
      chiết xuất sụn cá mập hỗ trợ tốt cho khớp"* — không thêm/bớt chữ.
- [ ] Có đọc/hiện **cảnh báo bắt buộc** cuối video: *"Thực phẩm này không phải
      là thuốc và không có tác dụng thay thế thuốc chữa bệnh."*
- [ ] Không gọi sản phẩm là **"thuốc"** ở bất kỳ đoạn nào trong video đã dựng.
- [ ] Không có cảnh **trước/sau kiểu khỏi bệnh**, không hứa hẹn thời gian cụ
      thể ("hết đau sau X ngày").
- [ ] Không dùng **feedback/testimonial dựng** — nếu có khách hàng thật xuất
      hiện, phải là người thật, đồng ý quay, không đọc kịch bản do agent viết
      thay lời họ.
- [ ] Nếu kịch bản có cảnh quay giấy tờ (**#09** bắt buộc) — giấy tờ trong
      khung hình là bản thật/scan rõ, không dùng ảnh chụp mờ hoặc chỉnh sửa.
- [ ] Kênh đăng nằm trong phạm vi **Giấy xác nhận nội dung quảng cáo số
      2016/2022/XNQC-ATTP** (Facebook/mạng xã hội — đã trong phạm vi cho phép).

---

## Checklist kỹ thuật khi đăng lên Ads Manager

- [ ] Tên ad chứa đúng số kịch bản (vd `script_09_v1`) để `sync-facebook` ghép
      được `script_id` tự động — xem quy ước tại `agent/lib/meta_client.py`.
- [ ] Ghi lại ngày bắt đầu chạy vào cột "Đăng Ads" ở bảng trên (dùng để đối
      chiếu khi phân tích feedback sau này).
- [ ] Ngân sách ban đầu nên chia đều cho 5 kịch bản Top để so sánh công bằng,
      tránh dồn ngân sách lệch khiến số liệu không so sánh được.

---

## Sau khi chạy quảng cáo

```bash
# Lấy số liệu thật (cần tên ad đã đặt đúng quy ước ở trên)
python -m agent.cli sync-facebook

# Phân tích kịch bản nào hiệu quả, tại sao
python -m agent.cli analyze-feedback

# Đề xuất tối ưu / kịch bản mới dựa trên số liệu thật
python -m agent.cli optimize
```

Chạy lại `analyze-feedback` + `optimize` định kỳ (vd mỗi tuần) khi có thêm số
liệu mới — `optimize` sẽ tự nối thêm lịch sử vào `data/optimized_scripts.md`,
không ghi đè vòng trước.
