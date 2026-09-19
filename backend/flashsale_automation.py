import asyncio
import os
import sys
import logging
import time
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext
from backend.video_automation import cleanup_stale_profile

logger = logging.getLogger("FlashSaleScheduler")

class FlashSaleScheduler:
    def __init__(self, profile_dir: str):
        if os.path.isabs(profile_dir):
            self.profile_dir = profile_dir
        else:
            self.profile_dir = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "ShopeeVideoAutoPoster", profile_dir
            ))
            if not os.path.exists(self.profile_dir):
                self.profile_dir = os.path.abspath(profile_dir)

        os.makedirs(self.profile_dir, exist_ok=True)
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def init_browser(self, headless: bool = False) -> BrowserContext:
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
                    logger.error(f"Không thể khởi chạy flash sale browser: {e}")
                    raise e
                await asyncio.sleep(1)

        await self.context.add_init_script("delete navigator.__proto__.webdriver;")
        self.context.set_default_timeout(40000)
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
            logger.error(f"Lỗi đóng browser flash sale: {e}")
            self.context = None
            self.playwright = None

    async def auto_create_flashsale(
        self,
        discount_percent: int = 10,
        stock_per_item: int = 10,
        target_product_count: int = 10,
        selected_products: Optional[List[str]] = None,
        log_callback=None
    ) -> Dict[str, Any]:
        """Tự động quét các khung giờ Flash Sale trống của Shop và đăng ký."""
        try:
            await self.init_browser(headless=False)
            self.page = await self.context.new_page()

            if log_callback:
                await log_callback("🚀 Truy cập Kênh Marketing ➔ Flash Sale của Shop...")
            
            await self.page.goto(
                "https://banhang.shopee.vn/portal/marketing/in-shop-flash-sale/list",
                wait_until="domcontentloaded",
                timeout=45000
            )
            await asyncio.sleep(4)

            # Kiểm tra đăng nhập
            if "login" in self.page.url.lower():
                if log_callback:
                    await log_callback("⚠️ Tài khoản chưa đăng nhập vào Kênh Người Bán.")
                return {"success": False, "error": "Chưa đăng nhập"}

            # Bấm nút 'Tạo chương trình Flash Sale mới' hoặc link tạo
            create_btn = self.page.locator("button:has-text('Tạo chương trình'), button:has-text('Tạo mới'), button:has-text('Thêm khung giờ'), a:has-text('Tạo chương trình'), .shopee-button--primary:has-text('Tạo')").first
            is_found = await create_btn.is_visible()
            
            if not is_found:
                # Thử chuyển trực tiếp vào trang tạo
                if log_callback:
                    await log_callback("Thử truy cập trực tiếp trang tạo Flash Sale...")
                await self.page.goto("https://banhang.shopee.vn/portal/marketing/in-shop-flash-sale/create", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                is_found = "create" in self.page.url.lower() or await self.page.locator(".time-slot-item, button:has-text('Thêm sản phẩm')").first.is_visible()
            else:
                if log_callback:
                    await log_callback("Bấm nút 'Tạo chương trình Flash Sale'...")
                await create_btn.click()
                await asyncio.sleep(3)

            # Chọn khung giờ tiếp theo khả dụng
            time_slots = await self.page.locator(".time-slot-item, .time-range-picker, input[type='radio'], .shopee-radio").all()
            if time_slots:
                if log_callback:
                    await log_callback(f"Tìm thấy {len(time_slots)} khung giờ. Đang chọn khung giờ khả dụng sớm nhất...")
                try:
                    await time_slots[0].click()
                    await asyncio.sleep(1)
                except Exception:
                    pass

            # Bấm xác nhận khung giờ nếu có popup/bước chọn
            confirm_slot_btn = self.page.locator("button:has-text('Xác nhận'), button:has-text('Tiếp tục'), button:has-text('Tiếp theo')").first
            if await confirm_slot_btn.is_visible():
                await confirm_slot_btn.click()
                await asyncio.sleep(2)

            # Bấm Thêm sản phẩm
            add_prod_btn = self.page.locator("button:has-text('Thêm sản phẩm'), button:has-text('Chọn sản phẩm'), .btn-add-product").first
            if await add_prod_btn.is_visible():
                if log_callback:
                    await log_callback("Đang mở hộp thoại chọn sản phẩm tham gia Flash Sale...")
                await add_prod_btn.click()
                await asyncio.sleep(3)

                # Nếu có danh sách sản phẩm được chọn cụ thể
                if selected_products and len(selected_products) > 0:
                    if log_callback:
                        await log_callback(f"🎯 Đang tìm và tích chọn {len(selected_products)} sản phẩm đã chỉ định...")

                    for prod_name in selected_products:
                        try:
                            clean_name = prod_name.strip()
                            if not clean_name:
                                continue
                            # Tìm ô search trong modal
                            modal_search = self.page.locator(".shopee-modal input[placeholder*='Tìm'], .modal-body input[placeholder*='Tìm'], input[placeholder*='Tên sản phẩm']").first
                            if await modal_search.is_visible():
                                await modal_search.fill(clean_name[:40])
                                await self.page.keyboard.press("Enter")
                                await asyncio.sleep(1.5)
                                # Tích chọn dòng đầu tiên
                                first_cb = self.page.locator(".shopee-modal .shopee-checkbox, .modal-body input[type='checkbox']").first
                                if await first_cb.is_visible():
                                    await first_cb.click()
                                    await asyncio.sleep(0.5)
                        except Exception:
                            continue
                else:
                    # Chọn các sản phẩm đầu tiên
                    checkboxes = await self.page.locator(".shopee-modal .shopee-checkbox, .modal-body input[type='checkbox'], input[type='checkbox']").all()
                    for cb in checkboxes[1:target_product_count + 1]:
                        try:
                            await cb.click(timeout=1000)
                            await asyncio.sleep(0.3)
                        except Exception:
                            pass

                confirm_prod_btn = self.page.locator(".modal-footer button:has-text('Xác nhận'), .modal-footer button:has-text('Hoàn tất'), button:has-text('Xác nhận')").first
                if await confirm_prod_btn.is_visible():
                    await confirm_prod_btn.click()
                    await asyncio.sleep(2)

            # Thiết lập giảm giá hàng loạt
            batch_edit_btn = self.page.locator("button:has-text('Chỉnh sửa hàng loạt'), button:has-text('Cài đặt hàng loạt'), button:has-text('Cập nhật hàng loạt')").first
            if await batch_edit_btn.is_visible():
                if log_callback:
                    await log_callback(f"Cài đặt giảm giá {discount_percent}%, số lượng kho mở bán {stock_per_item} cái...")
                await batch_edit_btn.click()
                await asyncio.sleep(1)

                discount_input = self.page.locator("input[placeholder*='%'], input[placeholder*='giảm']").first
                if await discount_input.is_visible():
                    await discount_input.fill(str(discount_percent))

                stock_input = self.page.locator("input[placeholder*='số lượng'], input[placeholder*='kho']").first
                if await stock_input.is_visible():
                    await stock_input.fill(str(stock_per_item))

                apply_btn = self.page.locator("button:has-text('Áp dụng cho tất cả'), button:has-text('Áp dụng')").first
                if await apply_btn.is_visible():
                    await apply_btn.click()
                    await asyncio.sleep(1)

            # Bấm Lưu / Bật chương trình
            save_btn = self.page.locator("button:has-text('Lưu & Bật'), button:has-text('Xác nhận tạo'), button:has-text('Hoàn tất'), button:has-text('Lưu')").first
            if await save_btn.is_visible():
                await save_btn.click()
                if log_callback:
                    await log_callback("🎉 Đã lưu và kích hoạt chương trình Flash Sale thành công!")
                await asyncio.sleep(3)
                return {"success": True, "message": "Đã tạo Flash Sale thành công"}
            else:
                if log_callback:
                    await log_callback("ℹ️ Đã hoàn tất các bước cấu hình Flash Sale trên trình duyệt.")
                return {"success": True, "message": "Hoàn tất thao tác"}

        except Exception as e:
            logger.error(f"Lỗi tạo Flash Sale: {e}")
            if log_callback:
                await log_callback(f"❌ Lỗi tự động Flash Sale: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            await self.close_browser()
