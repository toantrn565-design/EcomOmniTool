import asyncio
import os
import sys
import logging
import time
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext
from backend.video_automation import cleanup_stale_profile

from backend.profile_utils import resolve_profile_path

logger = logging.getLogger("ProductBooster")

class ShopeeProductBooster:
    def __init__(self, profile_dir: str):
        self.profile_dir = resolve_profile_path(profile_dir)
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

        blacklist_terms = [
            "ảnh sản phẩm", "tên sản phẩm", "sản phẩm", "hình ảnh", "thao tác", 
            "kho hàng", "giá", "chọn tất cả", "tất cả", "cập nhật", "chỉnh sửa", 
            "xem thêm", "đẩy sản phẩm", "đang đẩy", "có thể đẩy", "đánh giá sản phẩm", 
            "hiệu suất", "tồn kho", "sẵn sàng", "phân loại", "mã sku", "chi tiết", "xóa"
        ]

        def clean_product_name(raw_name: str) -> str:
            if not raw_name:
                return ""
            name = raw_name.strip()
            for junk in ["Ảnh sản phẩm", "Tên sản phẩm", "Hình ảnh", "Sản phẩm", "Mã SKU", "Kho hàng", "Thao tác", "Chỉnh sửa", "Cập nhật"]:
                if name.lower().startswith(junk.lower()):
                    name = name[len(junk):].strip()
            return name

        def is_valid_product(name: str) -> bool:
            if not name or len(name) < 4:
                return False
            name_low = name.lower()
            for b in blacklist_terms:
                if name_low == b or name_low.startswith(b + ":"):
                    return False
            return True

        def format_product_item(it: dict) -> Optional[dict]:
            prod_name = clean_product_name(it.get("name") or it.get("item_name") or "")
            if not is_valid_product(prod_name) or prod_name in seen_names:
                return None
            seen_names.add(prod_name)

            prod_id = str(it.get("id") or it.get("item_id") or it.get("product_id") or "")
            
            # Format cover image
            image_id = ""
            if it.get("images") and isinstance(it.get("images"), list) and len(it.get("images")) > 0:
                image_id = it.get("images")[0]
            elif it.get("cover_image"):
                image_id = it.get("cover_image")
            elif it.get("image"):
                image_id = it.get("image")

            img_url = ""
            if image_id:
                if image_id.startswith("http"):
                    img_url = image_id
                else:
                    img_url = f"https://down-vn.img.susercontent.com/file/{image_id}"

            # Format price
            price_detail = it.get("price_detail", {})
            price_val = price_detail.get("selling_price_min") or price_detail.get("price_min") or it.get("price") or it.get("min_price") or it.get("current_price") or "0"
            try:
                price_float = float(price_val)
                price_str = f"{price_float:,.0f} đ" if price_float > 0 else "Sẵn sàng"
            except Exception:
                price_str = str(price_val)

            # Format stock
            stock_detail = it.get("stock_detail", {})
            stock_val = stock_detail.get("total_available_stock") or stock_detail.get("total_seller_stock") or it.get("stock") or it.get("total_stock") or "Còn hàng"

            # Check boost info
            boost_info = it.get("boost_info", {})
            boost_end = boost_info.get("cool_down_seconds", 0) or boost_info.get("boost_cooldown", 0) or it.get("boost_cool_down_seconds", 0)
            is_boosted = boost_end > 0

            return {
                "id": prod_id or f"sp_{len(captured_api_products)+1}",
                "name": prod_name,
                "image": img_url,
                "price": price_str,
                "stock": str(stock_val),
                "is_boosted": is_boosted,
                "boost_status": "Đang đẩy" if is_boosted else "Có thể đẩy"
            }

        try:
            await self.init_browser(headless=True)
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

            captured_base_url = []
            total_shop_products = [0]

            # Lắng nghe request/response API của Shopee để bắt danh sách sản phẩm chuẩn JSON
            async def handle_response(response):
                try:
                    url = response.url
                    if any(api in url for api in ["get_product_list", "search_product_list"]):
                        if response.status == 200:
                            data = await response.json()
                            items = (
                                data.get("data", {}).get("products", []) or 
                                data.get("data", {}).get("list", []) or 
                                data.get("data", {}).get("mpsku_list", []) or 
                                []
                            )
                            if items:
                                if "SPC_CDS" in url and not captured_base_url:
                                    captured_base_url.append(url)
                                total_val = data.get("data", {}).get("page_info", {}).get("total") or data.get("data", {}).get("total", len(items))
                                if total_val > total_shop_products[0]:
                                    total_shop_products[0] = total_val
                                for it in items:
                                    p_obj = format_product_item(it)
                                    if p_obj:
                                        captured_api_products.append(p_obj)
                except Exception:
                    pass

            self.page.on("response", handle_response)

            if log_callback:
                await log_callback("🔍 Đang kết nối Kênh Người Bán Shopee để lấy danh mục toàn bộ sản phẩm...")
            
            await self.page.goto("https://banhang.shopee.vn/portal/product/list/all", wait_until="domcontentloaded", timeout=40000)
            
            # Chờ tối đa 5s để bắt trang đầu tiên
            for _ in range(10):
                if len(captured_api_products) > 0:
                    break
                await asyncio.sleep(0.5)

            # Kiểm tra đăng nhập
            if "login" in self.page.url.lower():
                if log_callback:
                    await log_callback("⚠️ Tài khoản chưa đăng nhập vào Kênh Người Bán Shopee. Vui lòng nhấn 'Quản lý Shop' -> 'Login' để đăng nhập.")
                return []

            # Tự động quét các trang tiếp theo để lấy 100% toàn bộ sản phẩm của Shop
            if captured_base_url and total_shop_products[0] > len(captured_api_products):
                base_url = captured_base_url[0]
                total = total_shop_products[0]
                if log_callback:
                    await log_callback(f"📦 Shop có tổng cộng {total} sản phẩm. Đang tải trọn bộ tất cả các trang...")
                
                page_num = 2
                max_pages = 20
                while len(captured_api_products) < total and page_num <= max_pages:
                    if "page_number=" in base_url:
                        next_url = base_url.replace("page_number=1", f"page_number={page_num}")
                    else:
                        next_url = base_url + f"&page_number={page_num}"
                    
                    try:
                        js_res = await self.page.evaluate(f"""
                            async () => {{
                                try {{
                                    const res = await fetch('{next_url}', {{credentials: 'include'}});
                                    if (res.ok) return await res.json();
                                }} catch(e) {{}}
                                return null;
                            }}
                        """)
                        if js_res and (js_res.get("data", {}).get("products") or js_res.get("data", {}).get("list")):
                            next_items = js_res.get("data", {}).get("products") or js_res.get("data", {}).get("list") or []
                            for it in next_items:
                                p_obj = format_product_item(it)
                                if p_obj:
                                    captured_api_products.append(p_obj)
                            page_num += 1
                        else:
                            break
                    except Exception:
                        break

            if captured_api_products:
                if log_callback:
                    await log_callback(f"✅ Đã tải thành công toàn bộ {len(captured_api_products)} sản phẩm từ Shop Shopee!")
                return captured_api_products

            # Fallback DOM Parsing chính xác cao
            rows = await self.page.locator(".product-item-row, .shopee-table-row, tr.product-row, .shopee-table tbody tr").all()

            if log_callback:
                await log_callback(f"Đang phân tích giao diện danh sách ({len(rows)} hàng)...")

            for idx, row in enumerate(rows):
                try:
                    name = ""
                    # Ưu tiên tìm đúng thẻ chứa tên sản phẩm
                    name_selectors = [
                        ".product-name", 
                        "[data-testid='product-name']", 
                        "div.mpsku-product-name", 
                        ".item-title", 
                        ".product-title", 
                        ".name-text", 
                        "a[href*='product/edit']",
                        "a[href*='portal/product']"
                    ]
                    for sel in name_selectors:
                        el = row.locator(sel).first
                        if await el.is_visible():
                            cand = await el.inner_text()
                            if cand and len(cand.strip()) >= 4 and not any(b == cand.strip().lower() for b in blacklist_terms):
                                name = cand.strip()
                                break
                    
                    if not name:
                        text_content = await row.inner_text()
                        lines = [l.strip() for l in text_content.split("\n") if l.strip()]
                        for line in lines:
                            line_clean = clean_product_name(line)
                            if len(line_clean) > 8 and is_valid_product(line_clean):
                                name = line_clean
                                break

                    name = clean_product_name(name)
                    if not is_valid_product(name) or name in seen_names:
                        continue
                    seen_names.add(name)

                    # Lấy ảnh sản phẩm
                    img_el = row.locator("img").first
                    img_src = ""
                    if await img_el.is_visible():
                        img_src = await img_el.get_attribute("src") or ""
                        if "buybox_label" in img_src or "base64" in img_src:
                            img_src = ""

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
