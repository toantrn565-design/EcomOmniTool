import os
import sys
import logging
import asyncio
import inspect
from playwright.async_api import async_playwright, Page, BrowserContext

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ListingUploader")

class ProductUploader:
    def __init__(self, profile_dir: str):
        # Đường dẫn profile dir relative từ thư mục ShopeeVideoAutoPoster hoặc tuyệt đối
        if os.path.isabs(profile_dir):
            self.profile_dir = profile_dir
        else:
            # Ưu tiên lấy từ thư mục của dự án ShopeeVideoAutoPoster bên cạnh
            self.profile_dir = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "ShopeeVideoAutoPoster", profile_dir
            ))
            
        os.makedirs(self.profile_dir, exist_ok=True)
        self.playwright = None
        self.context: BrowserContext = None
        self.page: Page = None

    async def init_browser(self, headless: bool = False) -> BrowserContext:
        """Khởi tạo trình duyệt Playwright với Chrome Profile để lấy session đăng nhập."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ]
        
        for attempt in range(1, 4):
            try:
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=self.profile_dir,
                    headless=headless,
                    no_viewport=False,
                    viewport={"width": 1280, "height": 850},
                    args=launch_args,
                    ignore_default_args=["--enable-automation"]
                )
                break
            except Exception as e:
                if attempt == 3:
                    logger.error(f"Không thể khởi chạy trình duyệt: {e}")
                    raise RuntimeError(
                        f"Không thể mở trình duyệt với profile {os.path.basename(self.profile_dir)}. "
                        "Hãy chắc chắn rằng không có cửa sổ Chrome nào khác của shop này đang mở."
                    ) from e
                logger.warning(f"Lần thử {attempt}/3 khởi chạy thất bại, thử lại sau 2 giây...")
                await asyncio.sleep(2)
        
        await self.context.add_init_script("delete navigator.__proto__.webdriver;")
        self.context.set_default_timeout(40000)
        
        # Hàm chặn tải các file rác để tiết kiệm RAM
        async def intercept_route(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                # Nhưng không chặn ảnh ở màn hình đăng bài vì cần xem preview
                if "shopee" in route.request.url and "product/new" in self.page.url:
                    await route.continue_()
                else:
                    await route.abort()
            else:
                await route.continue_()
                
        # self.context.route("**/*", intercept_route) # Tạm ẩn để an toàn, nếu anh muốn có thể bật lên.

        return self.context

    async def close_browser(self):
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            logger.info("Đã đóng trình duyệt Playwright.")
        except Exception as e:
            logger.error(f"Lỗi đóng trình duyệt: {e}")
            self.context = None
            self.playwright = None

    async def safe_goto(self, url: str, retries: int = 3) -> bool:
        for attempt in range(1, retries + 1):
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=40000)
                # Smart wait thay vì sleep
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except: pass
                return True
            except Exception as e:
                logger.warning(f"Lần thử {attempt}/{retries} đi tới {url} thất bại: {e}")
                if attempt == retries:
                    raise e
                await asyncio.sleep(2)
        return False

    async def click_element_safe(self, selector: str, timeout: int = 8000) -> bool:
        try:
            locator = self.page.locator(selector).first
            await locator.scroll_into_view_if_needed(timeout=timeout)
            await locator.click(timeout=timeout)
            return True
        except Exception:
            try:
                await locator.click(force=True, timeout=timeout)
                return True
            except Exception:
                try:
                    await locator.dispatch_event("click", timeout=timeout)
                    return True
                except Exception:
                    return False

    async def fill_input_safe(self, selector: str, text: str, timeout: int = 5000) -> bool:
        try:
            # Đảm bảo element xuất hiện
            try:
                await self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            except Exception:
                pass

            locators = self.page.locator(selector)
            count = await locators.count()
            
            target = None
            for i in range(count):
                loc = locators.nth(i)
                if await loc.is_visible() and await loc.is_enabled():
                    target = loc
                    break
            
            if not target:
                logger.error(f"Không tìm thấy input nào khả dụng cho: {selector}")
                return False

            await target.scroll_into_view_if_needed(timeout=timeout)
            # Thử click bằng Javascript trước để tránh element bị che
            try:
                await target.evaluate("el => el.click()")
            except:
                await target.click(timeout=timeout, force=True)
            
            # Kiểm tra xem có phải div contenteditable không
            is_contenteditable = False
            try:
                is_contenteditable = await target.evaluate("(el) => el.isContentEditable")
            except: pass
            
            # Chọn toàn bộ để xóa trước khi ghi đè
            await target.focus()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            
            # Nếu là thẻ input bình thường, thử clear bằng JS để chắc chắn
            if not is_contenteditable:
                try:
                    await target.evaluate("el => el.value = ''")
                except: pass

            if is_contenteditable:
                # Với div contenteditable, dùng keyboard.type để giả lập gõ phím chân thực
                await self.page.keyboard.type(str(text), delay=2)
            else:
                try:
                    await target.fill(str(text), timeout=timeout)
                except:
                    # Fallback type nếu fill lỗi
                    await self.page.keyboard.type(str(text), delay=2)
            return True
        except Exception as e:
            logger.error(f"Lỗi khi fill {selector}: {e}")
            return False

    async def switch_shopee_tab(self, tab_name: str, log_fn=None) -> bool:
        """Chuyển đổi tab trên form đăng bài Shopee bằng cách click vào tiêu đề tab."""
        try:
            tab_selectors = [
                f".shopee-tabs__tab:has-text('{tab_name}')",
                f".tab-item:has-text('{tab_name}')",
                f"div.shopee-tabs__tab:has-text('{tab_name}')",
                f"//div[contains(@class, 'shopee-tabs__tab') and text()='{tab_name}']",
                f"//div[contains(@class, 'tab-item') and text()='{tab_name}']"
            ]
            for sel in tab_selectors:
                locator = self.page.locator(sel).first
                if await locator.count() > 0 and await locator.is_visible():
                    if log_fn:
                        log_fn(f"Đang chuyển sang tab Shopee: {tab_name}...")
                    await locator.click(timeout=4000)
                    await asyncio.sleep(1.5)
                    return True
            return False
        except Exception as e:
            logger.debug(f"Lỗi chuyển tab Shopee {tab_name}: {e}")
            return False

    async def upload_to_shopee(
        self, 
        product_data: dict, 
        auto_publish: bool = False, 
        default_brand: str = "No brand",
        default_weight: float = 0.5, 
        default_dimensions: dict = None, 
        log_callback=None
    ) -> bool:
        """Tự động điền thông tin sản phẩm trên Shopee Kênh Người Bán."""
        def log(msg):
            logger.info(msg)
            if log_callback:
                if inspect.iscoroutinefunction(log_callback):
                    asyncio.create_task(log_callback(msg))
                else:
                    try: log_callback(msg)
                    except: pass

        log("Bắt đầu khởi tạo trình duyệt Shopee...")
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()

        try:
            log("Đang mở trang đăng sản phẩm mới trên Shopee...")
            await self.safe_goto("https://banhang.shopee.vn/portal/product/new")
            await asyncio.sleep(5)

            # Kiểm tra trạng thái đăng nhập
            if "login" in self.page.url or "banhang.shopee.vn" not in self.page.url:
                log("CẢNH BÁO: Phát hiện bạn chưa đăng nhập Shopee trên profile này.")
                log("Vui lòng thực hiện đăng nhập thủ công trên trình duyệt đang mở. Công cụ sẽ tự động tiếp tục khi bạn vào trang đăng sản phẩm...")
                while "product/new" not in self.page.url:
                    if self.page.is_closed():
                        log("Trình duyệt đã bị đóng. Kết thúc tiến trình.")
                        return False
                    await asyncio.sleep(2)
                log("Đã phát hiện đăng nhập thành công. Đang tiếp tục...")

            log("Đang chờ giao diện đăng sản phẩm Shopee tải hoàn tất...")
            # Chờ sự xuất hiện của input Tên sản phẩm
            name_selector = "input[placeholder*='Nhập vào'], input[placeholder*='Tên sản phẩm'], .shopee-input__inner"
            try:
                await self.page.wait_for_selector(name_selector, timeout=60000)
            except Exception:
                log("Giao diện tải quá lâu. Vui lòng kiểm tra lại trình duyệt.")
            
            await asyncio.sleep(3)

            # 1. Điền Tên sản phẩm
            log(f"Điền tên sản phẩm: {product_data['title']}")
            # Tìm input đầu tiên của form
            await self.fill_input_safe(name_selector, product_data['title'])
            
            # Tự động chọn ngành hàng gợi ý nếu có
            try:
                await asyncio.sleep(3)
                log("Đang tìm ngành hàng gợi ý từ Shopee...")
                suggested_cat_selectors = [
                    ".category-recommendation__item", 
                    ".recommend-category-item",
                    ".category-recommend-item",
                    "[class*='recommend'] [class*='item']",
                    "[class*='category'] [class*='recommend']"
                ]
                for cat_sel in suggested_cat_selectors:
                    cat_locator = self.page.locator(cat_sel)
                    if await cat_locator.count() > 0:
                        await cat_locator.first.click(timeout=3000)
                        log("Đã tự động chọn ngành hàng gợi ý tối ưu.")
                        break
            except Exception as e:
                logger.debug(f"Không tự động click được ngành hàng gợi ý: {e}")

            # 2. Điền Mô tả sản phẩm
            log("Điền mô tả sản phẩm...")
            switched = await self.switch_shopee_tab("Mô tả", log)
            if not switched:
                log("Không tìm thấy tab Mô tả, thử cuộn trang xuống...")
                await self.page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)
                
            desc_selectors = [
                "textarea[placeholder*='mô tả']",
                "textarea[placeholder*='Mô tả']",
                "textarea.shopee-textarea__inner",
                "textarea.shopee-react-textarea__inner",
                "[contenteditable='true'][placeholder*='mô tả']",
                ".product-edit-form-item:has-text('Mô tả') textarea",
                ".product-edit-form-item:has-text('Mô tả') [contenteditable='true']",
                ".edit-content [contenteditable='true']",
                "div[contenteditable='true']"
            ]
            desc_sel = ", ".join(desc_selectors)
            await self.fill_input_safe(desc_sel, product_data['description'])

            # 3. Tải lên hình ảnh
            log("Đang tải ảnh sản phẩm lên...")
            # Chuẩn bị đường dẫn ảnh đầy đủ
            image_paths = []
            for img in product_data.get("images", []):
                # Chuyển đổi relative path sang absolute path
                abs_img = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", img.lstrip("/")))
                if os.path.exists(abs_img):
                    image_paths.append(abs_img)
                else:
                    # Thử lấy trực tiếp từ file download nếu là path đầy đủ
                    if os.path.exists(img):
                        image_paths.append(img)

            if image_paths:
                log(f"Đã tìm thấy {len(image_paths)} ảnh hợp lệ. Đang truyền file vào trình duyệt...")
                try:
                    # Shopee thường có input type=file ẩn dưới các nút bấm ảnh
                    file_input = self.page.locator("input[type='file']").first
                    await file_input.set_input_files(image_paths[:9]) # Shopee tối đa 9 ảnh
                    log("Đã đẩy tệp tin ảnh lên thành công.")
                except Exception as e:
                    log(f"Lỗi đẩy file ảnh: {e}. Vui lòng tự kéo thả ảnh vào.")
            else:
                log("Không tìm thấy ảnh cục bộ nào để tải lên.")

            # 3.2 Tải lên video sản phẩm (nếu có)
            video_paths = []
            for vid in product_data.get("videos", []):
                abs_vid = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", vid.lstrip("/")))
                if os.path.exists(abs_vid):
                    video_paths.append(abs_vid)
                else:
                    if os.path.exists(vid):
                        video_paths.append(vid)

            if video_paths:
                log(f"Đã tìm thấy {len(video_paths)} video hợp lệ. Đang truyền file video vào Shopee...")
                try:
                    video_input = self.page.locator("input[type='file'][accept*='video'], input[type='file'][accept*='mp4']").first
                    if await video_input.count() > 0:
                        await video_input.set_input_files(video_paths[0])
                        log("Đã đẩy tệp tin video lên thành công.")
                    else:
                        all_file_inputs = self.page.locator("input[type='file']")
                        if await all_file_inputs.count() > 1:
                            await all_file_inputs.nth(1).set_input_files(video_paths[0])
                            log("Đã đẩy tệp tin video lên bằng fallback input.")
                except Exception as e:
                    log(f"Lỗi đẩy file video: {e}. Vui lòng tự tải video lên.")

            # 3.3 Tự động thiết lập thuộc tính bắt buộc (Thương hiệu)
            try:
                log(f"Đang cấu hình thuộc tính bắt buộc (Thương hiệu: {default_brand})...")
                await self.switch_shopee_tab("Thông tin chi tiết", log)
                
                brand_dropdown_sel = "input[placeholder*='Chọn thương hiệu'], input[placeholder*='Select brand'], .brand-selector, [class*='brand'] .select-trigger"
                brand_locator = self.page.locator(brand_dropdown_sel).first
                if await brand_locator.count() > 0:
                    await brand_locator.click(timeout=3000)
                    await asyncio.sleep(1.5)
                    
                    search_input = self.page.locator("input[placeholder*='Tìm kiếm'], input[placeholder*='Search']").first
                    if await search_input.count() > 0 and await search_input.is_visible():
                        await search_input.fill(default_brand)
                        await asyncio.sleep(1)
                    
                    brand_opt = self.page.locator(f".shopee-select-option:has-text('{default_brand}'), [class*='option']:has-text('{default_brand}')").first
                    if await brand_opt.count() > 0:
                        await brand_opt.click()
                        log(f"✅ Đã tự động chọn thương hiệu: {default_brand}")
                    else:
                        await self.page.keyboard.press("Enter")
                        log("Đã bấm Enter để chọn mặc định thương hiệu.")
            except Exception as e:
                logger.debug(f"Không thể chọn thương hiệu tự động: {e}")

            # 4. Thiết lập Phân loại hàng (Variations) & Giá bán
            variations = product_data.get("variations", [])
            skus = product_data.get("skus", [])

            await self.switch_shopee_tab("Thông tin bán hàng", log)
            if variations and len(skus) > 1:
                log("Cấu hình phân loại hàng phức tạp...")
                # Nhấn nút bật phân loại hàng
                btn_var_selector = "button:has-text('Thêm phân loại'), button:has-text('Bật phân loại hàng'), text='Thêm nhóm phân loại', .add-variation-btn, [class*='add-tier']"
                await self.click_element_safe(btn_var_selector)
                await asyncio.sleep(2)
                
                # Điền thông tin phân loại 1
                var1 = variations[0]
                log(f"Nhóm phân loại 1: {var1['name']}")
                # Điền tên nhóm phân loại 1
                group1_selector = "input[placeholder*='Ví dụ: màu sắc'], input[placeholder*='Tên phân loại']"
                await self.fill_input_safe(group1_selector, var1['name'])
                
                # Điền các tùy chọn của nhóm 1
                for idx, opt in enumerate(var1['options']):
                    opt_selector = f"input[placeholder*='Ví dụ: Đỏ']"
                    # Shopee sẽ tự động sinh thêm input mới khi ta điền
                    # Tìm các input tùy chọn hiện có
                    opt_locators = self.page.locator("input[placeholder*='Ví dụ:']")
                    count = await opt_locators.count()
                    if idx < count:
                        await opt_locators.nth(idx).fill(opt)
                    else:
                        # Thử nhấn nút Thêm option hoặc gõ Enter
                        await self.page.keyboard.press("Enter")
                        await asyncio.sleep(0.5)
                        new_opt_locators = self.page.locator("input[placeholder*='Ví dụ:']")
                        new_count = await new_opt_locators.count()
                        if new_count > idx:
                            await new_opt_locators.nth(idx).fill(opt)
                
                # Nhóm phân loại 2 (nếu có)
                if len(variations) > 1:
                    var2 = variations[1]
                    log(f"Nhóm phân loại 2: {var2['name']}")
                    btn_var2_selector = "button:has-text('Thêm nhóm phân loại 2'), button:has-text('Thêm phân loại 2'), text='Thêm nhóm phân loại 2', [class*='add-tier']:nth-child(2)"
                    await self.click_element_safe(btn_var2_selector)
                    await asyncio.sleep(1)
                    
                    # Điền tên nhóm phân loại 2
                    # Tìm input trống tiếp theo
                    # Cách đơn giản: điền trực tiếp vào input có placeholder gợi ý kích thước
                    group2_selector = "input[placeholder*='Ví dụ: kích thước']"
                    await self.fill_input_safe(group2_selector, var2['name'])
                    
                    # Điền các tùy chọn nhóm 2
                    for idx, opt in enumerate(var2['options']):
                        opt_locators = self.page.locator("input[placeholder*='Ví dụ: S']")
                        count = await opt_locators.count()
                        if idx < count:
                            await opt_locators.nth(idx).fill(opt)
                        else:
                            await self.page.keyboard.press("Enter")
                            await asyncio.sleep(0.5)
                            new_opt_locators = self.page.locator("input[placeholder*='Ví dụ: S']")
                            new_count = await new_opt_locators.count()
                            if new_count > idx:
                                await new_opt_locators.nth(idx).fill(opt)

                # Sử dụng tính năng thiết lập hàng loạt (Batch Edit) để gán giá và kho
                # Điều này giúp điền giá trị nhanh chóng mà không cần lặp qua table
                log("Đang gán giá và kho hàng loạt...")
                await asyncio.sleep(2)
                
                # Điền giá bán trung bình
                avg_price = sum(sku['price'] for sku in skus) // len(skus)
                avg_stock = sum(sku['stock'] for sku in skus) // len(skus) if skus else 50
                if avg_stock <= 0: avg_stock = 50
                
                batch_price_selector = "input[placeholder='Điền vào'], input[placeholder*='Giá']"
                batch_stock_selector = "input[placeholder*='Kho hàng'], input[placeholder*='Số lượng']"
                
                # Điền vào trường thiết lập hàng loạt
                # Thử tìm vùng Thiết lập hàng loạt
                batch_inputs = self.page.locator(".product-edit-form-item input[placeholder*='Nhập']")
                # Tìm các input trong block thiết lập hàng loạt
                await self.fill_input_safe("input[placeholder='Giá bán']", str(avg_price))
                await self.fill_input_safe("input[placeholder='Kho hàng']", str(avg_stock))
                
                # Bấm Áp dụng cho tất cả
                apply_all_btn = self.page.locator("button:has-text('Áp dụng cho tất cả'), button:has-text('Áp dụng')")
                if await apply_all_btn.count() > 0:
                    await apply_all_btn.first.click()
                    log("Đã áp dụng giá và kho hàng loạt thành công.")

            else:
                # Đăng sản phẩm đơn lẻ (Không có phân loại)
                log("Thiết lập giá và kho cho sản phẩm đơn lẻ...")
                single_price = skus[0]['price'] if skus else product_data.get('base_price', 100000)
                single_stock = skus[0]['stock'] if skus else 50
                if single_stock <= 0: single_stock = 50
                
                # Tìm input Giá bán và Kho hàng trực tiếp
                await self.fill_input_safe("input[placeholder='Nhập giá bán'], input[placeholder*='Giá bán']", str(single_price))
                await self.fill_input_safe("input[placeholder='Nhập kho hàng'], input[placeholder*='Kho hàng']", str(single_stock))

            # Điền thông tin đóng gói & cân nặng
            log("Cấu hình kích thước và cân nặng đóng gói...")
            switched = await self.switch_shopee_tab("Vận chuyển", log)
            if not switched:
                log("Không tìm thấy tab Vận chuyển, đang cuộn trang xuống để hiển thị...")
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
            try:
                # Ưu tiên lấy cân nặng/kích thước từ sản phẩm nguồn
                prod_weight = product_data.get("source_weight")
                if prod_weight is not None:
                    log(f"Sử dụng cân nặng từ sản phẩm gốc: {prod_weight} kg")
                else:
                    prod_weight = default_weight
                    log(f"Sử dụng cân nặng mặc định: {prod_weight} kg")

                prod_dimensions = product_data.get("source_dimensions")
                if prod_dimensions:
                    log(f"Sử dụng kích thước từ sản phẩm gốc: Dài {prod_dimensions.get('length')}cm, Rộng {prod_dimensions.get('width')}cm, Cao {prod_dimensions.get('height')}cm")
                else:
                    prod_dimensions = default_dimensions
                    if prod_dimensions:
                        log(f"Sử dụng kích thước mặc định: Dài {prod_dimensions.get('length')}cm, Rộng {prod_dimensions.get('width')}cm, Cao {prod_dimensions.get('height')}cm")

                # Chuyển đổi cân nặng từ kg sang grams cho Shopee
                try:
                    shopee_weight = int(float(prod_weight) * 1000)
                except:
                    shopee_weight = 500
                
                # Selector tìm trường Cân nặng (khối lượng sau đóng gói)
                weight_selectors = [
                    "input[placeholder*='khối lượng']",
                    "input[placeholder*='Cân nặng']",
                    "input[placeholder*='Khối lượng']",
                    "input[placeholder='g']",
                    "input[placeholder='kg']",
                    "input[class*='weight']",
                    ".weight-input input",
                    ".product-edit-form-item:has-text('Cân nặng') input",
                    ".product-edit-form-item:has-text('Khối lượng') input"
                ]
                weight_sel = ", ".join(weight_selectors)
                
                # Thực hiện điền Cân nặng nhiều lần với các selector khác nhau nếu thất bại
                success_weight = await self.fill_input_safe(weight_sel, str(shopee_weight))
                if not success_weight:
                    log("Cảnh báo: Không tìm thấy ô nhập cân nặng bằng selector chung, thử rà soát toàn bộ input có placeholder liên quan...")
                    # Fallback tìm tất cả các thẻ input trong vùng vận chuyển
                
                # Điền kích thước đóng gói nếu có
                if prod_dimensions:
                    width_sel = "input[placeholder*='Rộng'], input[placeholder*='rộng'], input[class*='width'], .product-edit-form-item:has-text('Kích thước') input:nth-child(2)"
                    length_sel = "input[placeholder*='Dài'], input[placeholder*='dài'], input[class*='length'], .product-edit-form-item:has-text('Kích thước') input:nth-child(1)"
                    height_sel = "input[placeholder*='Cao'], input[placeholder*='cao'], input[class*='height'], .product-edit-form-item:has-text('Kích thước') input:nth-child(3)"
                    
                    # Nếu các input này nằm trong một container "Kích thước đóng gói", đôi khi placeholder chỉ là 'cm'
                    cm_inputs = self.page.locator("input[placeholder*='cm']")
                    if await cm_inputs.count() >= 3:
                        log("Tìm thấy 3 ô nhập kích thước với placeholder 'cm'.")
                        await cm_inputs.nth(0).fill(str(prod_dimensions.get("length", 10)))
                        await cm_inputs.nth(1).fill(str(prod_dimensions.get("width", 10)))
                        await cm_inputs.nth(2).fill(str(prod_dimensions.get("height", 10)))
                    else:
                        await self.fill_input_safe(length_sel, str(prod_dimensions.get("length", 10)))
                        await self.fill_input_safe(width_sel, str(prod_dimensions.get("width", 10)))
                        await self.fill_input_safe(height_sel, str(prod_dimensions.get("height", 10)))
                
                # Bật tất cả các đơn vị vận chuyển khả dụng
                log("Đang kích hoạt các đơn vị vận chuyển...")
                await asyncio.sleep(1)
                shipping_toggles = self.page.locator(".shopee-switch input, [class*='shipping'] .shopee-switch")
                count_toggles = await shipping_toggles.count()
                for t_idx in range(min(5, count_toggles)):
                    try:
                        is_checked = await shipping_toggles.nth(t_idx).is_checked()
                        if not is_checked:
                            await shipping_toggles.nth(t_idx).click(timeout=2000)
                    except:
                        pass
            except Exception as e:
                log(f"Không thể tự động điền cân nặng/vận chuyển: {e}")

            # Đăng tự động nếu ở chế độ auto_publish
            if auto_publish:
                log("🚀 Đang tự động lưu và đăng sản phẩm lên Shopee...")
                try:
                    publish_btn = self.page.locator("button:has-text('Lưu & Hiển thị'), button:has-text('Lưu và hiển thị'), button.shopee-button--primary").first
                    if await publish_btn.count() > 0:
                        await publish_btn.click()
                        log("Đã bấm nút đăng! Đang kiểm tra xem Shopee có lưu đăng bài thành công...")
                        
                        # Chờ tối đa 8 giây xem URL có chuyển hướng sang trang quản lý danh sách sản phẩm hay không
                        success = False
                        for _ in range(8):
                            await asyncio.sleep(1)
                            if "portal/product" in self.page.url and "new" not in self.page.url:
                                success = True
                                break
                        
                        if success:
                            log("✅ Đăng sản phẩm lên Shopee thành công! Đang đóng trình duyệt...")
                            await asyncio.sleep(2)
                            await self.close_browser()
                            return True
                        else:
                            log("⚠️ CẢNH BÁO: Đăng sản phẩm thất bại hoặc bị kẹt do thiếu thông tin bắt buộc (ví dụ: chưa điền Thương hiệu/Brand).")
                            log("👉 Trình duyệt được GIỮ NGUYÊN để bạn sửa lỗi và tự nhấn đăng bài.")
                            return False
                except Exception as e:
                    log(f"Lỗi bấm đăng tự động: {e}")

            log("🚀 Đã điền xong các thông tin cơ bản!")
            log("👉 Phần việc còn lại của bạn trên trình duyệt:")
            log("1. Chọn ngành hàng chính xác (nếu Shopee chưa tự động nhận diện).")
            log("2. Điền kích thước đóng gói (Cân nặng, Chiều rộng, dài, cao) của sản phẩm ở cuối trang.")
            log("3. Bật đơn vị vận chuyển phù hợp và bấm nút 'Lưu và Hiển thị' (hoặc Đăng sản phẩm).")
            log("Hệ thống sẽ giữ trình duyệt này mở để bạn hoàn thiện nốt các bước cuối cùng.")

            # Giữ nguyên trình duyệt, không đóng
            return True

        except Exception as e:
            log(f"LỖI trong tiến trình điền form Shopee: {e}")
            # Để người dùng tự thao tác tiếp nếu lỗi giữa chừng
            return False

    async def upload_to_tiktok(
        self, 
        product_data: dict, 
        auto_publish: bool = False, 
        default_brand: str = "No brand",
        default_weight: float = 0.5, 
        default_dimensions: dict = None, 
        log_callback=None
    ) -> bool:
        """Tự động điền thông tin sản phẩm trên TikTok Seller Center."""
        def log(msg):
            logger.info(msg)
            if log_callback:
                if inspect.iscoroutinefunction(log_callback):
                    asyncio.create_task(log_callback(msg))
                else:
                    try: log_callback(msg)
                    except: pass

        log("Bắt đầu khởi tạo trình duyệt TikTok...")
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()

        try:
            log("Đang mở trang đăng sản phẩm mới trên TikTok Shop...")
            await self.safe_goto("https://seller-vn.tiktok.com/product/create")
            await asyncio.sleep(5)

            # Kiểm tra trạng thái đăng nhập
            if "login" in self.page.url or "seller-vn.tiktok.com" not in self.page.url:
                log("CẢNH BÁO: Phát hiện bạn chưa đăng nhập TikTok Seller Center trên profile này.")
                log("Vui lòng đăng nhập thủ công trên trình duyệt đang mở. Công cụ sẽ tự động tiếp tục khi bạn vào trang đăng sản phẩm...")
                while "product/create" not in self.page.url and "product/publish" not in self.page.url:
                    if self.page.is_closed():
                        log("Trình duyệt đã bị đóng. Kết thúc.")
                        return False
                    await asyncio.sleep(2)
                log("Đã phát hiện đăng nhập thành công. Đang tiếp tục...")

            log("Đang chờ giao diện đăng sản phẩm TikTok Shop tải hoàn tất...")
            # Chờ sự xuất hiện của input Tên sản phẩm
            name_selector = "input[placeholder*='tên sản phẩm'], input[placeholder*='Product name'], textarea[placeholder*='tên sản phẩm']"
            try:
                await self.page.wait_for_selector(name_selector, timeout=60000)
            except Exception:
                log("Giao diện tải quá lâu. Vui lòng tự điền nếu không tìm thấy selector.")
            
            await asyncio.sleep(3)

            # 1. Điền Tên sản phẩm
            log(f"Điền tên sản phẩm: {product_data['title']}")
            await self.fill_input_safe(name_selector, product_data['title'])
            
            # Tự động chọn ngành hàng gợi ý trên TikTok Shop nếu có
            try:
                await asyncio.sleep(3)
                log("Đang tìm ngành hàng gợi ý từ TikTok Shop...")
                tiktok_cat_selectors = [
                    ".recommend-category-item",
                    ".category-suggest-item",
                    "[class*='recommend'] [class*='category']",
                    "[class*='suggest'] [class*='item']"
                ]
                for cat_sel in tiktok_cat_selectors:
                    cat_locator = self.page.locator(cat_sel)
                    if await cat_locator.count() > 0:
                        await cat_locator.first.click(timeout=3000)
                        log("Đã tự động chọn ngành hàng gợi ý tối ưu.")
                        break
            except Exception as e:
                logger.debug(f"Không tự động click được ngành hàng gợi ý: {e}")

            # 2. Điền Mô tả sản phẩm
            log("Điền mô tả sản phẩm...")
            # TikTok Shop sử dụng rich text editor (thường là div contenteditable)
            desc_selectors = [
                "[contenteditable='true']",
                ".editor-content", 
                ".rich-text-editor", 
                "textarea[placeholder*='mô tả']",
                "textarea[placeholder*='Mô tả']",
                ".product-description textarea"
            ]
            desc_sel = ", ".join(desc_selectors)
            await self.fill_input_safe(desc_sel, product_data['description'])

            # 3. Tải lên hình ảnh
            log("Đang tải ảnh sản phẩm lên...")
            image_paths = []
            for img in product_data.get("images", []):
                abs_img = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", img.lstrip("/")))
                if os.path.exists(abs_img):
                    image_paths.append(abs_img)
                else:
                    if os.path.exists(img):
                        image_paths.append(img)

            if image_paths:
                log(f"Đã tìm thấy {len(image_paths)} ảnh hợp lệ. Đang truyền file vào trình duyệt...")
                try:
                    file_input = self.page.locator("input[type='file']").first
                    await file_input.set_input_files(image_paths[:9])
                    log("Đã đẩy tệp tin ảnh lên thành công.")
                except Exception as e:
                    log(f"Lỗi đẩy file ảnh: {e}. Vui lòng tự kéo thả ảnh vào.")

            # 3.2 Tải lên video sản phẩm TikTok Shop (nếu có)
            video_paths = []
            for vid in product_data.get("videos", []):
                abs_vid = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", vid.lstrip("/")))
                if os.path.exists(abs_vid):
                    video_paths.append(abs_vid)
                else:
                    if os.path.exists(vid):
                        video_paths.append(vid)

            if video_paths:
                log(f"Đã tìm thấy {len(video_paths)} video hợp lệ. Đang truyền video vào TikTok Shop...")
                try:
                    # Tìm input file cho video (thường có accept chứa video hoặc mp4)
                    video_input = self.page.locator("input[type='file'][accept*='video'], input[type='file'][accept*='mp4']").first
                    if await video_input.count() > 0:
                        await video_input.set_input_files(video_paths[0])
                        log("Đã đẩy tệp tin video lên TikTok Shop thành công.")
                    else:
                        all_file_inputs = self.page.locator("input[type='file']")
                        if await all_file_inputs.count() > 1:
                            await all_file_inputs.nth(1).set_input_files(video_paths[0])
                            log("Đã đẩy tệp tin video lên TikTok Shop bằng fallback input.")
                except Exception as e:
                    log(f"Lỗi đẩy file video lên TikTok Shop: {e}")

            # 3.3 Tự động thiết lập Thương hiệu TikTok
            try:
                brand_input = self.page.locator("input[placeholder*='Thương hiệu'], input[placeholder*='Brand'], .brand-select input").first
                if await brand_input.count() > 0 and await brand_input.is_visible():
                    log(f"Đang cấu hình Thương hiệu TikTok: {default_brand}")
                    await brand_input.click(timeout=3000)
                    await asyncio.sleep(1)
                    await self.fill_input_safe("input[placeholder*='Thương hiệu'], input[placeholder*='Brand']", default_brand)
                    await asyncio.sleep(1)
                    
                    brand_opt = self.page.locator(f"li:has-text('{default_brand}'), [class*='option']:has-text('{default_brand}')").first
                    if await brand_opt.count() > 0:
                        await brand_opt.click()
                        log(f"✅ Đã chọn thương hiệu TikTok: {default_brand}")
                    else:
                        await self.page.keyboard.press("Enter")
            except Exception as e:
                logger.debug(f"Không thể tự động chọn thương hiệu TikTok: {e}")

            # 4. Thiết lập Biến thể & Giá
            variations = product_data.get("variations", [])
            skus = product_data.get("skus", [])

            if variations and len(skus) > 1:
                log("Đang thiết lập các biến thể sản phẩm...")
                # Nhấn nút kích hoạt biến thể
                btn_var_selector = "button:has-text('Kích hoạt biến thể'), button:has-text('Thêm biến thể'), [class*='variation'] button"
                await self.click_element_safe(btn_var_selector)
                await asyncio.sleep(2)
                
                # Điền nhóm biến thể 1
                var1 = variations[0]
                log(f"Nhóm biến thể 1: {var1['name']}")
                # Thử điền tên biến thể
                var1_name_selector = "input[placeholder*='Ví dụ: màu sắc'], input[placeholder*='Color']"
                await self.fill_input_safe(var1_name_selector, var1['name'])
                
                # Điền các tùy chọn
                for idx, opt in enumerate(var1['options']):
                    opt_selector = "input[placeholder*='Ví dụ: Đỏ'], input[placeholder*='Red']"
                    opt_locators = self.page.locator(opt_selector)
                    count = await opt_locators.count()
                    if idx < count:
                        await opt_locators.nth(idx).fill(opt)
                    else:
                        await self.page.keyboard.press("Enter")
                        await asyncio.sleep(0.5)
                        new_opt_locators = self.page.locator(opt_selector)
                        new_count = await new_opt_locators.count()
                        if new_count > idx:
                            await new_opt_locators.nth(idx).fill(opt)

                # Sử dụng chỉnh sửa hàng loạt của TikTok để áp dụng giá/kho
                log("Đang gán giá và kho hàng loạt trên TikTok Shop...")
                await asyncio.sleep(2)
                
                avg_price = sum(sku['price'] for sku in skus) // len(skus)
                avg_stock = sum(sku['stock'] for sku in skus) // len(skus) if skus else 50
                if avg_stock <= 0: avg_stock = 50
                
                # Nhấn nút "Chỉnh sửa hàng loạt" hoặc "Batch Edit"
                batch_btn = self.page.locator("button:has-text('Chỉnh sửa hàng loạt'), button:has-text('Batch edit')")
                if await batch_btn.count() > 0:
                    await batch_btn.first.click()
                    await asyncio.sleep(1)
                    
                    # Điền giá trị
                    await self.fill_input_safe("input[placeholder='Giá bán'], input[placeholder*='Price']", str(avg_price))
                    await self.fill_input_safe("input[placeholder='Số lượng'], input[placeholder*='Stock'], input[placeholder*='Quantity']", str(avg_stock))
                    
                    # Xác nhận
                    confirm_btn = self.page.locator("button:has-text('Lưu'), button:has-text('Save'), button:has-text('Xác nhận')")
                    await confirm_btn.first.click()
                    log("Đã áp dụng thông tin hàng loạt.")
            else:
                # Đơn lẻ
                log("Thiết lập giá và kho sản phẩm đơn lẻ...")
                single_price = skus[0]['price'] if skus else product_data.get('base_price', 100000)
                single_stock = skus[0]['stock'] if skus else 50
                if single_stock <= 0: single_stock = 50
                
                # Điền trực tiếp giá và kho hàng
                price_selector = "input[placeholder*='Giá bán'], input[placeholder*='Price']"
                stock_selector = "input[placeholder*='Số lượng'], input[placeholder*='Stock'], input[placeholder*='Quantity']"
                await self.fill_input_safe(price_selector, str(single_price))
                await self.fill_input_safe(stock_selector, str(single_stock))

            # Điền cân nặng và kích thước
            log("Cấu hình cân nặng & kích thước đóng gói TikTok Shop...")
            try:
                # Ưu tiên lấy cân nặng/kích thước từ sản phẩm nguồn
                prod_weight = product_data.get("source_weight")
                if prod_weight is not None:
                    log(f"Sử dụng cân nặng từ sản phẩm gốc: {prod_weight} kg")
                else:
                    prod_weight = default_weight
                    log(f"Sử dụng cân nặng mặc định: {prod_weight} kg")

                prod_dimensions = product_data.get("source_dimensions")
                if prod_dimensions:
                    log(f"Sử dụng kích thước từ sản phẩm gốc: Dài {prod_dimensions.get('length')}cm, Rộng {prod_dimensions.get('width')}cm, Cao {prod_dimensions.get('height')}cm")
                else:
                    prod_dimensions = default_dimensions
                    if prod_dimensions:
                        log(f"Sử dụng kích thước mặc định: Dài {prod_dimensions.get('length')}cm, Rộng {prod_dimensions.get('width')}cm, Cao {prod_dimensions.get('height')}cm")

                # TikTok cân nặng tính bằng kg (ví dụ 0.5)
                weight_selectors = [
                    "input[placeholder*='Cân nặng']",
                    "input[placeholder*='Trọng lượng']",
                    "input[placeholder*='trọng lượng']",
                    "input[placeholder*='Weight']",
                    "input[placeholder*='kg']",
                    "input[placeholder*='g']",
                    "[class*='weight'] input"
                ]
                weight_sel = ", ".join(weight_selectors)
                await self.fill_input_safe(weight_sel, str(prod_weight))
                
                if prod_dimensions:
                    width_selectors = ["input[placeholder*='rộng']", "input[placeholder*='Rộng']", "input[placeholder*='Width']", "input[placeholder*='W']", "[class*='width'] input"]
                    length_selectors = ["input[placeholder*='dài']", "input[placeholder*='Dài']", "input[placeholder*='Length']", "input[placeholder*='L']", "[class*='length'] input"]
                    height_selectors = ["input[placeholder*='cao']", "input[placeholder*='Cao']", "input[placeholder*='Height']", "input[placeholder*='H']", "[class*='height'] input"]
                    
                    # Nếu TikTok dùng chung placeholder "cm"
                    cm_inputs = self.page.locator("input[placeholder*='cm']")
                    if await cm_inputs.count() >= 3:
                        log("Tìm thấy 3 ô nhập kích thước TikTok với placeholder 'cm'.")
                        await cm_inputs.nth(0).fill(str(prod_dimensions.get("length", 10)))
                        await cm_inputs.nth(1).fill(str(prod_dimensions.get("width", 10)))
                        await cm_inputs.nth(2).fill(str(prod_dimensions.get("height", 10)))
                    else:
                        await self.fill_input_safe(", ".join(length_selectors), str(prod_dimensions.get("length", 10)))
                        await self.fill_input_safe(", ".join(width_selectors), str(prod_dimensions.get("width", 10)))
                        await self.fill_input_safe(", ".join(height_selectors), str(prod_dimensions.get("height", 10)))
            except Exception as e:
                log(f"Không thể tự động điền cân nặng/vận chuyển TikTok: {e}")

            # Đăng tự động nếu ở chế độ auto_publish
            if auto_publish:
                log("🚀 Đang tự động lưu và kích hoạt sản phẩm lên TikTok Shop...")
                try:
                    publish_btn = self.page.locator("button:has-text('Kích hoạt'), button:has-text('Publish'), button:has-text('Đồng ý và Kích hoạt')").first
                    if await publish_btn.count() > 0:
                        await publish_btn.click()
                        log("Đã bấm nút Kích hoạt! Đang kiểm tra phản hồi từ TikTok Shop...")
                        
                        # Chờ tối đa 8 giây xem URL có chuyển hướng thoát khỏi trang tạo/sửa hay không
                        success = False
                        for _ in range(8):
                            await asyncio.sleep(1)
                            if "product/create" not in self.page.url and "product/publish" not in self.page.url:
                                success = True
                                break
                        
                        if success:
                            log("✅ Đăng sản phẩm lên TikTok Shop thành công! Đang đóng trình duyệt...")
                            await asyncio.sleep(2)
                            await self.close_browser()
                            return True
                        else:
                            log("⚠️ CẢNH BÁO: Kích hoạt sản phẩm thất bại. Có thể do thiếu thuộc tính bắt buộc hoặc lỗi định dạng.")
                            log("👉 Trình duyệt được GIỮ NGUYÊN để bạn kiểm tra lỗi đỏ trên màn hình và tự bấm Kích hoạt lại.")
                            return False
                except Exception as e:
                    log(f"Lỗi bấm đăng tự động TikTok: {e}")

            log("🚀 Đã điền xong các thông tin cơ bản lên TikTok Shop!")
            log("👉 Phần việc còn lại của bạn trên trình duyệt:")
            log("1. Chọn ngành hàng chính xác (nếu hệ thống chưa tự nhận diện).")
            log("2. Điền thông tin vận chuyển và cân nặng đóng gói ở cuối trang.")
            log("3. Kiểm tra lại toàn bộ và bấm nút 'Kích hoạt' (hoặc Đăng sản phẩm).")
            log("Hệ thống sẽ giữ trình duyệt này mở để bạn hoàn tất đăng bài.")

            return True

        except Exception as e:
            log(f"LỖI trong tiến trình điền form TikTok: {e}")
            return False
