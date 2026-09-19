import os
import re
import json
import time
import asyncio
import requests
import uuid
import inspect
from urllib.parse import urlparse
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

def safe_print(*args, **kwargs):
    try:
        msg = " ".join(str(a) for a in args)
        logger.info(msg)
    except:
        pass

# Thư mục lưu ảnh tải về
DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class ProductScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    async def init_browser(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        if not self.browser:
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            await self.context.add_init_script("delete navigator.__proto__.webdriver;")

    async def close(self):
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    def download_image(self, url, folder_path):
        """Tải một hình ảnh về thư mục chỉ định và trả về đường dẫn tương đối."""
        try:
            if not url:
                return None
            
            # Xử lý các link tương đối hoặc thiếu schema
            if url.startswith("//"):
                url = "https:" + url
                
            response = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "").lower()
                is_webp = "image/webp" in content_type or url.lower().endswith(".webp") or ".webp" in url.lower()
                is_large = len(response.content) > 1.8 * 1024 * 1024  # > 1.8 MB
                
                # Để tránh lỗi định dạng và dung lượng của Shopee (> 2.0MB),
                # Ta sẽ chuyển đổi toàn bộ ảnh WebP hoặc ảnh quá lớn sang JPG nén chất lượng cao.
                if is_webp or is_large:
                    try:
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(response.content))
                        
                        # Chuyển đổi RGBA/LA sang RGB
                        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                            background = Image.new("RGB", img.size, (255, 255, 255))
                            background.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
                            img = background
                        else:
                            img = img.convert("RGB")
                            
                        filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
                        file_path = os.path.join(folder_path, filename)
                        img.save(file_path, "JPEG", quality=85)
                    except Exception as pe:
                        safe_print(f"Lỗi convert ảnh sang jpeg: {pe}")
                        # Fallback lưu thô
                        ext = ".webp" if is_webp else ".jpg"
                        if "image/png" in content_type:
                            ext = ".png"
                        filename = f"img_{uuid.uuid4().hex[:8]}{ext}"
                        file_path = os.path.join(folder_path, filename)
                        with open(file_path, "wb") as f:
                            f.write(response.content)
                else:
                    ext = ".jpg"
                    if "image/png" in content_type:
                        ext = ".png"
                    
                    filename = f"img_{uuid.uuid4().hex[:8]}{ext}"
                    file_path = os.path.join(folder_path, filename)
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                
                # Trả về đường dẫn tương đối từ thư mục dự án
                filename = os.path.basename(file_path)
                return f"/downloads/{os.path.basename(folder_path)}/{filename}"
        except Exception as e:
            safe_print(f"Lỗi tải ảnh {url}: {e}")
        return None

    def download_video(self, url, folder_path):
        """Tải một video về thư mục chỉ định và trả về đường dẫn tương đối."""
        try:
            if not url:
                return None
            if url.startswith("//"):
                url = "https:" + url
                
            response = requests.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if response.status_code == 200:
                filename = f"vid_{uuid.uuid4().hex[:8]}.mp4"
                file_path = os.path.join(folder_path, filename)
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return f"/downloads/{os.path.basename(folder_path)}/{filename}"
        except Exception as e:
            safe_print(f"Lỗi tải video {url}: {e}")
        return None

    async def scrape(self, url: str) -> dict:
        await self.init_browser()
        
        # Nhận diện sàn
        domain = urlparse(url).netloc.lower()
        if "shopee" in domain:
            return await self.scrape_shopee(url)
        elif "tiktok" in domain:
            return await self.scrape_tiktok(url)
        else:
            raise ValueError("Đường link không thuộc sàn Shopee hoặc TikTok Shop được hỗ trợ.")

    async def scrape_shopee(self, url: str) -> dict:
        page = await self.context.new_page()
        shopee_data = {"raw_json": None}

        # Lắng nghe các request/response để bắt gói tin JSON của sản phẩm
        async def handle_response(response):
            # API Shopee v4 lấy chi tiết sản phẩm
            if "api/v4/item/get" in response.url:
                try:
                    shopee_data["raw_json"] = await response.json()
                except Exception as e:
                    safe_print(f"Lỗi đọc json Shopee API: {e}")

        page.on("response", handle_response)
        
        # Mở trang sản phẩm
        safe_print(f"Đang truy cập link Shopee: {url}...")
        try:
            # Chỉ cần truy cập và đợi một chút để API được gọi
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            # Chờ đến khi bắt được JSON hoặc hết 120 giây
            for i in range(120):
                if shopee_data["raw_json"]:
                    break
                try:
                    title_text = await page.title()
                    if "captcha" in title_text.lower() or "xác minh" in title_text.lower() or "robot" in title_text.lower() or "security" in title_text.lower():
                        if i % 10 == 0:
                            safe_print(f"[{i}s] ⚠️ Phát hiện trang xác minh Shopee (Captcha). Vui lòng hoàn thành xác minh trên trình duyệt đang mở...")
                except Exception:
                    pass
                await asyncio.sleep(1)
        except Exception as e:
            safe_print(f"Lỗi khi tải trang Shopee: {e}")
        finally:
            await page.close()

        # Nếu không bắt được qua interceptor, thử dùng regex lấy ItemID/ShopID và gọi fetch trực tiếp
        if not shopee_data["raw_json"]:
            safe_print("Không bắt được API qua intercept. Thử phân tích ID từ URL...")
            match = re.search(r"i\.(\d+)\.(\d+)", url)
            if not match:
                match = re.search(r"product/(\d+)/(\d+)", url)
            
            if match:
                shop_id, item_id = match.group(1), match.group(2)
                safe_print(f"Tìm thấy ShopID: {shop_id}, ItemID: {item_id}. Tiến hành fetch trực tiếp trong trình duyệt...")
                dummy_page = await self.context.new_page()
                try:
                    await dummy_page.goto("https://shopee.vn", wait_until="domcontentloaded")
                    fetch_url = f"https://shopee.vn/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
                    res_text = await dummy_page.evaluate(f"async () => {{ const res = await fetch('{fetch_url}'); return await res.json(); }}")
                    shopee_data["raw_json"] = res_text
                except Exception as e:
                    safe_print(f"Fetch trực tiếp thất bại: {e}")
                finally:
                    await dummy_page.close()

        if not shopee_data["raw_json"] or "data" not in shopee_data["raw_json"]:
            # Fallback sang quét DOM cơ bản nếu hoàn toàn thất bại
            raise RuntimeError("Không thể lấy dữ liệu sản phẩm Shopee. Có thể do chặn bot hoặc link không chính xác.")

        # Phân tích dữ liệu từ JSON Shopee
        item = shopee_data["raw_json"]["data"]
        product_id = str(item.get("itemid", uuid.uuid4().hex[:10]))
        title = item.get("name", "")
        description = item.get("description", "")
        
        # Tạo thư mục tải ảnh riêng cho sản phẩm này
        folder_name = f"shopee_{product_id}_{int(time.time())}"
        product_folder = os.path.join(DOWNLOAD_DIR, folder_name)
        os.makedirs(product_folder, exist_ok=True)
        
        # Danh sách ảnh chính
        shopee_images = item.get("images", [])
        image_urls = [f"https://down-tx-vn.img.susercontent.com/file/{img_id}" for img_id in shopee_images]
        downloaded_images = []
        for img_url in image_urls:
            local_path = self.download_image(img_url, product_folder)
            if local_path:
                downloaded_images.append(local_path)
                
        # Tải video sản phẩm Shopee (nếu có)
        downloaded_videos = []
        video_info_list = item.get("video_info_list", [])
        if video_info_list and isinstance(video_info_list, list):
            for vid in video_info_list:
                video_url = vid.get("video_url") or vid.get("url")
                if not video_url and vid.get("defn_list"):
                    for defn in vid.get("defn_list", []):
                        if defn.get("url"):
                            video_url = defn.get("url")
                            break
                if video_url:
                    local_vid = self.download_video(video_url, product_folder)
                    if local_vid:
                        downloaded_videos.append(local_vid)
                
        # Phân loại và SKU
        variations = []
        skus = []
        
        # Trích xuất Variations từ tier_variations
        tier_variations = item.get("tier_variations", [])
        for tier in tier_variations:
            name = tier.get("name", "")
            options = tier.get("options", [])
            # Tải ảnh phân loại nếu có
            tier_images = []
            if tier.get("images"):
                for t_img in tier.get("images", []):
                    t_url = f"https://down-tx-vn.img.susercontent.com/file/{t_img}"
                    local_img = self.download_image(t_url, product_folder)
                    tier_images.append(local_img)
            
            variations.append({
                "name": name,
                "options": options,
                "images": tier_images
            })
            
        # Trích xuất SKU từ models
        models = item.get("models", [])
        for model in models:
            price = model.get("price", 0) / 100000  # Đơn vị Shopee lưu nhân thêm 100k
            stock = model.get("normal_stock", model.get("stock", 0))
            sku_code = model.get("sku", "")
            
            # Map index phân loại
            extinfo = model.get("extinfo", {})
            tier_index = model.get("extinfo", {}).get("tier_index", [])
            if not tier_index and "tier_index" in model:
                tier_index = model["tier_index"]
                
            skus.append({
                "variation_indexes": tier_index,
                "price": int(price),
                "stock": int(stock),
                "sku_code": sku_code
            })

        # Nếu sản phẩm không có phân loại
        if not variations or len(models) <= 1:
            base_price = int(item.get("price", 0) / 100000)
            stock = int(item.get("stock", 0))
            skus = [{
                "variation_indexes": [],
                "price": base_price,
                "stock": stock,
                "sku_code": item.get("item_sku", "")
            }]
            variations = []

        # Trích xuất cân nặng và kích thước đóng gói của Shopee
        source_weight = None
        if "weight" in item and item["weight"] is not None:
            try:
                source_weight = float(item["weight"])
                if source_weight > 100:
                    source_weight = source_weight / 1000.0
            except Exception:
                pass

        source_dimensions = None
        ext_dimension = item.get("dimension") or item.get("extinfo", {}).get("dimension")
        if ext_dimension and isinstance(ext_dimension, dict):
            try:
                source_dimensions = {
                    "length": float(ext_dimension.get("length") or 10),
                    "width": float(ext_dimension.get("width") or 10),
                    "height": float(ext_dimension.get("height") or 10)
                }
            except Exception:
                pass

        result = {
            "source": "shopee",
            "product_id": product_id,
            "title": title,
            "description": description,
            "images": downloaded_images,
            "videos": downloaded_videos,
            "variations": variations,
            "skus": skus,
            "original_url": url
        }
        if source_weight is not None:
            result["source_weight"] = source_weight
        if source_dimensions is not None:
            result["source_dimensions"] = source_dimensions
            
        return result

    async def scrape_tiktok(self, url: str) -> dict:
        page = await self.context.new_page()
        tiktok_data = {"raw_json": None}

        # Lắng nghe response chứa dữ liệu sản phẩm
        async def handle_response(response):
            url_lower = response.url.lower()
            # Intercept API chứa dữ liệu chi tiết sản phẩm TikTok Shop
            if "api/v1/web/product/detail" in url_lower or "api/v1/shop/product/detail" in url_lower or "product/detail" in url_lower:
                try:
                    tiktok_data["raw_json"] = await response.json()
                    safe_print(f"Đã bắt được API TikTok Shop: {response.url}")
                except Exception:
                    pass
            elif response.request.resource_type == "fetch":
                # Thử quét nội dung response xem có chứa thông tin sản phẩm không
                try:
                    text = await response.text()
                    if "product_info" in text and "skus" in text and "title" in text:
                        data = json.loads(text)
                        tiktok_data["raw_json"] = data
                        safe_print("Đã bắt được API TikTok Shop thông qua quét text nội dung")
                except Exception:
                    pass

        page.on("response", handle_response)

        safe_print(f"Đang truy cập link TikTok: {url}...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Chờ đến khi bắt được JSON hoặc hết 120 giây
            for i in range(120):
                if tiktok_data["raw_json"]:
                    break
                try:
                    title_text = await page.title()
                    if "verify" in title_text.lower() or "xác minh" in title_text.lower() or "security" in title_text.lower() or "robot" in title_text.lower():
                        if i % 10 == 0:
                            safe_print(f"[{i}s] ⚠️ Phát hiện trang xác minh TikTok (Captcha). Vui lòng kéo thanh trượt (slider) trên trình duyệt đang mở để tiếp tục...")
                except Exception:
                    pass
                await asyncio.sleep(1)
        except Exception as e:
            safe_print(f"Lỗi khi tải trang TikTok: {e}")
        
        # Nếu không bắt được qua API, cào bằng DOM (Fallback)
        if not tiktok_data["raw_json"]:
            safe_print("Không bắt được API TikTok Shop. Thử lấy từ script tag __INIT_DATA__ hoặc tương tự...")
            try:
                scripts = await page.locator("script").all()
                for script in scripts:
                    content = await script.inner_html()
                    if "__INIT_DATA__" in content or "window.__M_INITIAL_PROPS__" in content or "SIGI_STATE" in content:
                        # Thử lấy dữ liệu thô dạng chuỗi
                        match = re.search(r"({.*})", content)
                        if match:
                            try:
                                data = json.loads(match.group(1))
                                tiktok_data["raw_json"] = data
                                safe_print("Đã lấy được dữ liệu từ Script Tag!")
                                break
                            except:
                                pass
            except Exception as e:
                safe_print(f"Lỗi lấy script tag: {e}")

        # Thử lấy từ DOM
        dom_fallback = False
        if not tiktok_data["raw_json"]:
            dom_fallback = True
            safe_print("Cảnh báo: Không bắt được API/Script JSON. Tiến hành cào thông tin cơ bản từ DOM...")
            try:
                title = await page.locator("h1, [class*='title'], [class*='Title']").first.inner_text()
                if "verify" in title.lower() or "xác minh" in title.lower() or "robot" in title.lower():
                    raise RuntimeError("TikTok yêu cầu xác minh Captcha. Bạn đã không giải Captcha trong thời gian cho phép, vui lòng thử lại!")
                    
                # Thử tìm mô tả sản phẩm
                desc_el = page.locator("[class*='desc'], [class*='Desc'], [class*='description'], [class*='Description']").first
                description = await desc_el.inner_text() if await desc_el.count() > 0 else ""
                
                # Tìm ảnh
                img_elements = await page.locator("img[src*='tos-alistore'] , img[src*='tiktokcdn']").all()
                image_urls = []
                for el in img_elements:
                    src = await el.get_attribute("src")
                    if src and src not in image_urls:
                        image_urls.append(src)
                
                # Cắt bớt nếu lấy quá nhiều ảnh rác
                image_urls = image_urls[:8]
            except Exception as e:
                safe_print(f"Lỗi cào DOM: {e}")
                raise RuntimeError("Không thể lấy dữ liệu sản phẩm TikTok. Vui lòng kiểm tra lại link.")
        
        await page.close()

        if dom_fallback:
            # Xử lý kết quả từ DOM
            product_id = uuid.uuid4().hex[:10]
            folder_name = f"tiktok_{product_id}_{int(time.time())}"
            product_folder = os.path.join(DOWNLOAD_DIR, folder_name)
            os.makedirs(product_folder, exist_ok=True)
            
            downloaded_images = []
            for img_url in image_urls:
                local_path = self.download_image(img_url, product_folder)
                if local_path:
                    downloaded_images.append(local_path)
            
            return {
                "source": "tiktok",
                "product_id": product_id,
                "title": title,
                "description": description,
                "images": downloaded_images,
                "variations": [],
                "skus": [{
                    "variation_indexes": [],
                    "price": 100000, # Giá tạm thời
                    "stock": 99,
                    "sku_code": ""
                }],
                "original_url": url
            }

        # Nếu bắt được JSON, phân tích cấu trúc JSON của TikTok
        raw = tiktok_data["raw_json"]
        
        # Tìm phần chứa thông tin sản phẩm (mới hoặc cũ)
        product_info = {}
        if "page_config" in raw and "components_map" in raw["page_config"]:
            for comp in raw["page_config"]["components_map"]:
                if "component_data" in comp and "product_info" in comp["component_data"]:
                    product_info = comp["component_data"]["product_info"]
                    break

        if not product_info:
            if "data" in raw and isinstance(raw["data"], dict):
                product_info = raw["data"].get("product_info", raw["data"].get("product", raw["data"]))
            else:
                product_info = raw.get("product_info", raw.get("product", raw))

        product_model = product_info.get("product_model", product_info.get("product", product_info))
        promotion_model = product_info.get("promotion_model", {})

        product_id = str(product_model.get("product_id", product_info.get("product_id", uuid.uuid4().hex[:10])))
        title = product_model.get("name", product_info.get("title", product_info.get("name", "")))
        
        # Xử lý mô tả (Mô tả trên TikTok mới là chuỗi JSON chứa rich text)
        desc_raw = product_model.get("description", product_info.get("description", product_info.get("desc", "")))
        description = ""
        if desc_raw:
            if isinstance(desc_raw, str) and (desc_raw.strip().startswith("[") or desc_raw.strip().startswith("{")):
                try:
                    desc_list = json.loads(desc_raw)
                    text_parts = []
                    for item in desc_list:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                    description = "\n".join(text_parts)
                except Exception:
                    description = desc_raw
            else:
                description = desc_raw

        # Tải ảnh sản phẩm
        folder_name = f"tiktok_{product_id}_{int(time.time())}"
        product_folder = os.path.join(DOWNLOAD_DIR, folder_name)
        os.makedirs(product_folder, exist_ok=True)
        
        images_list = product_model.get("images", product_info.get("images", product_info.get("hero_images", [])))
        downloaded_images = []
        for img in images_list:
            img_url = ""
            if isinstance(img, dict):
                url_list = img.get("url_list", [])
                if url_list:
                    img_url = url_list[0]
            elif isinstance(img, str):
                img_url = img
                
            if img_url:
                local_path = self.download_image(img_url, product_folder)
                if local_path:
                    downloaded_images.append(local_path)

        # Tải video sản phẩm (nếu có)
        downloaded_videos = []
        videos_data = product_model.get("videos", {})
        if videos_data and isinstance(videos_data, dict):
            for vid_id, vid_info in videos_data.items():
                video_url = ""
                video_infos = vid_info.get("video_infos", [])
                if video_infos:
                    video_url = video_infos[0].get("main_url") or video_infos[0].get("backup_url")
                if video_url:
                    local_vid = self.download_video(video_url, product_folder)
                    if local_vid:
                        downloaded_videos.append(local_vid)

        # Phân loại và SKU
        variations = []
        skus = []
        
        # Trích xuất Variations từ sale_properties hoặc sale_props hoặc variations
        sale_properties = product_model.get("sale_properties", product_info.get("sale_properties", product_info.get("sale_props", product_info.get("variations", []))))
        for prop in sale_properties:
            # Nhận dạng cả dạng mới (property_name, property_values) và dạng cũ (name, values)
            name = prop.get("property_name", prop.get("name", ""))
            options = []
            vals = prop.get("property_values", prop.get("values", []))
            for val in vals:
                options.append(val.get("property_value_name", val.get("name", "")))
            
            variations.append({
                "name": name,
                "options": options,
                "images": []
            })

        # Trích xuất SKUs
        sku_list = product_model.get("skus", product_info.get("skus", []))
        promotion_product_price = promotion_model.get("promotion_product_price", {})
        skus_price = promotion_product_price.get("skus_price", {})
        
        source_weight = None
        source_dimensions = None

        for sku_item in sku_list:
            sku_id = sku_item.get("sku_id", "")
            
            # Lấy giá
            price_val = 0
            if sku_id and sku_id in skus_price:
                price_str = skus_price[sku_id].get("sale_price_decimal", "0")
                try:
                    price_val = int(price_str)
                except ValueError:
                    try:
                        price_val = int(float(price_str))
                    except Exception:
                        pass
            else:
                price_info = sku_item.get("price", {})
                price_str = price_info.get("sale_price", price_info.get("original_price", 0))
                try:
                    price_val = int(float(price_str))
                    if price_val > 10000000:
                        price_val = price_val // 100
                except Exception:
                    pass

            # Lượng hàng tồn kho
            stock = sku_item.get("sku_quantity", {}).get("available_quantity", 99)
            if stock == 99 and "stock" in sku_item:
                stock = sku_item.get("stock", {}).get("available_stock", 99)
            
            sku_code = sku_item.get("seller_sku", "")

            # Map variation indexes
            variation_indexes = []
            property_pairs = sku_item.get("property_pairs", [])
            
            if property_pairs and variations:
                for var in variations:
                    var_name = var["name"]
                    opt_idx = 0
                    for pair in property_pairs:
                        if pair.get("sku_property_name") == var_name:
                            val_name = pair.get("sku_property_value_name", "")
                            if val_name in var["options"]:
                                opt_idx = var["options"].index(val_name)
                                break
                    variation_indexes.append(opt_idx)
            else:
                # Fallback map theo tên sku_name cũ
                sku_name = sku_item.get("sku_name", "")
                if sku_name and variations:
                    parts = [p.strip() for p in sku_name.split(",")]
                    for idx, var in enumerate(variations):
                        opt_idx = 0
                        if idx < len(parts):
                            part = parts[idx]
                            if part in var["options"]:
                                opt_idx = var["options"].index(part)
                        variation_indexes.append(opt_idx)

            skus.append({
                "variation_indexes": variation_indexes,
                "price": price_val,
                "stock": stock,
                "sku_code": sku_code
            })

            # Trích xuất cân nặng/kích thước từ SKU đầu tiên
            if source_weight is None:
                w_val = sku_item.get("weight", {}).get("weight") or sku_item.get("package_weight")
                if w_val is not None:
                    try:
                        source_weight = float(w_val) / 1000.0  # Đổi ra kg
                    except Exception:
                        pass
            if source_dimensions is None:
                dim = sku_item.get("dimension") or sku_item.get("dimension_v2")
                if dim:
                    try:
                        source_dimensions = {
                            "length": float(dim.get("length") or 10),
                            "width": float(dim.get("width") or 10),
                            "height": float(dim.get("height") or 10)
                        }
                    except Exception:
                        pass

        if not variations or not skus:
            price_info = product_model.get("price", product_info.get("price", {}))
            price_val = int(price_info.get("sale_price", price_info.get("original_price", 100000)))
            stock = product_model.get("stock", {}).get("available_stock", 99)
            skus = [{
                "variation_indexes": [],
                "price": price_val,
                "stock": stock,
                "sku_code": ""
            }]
            variations = []

        result = {
            "source": "tiktok",
            "product_id": product_id,
            "title": title,
            "description": description,
            "images": downloaded_images,
            "videos": downloaded_videos,
            "variations": variations,
            "skus": skus,
            "original_url": url
        }
        
        if source_weight is not None:
            result["source_weight"] = source_weight
        if source_dimensions is not None:
            result["source_dimensions"] = source_dimensions
            
        return result

    async def scrape_bulk(self, urls: list, log_callback=None) -> list:
        results = []
        for idx, url in enumerate(urls):
            url = url.strip()
            if not url:
                continue
            msg = f"🔍 Đang cào sản phẩm {idx+1}/{len(urls)}: {url}"
            if log_callback:
                if inspect.iscoroutinefunction(log_callback):
                    await log_callback(msg)
                else:
                    try: log_callback(msg)
                    except: pass
            try:
                data = await self.scrape(url)
                results.append(data)
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                msg_err = f"❌ Lỗi cào sản phẩm {idx+1}: {repr(e)}"
                
                # Lưu log ra file để debug
                try:
                    with open(os.path.join(DOWNLOAD_DIR, "debug_scraper.txt"), "a", encoding="utf-8") as f:
                        f.write(f"--- LỖI CÀO SẢN PHẨM {url} ---\n{msg_err}\n{error_traceback}\n")
                except:
                    pass

                if log_callback:
                    if inspect.iscoroutinefunction(log_callback):
                        await log_callback(msg_err)
                    else:
                        try: log_callback(msg_err)
                        except: pass
        return results

    async def extract_shop_products(self, url: str, log_callback=None) -> list:
        domain = urlparse(url).netloc.lower()
        
        if "shopee" in domain:
            return await self.extract_shopee_shop(url, log_callback)
        elif "tiktok" in domain:
            return await self.extract_tiktok_shop(url, log_callback)
        else:
            raise ValueError("Không hỗ trợ lấy danh sách sản phẩm từ link shop này.")

    async def extract_shopee_shop(self, url: str, log_callback=None) -> list:
        msg = "🚀 Đang mở trình duyệt để quét shop Shopee... Vui lòng hoàn thành kéo slider Captcha trên màn hình Chrome vừa xuất hiện nếu có!"
        if log_callback:
            if inspect.iscoroutinefunction(log_callback): await log_callback(msg)
            else: log_callback(msg)
            
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        await context.add_init_script("delete navigator.__proto__.webdriver;")
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            # Đợi selector sản phẩm xuất hiện
            product_selector = "a[href*='-i.'], a[href*='/product/']"
            try:
                await page.wait_for_selector(product_selector, timeout=60000)
            except Exception:
                raise RuntimeError("Không phát hiện sản phẩm trên trang Shopee. Có thể do Captcha chưa được giải quyết hoặc link shop sai.")
                
            msg_ok = "✅ Giải captcha thành công! Đang cuộn trang lấy danh sách sản phẩm..."
            if log_callback:
                if inspect.iscoroutinefunction(log_callback): await log_callback(msg_ok)
                else: log_callback(msg_ok)
            
            # Cuộn trang
            for i in range(5):
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(1.5)
                
            links = await page.locator("a").all()
            product_urls = []
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    if "-i." in href or "/product/" in href:
                        if href.startswith("/"):
                            href = "https://shopee.vn" + href
                        if href not in product_urls:
                            product_urls.append(href)
            return product_urls
        finally:
            await context.close()
            await browser.close()
            await playwright.stop()

    async def extract_tiktok_shop(self, url: str, log_callback=None) -> list:
        msg = "🚀 Đang mở trình duyệt để quét shop TikTok... Vui lòng hoàn thành kéo slider Captcha trên màn hình Chrome vừa xuất hiện nếu có!"
        if log_callback:
            if inspect.iscoroutinefunction(log_callback): await log_callback(msg)
            else: log_callback(msg)
            
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        await context.add_init_script("delete navigator.__proto__.webdriver;")
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)
            
            # Click vào tab Cửa hàng/Shop nếu có
            shop_tabs = ["text='Shop'", "text='Cửa hàng'", "[class*='shop']", "[class*='Shop']", "[class*='showcase']"]
            for selector in shop_tabs:
                try:
                    locator = page.locator(selector)
                    if await locator.count() > 0:
                        await locator.first.click(timeout=3000)
                        await asyncio.sleep(2)
                        break
                except:
                    pass
            
            # Đợi selector sản phẩm xuất hiện
            product_selector = "a[href*='/view/product/'], a[href*='shop.tiktok.com']"
            try:
                await page.wait_for_selector(product_selector, timeout=60000)
            except Exception:
                raise RuntimeError("Không phát hiện sản phẩm trên trang TikTok Shop. Có thể do Captcha chưa được giải quyết hoặc link shop sai.")
                
            msg_ok = "✅ Giải captcha thành công! Đang cuộn trang lấy danh sách sản phẩm..."
            if log_callback:
                if inspect.iscoroutinefunction(log_callback): await log_callback(msg_ok)
                else: log_callback(msg_ok)
            
            # Cuộn trang
            for _ in range(5):
                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(1.5)
                
            links = await page.locator("a").all()
            product_urls = []
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    if "/view/product/" in href or "shop.tiktok.com" in href:
                        if href.startswith("//"):
                            href = "https:" + href
                        elif href.startswith("/"):
                            href = "https://www.tiktok.com" + href
                        if href not in product_urls:
                            product_urls.append(href)
            return product_urls
        finally:
            await context.close()
            await browser.close()
            await playwright.stop()

# Singleton instance
scraper = ProductScraper()
