# 🛒 EcomOmniTool - Phần Mềm Tự Động Hóa & Tối Ưu Bán Hàng Đa Sàn Thương Mại Điện Tử

![EcomOmniTool Banner](https://img.shields.io/badge/Shopee-Auto%20Sales%20Suite-EE4D2D?style=for-the-badge&logo=shopee&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Google Gemini AI](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)

**EcomOmniTool** là giải pháp phần mềm tự động hóa toàn diện all-in-one dành cho các nhà bán hàng (Sellers) và nhà sáng tạo nội dung (Creators) trên các sàn Thương Mại Điện Tử (Shopee, TikTok Shop, Lazada, Facebook Reels). 

Được trang bị trí tuệ nhân tạo **Google Gemini AI** và công nghệ điều khiển trình duyệt tự động **Playwright**, EcomOmniTool giúp bạn vận hành hàng chục gian hàng cùng lúc mà không tốn công sức.

---

## 🌟 Các Tính Năng Nổi Bật

### 1. 🎬 Tự Động Đăng Video Hàng Loạt (Shopee Video / TikTok / Reels)
- Tự động quét toàn bộ kho video từ thư mục máy tính.
- Gắn thẻ sản phẩm Shopee Video chính xác, tự động chèn hashtag & caption chuẩn SEO.
- Hỗ trợ chạy đa tài khoản luân phiên với cơ chế chống checkpoint thông minh.

### 2. 🚀 Tự Động Đẩy Sản Phẩm 4H (Auto Product Booster)
- Tự động kích hoạt tính năng Đẩy Sản Phẩm 4 tiếng/lần của Shopee.
- Quét và hiển thị 100% danh mục sản phẩm thực tế từ Kênh Người Bán.
- Chế độ **Chạy Tất Cả Shop đồng thời** hoặc chọn từng sản phẩm mục tiêu theo ý muốn.
- Hỗ trợ mở trực tiếp trình duyệt Kênh Người Bán chỉ với 1 click.

### 3. ⚡ Tự Động Tạo Flash Sale Của Shop
- Tự động tìm kiếm các khung giờ trống trong ngày trên Kênh Marketing Shopee.
- Tự động tạo chiến dịch Flash Sale với mức giảm giá (%) và số lượng kho tùy chỉnh.
- Hỗ trợ chọn danh sách sản phẩm chỉ định hoặc tự động chọn các mặt hàng bán chạy.

### 4. 🤖 AI Sales Consultant - Trực Chat & Tư Vấn Khách 24/7
- Tích hợp **Google Gemini AI 1.5 Flash** phản hồi tin nhắn khách hàng trong 15 giây.
- Kịch bản bán hàng thông minh: Tư vấn size quần áo chuẩn theo chiều cao/cân nặng, kiểm tra tồn kho, hướng dẫn lấy mã giảm giá / freeship.
- Bảng **Live Chat History (Real-time)** theo dõi lịch sử tư vấn trực tiếp.
- Tích hợp công cụ **🧪 Test AI Chat** trực tiếp trên giao diện để kiểm tra câu trả lời ngay lập tức.

### 5. 📦 Clone & Sao Chép Sản Phẩm Đa Sàn (Product Scraper & Copier)
- Quét thông tin sản phẩm chuẩn từ link Shopee, TikTok Shop, Taobao, 1688.
- Tự động tải ảnh, video mô tả, bảng phân loại hàng và giá bán.
- Đăng tải lại sang gian hàng của bạn với 1 click.

### 6. ✨ AI SEO Content Rewriter & Đóng Khung Ảnh 1:1
- **AI Rewriter**: Viết lại Tiêu đề và Mô tả sản phẩm độc quyền, chống trùng lặp thuật toán sàn.
- **Image Styler**: Tự động đóng khung viền Flash Sale, gắn nhãn Freeship Extra, Voucher Hot chuẩn tỷ lệ vuông 1:1.

### 7. ⏰ Bộ Hẹn Giờ Khung Giờ Vàng (Golden Hours Cron Scheduler)
- Đặt lịch tự động đăng video, đẩy sản phẩm, bật Flash Sale vào các khung giờ cao điểm (11h30 trưa, 20h00 tối).

---

## 🛠️ Cài Đặt & Hướng Dẫn Sử Dụng

### 1. Yêu Cầu Hệ Thống
- Hệ điều hành: **Windows 10 / 11** (hoặc macOS / Linux).
- **Python 3.10+**.
- Trình duyệt **Google Chrome** (khuyên dùng).

### 2. Cài Đặt Môi Trường
```bash
# 1. Clone repository về máy
git clone https://github.com/toantrn565-design/EcomOmniTool.git
cd EcomOmniTool

# 2. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

# 3. Cài đặt trình duyệt Playwright
playwright install chromium
```

### 3. Khởi Chạy Ứng Dụng
- **Cách 1**: Nhấp đúp vào file `KHOI_CHAY_TOOL.bat` (hoặc `KHOI_CHAY_AN.vbs`).
- **Cách 2**: Chạy qua lệnh terminal:
```bash
python main.py
```
- Trình duyệt sẽ tự động mở giao diện điều khiển tại địa chỉ: **`http://127.0.0.1:8030`**.

---

## 📁 Cấu Trúc Dự Án

```
EcomOmniTool/
├── backend/
│   ├── app.py                   # FastAPI REST API & WebSocket Controller
│   ├── video_automation.py      # Playwright Automation Engine đa nền tảng
│   ├── boost_automation.py      # Module Tự động Đẩy sản phẩm 4h & Quét Seller API
│   ├── flashsale_automation.py  # Module Tạo Flash Sale Kênh Marketing
│   ├── ai_chat_agent.py         # Module AI Sales Consultant 24/7 (Gemini AI)
│   ├── scraper.py               # Module Quét và bóc tách dữ liệu sản phẩm
│   ├── uploader.py              # Module Đăng tải sản phẩm tự động
│   ├── image_styler.py          # Module Đóng khung ảnh & thiết kế viền 1:1
│   └── cron_scheduler.py        # Module Lên lịch hẹn giờ khung giờ vàng
├── frontend/
│   ├── index.html               # Giao diện điều khiển trung tâm (Dashboard)
│   ├── style.css                # Dark Mode Glassmorphism UI Style
│   └── app.js                   # Xử lý logic giao diện & Real-time Polling
├── config/
│   ├── accounts.example.json    # Mẫu cấu hình tài khoản Shop
│   └── settings.example.json    # Mẫu cấu hình API Key & Cài đặt chung
├── main.py                      # Điểm khởi chạy chính của ứng dụng
├── requirements.txt             # Danh sách thư viện Python cần thiết
├── KHOI_CHAY_TOOL.bat           # Script khởi chạy nhanh 1 click
└── README.md                    # Tài liệu hướng dẫn sử dụng
```

---

## 🔒 Bảo Mật & An Toàn

- Mọi thông tin đăng nhập, Profile Cookies và API Keys đều được lưu trữ hoàn toàn **cục bộ (Local) trên máy tính của bạn**.
- Thư mục `.gitignore` được thiết lập chặt chẽ để đảm bảo không bao giờ bị rò rỉ dữ liệu tài khoản khi đưa lên Git.

---

## 📄 Bản Quyền & Giấy Phép
Phát triển và phân phối bởi **JAVIS AI WORKFORCE & EcomOmniTool Team**.
Được phát hành dưới giấy phép **MIT License**.
