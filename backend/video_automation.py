import asyncio
import os
import sys
import logging
import inspect
import psutil
from playwright.async_api import async_playwright, Page, BrowserContext

# Thiết lập ghi log cơ bản
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ShopeeAutomation")

def cleanup_stale_profile(profile_dir: str):
    """Tự động giải phóng các tiến trình Chrome/Playwright cũ và dọn dẹp lock file tránh lỗi ProcessSingleton."""
    try:
        abs_prof = os.path.abspath(profile_dir)
        norm_prof = os.path.normpath(abs_prof).lower()
        prof_base = os.path.basename(norm_prof).lower()
        
        # 1. Kill các process Chrome/Chromium cũ đang chiếm giữ thư mục profile này
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                exe = (proc.info.get('exe') or '').lower()
                cmdline = proc.info.get('cmdline') or []
                cmd_str = " ".join(cmdline).lower()
                is_browser_exe = any(b in exe for b in ['chrome.exe', 'chromium.exe', 'msedge.exe', 'ms-playwright'])
                if is_browser_exe and (norm_prof in cmd_str or prof_base in cmd_str):
                    proc.kill()
            except Exception:
                pass

        # 2. Xóa các file lock của Chromium / Chrome
        if os.path.exists(abs_prof):
            for fname in ["SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile", "Lockfile", "LOCK"]:
                fpath = os.path.join(abs_prof, fname)
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Lỗi dọn dẹp profile cũ: {e}")

class ShopeeVideoUploader:
    def __init__(self, profile_dir: str = "shopee_profile"):
        from backend.profile_utils import resolve_profile_path
        self.profile_dir = resolve_profile_path(profile_dir)
        os.makedirs(self.profile_dir, exist_ok=True)
        self.playwright = None
        self.context: BrowserContext = None
        self.page: Page = None

    async def init_browser(self, headless: bool = False) -> BrowserContext:
        """Khởi tạo trình duyệt Playwright với Persistent Context để giữ session đăng nhập."""
        cleanup_stale_profile(self.profile_dir)
        
        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        # Cài đặt tham số tránh bị phát hiện (stealth settings)
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
        
        # Thử khởi chạy trình duyệt tối đa 3 lần đề phòng lỗi lock tạm thời
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
                    logger.error(f"Không thể khởi chạy trình duyệt sau 3 lần thử: {e}")
                    raise RuntimeError(
                        f"Không thể mở trình duyệt trên thư mục profile {os.path.basename(self.profile_dir)}. "
                        "Có thể trình duyệt khác của tài khoản này đang mở. Vui lòng đóng hết và thử lại."
                    ) from e
                logger.warning(f"Lần thử {attempt}/3 khởi chạy trình duyệt thất bại, đợi 1s... Lỗi: {e}")
                await asyncio.sleep(1)
        
        # Xoá bỏ thuộc tính navigator.webdriver để lách bộ quét của Shopee
        await self.context.add_init_script("delete navigator.__proto__.webdriver;")
        
        # Thiết lập thời gian chờ mặc định là 35 giây
        self.context.set_default_timeout(35000)
        return self.context

    async def close_browser(self):
        """Đóng trình duyệt và dọn dẹp tài nguyên."""
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            logger.info("Đã đóng trình duyệt Playwright thành công.")
        except Exception as e:
            logger.error(f"Lỗi khi đóng trình duyệt: {e}")
            self.context = None
            self.playwright = None

    async def safe_goto(self, url: str, wait_until: str = "domcontentloaded", retries: int = 3, timeout: int = 30000) -> bool:
        """Thực hiện điều hướng trang với cơ chế thử lại nếu gặp lỗi mạng."""
        for attempt in range(1, retries + 1):
            try:
                await self.page.goto(url, wait_until=wait_until, timeout=timeout)
                return True
            except Exception as e:
                logger.warning(f"Lần thử {attempt}/{retries} điều hướng tới {url} thất bại: {e}")
                if attempt == retries:
                    raise e
                await asyncio.sleep(3)
        return False

    async def click_element(self, selector_or_locator, timeout: int = 5000) -> bool:
        """Thực hiện click an toàn một phần tử với nhiều phương pháp fallback."""
        try:
            locator = self.page.locator(selector_or_locator).first if isinstance(selector_or_locator, str) else selector_or_locator
            await locator.scroll_into_view_if_needed(timeout=timeout)
            # Thử click thông thường
            await locator.click(timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"Click thường thất bại: {e}. Thử force click...")
            try:
                await locator.click(force=True, timeout=timeout)
                return True
            except Exception as e2:
                logger.warning(f"Force click thất bại: {e2}. Thử dispatch click event...")
                try:
                    await locator.dispatch_event("click", timeout=timeout)
                    return True
                except Exception as e3:
                    logger.error(f"Tất cả phương pháp click đều thất bại: {e3}")
                    return False

    async def open_login_session(self, log_callback=None) -> bool:
        """Mở cửa sổ trình duyệt để người dùng đăng nhập thủ công và lưu session."""
        def log(msg):
            logger.info(msg)
            if log_callback:
                asyncio.create_task(log_callback(msg))

        log("Đang mở trình duyệt để bạn đăng nhập Shopee...")
        await self.init_browser(headless=False)
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        try:
            # Đi đến trang Seller Centre
            log("Đang tải trang Kênh Người Bán Shopee (banhang.shopee.vn)...")
            await self.safe_goto("https://banhang.shopee.vn/", wait_until="domcontentloaded")
            
            log("Trình duyệt đã mở. Vui lòng thực hiện đăng nhập trên cửa sổ trình duyệt (Nhập OTP, SMS, Quét QR...).")
            log("Sau khi đăng nhập thành công và vào tới trang chính Shopee, bạn hãy ĐÓNG cửa sổ trình duyệt đó đi và bấm nút 'Kiểm tra' cạnh nút Đăng nhập trên giao diện tool để xác nhận trực tuyến.")
            
            # Vòng lặp chờ người dùng đăng nhập hoặc tắt trình duyệt
            while True:
                if not self.context or not self.context.pages or (self.page and self.page.is_closed()):
                    if self.context and self.context.pages:
                        self.page = self.context.pages[0]
                    else:
                        log("Cửa sổ trình duyệt đã bị đóng.")
                        break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            log("Đã kết thúc phiên đăng nhập.")
        finally:
            await self.close_browser()
        return True

    async def check_login_status(self) -> bool:
        """Kiểm tra xem session cũ còn hiệu lực hay không."""
        try:
            # Sử dụng headful để tránh bị chặn kiểm tra bot ở headless mode
            await self.init_browser(headless=False)
            self.page = await self.context.new_page()
            
            # Đến thẳng trang đăng video
            logger.info("Đang điều hướng tới trang upload để kiểm tra login...")
            await self.safe_goto("https://banhang.shopee.vn/creator-center/video-upload/upload", wait_until="domcontentloaded")
            await asyncio.sleep(5) # Đợi chuyển hướng nếu có
            
            current_url = self.page.url
            logger.info(f"URL hiện tại sau khi kiểm tra login: {current_url}")
            
            # Nếu bị chuyển hướng sang trang đăng nhập, trang xác minh hoặc không còn ở creator-center
            if "creator-center" not in current_url.lower() or any(term in current_url.lower() for term in ["login", "signin", "verify", "traffic", "accounts.shopee.vn"]):
                logger.info("Chưa đăng nhập (phát hiện chuyển hướng hoặc url không hợp lệ).")
                return False
                
            # Kiểm tra xem input file upload video có tồn tại trên page không để xác nhận thực sự truy cập được form
            try:
                file_input = self.page.locator("input[type='file']").first
                await file_input.wait_for(state="attached", timeout=5000)
                logger.info("Đã đăng nhập thành công (tìm thấy input file).")
                return True
            except Exception:
                logger.warning("Không tìm thấy input file trên trang upload. Đăng nhập có thể thất bại.")
            
            return False
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra trạng thái login: {e}")
            return False
        finally:
            await self.close_browser()

    async def capture_screenshot(self, name: str, log_callback=None) -> str:
        """Chụp ảnh màn hình để hỗ trợ tìm lỗi."""
        def log(msg):
            logger.info(msg)
            if log_callback:
                if inspect.iscoroutinefunction(log_callback):
                    asyncio.create_task(log_callback(msg))
                else:
                    try:
                        log_callback(msg)
                    except Exception:
                        pass
        try:
            static_dir = os.path.abspath(os.path.join("backend", "static"))
            os.makedirs(static_dir, exist_ok=True)
            screenshot_path = os.path.join(static_dir, name)
            await self.page.screenshot(path=screenshot_path)
            log(f"📸 Đã chụp ảnh màn hình lưu tại: {screenshot_path}")
            
            # Copy vào thư mục artifacts của ide
            artifacts_dir = r"C:\Users\HoangHaiPC\.gemini\antigravity-ide\brain\fdec143c-8fa9-4778-956b-8badcb0a71c4"
            if os.path.exists(artifacts_dir):
                import shutil
                shutil.copy(screenshot_path, os.path.join(artifacts_dir, name))
                log(f"📸 Đã copy ảnh chụp lỗi vào artifacts: {name}")
            return screenshot_path
        except Exception as e:
            logger.error(f"Không thể chụp ảnh màn hình: {e}")
            return ""

    async def upload_video(
        self, 
        video_path: str, 
        caption: str, 
        product_keywords: list = None, 
        product_tagging_mode: str = "manual",
        log_callback=None
    ) -> bool:
        """
        Thực hiện tải lên 1 video, gắn sản phẩm và đăng bài.
        product_keywords: danh sách từ khoá hoặc ID/URL sản phẩm cần gắn (tối đa 6).
        """
        def log(msg):
            logger.info(msg)
            if log_callback:
                if inspect.iscoroutinefunction(log_callback):
                    asyncio.create_task(log_callback(msg))
                else:
                    try:
                        log_callback(msg)
                    except Exception:
                        pass

        if not os.path.exists(video_path):
            log(f"LỖI: Tệp video không tồn tại tại đường dẫn: {video_path}")
            return False

        log(f"Bắt đầu quá trình đăng video: {os.path.basename(video_path)}")
        
        # Mở trình duyệt ở chế độ hiển thị (headful) để đảm bảo độ tin cậy và người dùng có thể can thiệp nếu cần
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()
        
        try:
            # 1. Đi tới trang đăng video Shopee
            log("Đang điều hướng tới trang tải video Shopee...")
            await self.safe_goto("https://banhang.shopee.vn/creator-center/video-upload/upload", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            # Kiểm tra xem có bị bắt đăng nhập không
            current_url = self.page.url.lower()
            if "creator-center" not in current_url or any(term in current_url for term in ["login", "signin", "verify", "traffic", "accounts.shopee.vn"]):
                log("LỖI: Chưa đăng nhập hoặc phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.")
                return False
            
            # 2. Tải video lên thông qua input file
            log("Đang tìm input file để chọn video...")
            input_file = self.page.locator("input[type='file']").first
            await input_file.set_input_files(video_path)
            log("Đã chọn file video. Đang chờ video được tải lên...")
            
            # 3. Đợi khung nhập mô tả hiển thị (Minh chứng video đã được tải lên và bắt đầu xử lý)
            log("Đang chờ form nhập thông tin video xuất hiện...")
            form_selector = ".src-pages-videoUpload-components-CaptionInput---editor--2RBj0, [contenteditable='true'], [placeholder*='chú thích'], [placeholder*='caption'], button:has-text('Thêm sản phẩm')"
            
            try:
                # Đợi tối đa 45 giây cho form xuất hiện
                await self.page.wait_for_selector(form_selector, timeout=45000)
                log("Form nhập thông tin video đã sẵn sàng.")
            except Exception:
                log("LỖI: Quá thời gian chờ form nhập thông tin video. Tải video lên có thể đã thất bại.")
                return False

            # Đợi một chút để tiến trình tải lên hiển thị ổn định
            await asyncio.sleep(3)
            
            # Đợi tải video lên hoàn tất (kiểm tra trạng thái "Đang tải" hoặc phần trăm biến mất)
            log("Đang tải video lên hệ thống, vui lòng chờ...")
            for check_idx in range(120): # Chờ tối đa 10 phút (120 * 5s)
                is_uploading = False
                uploading_el = self.page.locator("text='Đang tải'")
                percent_el = self.page.locator("span:has-text('%')")
                
                if await uploading_el.count() > 0 and await uploading_el.first.is_visible():
                    is_uploading = True
                    try:
                        pct = await percent_el.first.inner_text() if await percent_el.count() > 0 else ""
                        log(f"Tiến trình tải lên: {pct if pct else 'Đang xử lý...'}")
                    except Exception:
                        pass
                elif await percent_el.count() > 0 and await percent_el.first.is_visible():
                    is_uploading = True
                    try:
                        pct = await percent_el.first.inner_text()
                        log(f"Tiến trình tải lên: {pct}")
                    except Exception:
                        pass
                
                if is_uploading:
                    await asyncio.sleep(5)
                else:
                    log("Tải video lên hoàn tất.")
                    break
            
            # 4. Nhập Caption / Mô tả
            log("Đang nhập mô tả cho video...")
            caption_filled = False
            caption_selectors = [
                "[placeholder*='chú thích vào video']",
                "[placeholder*='chú thích']",
                "[placeholder*='chú thích của bạn']",
                "[placeholder*='caption']",
                ".src-pages-videoUpload-components-CaptionInput---editor--2RBj0",
                "[contenteditable='true']",
                "textarea"
            ]
            for sel in caption_selectors:
                try:
                    element = self.page.locator(sel).first
                    if await element.is_visible():
                        await element.click()
                        await self.page.keyboard.press("Control+A")
                        await self.page.keyboard.press("Backspace")
                        await element.fill(caption)
                        log(f"Đã nhập mô tả: '{caption}'")
                        caption_filled = True
                        break
                except Exception as e:
                    logger.warning(f"Lỗi thử selector mô tả {sel}: {e}")
                    continue
                    
            if not caption_filled:
                log("CẢNH BÁO: Không tìm thấy ô nhập mô tả tự động. Vui lòng nhập tay nếu cần.")
            
            await asyncio.sleep(2)
            
            # 4. Gắn sản phẩm (Giỏ hàng)
            log("Kiểm tra tính năng gắn giỏ hàng của Shop...")
            
            # Xác định xem có nên mở giỏ hàng hay không
            should_click_add_product = False
            if product_tagging_mode == "auto":
                should_click_add_product = True
            elif product_tagging_mode == "manual":
                if product_keywords and len(product_keywords) > 0:
                    should_click_add_product = True
                else:
                    log("Chế độ Gắn sản phẩm bằng tay (manual) và không cấu hình từ khóa -> Bỏ qua bước gắn giỏ hàng.")
            
            add_product_clicked = False
            if should_click_add_product:
                add_product_selectors = [
                    ".src-pages-videoUpload-components-CaptionEdit---addProduct--Yaz5D",
                    "[class*='addProduct']",
                    "text='Thêm sản phẩm'",
                    "text='Thêm sản phẩm (0/6)'",
                    "button:has-text('Thêm sản phẩm')",
                    ".add-product-btn"
                ]
                
                for sel in add_product_selectors:
                    try:
                        btn = self.page.locator(sel).first
                        if await btn.is_visible():
                            clicked = await self.click_element(btn)
                            if clicked:
                                log("Đã click nút 'Thêm sản phẩm'. Đang kiểm tra xem modal danh sách có mở ra...")
                                add_product_clicked = True
                                break
                    except Exception:
                        continue
            
            modal_opened = False
            if add_product_clicked:
                await asyncio.sleep(3) # Đợi modal hiển thị
                
                # Kiểm tra xem có phần tử đặc trưng của modal sản phẩm xuất hiện hay không
                modal_indicators = [
                    ".eds-react-dialog",
                    "input[placeholder*='Tìm kiếm']",
                    "input[placeholder*='Search']",
                    "button:has-text('Xác nhận')",
                    "button:has-text('Confirm')"
                ]
                for m_sel in modal_indicators:
                    try:
                        el = self.page.locator(m_sel).first
                        if await el.count() > 0 and await el.is_visible():
                            modal_opened = True
                            log("Phát hiện modal sản phẩm hiển thị thành công. Shop này hỗ trợ gắn giỏ hàng.")
                            break
                    except Exception:
                        continue
            
            if modal_opened:
                if product_keywords and len(product_keywords) > 0:
                    log(f"Phát hiện yêu cầu gắn sản phẩm: {product_keywords}")
                    
                    # Duyệt qua tối đa 6 sản phẩm
                    for idx, keyword in enumerate(product_keywords[:6]):
                        log(f"Đang tìm kiếm sản phẩm thứ {idx+1}: {keyword}")
                        
                        # Tìm ô tìm kiếm trong modal
                        search_selectors = [
                            ".eds-react-dialog input[placeholder*='Tìm kiếm']",
                            "input[placeholder*='Tìm kiếm tên sản phẩm']",
                            "input[placeholder*='Tìm kiếm']",
                            "input[placeholder*='Search']",
                            ".product-search-input input"
                        ]
                        
                        search_input_found = False
                        for s_sel in search_selectors:
                            try:
                                s_input = self.page.locator(s_sel).first
                                if await s_input.is_visible():
                                    await s_input.click()
                                    await self.page.keyboard.press("Control+A")
                                    await self.page.keyboard.press("Backspace")
                                    await s_input.fill(keyword)
                                    search_input_found = True
                                    break
                            except Exception:
                                continue
                        
                        if search_input_found:
                            # Tìm và click nút Áp dụng
                            apply_btn_selectors = [
                                ".eds-react-dialog button:has-text('Áp dụng')",
                                ".eds-react-dialog button:has-text('Apply')",
                                "button:has-text('Áp dụng')",
                                "button:has-text('Apply')",
                                ".eds-btn--primary"
                            ]
                            
                            apply_clicked = False
                            for a_sel in apply_btn_selectors:
                                try:
                                    apply_btn = self.page.locator(a_sel).first
                                    if await apply_btn.is_visible():
                                        apply_clicked = await self.click_element(apply_btn)
                                        if apply_clicked:
                                            break
                                except Exception:
                                    continue
                                    
                            if not apply_clicked:
                                await self.page.keyboard.press("Enter")
                                
                            # Chờ bảng sản phẩm hiển thị bằng cách đợi dòng dữ liệu đầu tiên xuất hiện
                            try:
                                await self.page.locator(".eds-react-dialog tbody tr").first.wait_for(state="visible", timeout=8000)
                            except Exception:
                                await asyncio.sleep(3) # Fallback sleep
                            
                            selected = False
                            # Đầu tiên thử tìm checkbox của dòng sản phẩm đầu tiên trong bảng tbody
                            try:
                                first_row = self.page.locator(".eds-react-dialog tbody tr").first
                                if await first_row.count() > 0:
                                    for sub_sel in ["input[type='checkbox']", ".eds-react-checkbox__input", ".eds-checkbox__input"]:
                                        chk = first_row.locator(sub_sel).first
                                        if await chk.count() > 0 and await chk.is_checked() is False:
                                            await chk.dispatch_event('click')
                                            log(f"Đã chọn sản phẩm đầu tiên bằng click dòng trong bảng (selector: {sub_sel})")
                                            selected = True
                                            break
                            except Exception as e:
                                logger.warning(f"Lỗi khi thử chọn checkbox dòng đầu tiên: {e}")
 
                            # Nếu chưa chọn được, thử fall back các selector checkbox trực tiếp khác
                            if not selected:
                                for check_sel in [
                                    ".eds-react-dialog tbody input[type='checkbox']",
                                    ".eds-react-dialog input[type='checkbox']",
                                    ".eds-react-checkbox__input",
                                    "input[type='checkbox']"
                                ]:
                                    try:
                                        chk_locator = self.page.locator(check_sel).first
                                        if await chk_locator.count() > 0 and await chk_locator.is_checked() is False:
                                            await chk_locator.dispatch_event('click')
                                            log(f"Đã chọn sản phẩm bằng fallback selector: {check_sel}")
                                            selected = True
                                            break
                                    except Exception:
                                        continue
                            
                            if selected:
                                log(f"Đã gắn thành công sản phẩm: {keyword}")
                            else:
                                log(f"Không tìm thấy nút Chọn cho sản phẩm: {keyword}")
                        else:
                            log(f"Không tìm thấy ô tìm kiếm sản phẩm cho: {keyword}")
                            
                        await asyncio.sleep(1) # Delay nhỏ giữa các sản phẩm
                else:
                    log("Video này không cấu hình sản phẩm để gắn giỏ trong Chế độ Tự động (auto). Tự động chọn sản phẩm đầu tiên hiển thị...")
                    
                    # Chờ danh sách tải ra
                    try:
                        await self.page.locator(".eds-react-dialog tbody tr").first.wait_for(state="visible", timeout=5000)
                    except Exception:
                        await asyncio.sleep(2)
                        
                    selected = False
                    # Đầu tiên thử tìm checkbox của dòng sản phẩm đầu tiên trong bảng tbody
                    try:
                        first_row = self.page.locator(".eds-react-dialog tbody tr").first
                        if await first_row.count() > 0:
                            for sub_sel in ["input[type='checkbox']", ".eds-react-checkbox__input", ".eds-checkbox__input"]:
                                chk = first_row.locator(sub_sel).first
                                if await chk.count() > 0 and await chk.is_checked() is False:
                                    await chk.dispatch_event('click')
                                    log(f"Đã tự động chọn sản phẩm đầu tiên (selector: {sub_sel})")
                                    selected = True
                                    break
                    except Exception as e:
                        logger.warning(f"Lỗi khi thử tự động chọn checkbox dòng đầu tiên: {e}")
 
                    # Nếu chưa chọn được, thử fall back các selector checkbox trực tiếp khác
                    if not selected:
                        for check_sel in [
                            ".eds-react-dialog tbody input[type='checkbox']",
                            ".eds-react-dialog input[type='checkbox']",
                            ".eds-react-checkbox__input",
                            "input[type='checkbox']"
                        ]:
                            try:
                                chk_locator = self.page.locator(check_sel).first
                                if await chk_locator.count() > 0 and await chk_locator.is_checked() is False:
                                    await chk_locator.dispatch_event('click')
                                    log(f"Đã tự động chọn sản phẩm bằng fallback selector: {check_sel}")
                                    selected = True
                                    break
                            except Exception:
                                continue
                    if not selected:
                        log("CẢNH BÁO: Không tự động chọn được sản phẩm mặc định nào trong danh sách.")
                
                # Bấm nút Xác nhận trong modal để lưu sản phẩm đã chọn (hoặc đóng modal)
                confirm_selectors = [
                    ".eds-react-dialog button.eds-btn--primary",
                    ".eds-react-dialog button:has-text('Xác nhận')",
                    ".eds-react-dialog button:has-text('Confirm')",
                    "button:has-text('Xác nhận')",
                    "button:has-text('Xong')",
                    "button:has-text('Confirm')",
                    "button:has-text('OK')",
                    ".product-modal-confirm-btn"
                ]
                
                confirmed = False
                for c_sel in confirm_selectors:
                    try:
                        btn = self.page.locator(c_sel).first
                        if await btn.is_visible():
                            confirmed = await self.click_element(btn)
                            if confirmed:
                                log("Đã đóng modal sản phẩm.")
                                break
                    except Exception:
                        continue
                
                if not confirmed:
                    log("CẢNH BÁO: Không tìm thấy nút Xác nhận để đóng modal. Thử nhấn Escape...")
                    await self.page.keyboard.press("Escape")
                
                await asyncio.sleep(2)
            else:
                log("Không hiển thị hoặc không mở modal sản phẩm. Tiến hành đăng video luôn.")
            
            # 5. Click Đăng bài
            log("Đang chuẩn bị đăng video...")
            await asyncio.sleep(5) # Đợi video hoàn tất xử lý
            
            # Tự động tick chấp nhận Điều khoản dịch vụ nếu có
            try:
                terms_checkbox_text = self.page.locator(
                    "span:has-text('Khi đăng bài'), label:has-text('Khi đăng bài'), p:has-text('Khi đăng bài'), "
                    "span:has-text('By publishing'), label:has-text('By publishing'), p:has-text('By publishing')"
                ).first
                if await terms_checkbox_text.count() > 0 and await terms_checkbox_text.is_visible():
                    log("Phát hiện checkbox chấp nhận Điều khoản dịch vụ Shopee Video. Đang kiểm tra và tick chọn...")
                    
                    # Tìm checkbox nằm gần hoặc bên trong khối text điều khoản
                    checkbox = terms_checkbox_text.locator("xpath=../..//input[@type='checkbox']").first
                    if await checkbox.count() == 0:
                        checkbox = terms_checkbox_text.locator("xpath=..//input[@type='checkbox']").first
                    if await checkbox.count() == 0:
                        checkbox = self.page.locator("input[type='checkbox']").first
                        
                    if await checkbox.count() > 0:
                        if not await checkbox.is_checked():
                            try:
                                await checkbox.click(force=True)
                                log("Đã tick chọn chấp nhận điều khoản dịch vụ (bằng input[type='checkbox']).")
                            except Exception:
                                await terms_checkbox_text.click()
                                log("Đã click vào văn bản điều khoản để chấp nhận.")
                    else:
                        await terms_checkbox_text.click()
                        log("Đã click vào văn bản điều khoản để chấp nhận.")
                    await asyncio.sleep(1)
            except Exception as ex:
                logger.warning(f"Lỗi khi xử lý tick chọn điều khoản dịch vụ: {ex}")
            
            post_selectors = [
                "button.eds-btn--primary:text-is('Đăng')",
                "button.eds-btn--primary:has-text('Đăng'):not(:has-text('nhập')):not(:has-text('ký'))",
                "button:has-text('Đăng'):not(:has-text('nhập')):not(:has-text('ký'))",
                "button.eds-btn--primary:text-is('Post')",
                "button.eds-btn--primary:text-is('Publish')",
                "button.eds-btn--primary"
            ]
            
            posted = False
            for p_sel in post_selectors:
                try:
                    btn = self.page.locator(p_sel).first
                    if await btn.is_visible() and not await btn.is_disabled():
                        posted = await self.click_element(btn)
                        if posted:
                            log(f"Đã bấm nút Đăng bài bằng selector: {p_sel}")
                            break
                except Exception:
                    continue
                    
            if not posted:
                log("CẢNH BÁO: Không tự động bấm Đăng bài được. Vui lòng kiểm tra và tự bấm Đăng trên màn hình duyệt.")
                log("Đang đợi bạn kiểm tra và tự bấm nút Đăng trên trình duyệt (Chờ tối đa 30s)...")
                user_clicked = False
                for _ in range(30):
                    await asyncio.sleep(1)
                    if "video-upload/upload" not in self.page.url.lower():
                        log("Phát hiện trang đã được chuyển hướng. Đăng video thành công!")
                        user_clicked = True
                        break
                if not user_clicked:
                    log("LỖI: Hết thời gian chờ. Không bấm được nút Đăng bài.")
                    await self.close_browser()
                    return False
            else:
                # Đã click nút Đăng tự động, bây giờ chờ xác nhận chuyển hướng để chắc chắn đăng thành công
                log("Đã click nút Đăng. Đang chờ chuyển hướng để xác nhận đăng thành công...")
                success_redirect = False
                for _ in range(15): # Chờ tối đa 15s
                    await asyncio.sleep(1)
                    if "video-upload/upload" not in self.page.url.lower():
                        log("Phát hiện trang đã được chuyển hướng. Đăng video thành công!")
                        success_redirect = True
                        break
                
                if not success_redirect:
                    # Chụp ảnh lỗi trước khi xử lý
                    await self.capture_screenshot("last_upload_error.png", log_callback=log)
                    
                    # Kiểm tra xem có thông báo lỗi hiển thị trên màn hình không
                    error_locators = [
                        ".eds-form-item-explain-error", 
                        ".eds-message", 
                        "[class*='error']", 
                        "[class*='toast']",
                        "text='vui lòng'",
                        "text='lỗi'"
                    ]
                    found_error = False
                    for err_sel in error_locators:
                        try:
                            err_el = self.page.locator(err_sel).first
                            if await err_el.is_visible():
                                err_text = await err_el.inner_text()
                                log(f"LỖI hiển thị trên trang Shopee: {err_text}")
                                found_error = True
                                break
                        except Exception:
                            continue
                    
                    if found_error:
                        return False
                    else:
                        log("CẢNH BÁO: Đã bấm Đăng nhưng trang chưa chuyển hướng sau 15s. Sẽ đợi thêm 10s...")
                        for _ in range(10):
                            await asyncio.sleep(1)
                            if "video-upload/upload" not in self.page.url.lower():
                                log("Phát hiện trang đã được chuyển hướng sau thời gian chờ thêm. Đăng video thành công!")
                                success_redirect = True
                                break
                        if not success_redirect:
                            log("LỖI: Không thể xác nhận đăng thành công (trang không chuyển hướng).")
                            # Chụp thêm ảnh lỗi lần 2 sau khi hết thời gian chờ
                            await self.capture_screenshot("last_upload_error_timeout.png", log_callback=log)
                            return False
                
                await asyncio.sleep(2)
                return True
            
        except Exception as e:
            log(f"LỖI trong quá trình đăng video: {e}")
            return False
        finally:
            await self.close_browser()


def get_uploader(platform: str, profile_dir: str):
    platform = platform.lower()
    if platform == "tiktok":
        return TikTokVideoUploader(profile_dir=profile_dir)
    elif platform == "youtube":
        return YouTubeShortsUploader(profile_dir=profile_dir)
    elif platform == "reels":
        return FacebookReelsUploader(profile_dir=profile_dir)
    else:
        return ShopeeVideoUploader(profile_dir=profile_dir)


class TikTokVideoUploader(ShopeeVideoUploader):
    async def check_login_status(self) -> bool:
        try:
            await self.init_browser(headless=False)
            page = await self.context.new_page()
            logger.info("Đang điều hướng tới TikTok Creator Center để kiểm tra login...")
            await page.goto("https://www.tiktok.com/creator-center/upload?from=upload", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            current_url = page.url.lower()
            logger.info(f"URL hiện tại sau khi kiểm tra login TikTok: {current_url}")
            
            if "login" in current_url or "signin" in current_url or "accounts" in current_url:
                logger.info("TikTok chưa đăng nhập.")
                await self.close_browser()
                return False
                
            # Kiểm tra xem có input file hoặc phần tử đặc trưng của trang upload không
            file_input = page.locator("input[type='file']").first
            try:
                await file_input.wait_for(state="attached", timeout=5000)
                logger.info("TikTok đã đăng nhập thành công.")
                await self.close_browser()
                return True
            except Exception:
                pass
            
            await self.close_browser()
            return False
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra login TikTok: {e}")
            await self.close_browser()
            return False

    async def open_login_session(self, log_callback=None) -> bool:
        def log(msg):
            logger.info(msg)
            if log_callback:
                asyncio.create_task(log_callback(msg))

        log("Đang mở trình duyệt để bạn đăng nhập TikTok...")
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()
        
        log("Đang tải trang TikTok Upload...")
        await self.page.goto("https://www.tiktok.com/creator-center/upload?from=upload", wait_until="domcontentloaded")
        
        log("Trình duyệt đã mở. Vui lòng thực hiện đăng nhập trên cửa sổ trình duyệt (Nhập OTP, SMS, Quét QR...).")
        log("Sau khi đăng nhập thành công, bạn hãy ĐÓNG cửa sổ trình duyệt đó đi và bấm nút 'Check' (màu xám) trên giao diện tool để xác nhận.")
        
        try:
            while True:
                if self.page.is_closed():
                    log("Cửa sổ trình duyệt đã bị đóng.")
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            log("Đã kết thúc phiên đăng nhập.")
        finally:
            await self.close_browser()
        return True

    async def upload_video(
        self, 
        video_path: str, 
        caption: str, 
        product_keywords: list = None, 
        product_tagging_mode: str = "manual",
        log_callback=None
    ) -> bool:
        def log(msg):
            logger.info(msg)
            if log_callback:
                if inspect.iscoroutinefunction(log_callback):
                    asyncio.create_task(log_callback(msg))
                else:
                    try: log_callback(msg)
                    except: pass

        if not os.path.exists(video_path):
            log(f"LỖI: Tệp video không tồn tại: {video_path}")
            return False

        log(f"Bắt đầu đăng video TikTok: {os.path.basename(video_path)}")
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()
        
        try:
            log("Đang điều hướng tới trang upload TikTok...")
            await self.safe_goto("https://www.tiktok.com/creator-center/upload?from=upload", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            # 1. Kiểm tra login
            current_url = self.page.url.lower()
            if "login" in current_url or "signin" in current_url:
                log("LỖI: TikTok chưa đăng nhập. Vui lòng đăng nhập lại.")
                return False
                
            # 2. Upload video file
            log("Đang tìm ô chọn file video TikTok...")
            file_input = self.page.locator("input[type='file']").first
            await file_input.set_input_files(video_path)
            log("Đang upload video lên TikTok, vui lòng đợi...")
            
            # Đợi upload và form điền thông tin hiển thị
            caption_selector = "[contenteditable='true'], .public-DraftStyleDefault-block, textarea"
            try:
                await self.page.wait_for_selector(caption_selector, timeout=60000)
                log("Video đã tải lên, form nhập thông tin đã sẵn sàng.")
            except Exception:
                log("LỖI: Hết thời gian chờ video tải lên TikTok.")
                return False
                
            await asyncio.sleep(5)
            
            # 3. Điền Caption
            log("Đang điền tiêu đề và caption TikTok...")
            caption_filled = False
            for sel in [".public-DraftStyleDefault-block", "[contenteditable='true']", "textarea"]:
                try:
                    el = self.page.locator(sel).first
                    if await el.is_visible():
                        await el.click()
                        await self.page.keyboard.press("Control+A")
                        await self.page.keyboard.press("Backspace")
                        await el.fill(caption)
                        log(f"Đã nhập caption: '{caption}'")
                        caption_filled = True
                        break
                except Exception:
                    continue
            if not caption_filled:
                log("CẢNH BÁO: Không tự điền caption được. Bạn có thể tự viết trên màn hình.")
                
            await asyncio.sleep(3)
            
            # 3.5. Gắn sản phẩm (Giỏ hàng) cho TikTok
            # Bật disclosure nếu cần hoặc tự động bật nếu có gắn sản phẩm
            try:
                if product_keywords and len(product_keywords) > 0:
                    log("Tự động bật khai báo nội dung thương mại khi gắn sản phẩm...")
                    # Mở rộng phần cài đặt bổ sung nếu có
                    more_options_selectors = [
                        "text='Cài đặt khác'", "text='More options'", 
                        "text='Khai báo nội dung và quảng cáo'", "text='Content disclosure and ads'"
                    ]
                    for mo_sel in more_options_selectors:
                        try:
                            mo_btn = self.page.locator(mo_sel).first
                            if await mo_btn.is_visible():
                                await self.click_element(mo_btn)
                                await asyncio.sleep(1)
                                break
                        except:
                            continue

                    # Bật nút disclosure switch/checkbox
                    disclosure_checkbox = self.page.locator(
                        "input[type='checkbox'][class*='disclosure'], input[type='checkbox'][class*='switch'], "
                        "label:has-text('Khai báo nội dung'), label:has-text('Content disclosure')"
                    ).first
                    if await disclosure_checkbox.is_visible():
                        if not await disclosure_checkbox.is_checked():
                            await disclosure_checkbox.click(force=True)
                            await asyncio.sleep(1)
            except Exception as ex:
                log(f"Cảnh báo khi xử lý Disclosure: {ex}")

            # Thao tác gắn giỏ hàng sản phẩm trên TikTok
            add_product_clicked = False
            if product_keywords and len(product_keywords) > 0:
                log(f"Đang tiến hành gắn {len(product_keywords)} sản phẩm vào video TikTok...")
                
                # Tìm và click nút Thêm liên kết / Sản phẩm
                add_link_selectors = [
                    "text='Thêm liên kết'", "text='Add link'",
                    "text='Sản phẩm'", "text='Product'",
                    "[class*='add-link']", "[class*='product-link']",
                    "div:has-text('Thêm liên kết')", "div:has-text('Add link')"
                ]
                
                for sel in add_link_selectors:
                    try:
                        btn = self.page.locator(sel).first
                        if await btn.is_visible():
                            clicked = await self.click_element(btn)
                            if clicked:
                                log("Đã click nút 'Thêm liên kết/Sản phẩm'")
                                add_product_clicked = True
                                break
                    except Exception:
                        continue

            if add_product_clicked:
                await asyncio.sleep(3) # Chờ modal hiển thị
                
                # Nếu click 'Thêm liên kết' chung, chọn tiếp loại 'Sản phẩm/Product'
                try:
                    product_option = self.page.locator("text='Sản phẩm', text='Product'").first
                    if await product_option.is_visible():
                        await self.click_element(product_option)
                        await asyncio.sleep(2)
                except:
                    pass

                # Duyệt qua tối đa 6 sản phẩm
                for idx, keyword in enumerate(product_keywords[:6]):
                    log(f"Đang tìm sản phẩm thứ {idx+1}: {keyword}")
                    
                    search_selectors = [
                        "input[placeholder*='Tìm kiếm']",
                        "input[placeholder*='Search']",
                        "input[placeholder*='sản phẩm']",
                        "input[type='text']",
                        "[role='dialog'] input"
                    ]
                    
                    search_input_found = False
                    for s_sel in search_selectors:
                        try:
                            s_input = self.page.locator(s_sel).first
                            if await s_input.is_visible():
                                await s_input.click()
                                await self.page.keyboard.press("Control+A")
                                await self.page.keyboard.press("Backspace")
                                await s_input.fill(keyword)
                                search_input_found = True
                                break
                        except Exception:
                            continue
                    
                    if search_input_found:
                        await self.page.keyboard.press("Enter")
                        await asyncio.sleep(3) # Đợi tìm kiếm
                        
                        # Click nút "Thêm" hoặc checkbox cho dòng sản phẩm đầu tiên
                        add_btn_selectors = [
                            "button:has-text('Thêm')", "button:has-text('Add')",
                            "button:has-text('Chọn')", "button:has-text('Select')",
                            ".btn-add", "[class*='addButton']",
                            "tr input[type='checkbox']", "input[type='checkbox']"
                        ]
                        
                        added = False
                        for a_sel in add_btn_selectors:
                            try:
                                add_btn = self.page.locator(a_sel).first
                                if await add_btn.is_visible():
                                    added = await self.click_element(add_btn)
                                    if added:
                                        log(f"Đã gắn thành công sản phẩm: {keyword}")
                                        break
                            except Exception:
                                continue
                                
                        if not added:
                            log(f"Không thể click gắn sản phẩm: {keyword}")
                    else:
                        log(f"Không tìm thấy ô tìm kiếm trong modal sản phẩm.")
                    await asyncio.sleep(1)

                # Xác nhận lưu hoặc đóng modal sản phẩm
                confirm_selectors = [
                    "button:has-text('Xác nhận')", "button:has-text('Confirm')",
                    "button:has-text('Xong')", "button:has-text('Done')",
                    "button:has-text('OK')"
                ]
                for c_sel in confirm_selectors:
                    try:
                        btn = self.page.locator(c_sel).first
                        if await btn.is_visible():
                            await self.click_element(btn)
                            log("Đã xác nhận danh sách sản phẩm.")
                            break
                        else:
                            await self.page.keyboard.press("Escape")
                    except:
                        continue
                await asyncio.sleep(2)

            await asyncio.sleep(3)
            
            # 4. Click Đăng bài
            log("Đang bấm nút Đăng video lên TikTok...")
            posted = False
            post_selectors = [
                "button:has-text('Đăng')", 
                "button:has-text('Post')", 
                ".btn-post",
                "button[type='submit']"
            ]
            for p_sel in post_selectors:
                try:
                    btn = self.page.locator(p_sel).first
                    if await btn.is_visible() and not await btn.is_disabled():
                        posted = await self.click_element(btn)
                        if posted:
                            log("Đã click nút Đăng TikTok.")
                            break
                except Exception:
                    continue
            
            if not posted:
                log("CẢNH BÁO: Không tự động đăng được. Vui lòng bấm Đăng thủ công trên trình duyệt (chờ tối đa 30 giây)...")
                for _ in range(30):
                    await asyncio.sleep(1)
                    if "upload" not in self.page.url.lower():
                        log("Phát hiện đã chuyển hướng. TikTok đăng video thành công!")
                        return True
                log("LỖI: Hết thời gian chờ tự đăng bài.")
                return False
                
            log("Chờ 10 giây để xác nhận đăng tải hoàn tất...")
            await asyncio.sleep(10)
            return True
        except Exception as e:
            log(f"LỖI trong quá trình đăng video TikTok: {e}")
            return False
        finally:
            await self.close_browser()


class YouTubeShortsUploader(ShopeeVideoUploader):
    async def check_login_status(self) -> bool:
        try:
            await self.init_browser(headless=False)
            page = await self.context.new_page()
            logger.info("Đang điều hướng tới YouTube Studio để kiểm tra login...")
            await page.goto("https://studio.youtube.com/", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            current_url = page.url.lower()
            logger.info(f"URL hiện tại sau khi kiểm tra login YouTube: {current_url}")
            
            if "accounts.google.com" in current_url or "signin" in current_url:
                logger.info("YouTube chưa đăng nhập.")
                await self.close_browser()
                return False
                
            try:
                btn = page.locator("#create-icon, #upload-icon, [id='upload-button']").first
                await btn.wait_for(state="attached", timeout=5000)
                logger.info("YouTube đã đăng nhập thành công.")
                await self.close_browser()
                return True
            except Exception:
                pass
            
            await self.close_browser()
            return False
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra login YouTube: {e}")
            await self.close_browser()
            return False

    async def open_login_session(self, log_callback=None) -> bool:
        def log(msg):
            logger.info(msg)
            if log_callback:
                asyncio.create_task(log_callback(msg))

        log("Đang mở trình duyệt để bạn đăng nhập YouTube...")
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()
        
        log("Đang tải trang YouTube Studio...")
        await self.page.goto("https://studio.youtube.com/", wait_until="domcontentloaded")
        
        log("Trình duyệt đã mở. Vui lòng thực hiện đăng nhập tài khoản Google của bạn.")
        log("Sau khi vào tới màn hình YouTube Studio, bạn hãy ĐÓNG cửa sổ trình duyệt đó đi và bấm nút 'Check' (màu xám) trên giao diện tool để xác nhận.")
        
        try:
            while True:
                if self.page.is_closed():
                    log("Cửa sổ trình duyệt đã bị đóng.")
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            log("Đã kết thúc phiên đăng nhập.")
        finally:
            await self.close_browser()
        return True

    async def upload_video(self, video_path: str, caption: str, log_callback=None) -> bool:
        def log(msg):
            logger.info(msg)
            if log_callback:
                if inspect.iscoroutinefunction(log_callback):
                    asyncio.create_task(log_callback(msg))
                else:
                    try: log_callback(msg)
                    except: pass

        if not os.path.exists(video_path):
            log(f"LỖI: Tệp video không tồn tại: {video_path}")
            return False

        log(f"Bắt đầu đăng video YouTube Shorts: {os.path.basename(video_path)}")
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()
        
        try:
            log("Đang điều hướng tới YouTube Studio...")
            await self.safe_goto("https://studio.youtube.com/", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            if "accounts.google.com" in self.page.url or "signin" in self.page.url:
                log("LỖI: Chưa đăng nhập tài khoản Google. Vui lòng đăng nhập trước.")
                return False
                
            log("Đang bấm nút Tải video lên...")
            upload_btn_selectors = ["[id='upload-button']", "[id='upload-icon']", "ytcp-icon-button[id='upload-icon']", "#create-icon"]
            clicked_upload = False
            for sel in upload_btn_selectors:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.is_visible():
                        clicked_upload = await self.click_element(btn)
                        if clicked_upload:
                            break
                except Exception:
                    continue
            if not clicked_upload:
                log("Thử bấm nút Tạo ở góc phải...")
                await self.page.locator("#create-icon").first.click()
                await asyncio.sleep(1)
                await self.page.locator("paper-item:has-text('Tải video lên'), paper-item:has-text('Upload videos')").first.click()
                
            await asyncio.sleep(2)
            
            log("Đang chọn file video...")
            file_input = self.page.locator("input[type='file']").first
            await file_input.set_input_files(video_path)
            log("Đã chọn file. Chờ hộp thoại chỉnh sửa tải ra...")
            
            title_input_selector = "ytcp-social-suggestions-textbox[id='title-textarea'] [contenteditable='true'], [id='textbox'], [contenteditable='true']"
            await self.page.wait_for_selector(title_input_selector, timeout=45000)
            await asyncio.sleep(2)
            
            log("Đang điền tiêu đề Shorts...")
            title_el = self.page.locator(title_input_selector).first
            await title_el.click()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await title_el.fill(caption[:100])
            
            log("Tích chọn 'Không dành cho trẻ em'...")
            not_for_kids_selectors = [
                "paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MADE_FOR_KIDS']",
                "paper-radio-button:has-text('Không, đây không phải nội dung dành cho trẻ em')",
                "paper-radio-button:has-text('No, it\'s not made for kids')"
            ]
            for r_sel in not_for_kids_selectors:
                try:
                    radio = self.page.locator(r_sel).first
                    if await radio.is_visible():
                        await radio.click()
                        break
                except Exception:
                    continue
            
            await asyncio.sleep(2)
            
            for step in range(3):
                log(f"Bấm Tiếp theo (Bước {step+1}/3)...")
                next_btn = self.page.locator("[id='next-button']").first
                await self.click_element(next_btn)
                await asyncio.sleep(2)
                
            log("Chọn chế độ hiển thị 'Công khai'...")
            public_selectors = [
                "paper-radio-button[name='PUBLIC']",
                "paper-radio-button:has-text('Công khai')",
                "paper-radio-button:has-text('Public')"
            ]
            for p_sel in public_selectors:
                try:
                    radio = self.page.locator(p_sel).first
                    if await radio.is_visible():
                        await radio.click()
                        break
                except Exception:
                    continue
            
            await asyncio.sleep(2)
            
            log("Bấm nút Xuất bản (Publish)...")
            done_btn = self.page.locator("[id='done-button']").first
            await self.click_element(done_btn)
            
            log("Chờ 10 giây để video tải lên và xuất bản...")
            await asyncio.sleep(10)
            return True
        except Exception as e:
            log(f"LỖI khi đăng YouTube Shorts: {e}")
            return False
        finally:
            await self.close_browser()


class FacebookReelsUploader(ShopeeVideoUploader):
    async def check_login_status(self) -> bool:
        try:
            await self.init_browser(headless=False)
            page = await self.context.new_page()
            logger.info("Đang điều hướng tới Meta Business Suite Reels Composer để kiểm tra login...")
            await page.goto("https://business.facebook.com/latest/reels_composer", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            current_url = page.url.lower()
            logger.info(f"URL hiện tại sau khi kiểm tra login Facebook: {current_url}")
            
            if "login" in current_url or "signin" in current_url or "facebook.com/login" in current_url:
                logger.info("Facebook chưa đăng nhập.")
                await self.close_browser()
                return False
                
            try:
                file_input = page.locator("input[type='file']").first
                await file_input.wait_for(state="attached", timeout=5000)
                logger.info("Facebook đã đăng nhập thành công.")
                await self.close_browser()
                return True
            except Exception:
                pass
            
            await self.close_browser()
            return False
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra login Facebook: {e}")
            await self.close_browser()
            return False

    async def open_login_session(self, log_callback=None) -> bool:
        def log(msg):
            logger.info(msg)
            if log_callback:
                asyncio.create_task(log_callback(msg))

        log("Đang mở trình duyệt để bạn đăng nhập Facebook...")
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()
        
        log("Đang tải trang Meta Business Suite Reels Composer...")
        await self.page.goto("https://business.facebook.com/latest/reels_composer", wait_until="domcontentloaded")
        
        log("Trình duyệt đã mở. Vui lòng thực hiện đăng nhập tài khoản Facebook chứa Fanpage của bạn.")
        log("Sau khi vào tới trang Reels Composer chính thức, bạn hãy ĐÓNG cửa sổ trình duyệt đó đi và bấm nút 'Check' (màu xám) trên giao diện tool để xác nhận.")
        
        try:
            while True:
                if self.page.is_closed():
                    log("Cửa sổ trình duyệt đã bị đóng.")
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            log("Đã kết thúc phiên đăng nhập.")
        finally:
            await self.close_browser()
        return True

    async def upload_video(self, video_path: str, caption: str, log_callback=None) -> bool:
        def log(msg):
            logger.info(msg)
            if log_callback:
                if inspect.iscoroutinefunction(log_callback):
                    asyncio.create_task(log_callback(msg))
                else:
                    try: log_callback(msg)
                    except: pass

        if not os.path.exists(video_path):
            log(f"LỖI: Tệp video không tồn tại: {video_path}")
            return False

        log(f"Bắt đầu đăng Facebook Reels: {os.path.basename(video_path)}")
        await self.init_browser(headless=False)
        self.page = await self.context.new_page()
        
        try:
            log("Đang điều hướng tới Reels Composer...")
            await self.safe_goto("https://business.facebook.com/latest/reels_composer", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            if "login" in self.page.url or "facebook.com/login" in self.page.url:
                log("LỖI: Chưa đăng nhập Facebook. Vui lòng đăng nhập lại.")
                return False
                
            log("Đang tìm ô chọn file video Reels...")
            file_input = self.page.locator("input[type='file']").first
            await file_input.set_input_files(video_path)
            log("Đang tải video lên Meta Business Suite, vui lòng chờ...")
            
            desc_selector = "[placeholder*='mô tả'], [placeholder*='description'], textarea, div[contenteditable='true']"
            try:
                await self.page.wait_for_selector(desc_selector, timeout=60000)
                log("Đã sẵn sàng ô điền thông tin Reels.")
            except Exception:
                log("LỖI: Hết thời gian chờ video tải lên Facebook.")
                return False
                
            await asyncio.sleep(5)
            
            log("Đang điền mô tả Reels...")
            desc_filled = False
            for sel in [desc_selector, "textarea", "div[contenteditable='true']"]:
                try:
                    el = self.page.locator(sel).first
                    if await el.is_visible():
                        await el.click()
                        await self.page.keyboard.press("Control+A")
                        await self.page.keyboard.press("Backspace")
                        await el.fill(caption)
                        log(f"Đã điền mô tả: '{caption}'")
                        desc_filled = True
                        break
                except Exception:
                    continue
            if not desc_filled:
                log("CẢNH BÁO: Không tự động điền được mô tả. Bạn có thể tự viết trên trình duyệt.")
                
            await asyncio.sleep(3)
            
            for step in range(2):
                log(f"Bấm Tiếp (Bước {step+1}/2)...")
                next_btn_selectors = [
                    "div[role='button']:has-text('Tiếp')",
                    "div[role='button']:has-text('Next')",
                    "button:has-text('Tiếp')",
                    "button:has-text('Next')",
                ]
                clicked_next = False
                for n_sel in next_btn_selectors:
                    try:
                        btn = self.page.locator(n_sel).first
                        if await btn.is_visible() and not await btn.is_disabled():
                            clicked_next = await self.click_element(btn)
                            if clicked_next:
                                break
                    except Exception:
                        continue
                if not clicked_next:
                    log("Không tự động bấm Tiếp được, thử nhấn Enter...")
                    await self.page.keyboard.press("Enter")
                await asyncio.sleep(3)
                
            log("Bấm nút Chia sẻ Reels...")
            share_btn_selectors = [
                "div[role='button']:has-text('Chia sẻ')",
                "div[role='button']:has-text('Share')",
                "div[role='button']:has-text('Đăng')",
                "div[role='button']:has-text('Publish')",
                "button:has-text('Chia sẻ')",
                "button:has-text('Share')"
            ]
            shared = False
            for s_sel in share_btn_selectors:
                try:
                    btn = self.page.locator(s_sel).first
                    if await btn.is_visible() and not await btn.is_disabled():
                        shared = await self.click_element(btn)
                        if shared:
                            log("Đã click nút Chia sẻ Reels.")
                            break
                except Exception:
                    continue
                    
            if not shared:
                log("CẢNH BÁO: Không tự động Chia sẻ được. Vui lòng bấm thủ công trên trình duyệt (chờ tối đa 30 giây)...")
                for _ in range(30):
                    await asyncio.sleep(1)
                    if "reels_composer" not in self.page.url.lower():
                        log("Phát hiện đã chuyển hướng. Facebook Reels đăng thành công!")
                        return True
                log("LỖI: Hết thời gian chờ tự chia sẻ Reels.")
                return False
                
            log("Chờ 10 giây để Reels được xuất bản hoàn chỉnh...")
            await asyncio.sleep(10)
            return True
        except Exception as e:
            log(f"LỖI trong quá trình đăng Facebook Reels: {e}")
            return False
        finally:
            await self.close_browser()
