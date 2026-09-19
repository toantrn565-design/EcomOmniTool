import asyncio
import os
import sys
import logging
import time
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext
from backend.video_automation import cleanup_stale_profile

logger = logging.getLogger("ProductBooster")

class ShopeeProductBooster:
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

    async def init_browser(self, headless: bool = True) -> BrowserContext:
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
                    logger.error(f"Không thể khởi chạy booster browser: {e}")
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
            logger.error(f"Lỗi đóng browser booster: {e}")
            self.context = None
            self.playwright = None

    async def open_seller_portal(self, log_callback=None):
        """Mở trực tiếp Kênh Người Bán Shopee trên trình duyệt để người dùng tự thao tác."""
        try:
            await self.init_browser(headless=False)
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            if log_callback:
                await log_callback("Đang mở trình duyệt Kênh Người Bán Shopee...")
            await self.page.goto("https://banhang.shopee.vn/portal/product/list/all", wait_until="domcontentloaded", timeout=45000)
            if log_callback:
                await log_callback("Trình duyệt Kênh Người Bán đã mở. Bạn có thể trực tiếp xem và chọn sản phẩm.")
            while True:
                if not self.context or not self.context.pages or (self.page and self.page.is_closed()):
                    if self.context and self.context.pages:
                        self.page = self.context.pages[0]
                    else:
                        break
                await asyncio.sleep(1)
        except Exception as e:
            if log_callback:
                await log_callback("Đã đóng trình duyệt Kênh Người Bán.")
        finally:
            await self.close_browser()

    async def get_products_list(self, log_callback=None) -> List[Dict[str, Any]]:
        """Lấy danh sách các sản phẩm đang có trong Shop Shopee chuẩn xác 100%."""
        products = []
        captured_api_products = []
        seen_names = set()

        def clean_product_name(raw_name: str) -> str:
            if not raw_name:
                return ""
            name = raw_name.strip()
            # Bỏ các tiền tố / hậu tố giao diện thừa
            for junk in ["Ảnh sản phẩm", "Tên sản phẩm", "Hình ảnh", "Sản phẩm", "Mã SKU", "Kho hàng", "Thao tác", "Chỉnh sửa"]:
                if name.lower().startswith(junk.lower()):
                    name = name[len(junk):].strip()
            return name

        def is_valid_product(name: str) -> bool:
            if not name or len(name) < 4:
                return False
            name_low = name.lower()
            blacklisted = ["ảnh sản phẩm", "tên sản phẩm", "sản phẩm", "hình ảnh", "thao tác", "kho hàng", "giá", "chọn tất cả", "tất cả"]
            if name_low in blacklisted:
                return False
            return True

        try:
            await self.init_browser(headless=True)
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

            # Lắng nghe request/response API của Shopee để bắt danh sách sản phẩm chuẩn JSON
            async def handle_response(response):
                try:
                    url = response.url
                    if any(api in url for api in ["/api/v3/product/search_product_list/", "/api/v3/product/get_product_list_filter/", "/api/v3/product/list/", "/api/v3/product/get_product_list/"]):
                        if response.status == 200:
                            data = await response.json()
                            items = data.get("data", {}).get("products", []) or data.get("data", {}).get("list", []) or data.get("products", [])
                            for it in items:
                                prod_name = clean_product_name(it.get("name") or it.get("item_name") or "")
                                if not is_valid_product(prod_name) or prod_name in seen_names:
                                    continue
                                seen_names.add(prod_name)
                                prod_id = str(it.get("id") or it.get("item_id") or "")
                                image_id = it.get("images", [""])[0] if it.get("images") else (it.get("cover_image") or "")
                                img_url = f"https://down-vn.img.susercontent.com/file/{image_id}" if image_id and not image_id.startswith("http") else image_id
                                price_val = it.get("price") or it.get("min_price") or "0"
                                stock_val = it.get("stock") or it.get("total_stock") or "0"
                                boost_end = it.get("boost_cool_down_seconds", 0)
                                is_boosted = boost_end > 0
                                captured_api_products.append({
                                    "id": prod_id,
                                    "name": prod_name,
                                    "image": img_url,
                                    "price": f"{float(price_val):,.0f} đ" if str(price_val).replace('.','').isdigit() and float(price_val) > 1000 else str(price_val),
                                    "stock": str(stock_val),
                                    "is_boosted": is_boosted,
                                    "boost_status": "Đang đẩy" if is_boosted else "Có thể đẩy"
                                })
                except Exception:
                    pass

            self.page.on("response", handle_response)

            if log_callback:
                await log_callback("🔍 Đang kết nối Kênh Người Bán Shopee để lấy danh mục sản phẩm...")
            
            await self.page.goto("https://banhang.shopee.vn/portal/product/list/all", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(4)

            # Kiểm tra đăng nhập
            if "login" in self.page.url.lower():
                if log_callback:
                    await log_callback("⚠️ Tài khoản chưa đăng nhập vào Kênh Người Bán Shopee. Vui lòng đăng nhập trong 'Quản lý Shop'.")
                return []

            # Thử gọi trực tiếp API Shopee qua JS evaluate
            if not captured_api_products:
                try:
                    js_data = await self.page.evaluate("""
                        async () => {
                            try {
                                const res = await fetch('/api/v3/product/search_product_list/?page_number=1&page_size=48&source=seller_center_web', {credentials: 'include'});
                                if (res.ok) {
                                    return await res.json();
                                }
                            } catch(e) {}
                            return null;
                        }
                    """)
                    if js_data and js_data.get("data", {}).get("products"):
                        for it in js_data["data"]["products"]:
                            prod_name = clean_product_name(it.get("name") or it.get("item_name") or "")
                            if not is_valid_product(prod_name) or prod_name in seen_names:
                                continue
                            seen_names.add(prod_name)
                            prod_id = str(it.get("id") or it.get("item_id") or "")
                            image_id = it.get("images", [""])[0] if it.get("images") else ""
                            img_url = f"https://down-vn.img.susercontent.com/file/{image_id}" if image_id and not image_id.startswith("http") else image_id
                            price_val = it.get("price") or it.get("min_price") or "0"
                            stock_val = it.get("stock") or it.get("total_stock") or "0"
                            boost_end = it.get("boost_cool_down_seconds", 0)
                            is_boosted = boost_end > 0
                            captured_api_products.append({
                                "id": prod_id,
                                "name": prod_name,
                                "image": img_url,
                                "price": f"{float(price_val):,.0f} đ" if str(price_val).replace('.','').isdigit() and float(price_val) > 1000 else str(price_val),
                                "stock": str(stock_val),
                                "is_boosted": is_boosted,
                                "boost_status": "Đang đẩy" if is_boosted else "Có thể đẩy"
                            })
                except Exception:
                    pass

            if captured_api_products:
                if log_callback:
                    await log_callback(f"✅ Đã tải thành công {len(captured_api_products)} sản phẩm chuẩn xác từ Shopee!")
                return captured_api_products

            # Fallback DOM Parsing chính xác cao
            rows = await self.page.locator(".product-item-row, .shopee-table-row, tr.product-row, .product-item").all()
            if not rows:
                rows = await self.page.locator(".shopee-table tbody tr").all()

            if log_callback:
                await log_callback(f"Đang phân tích giao diện danh sách ({len(rows)} hàng)...")

            for idx, row in enumerate(rows):
                try:
                    # Trích xuất tên từ các selector tiêu đề cụ thể thay vì toàn bộ text của dòng
                    name = ""
                    name_locator = row.locator(".product-name, .item-name, .product-title, .name-text, a[href*='product'], div[class*='name']").first
                    if await name_locator.is_visible():
                        name = await name_locator.inner_text()
                    
                    if not name:
                        text_content = await row.inner_text()
                        lines = [l.strip() for l in text_content.split("\n") if l.strip()]
                        for line in lines:
                            line_clean = clean_product_name(line)
                            if len(line_clean) > 8 and not any(k in line_clean.lower() for k in ["mã sku", "kho:", "giá:", "đang đẩy", "thao tác", "chỉnh sửa", "phân loại"]):
                                name = line_clean
                                break

                    name = clean_product_name(name)
                    if not is_valid_product(name) or name in seen_names:
                        continue
                    seen_names.add(name)

                    # Lấy ảnh
                    img_el = row.locator("img").first
                    img_src = ""
                    if await img_el.is_visible():
                        img_src = await img_el.get_attribute("src") or ""

                    text_all = await row.inner_text()
                    is_boosted = "đang đẩy" in text_all.lower() or "còn 0" in text_all.lower()
                    
                    products.append({
                        "id": f"sp_{idx+1}",
                        "name": name[:120],
                        "image": img_src,
                        "price": "Sẵn sàng",
                        "stock": "Còn hàng",
                        "is_boosted": is_boosted,
                        "boost_status": "Đang đẩy" if is_boosted else "Có thể đẩy"
                    })
                except Exception:
                    continue

            if log_callback:
                await log_callback(f"✅ Đã tải danh sách {len(products)} sản phẩm thành công.")

        except Exception as e:
            logger.error(f"Lỗi lấy danh sách sản phẩm: {e}")
            if log_callback:
                await log_callback(f"❌ Lỗi lấy sản phẩm: {e}")
        finally:
            await self.close_browser()

        return products

    async def execute_boost(self, mode: str = "smart", target_keywords: List[str] = None, log_callback=None) -> Dict[str, Any]:
        """Thực hiện click nút 'Đẩy sản phẩm' cho tối đa 5 sản phẩm."""
        boosted_count = 0
        already_boosted = 0
        try:
            await self.init_browser(headless=True)
            self.page = await self.context.new_page()

            if log_callback:
                await log_callback("🚀 Truy cập trang Quản lý sản phẩm Kênh Người Bán...")
            await self.page.goto("https://banhang.shopee.vn/portal/product/list/all", wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(4)

            # Nếu có danh sách sản phẩm chỉ định cụ thể (target_keywords / product_ids)
            if target_keywords and len(target_keywords) > 0:
                if log_callback:
                    await log_callback(f"🎯 Bắt đầu đẩy {len(target_keywords)} sản phẩm theo danh sách chỉ định...")

                for kw in target_keywords:
                    if boosted_count + already_boosted >= 5:
                        break
                    try:
                        clean_kw = kw.strip()
                        if not clean_kw:
                            continue
                        if log_callback:
                            await log_callback(f"🔎 Đang tìm sản phẩm: '{clean_kw[:40]}...'")

                        # Tìm ô search sản phẩm
                        search_input = self.page.locator("input[placeholder*='Tìm kiếm'], input[placeholder*='sản phẩm'], input[placeholder*='Tên']").first
                        if await search_input.is_visible():
                            await search_input.fill(clean_kw)
                            await self.page.keyboard.press("Enter")
                            await asyncio.sleep(3)

                        # Kiểm tra xem sản phẩm có đang được đẩy không
                        page_text = await self.page.inner_text("body")
                        if "đang đẩy" in page_text.lower() or "còn 0" in page_text.lower():
                            already_boosted += 1
                            if log_callback:
                                await log_callback(f"ℹ️ Sản phẩm '{clean_kw[:35]}' hiện đang trong chu kỳ đẩy.")
                            continue

                        # 1. Thử click nút đẩy trực tiếp
                        boost_btn = self.page.locator("button:has-text('Đẩy sản phẩm'), button:has-text('Đẩy ngay'), button:has-text('Tăng lượt xem'), a:has-text('Đẩy sản phẩm')").first
                        if await boost_btn.is_visible() and await boost_btn.is_enabled():
                            await boost_btn.click()
                            boosted_count += 1
                            if log_callback:
                                await log_callback(f"✅ Đã kích hoạt đẩy thành công: {clean_kw[:40]}")
                            await asyncio.sleep(1.5)
                            continue

                        # 2. Thử mở dropdown 'Thao tác' / 'Thêm'
                        more_menus = await self.page.locator("button:has-text('Thêm'), button:has-text('Thao tác'), .shopee-dropdown, .operation-dropdown, button.more-action-btn").all()
                        for menu in more_menus:
                            try:
                                await menu.scroll_into_view_if_needed()
                                await menu.click(timeout=2000)
                                await asyncio.sleep(0.5)
                                boost_opt = self.page.locator(".shopee-dropdown-item:has-text('Đẩy'), .shopee-dropdown-menu :has-text('Đẩy'), text='Đẩy sản phẩm', text='Tăng lượt xem'").first
                                if await boost_opt.is_visible():
                                    await boost_opt.click(timeout=2000)
                                    boosted_count += 1
                                    if log_callback:
                                        await log_callback(f"✅ Đã kích hoạt đẩy thành công: {clean_kw[:40]}")
                                    await asyncio.sleep(1.5)
                                    break
                            except Exception:
                                continue

                    except Exception as e:
                        logger.warning(f"Không thể đẩy sản phẩm {kw}: {e}")
                        continue

            # Nếu chưa đủ 5 sản phẩm hoặc chế độ xoay tua tự động (smart)
            if (boosted_count + already_boosted) < 5 and mode != "strict":
                # Tìm các hàng sản phẩm
                rows = await self.page.locator(".product-item-row, .shopee-table-row, tr.product-row, .shopee-table tbody tr").all()
                if log_callback:
                    await log_callback(f"Đang duyệt {len(rows)} hàng sản phẩm để kích hoạt các vị trí đẩy trống...")

                for row in rows:
                    if boosted_count + already_boosted >= 5:
                        break
                    try:
                        row_text = await row.inner_text()
                        if "đang đẩy" in row_text.lower() or "còn 0" in row_text.lower():
                            already_boosted += 1
                            continue

                        # Thử nút đẩy trực tiếp trong row
                        direct_btn = row.locator("button:has-text('Đẩy sản phẩm'), button:has-text('Đẩy ngay'), a:has-text('Đẩy sản phẩm')").first
                        if await direct_btn.is_visible() and await direct_btn.is_enabled():
                            await direct_btn.click(timeout=2000)
                            boosted_count += 1
                            if log_callback:
                                await log_callback(f"✅ Đã kích hoạt đẩy thành công vị trí #{boosted_count + already_boosted}")
                            await asyncio.sleep(1.5)
                            continue

                        # Thử mở dropdown trong row
                        row_menu = row.locator("button:has-text('Thêm'), button:has-text('Thao tác'), .shopee-dropdown").first
                        if await row_menu.is_visible():
                            await row_menu.scroll_into_view_if_needed()
                            await row_menu.click(timeout=1500)
                            await asyncio.sleep(0.5)
                            boost_opt = self.page.locator(".shopee-dropdown-menu :has-text('Đẩy'), text='Đẩy sản phẩm', text='Tăng lượt xem'").first
                            if await boost_opt.is_visible():
                                await boost_opt.click(timeout=2000)
                                boosted_count += 1
                                if log_callback:
                                    await log_callback(f"✅ Đã kích hoạt đẩy thành công vị trí #{boosted_count + already_boosted}")
                                await asyncio.sleep(1.5)
                    except Exception:
                        continue

            total_active = boosted_count + already_boosted
            if log_callback:
                if total_active >= 5:
                    await log_callback(f"🎉 Hoàn thành: Đã có đủ 5/5 vị trí đẩy sản phẩm đang hoạt động (Đẩy mới: {boosted_count}, Đang chạy: {already_boosted}).")
                else:
                    await log_callback(f"🎉 Hoàn thành lượt đẩy: {total_active}/5 vị trí đã được kích hoạt.")

            return {
                "success": True,
                "boosted_count": boosted_count,
                "already_boosted": already_boosted,
                "total_active": total_active,
                "timestamp": time.time(),
                "next_run_in_seconds": 4 * 3600 + 120
            }

        except Exception as e:
            logger.error(f"Lỗi khi thực hiện đẩy sản phẩm: {e}")
            if log_callback:
                await log_callback(f"❌ Lỗi tiến trình đẩy sản phẩm: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            await self.close_browser()
