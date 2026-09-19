import asyncio
import os
import sys
import json
import logging
import time
from typing import List, Dict, Any, Optional
import requests
from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger("AIChatAgent")

# Bộ nhớ lưu lịch sử tin nhắn tư vấn AI để hiển thị trực tiếp lên UI
chat_history_records: List[Dict[str, Any]] = []

def add_chat_record(shop_name: str, customer_msg: str, ai_reply: str, status: str = "Đã gửi"):
    record = {
        "id": f"msg_{int(time.time()*1000)}",
        "time": time.strftime("%H:%M:%S", time.localtime()),
        "date": time.strftime("%d/%m/%Y", time.localtime()),
        "shop_name": shop_name,
        "customer_message": customer_msg,
        "ai_reply": ai_reply,
        "status": status
    }
    chat_history_records.insert(0, record)
    if len(chat_history_records) > 200:
        chat_history_records.pop()
    return record

SYSTEM_SALES_PROMPT = """Bạn là Chuyên viên Tư vấn Bán hàng xuất sắc và tận tâm của Shop trên sàn Thương mại Điện tử (Shopee / TikTok Shop).
Nhiệm vụ của bạn là trả lời tin nhắn của khách hàng một cách tự nhiên, thân thiện, lễ phép (xưng Dạ/Em, gọi Anh/Chị hoặc Bạn) và ĐẶC BIỆT luôn hướng tới việc THÚC ĐẨY CHỐT ĐƠN (Call to Action).

Nguyên tắc trả lời:
1. Tư vấn size: Dựa vào chiều cao, cân nặng của khách để gợi ý size phù hợp nhất kèm lời chúc chu đáo.
2. Tình trạng hàng: Khẳng định shop luôn sẵn hàng tại kho, đóng gói kỹ càng gửi đi ngay trong ngày.
3. Thời gian giao hàng: Dự kiến 1-2 ngày (nội thành) hoặc 2-4 ngày (toàn quốc).
4. Mã giảm giá / Voucher: Hướng dẫn khách thu thập voucher ở đầu trang hoặc xem qua mục Shopee Video của Shop để nhận trợ giá 20%-50%.
5. Khép lại câu trả lời bằng lời kêu gọi đặt hàng sớm (VD: "Anh/Chị đặt sớm để shop gửi đơn đi trong ca hôm nay nhé ạ ❤️").
6. Trả lời ngắn gọn, súc tích (dưới 4 câu), dùng emoji sinh động, không dài dòng.
7. Nếu khách hàng có thái độ tức giận, khiếu nại hàng vỡ/hỏng hoặc đòi gặp chủ shop, hãy xoa dịu lịch sự và báo rằng quản lý shop sẽ liên hệ hỗ trợ ngay lập tức.
"""

SYSTEM_REWRITER_PROMPT = """Bạn là Chuyên gia Tối ưu SEO và Content Bán hàng E-Commerce (Shopee, TikTok Shop, Lazada).
Nhiệm vụ của bạn là viết lại Tiêu đề và Bài viết Mô tả sản phẩm từ dữ liệu thô cào được để:
1. Tiêu đề mới đạt chuẩn SEO: [Loại Sản Phẩm] + [Tên/Thương hiệu] + [Đặc điểm/Tính năng nổi bật] + [Công dụng chính] + [Từ khóa tìm kiếm hot].
2. Bài mô tả mới: Cấu trúc rõ ràng gồm các phần:
   - 🌟 ĐẶC ĐIỂM NỔI BẬT
   - 📋 THÔNG SỐ KỸ THUẬT / CHI TIẾT SẢN PHẨM
   - 💡 HƯỚNG DẪN SỬ DỤNG & BẢO QUẢN
   - 🛡️ CHÍNH SÁCH BẢO HÀNH & CAM KẾT CỦA SHOP
3. Tránh 100% việc trùng lặp câu chữ với bản gốc để không bị thuật toán sàn phạt copy sản phẩm.
4. Trả về kết quả dưới định dạng JSON:
{
  "title": "Tiêu đề chuẩn SEO mới",
  "description": "Nội dung mô tả mới có icon đẹp mắt"
}
"""

class AIProductRewriter:
    @staticmethod
    async def rewrite_product(
        title: str,
        description: str,
        api_key: Optional[str] = None,
        log_callback=None
    ) -> Dict[str, str]:
        """Viết lại Tiêu đề và Mô tả sản phẩm chuẩn SEO bằng AI."""
        if log_callback:
            await log_callback(f"Đang tối ưu nội dung AI cho sản phẩm: {title[:40]}...")

        if api_key and api_key.strip():
            try:
                # Gọi Gemini API
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key.strip()}"
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": f"{SYSTEM_REWRITER_PROMPT}\n\nSẢN PHẨM GỐC CẦN VIẾT LẠI:\nTiêu đề: {title}\nMô tả: {description[:1500]}"
                        }]
                    }],
                    "generationConfig": {
                        "response_mime_type": "application/json",
                        "temperature": 0.7
                    }
                }
                res = requests.post(endpoint, json=payload, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(raw_text)
                    if log_callback:
                        await log_callback("✅ AI đã tạo nội dung mới chuẩn SEO thành công!")
                    return {
                        "title": parsed.get("title", title),
                        "description": parsed.get("description", description)
                    }
            except Exception as e:
                logger.error(f"Lỗi gọi Gemini API: {e}")
                if log_callback:
                    await log_callback(f"⚠️ Không gọi được API ngoài: {e}. Sử dụng bộ biến đổi nội dung thông minh.")

        # Fallback Engine thông minh nếu chưa có API Key
        clean_title = title.replace("  ", " ").strip()
        new_title = f"[CHÍNH HÃNG] {clean_title} - Cao Cấp, Tiện Lợi & Độ Bền Cao"
        
        new_desc = f"""🔥 SIÊU PHẨM: {title.upper()} 🔥

🌟 ĐẶC ĐIỂM NỔI BẬT:
- Thiết kế hiện đại, thông minh, tối ưu cho trải nghiệm người dùng.
- Chất liệu cao cấp, độ bền vượt trội, an toàn tuyệt đối khi sử dụng.
- Sản phẩm được kiểm định chất lượng nghiêm ngặt trước khi xuất xưởng.

📋 THÔNG TIN CHI TIẾT SẢN PHẨM:
{description[:800]}

🛡️ CAM KẾT CỦA SHOP:
✅ Hàng chính hãng 100%, bảo hành đổi trả trong 7 ngày nếu lỗi từ nhà sản xuất.
✅ Đóng gói cẩn thận 3 lớp chống sốc, giao hàng siêu tốc toàn quốc.
✅ Hỗ trợ tư vấn và giải đáp thắc mắc 24/7 nhiệt tình.

👉 BẤM ĐẶT HÀNG NGAY HÔM NAY ĐỂ NHẬN ƯU ĐÃI VOUCHER TỐT NHẤT!"""

        return {
            "title": new_title[:120],
            "description": new_desc
        }


class AISalesConsultant:
    def __init__(self, profile_dir: str, shop_name: str = "Shop", api_key: Optional[str] = None):
        from backend.profile_utils import resolve_profile_path
        self.profile_dir = resolve_profile_path(profile_dir)
        os.makedirs(self.profile_dir, exist_ok=True)

        self.shop_name = shop_name
        self.api_key = api_key
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_running = False
        self.replied_message_ids = set()

    async def init_browser(self, headless: bool = True) -> BrowserContext:
        from backend.video_automation import cleanup_stale_profile
        cleanup_stale_profile(self.profile_dir)
        if not self.playwright:
            self.playwright = await async_playwright().start()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--start-maximized"
        ]

        launch_kwargs = {
            "user_data_dir": self.profile_dir,
            "headless": headless,
            "args": launch_args,
            "ignore_default_args": ["--enable-automation"]
        }
        if not headless:
            launch_kwargs["no_viewport"] = True
        else:
            launch_kwargs["viewport"] = {"width": 1280, "height": 850}

        for attempt in range(1, 4):
            try:
                cleanup_stale_profile(self.profile_dir)
                try:
                    self.context = await self.playwright.chromium.launch_persistent_context(
                        channel="chrome",
                        **launch_kwargs
                    )
                except Exception:
                    self.context = await self.playwright.chromium.launch_persistent_context(
                        **launch_kwargs
                    )
                break
            except Exception as e:
                if attempt == 3:
                    logger.error(f"Không thể khởi chạy chat agent browser: {e}")
                    raise e
                await asyncio.sleep(1)

        await self.context.add_init_script("delete navigator.__proto__.webdriver;")
        self.context.set_default_timeout(35000)
        return self.context

    async def close_browser(self):
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            logger.error(f"Lỗi đóng browser chat agent: {e}")
            self.context = None
            self.playwright = None

    async def generate_reply(self, customer_message: str, product_context: str = "") -> str:
        """Sinh câu trả lời tự động bằng AI."""
        if self.api_key and self.api_key.strip():
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key.strip()}"
                prompt_text = f"{SYSTEM_SALES_PROMPT}\n\nThông tin sản phẩm khách đang xem: {product_context}\n\nKhách hàng hỏi: \"{customer_message}\"\n\nHãy trả lời khách ngắn gọn và duyên dáng:"
                payload = {
                    "contents": [{"parts": [{"text": prompt_text}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200}
                }
                res = requests.post(endpoint, json=payload, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                logger.error(f"Lỗi AI Chat: {e}")

        # Fallback Rule-based thông minh
        msg_lower = customer_message.lower()
        if any(w in msg_lower for w in ["size", "kg", "m6", "m7", "m8", "nặng", "cao"]):
            return "Dạ với chiều cao và cân nặng của mình, bạn mặc size chuẩn sẽ rất vừa và đẹp ạ! Shop có đủ bảng size trong ảnh sản phẩm, bạn đặt sớm để shop gửi hàng đi ngay nhé ❤️"
        elif any(w in msg_lower for w in ["còn hàng", "hàng còn", "còn k", "con ko"]):
            return "Dạ sản phẩm này bên shop luôn sẵn hàng số lượng lớn tại kho ạ. Bạn bấm đặt hàng sớm shop đóng gói gửi đi trong hôm nay nha!"
        elif any(w in msg_lower for w in ["ship", "giao", "bao lâu", "hà nội", "hcm"]):
            return "Dạ thời gian giao hàng dự kiến khoảng 1-2 ngày (nội thành) hoặc 2-3 ngày (tỉnh) nha bạn. Shop gửi hỏa tốc/nhanh hàng ngày ạ ❤️"
        elif any(w in msg_lower for w in ["giảm giá", "voucher", "mã", "freeship"]):
            return "Dạ shop đang có voucher giảm giá ở đầu trang và mã freeship extra. Đặc biệt khi mua qua mục Shopee Video của shop còn được trợ giá thêm 20%-50% nữa đó ạ!"
        else:
            return "Dạ shop chào bạn ạ! Cảm ơn bạn đã quan tâm đến sản phẩm của shop. Bạn cần tư vấn thêm về màu sắc, kích cỡ hay ưu đãi nào cứ nhắn shop hỗ trợ ngay nhé ❤️"

    async def open_chat_portal(self, log_callback=None):
        """Mở trực tiếp Kênh Chat Shopee trên trình duyệt để người dùng tự xem và kiểm tra."""
        try:
            await self.init_browser(headless=False)
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            if log_callback:
                await log_callback(f"Đang mở giao diện Chat Shopee cho {self.shop_name}...")
            await self.page.goto("https://banhang.shopee.vn/webchat/conversations", wait_until="domcontentloaded", timeout=45000)
            if log_callback:
                await log_callback("Trình duyệt Chat đã mở. Bạn có thể xem lịch sử hội thoại thực tế của khách hàng.")
            while True:
                if not self.context or not self.context.pages or (self.page and self.page.is_closed()):
                    if self.context and self.context.pages:
                        self.page = self.context.pages[0]
                    else:
                        break
                await asyncio.sleep(1)
        except Exception as e:
            if log_callback:
                await log_callback(f"Đã đóng trình duyệt Chat.")
        finally:
            await self.close_browser()

    async def start_listening_loop(self, log_callback=None):
        """Vòng lặp lắng nghe tin nhắn đến và tự động trả lời."""
        self.is_running = True
        try:
            await self.init_browser(headless=True)
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

            if log_callback:
                await log_callback(f"🔍 Đang kết nối Kênh Chat Shopee cho Shop: {self.shop_name}...")
            await self.page.goto("https://banhang.shopee.vn/webchat/conversations", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(5)

            if "login" in self.page.url.lower():
                if log_callback:
                    await log_callback("⚠️ Tài khoản chưa đăng nhập Chat. Vui lòng đăng nhập trong 'Quản lý Shop'.")
                self.is_running = False
                return

            if log_callback:
                await log_callback(f"🤖 AI Sales Consultant đã sẵn sàng trực chiến 24/7 cho Shop: {self.shop_name}!")

            while self.is_running:
                try:
                    # 1. Tìm các hội thoại có tin nhắn chưa đọc
                    conv_items = await self.page.locator(".conversation-item.unread, .unread-badge, [class*='unread'], .conversation-item, div[class*='conversation-item']").all()
                    
                    if conv_items:
                        for item in conv_items[:3]:
                            try:
                                if await item.is_visible():
                                    await item.click(timeout=2000)
                                    await asyncio.sleep(1.2)

                                # Lấy danh sách tin nhắn trong khung chat
                                message_locators = await self.page.locator(".message-item, .chat-message-text, div[class*='message-item'], div[class*='message-text'], div[class*='msg-content']").all()
                                if message_locators:
                                    last_msg_el = message_locators[-1]
                                    last_msg = await last_msg_el.inner_text()
                                    last_msg = last_msg.strip()
                                    if not last_msg:
                                        continue

                                    # Kiểm tra xem tin nhắn cuối có phải từ người mua không (không phải tin nhắn do shop gửi)
                                    parent_cls = await last_msg_el.evaluate("el => el.closest('.message-item, div[class*=\"message\"]')?.className || ''")
                                    is_mine = any(k in parent_cls.lower() for k in ["is-me", "self", "sender-me", "message-right", "msg-self"])
                                    
                                    msg_key = f"{self.shop_name}_{last_msg}"
                                    
                                    if not is_mine and msg_key not in self.replied_message_ids:
                                        self.replied_message_ids.add(msg_key)
                                        if log_callback:
                                            await log_callback(f"💬 [Khách nhắn - {self.shop_name}]: \"{last_msg[:60]}\"")

                                        reply_text = await self.generate_reply(last_msg)
                                        
                                        # Điền và gửi tin nhắn
                                        chat_input = self.page.locator("textarea, [contenteditable='true'], .chat-input, input[class*='chat']").first
                                        if await chat_input.is_visible():
                                            await chat_input.fill(reply_text)
                                            await asyncio.sleep(0.5)
                                            send_btn = self.page.locator("button:has-text('Gửi'), button.send-button, button[class*='send']").first
                                            if await send_btn.is_visible():
                                                await send_btn.click()
                                            else:
                                                await chat_input.press("Enter")
                                            
                                            # Ghi vào lịch sử chat
                                            add_chat_record(
                                                shop_name=self.shop_name,
                                                customer_msg=last_msg,
                                                ai_reply=reply_text,
                                                status="Đã phản hồi"
                                            )

                                            if log_callback:
                                                await log_callback(f"🤖 [AI trả lời - {self.shop_name}]: \"{reply_text[:70]}...\"")
                                                await log_callback("✅ Đã gửi phản hồi tự động thành công!")
                            except Exception as e:
                                pass

                except Exception as e:
                    pass

                await asyncio.sleep(4)

        except Exception as e:
            logger.error(f"Lỗi vòng lặp chat: {e}")
            if log_callback:
                await log_callback(f"❌ Dừng AI Chat ({self.shop_name}) do lỗi: {e}")
        finally:
            self.is_running = False
            await self.close_browser()

    def stop(self):
        self.is_running = False
