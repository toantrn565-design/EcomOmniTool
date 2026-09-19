import os
import json
import time
import asyncio
import pandas as pd
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging

# Imports for Video Poster
from backend.video_automation import ShopeeVideoUploader, get_uploader

# Imports for Product Copier
from backend.scraper import scraper, DOWNLOAD_DIR
from backend.uploader import ProductUploader

# Imports for New Modules
from backend.boost_automation import ShopeeProductBooster
from backend.flashsale_automation import FlashSaleScheduler
from backend.ai_chat_agent import AISalesConsultant, AIProductRewriter, chat_history_records, add_chat_record
from backend.image_styler import ImageStyler
from backend.cron_scheduler import cron_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ecom OmniTool Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thư mục chứa tài khoản cấu hình (Liên kết với tool cũ)
SHOPEE_POSTER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ShopeeVideoAutoPoster"))
CONFIG_DIR = os.path.join(SHOPEE_POSTER_DIR, "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
ACCOUNTS_FILE = os.path.join(CONFIG_DIR, "accounts.json")

# Nếu thư mục config cũ không tồn tại, tạo mới nội bộ
if not os.path.exists(CONFIG_DIR):
    CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
    os.makedirs(CONFIG_DIR, exist_ok=True)
    CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
    ACCOUNTS_FILE = os.path.join(CONFIG_DIR, "accounts.json")

# --- WebSocket & Logs Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await asyncio.wait_for(connection.send_text(message), timeout=2.0)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

ws_manager = ConnectionManager()
logs_buffer = []

async def log_to_ui(message: str):
    """Ghi log và gửi qua WebSocket lên UI."""
    formatted_msg = f"[{asyncio.get_event_loop().time():.1f}] {message}"
    logs_buffer.append(formatted_msg)
    if len(logs_buffer) > 500:
        logs_buffer.pop(0)
    asyncio.create_task(ws_manager.broadcast(formatted_msg))


# --- State & Locks cho Video Poster ---
_profile_locks = {}
def get_profile_lock(profile_dir: str) -> asyncio.Lock:
    abs_path = os.path.abspath(profile_dir)
    if abs_path not in _profile_locks:
        _profile_locks[abs_path] = asyncio.Lock()
    return _profile_locks[abs_path]

class UploaderState:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False
        self.current_video = ""
        self.total_videos = 0
        self.completed_videos = 0
        self.current_account_id = ""
        self.current_task = None

uploader_state = UploaderState()

# --- Settings & Accounts Data ---
DEFAULT_SETTINGS = {
    "default_caption_suffix": "\n#shopee #shopeevideo #affiliate",
    "delay_between_posts": 60,
    "product_tagging_mode": "manual"
}

def load_settings() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except Exception:
            return DEFAULT_SETTINGS
    return DEFAULT_SETTINGS

def save_settings(settings: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

def load_accounts() -> list:
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                accounts = json.load(f)
                # Chuẩn hóa platform
                for acc in accounts:
                    if "platform" not in acc:
                        acc["platform"] = "shopee"
                return accounts
        except Exception:
            return []
    return []

def save_accounts(accounts: list):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=4, ensure_ascii=False)


# --- API Models ---
class SettingsUpdate(BaseModel):
    default_caption_suffix: str
    delay_between_posts: int
    product_tagging_mode: str = "manual"

class AccountModel(BaseModel):
    id: str
    name: str
    type: str = "seller"
    platform: str = "shopee"
    profile_dir: str
    video_folder: str = ""
    proxy_server: Optional[str] = ""
    proxy_username: Optional[str] = ""
    proxy_password: Optional[str] = ""
    status: str = "Chưa kết nối"
    auth_mode: Optional[str] = "browser"
    shopee_partner_id: Optional[str] = ""
    shopee_partner_key: Optional[str] = ""
    shopee_shop_id: Optional[str] = ""
    shopee_access_token: Optional[str] = ""
    tiktok_app_key: Optional[str] = ""
    tiktok_app_secret: Optional[str] = ""
    tiktok_shop_cipher: Optional[str] = ""
    tiktok_access_token: Optional[str] = ""
    mcp_url: Optional[str] = ""
    mcp_token: Optional[str] = ""

class ImageFrameRequest(BaseModel):
    image_url_or_path: str
    frame_type: str = "flashsale"
    badge_text: str = "FREESHIP EXTRA"
    discount_tag: str = "-50%"

class ScheduleAddRequest(BaseModel):
    task_type: str
    account_id: str
    target_time: str
    payload: Optional[dict] = None

class VideoMetadataUpdate(BaseModel):
    file_name: str
    caption: str
    products: str
    status: str = "Sẵn sàng"

class StartUploadRequest(BaseModel):
    account_ids: List[str] = None
    account_id: str = ""
    videos: List[dict] = None

class ScrapeRequest(BaseModel):
    url: str

class ScrapeBulkRequest(BaseModel):
    urls: List[str]

class ExtractShopRequest(BaseModel):
    url: str

class PublishRequest(BaseModel):
    account_id: str
    product_data: Dict[str, Any]

class PublishBulkRequest(BaseModel):
    account_id: str
    products: List[Dict[str, Any]]
    auto_publish: bool = False
    default_brand: str = "No brand"
    default_weight: float = 0.5
    default_dimensions: Optional[Dict[str, float]] = None

class BoostRequest(BaseModel):
    account_id: str
    mode: str = "smart"
    product_ids: Optional[List[str]] = None

class InstantBoostRequest(BaseModel):
    account_id: str
    product_name: str

class FlashSaleRequest(BaseModel):
    account_id: str
    discount_percent: int = 10
    stock_per_item: int = 10
    target_product_count: int = 10
    selected_products: Optional[List[str]] = None

class AIChatToggleRequest(BaseModel):
    account_id: str
    action: str = "start"
    api_key: Optional[str] = ""

class AIChatTestRequest(BaseModel):
    account_id: str
    customer_message: str
    api_key: Optional[str] = ""

class AIRewriteRequest(BaseModel):
    title: str
    description: str
    api_key: Optional[str] = ""


# ==========================================
# MODULE 1: TÀI KHOẢN VÀ CÀI ĐẶT
# ==========================================

@app.get("/api/settings")
def get_settings():
    return load_settings()

@app.post("/api/settings")
def update_settings(settings: SettingsUpdate):
    save_settings(settings.dict())
    return {"status": "success", "message": "Đã lưu cài đặt chung."}

@app.get("/api/accounts")
def get_accounts():
    return load_accounts()

@app.post("/api/accounts")
def add_or_update_account(account: AccountModel):
    accounts = load_accounts()
    existing_idx = -1
    for idx, acc in enumerate(accounts):
        if acc["id"] == account.id:
            existing_idx = idx
            break
            
    if existing_idx >= 0:
        old_status = accounts[existing_idx].get("status", "Chưa kết nối")
        accounts[existing_idx] = account.dict()
        if not account.status or account.status == "Chưa kết nối":
            accounts[existing_idx]["status"] = old_status
    else:
        accounts.append(account.dict())
        
    save_accounts(accounts)
    return {"status": "success", "message": "Đã lưu thông tin tài khoản."}

@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str):
    accounts = load_accounts()
    updated_accounts = [acc for acc in accounts if acc["id"] != account_id]
    save_accounts(updated_accounts)
    return {"status": "success", "message": "Đã xóa tài khoản."}

async def run_login_task(profile_dir: str, platform: str):
    lock = get_profile_lock(profile_dir)
    async with lock:
        uploader = get_uploader(platform, profile_dir=profile_dir)
        try:
            await uploader.open_login_session(log_callback=log_to_ui)
        except Exception as e:
            await log_to_ui(f"Lỗi khi mở phiên đăng nhập: {str(e)}")

@app.post("/api/accounts/{account_id}/login")
def start_account_login(account_id: str, background_tasks: BackgroundTasks):
    accounts = load_accounts()
    account = next((acc for acc in accounts if acc["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
        
    profile_dir = account["profile_dir"]
    lock = get_profile_lock(profile_dir)
    if lock.locked():
        raise HTTPException(status_code=400, detail="Trình duyệt đang bận.")
        
    background_tasks.add_task(run_login_task, profile_dir, account.get("platform", "shopee"))
    return {"status": "success", "message": f"Đang mở trình duyệt đăng nhập cho {account['name']}..."}

@app.get("/api/accounts/{account_id}/check")
async def check_account_connection(account_id: str):
    accounts = load_accounts()
    account = next((acc for acc in accounts if acc["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
        
    profile_dir = account["profile_dir"]
    lock = get_profile_lock(profile_dir)
    if lock.locked():
        raise HTTPException(status_code=400, detail="Trình duyệt đang mở.")
        
    async with lock:
        platform = account.get("platform", "shopee")
        uploader = get_uploader(platform, profile_dir)
        is_logged_in = await uploader.check_login_status()
        
        new_status = "Đã kết nối" if is_logged_in else "Chưa kết nối"
        for acc in accounts:
            if acc["id"] == account_id:
                acc["status"] = new_status
                break
        save_accounts(accounts)
        return {"logged_in": is_logged_in, "status": new_status}


# ==========================================
# MODULE 2: VIDEO AUTO POSTER
# ==========================================

def get_metadata_file_path(video_folder: str) -> str:
    return os.path.join(video_folder, ".shopee_video_metadata.json")

def sync_and_scan_videos(account: dict) -> list:
    video_folder = account.get("video_folder")
    if not video_folder or not os.path.exists(video_folder):
        return []

    video_files = [f for f in os.listdir(video_folder) if f.lower().endswith(".mp4")]
    metadata_file = get_metadata_file_path(video_folder)
    cached_metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                cached_metadata = {item["file_name"]: item for item in json.load(f)}
        except Exception:
            pass

    csv_metadata = {}
    csv_path = os.path.join(video_folder, "metadata.csv")
    xlsx_path = os.path.join(video_folder, "metadata.xlsx")
    
    if os.path.exists(xlsx_path):
        try:
            df = pd.read_excel(xlsx_path)
            for _, row in df.iterrows():
                fname = str(row.get("file_name", ""))
                if fname:
                    csv_metadata[fname] = {
                        "caption": str(row.get("caption", "")),
                        "products": str(row.get("products", "")) if not pd.isna(row.get("products")) else ""
                    }
        except Exception as e:
            logger.error(f"Lỗi đọc file metadata.xlsx: {e}")
            
    elif os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                fname = str(row.get("file_name", ""))
                if fname:
                    csv_metadata[fname] = {
                        "caption": str(row.get("caption", "")),
                        "products": str(row.get("products", "")) if not pd.isna(row.get("products")) else ""
                    }
        except Exception as e:
            logger.error(f"Lỗi đọc file metadata.csv: {e}")

    result = []
    for file in video_files:
        if file in cached_metadata:
            item = cached_metadata[file]
            if file in csv_metadata:
                if not item.get("products") and csv_metadata[file]["products"]:
                    item["products"] = csv_metadata[file]["products"]
                if not item.get("caption") and csv_metadata[file]["caption"]:
                    item["caption"] = csv_metadata[file]["caption"]
            result.append(item)
        elif file in csv_metadata:
            result.append({
                "file_name": file,
                "caption": csv_metadata[file]["caption"],
                "products": csv_metadata[file]["products"],
                "status": "Sẵn sàng"
            })
        else:
            caption_default = os.path.splitext(file)[0]
            result.append({
                "file_name": file,
                "caption": caption_default,
                "products": "",
                "status": "Sẵn sàng"
            })
            
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    return result

@app.get("/api/videos")
def scan_and_get_videos(account_id: str):
    accounts = load_accounts()
    account = next((acc for acc in accounts if acc["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=400, detail="Vui lòng chọn Shop hoạt động.")
    return sync_and_scan_videos(account)

@app.post("/api/videos/save")
def save_videos_metadata(account_id: str, videos: List[VideoMetadataUpdate]):
    accounts = load_accounts()
    account = next((acc for acc in accounts if acc["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    video_folder = account.get("video_folder")
    if not video_folder or not os.path.exists(video_folder):
        raise HTTPException(status_code=400, detail="Thư mục video không tồn tại.")
    data = [v.dict() for v in videos]
    metadata_file = get_metadata_file_path(video_folder)
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return {"status": "success", "message": "Đã lưu thông tin video."}

@app.get("/api/uploader/status")
def get_uploader_status():
    return {
        "is_running": uploader_state.is_running,
        "current_video": uploader_state.current_video,
        "total_videos": uploader_state.total_videos,
        "completed_videos": uploader_state.completed_videos,
        "current_account_id": uploader_state.current_account_id,
    }

async def run_upload_pipeline(account_ids: List[str], video_list: List[dict] = None):
    try:
        settings = load_settings()
        delay = settings.get("delay_between_posts", 60)
        suffix = settings.get("default_caption_suffix", "")
        
        shop_queues = {} 
        total_videos_to_post = 0
        
        for account_id in account_ids:
            accounts = load_accounts()
            account = next((acc for acc in accounts if acc["id"] == account_id), None)
            if not account or account.get("status") != "Đã kết nối":
                continue
            video_folder = account.get("video_folder")
            if not video_folder or not os.path.exists(video_folder):
                continue
                
            current_videos = []
            if len(account_ids) == 1 and video_list:
                current_videos = video_list
            else:
                try:
                    all_meta = sync_and_scan_videos(account)
                    current_videos = [v for v in all_meta if v.get("status", "Sẵn sàng") in ["Sẵn sàng", "Lỗi"]]
                except Exception:
                    continue
                    
            if current_videos:
                shop_queues[account_id] = current_videos
                total_videos_to_post += len(current_videos)
                
        if total_videos_to_post == 0:
            await log_to_ui("ℹ️ Không tìm thấy video chờ đăng.")
            uploader_state.is_running = False
            return
            
        uploader_state.total_videos = total_videos_to_post
        uploader_state.completed_videos = 0
        uploader_state.is_running = True
        uploader_state.stop_requested = False
        
        await log_to_ui(f"Bắt đầu chiến dịch video cho {len(shop_queues)} Shop.")
        
        max_queue_len = max(len(queue) for queue in shop_queues.values()) if shop_queues else 0
        post_count = 0
        for idx in range(max_queue_len):
            for account_id in account_ids:
                if uploader_state.stop_requested:
                    break
                    
                queue = shop_queues.get(account_id, [])
                if idx >= len(queue):
                    continue
                    
                video = queue[idx]
                accounts = load_accounts()
                account = next((acc for acc in accounts if acc["id"] == account_id), None)
                video_folder = account.get("video_folder")
                profile_dir = account["profile_dir"]
                
                file_name = video.get("file_name")
                caption = video.get("caption", "") + suffix
                products_str = video.get("products", "")
                products = [p.strip() for p in products_str.replace(";", ",").split(",") if p.strip()] if products_str else []
                    
                uploader_state.current_account_id = account_id
                uploader_state.current_video = file_name
                video_path = os.path.join(video_folder, file_name)
                
                post_count += 1
                await log_to_ui(f"Đang đăng video [{post_count}/{total_videos_to_post}]: {file_name}")
                
                platform = account.get("platform", "shopee")
                lock = get_profile_lock(profile_dir)
                async with lock:
                    uploader = get_uploader(platform, profile_dir)
                    success = False
                    try:
                        product_tagging_mode = settings.get("product_tagging_mode", "manual")
                        success = await uploader.upload_video(
                            video_path=video_path,
                            caption=caption,
                            product_keywords=products,
                            product_tagging_mode=product_tagging_mode,
                            log_callback=log_to_ui
                        )
                    except Exception as e:
                        await log_to_ui(f"Lỗi: {str(e)}")
                    
                if success:
                    uploader_state.completed_videos += 1
                    await log_to_ui(f"✅ Đăng thành công: {file_name}")
                else:
                    await log_to_ui(f"❌ Đăng thất bại: {file_name}")
                    
                if post_count < total_videos_to_post and not uploader_state.stop_requested:
                    for _ in range(delay):
                        if uploader_state.stop_requested: break
                        await asyncio.sleep(1)
                        
    except asyncio.CancelledError:
        pass
    finally:
        uploader_state.is_running = False
        uploader_state.current_task = None

@app.post("/api/uploader/start")
async def start_uploader(request: StartUploadRequest):
    if uploader_state.is_running:
        raise HTTPException(status_code=400, detail="Tiến trình đang chạy.")
    account_ids = request.account_ids or ([request.account_id] if request.account_id else [])
    if not account_ids:
        raise HTTPException(status_code=400, detail="Chưa chọn Shop.")
    task = asyncio.create_task(run_upload_pipeline(account_ids, request.videos))
    uploader_state.current_task = task
    return {"status": "success", "message": "Bắt đầu chạy nền."}

@app.post("/api/uploader/stop")
def stop_uploader():
    if not uploader_state.is_running:
        return {"status": "info"}
    uploader_state.stop_requested = True
    if uploader_state.current_task and not uploader_state.current_task.done():
        uploader_state.current_task.cancel()
    return {"status": "success"}


# ==========================================
# MODULE 3: PRODUCT COPIER
# ==========================================

@app.post("/api/scrape")
async def scrape_product(request: ScrapeRequest):
    url = request.url.strip()
    if not url: raise HTTPException(status_code=400)
    await log_to_ui(f"Bắt đầu cào link: {url}")
    try:
        data = await scraper.scrape(url)
        await log_to_ui("Cào sản phẩm thành công.")
        return data
    except Exception as e:
        await log_to_ui(f"Lỗi cào sản phẩm: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scrape-bulk")
async def scrape_product_bulk(request: ScrapeBulkRequest):
    urls = [u.strip() for u in request.urls if u.strip()]
    if not urls: raise HTTPException(status_code=400)
    await log_to_ui(f"Bắt đầu cào hàng loạt {len(urls)} link...")
    try:
        results = await scraper.scrape_bulk(urls, log_callback=log_to_ui)
        await log_to_ui(f"Đã cào xong {len(results)}/{len(urls)} sản phẩm.")
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract-shop")
async def extract_shop(request: ExtractShopRequest):
    url = request.url.strip()
    if not url: raise HTTPException(status_code=400)
    await log_to_ui(f"Bắt đầu quét shop: {url}")
    try:
        product_urls = await scraper.extract_shop_products(url, log_callback=log_to_ui)
        await log_to_ui(f"Tìm thấy {len(product_urls)} sản phẩm.")
        return {"urls": product_urls}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_product_uploader_bulk(
    profile_dir: str, platform: str, products: list, 
    auto_publish: bool, default_brand: str, default_weight: float, default_dimensions: dict
):
    await log_to_ui(f"Khởi chạy đăng {len(products)} sản phẩm...")
    for idx, prod in enumerate(products):
        await log_to_ui(f"Đang đăng: {prod['title'][:40]}")
        lock = get_profile_lock(profile_dir)
        async with lock:
            uploader = ProductUploader(profile_dir=profile_dir)
            try:
                if platform.lower() == "shopee":
                    success = await uploader.upload_to_shopee(
                        prod, auto_publish, default_brand, default_weight, default_dimensions, log_to_ui
                    )
                elif platform.lower() == "tiktok":
                    success = await uploader.upload_to_tiktok(
                        prod, auto_publish, default_brand, default_weight, default_dimensions, log_to_ui
                    )
                if success:
                    await log_to_ui("✅ Đăng sản phẩm thành công!")
                else:
                    await log_to_ui("❌ Thất bại khi đăng.")
                await asyncio.sleep(5)
            except Exception as e:
                await log_to_ui(f"Lỗi: {e}")

@app.post("/api/publish-bulk")
async def publish_product_bulk(request: PublishBulkRequest, background_tasks: BackgroundTasks):
    accounts = load_accounts()
    account = next((a for a in accounts if a["id"] == request.account_id), None)
    if not account: raise HTTPException(status_code=404)
    profile_dir = account.get("profile_dir")
    platform = account.get("platform", "shopee")
    background_tasks.add_task(
        run_product_uploader_bulk,
        profile_dir, platform, request.products, request.auto_publish,
        request.default_brand, request.default_weight, request.default_dimensions
    )
    return {"status": "success", "message": "Bắt đầu đăng hàng loạt trong nền."}


# ==========================================
# MODULE 4: TỰ ĐỘNG ĐẨY SẢN PHẨM 4H (AUTO BOOST) - ĐA SHOP ĐỒNG THỜI
# ==========================================

class ShopBoosterTask:
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.is_running = False
        self.stop_requested = False
        self.next_run_time = 0
        self.task: Optional[asyncio.Task] = None

active_booster_tasks: Dict[str, ShopBoosterTask] = {}

async def run_shop_boost_loop(account_id: str, mode: str, product_ids: Optional[List[str]]):
    bstate = active_booster_tasks.get(account_id)
    if not bstate:
        return
    try:
        bstate.is_running = True
        bstate.stop_requested = False
        
        while not bstate.stop_requested:
            accounts = load_accounts()
            account = next((a for a in accounts if a["id"] == account_id), None)
            if not account:
                await log_to_ui(f"❌ Không tìm thấy tài khoản (ID: {account_id}) để đẩy sản phẩm.")
                break
                
            profile_dir = account.get("profile_dir")
            lock = get_profile_lock(profile_dir)
            shop_name = account.get("name", "Shop")
            
            await log_to_ui(f"🚀 Bắt đầu chu kỳ đẩy 5 sản phẩm cho Shop: {shop_name}")
            async with lock:
                booster = ShopeeProductBooster(profile_dir=profile_dir)
                res = await booster.execute_boost(mode=mode, target_keywords=product_ids, log_callback=log_to_ui)
                
            bstate.next_run_time = time.time() + (4 * 3600 + 120)
            await log_to_ui(f"⏳ [{shop_name}] Đã lên lịch lượt đẩy tiếp theo sau 4 tiếng (lúc {time.strftime('%H:%M:%S', time.localtime(bstate.next_run_time))})")
            
            for _ in range(4 * 3600 + 120):
                if bstate.stop_requested:
                    break
                await asyncio.sleep(1)
                
    except asyncio.CancelledError:
        pass
    except Exception as e:
        await log_to_ui(f"❌ Lỗi tiến trình đẩy 4h ({account_id}): {e}")
    finally:
        bstate.is_running = False
        if account_id in active_booster_tasks:
            del active_booster_tasks[account_id]

@app.get("/api/boost/products")
async def get_boost_products(account_id: str):
    accounts = load_accounts()
    account = next((a for a in accounts if a["id"] == account_id), None)
    if not account: raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    
    # 1. Kiểm tra nếu tài khoản có cài đặt Shopee Open API chính thức
    if account.get("shopee_partner_id") and account.get("shopee_partner_key") and account.get("shopee_access_token"):
        try:
            from backend.ecom_api_client import ShopeeOpenAPI
            client = ShopeeOpenAPI(
                partner_id=int(account["shopee_partner_id"]),
                partner_key=account["shopee_partner_key"],
                shop_id=int(account.get("shopee_shop_id") or 0),
                access_token=account["shopee_access_token"]
            )
            prods = client.get_products()
            if prods:
                await log_to_ui(f"✅ Đã tải thành công {len(prods)} sản phẩm qua Shopee Open API chính thức!")
                return prods
        except Exception as e:
            await log_to_ui(f"⚠️ Lỗi gọi Shopee Open API: {e}. Đang chuyển sang quét tự động...")

    # 2. Kiểm tra nếu dùng TikTok Shop Open API
    if (account.get("platform") == "tiktok" or account.get("tiktok_app_key")) and account.get("tiktok_access_token"):
        try:
            from backend.ecom_api_client import TikTokShopAPI
            client = TikTokShopAPI(
                app_key=account.get("tiktok_app_key", ""),
                app_secret=account.get("tiktok_app_secret", ""),
                access_token=account.get("tiktok_access_token", ""),
                shop_cipher=account.get("tiktok_shop_cipher", "")
            )
            prods = client.get_products()
            if prods:
                await log_to_ui(f"✅ Đã tải thành công {len(prods)} sản phẩm qua TikTok Shop Open API!")
                return prods
        except Exception as e:
            await log_to_ui(f"⚠️ Lỗi gọi TikTok Shop API: {e}.")

    # 3. Fallback qua Browser Automation Session
    profile_dir = account.get("profile_dir")
    lock = get_profile_lock(profile_dir)
    async with lock:
        booster = ShopeeProductBooster(profile_dir=profile_dir)
        return await booster.get_products_list(log_callback=log_to_ui)

@app.post("/api/boost/instant")
async def boost_single_product(request: InstantBoostRequest):
    accounts = load_accounts()
    account = next((a for a in accounts if a["id"] == request.account_id), None)
    if not account: raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    profile_dir = account.get("profile_dir")
    lock = get_profile_lock(profile_dir)
    async with lock:
        booster = ShopeeProductBooster(profile_dir=profile_dir)
        res = await booster.execute_boost(mode="strict", target_keywords=[request.product_name], log_callback=log_to_ui)
        return res

@app.post("/api/boost/start")
async def start_boost(request: BoostRequest):
    accounts = load_accounts()
    target_accounts = []
    if request.account_id == "all":
        target_accounts = [acc for acc in accounts if acc.get("status") == "Đã kết nối" or os.path.exists(acc.get("profile_dir", ""))]
        if not target_accounts:
            target_accounts = accounts
    else:
        target_acc = next((a for a in accounts if a["id"] == request.account_id), None)
        if target_acc:
            target_accounts = [target_acc]

    if not target_accounts:
        raise HTTPException(status_code=404, detail="Không tìm thấy Shop nào để chạy.")

    started_count = 0
    for acc in target_accounts:
        acc_id = acc["id"]
        if acc_id in active_booster_tasks and active_booster_tasks[acc_id].is_running:
            continue
        
        bstate = ShopBoosterTask(acc_id)
        active_booster_tasks[acc_id] = bstate
        task = asyncio.create_task(run_shop_boost_loop(acc_id, request.mode, request.product_ids))
        bstate.task = task
        started_count += 1

    return {"status": "success", "message": f"Đã kích hoạt tự động đẩy sản phẩm cho {started_count} Shop song song."}

@app.post("/api/boost/stop")
def stop_boost(account_id: Optional[str] = None):
    if not active_booster_tasks:
        return {"status": "info", "message": "Không có Shop nào đang đẩy."}
    
    target_ids = list(active_booster_tasks.keys()) if not account_id or account_id == "all" else [account_id]
    stopped = 0
    for aid in target_ids:
        bstate = active_booster_tasks.get(aid)
        if bstate:
            bstate.stop_requested = True
            if bstate.task and not bstate.task.done():
                bstate.task.cancel()
            stopped += 1
            
    return {"status": "success", "message": f"Đã dừng tiến trình đẩy sản phẩm của {stopped} Shop."}

@app.get("/api/boost/status")
def get_boost_status():
    running_accounts = [aid for aid, b in active_booster_tasks.items() if b.is_running]
    first_state = next((b for b in active_booster_tasks.values() if b.is_running), None)
    remaining = max(0, int(first_state.next_run_time - time.time())) if first_state and first_state.next_run_time > 0 else 0
    
    return {
        "is_running": len(running_accounts) > 0,
        "running_count": len(running_accounts),
        "running_accounts": running_accounts,
        "current_account_id": running_accounts[0] if running_accounts else "",
        "remaining_seconds": remaining,
        "next_run_time": first_state.next_run_time if first_state else 0
    }


# ==========================================
# MODULE 5: TỰ ĐỘNG FLASHSALE CỦA SHOP
# ==========================================

@app.get("/api/flashsale/products")
async def get_flashsale_products(account_id: str):
    return await get_boost_products(account_id)

async def run_flashsale_task(account_id: str, discount_percent: int, stock_per_item: int, target_product_count: int, selected_products: Optional[List[str]]):
    accounts = load_accounts()
    account = next((a for a in accounts if a["id"] == account_id), None)
    if not account:
        await log_to_ui(f"❌ Không tìm thấy tài khoản Flash Sale (ID: {account_id}).")
        return
    profile_dir = account.get("profile_dir")
    lock = get_profile_lock(profile_dir)
    async with lock:
        scheduler = FlashSaleScheduler(profile_dir=profile_dir)
        await scheduler.auto_create_flashsale(
            discount_percent=discount_percent,
            stock_per_item=stock_per_item,
            target_product_count=target_product_count,
            selected_products=selected_products,
            log_callback=log_to_ui
        )

@app.post("/api/flashsale/trigger")
def trigger_flashsale(request: FlashSaleRequest, background_tasks: BackgroundTasks):
    accounts = load_accounts()
    target_accounts = []
    if request.account_id == "all":
        target_accounts = accounts
    else:
        target_acc = next((a for a in accounts if a["id"] == request.account_id), None)
        if target_acc:
            target_accounts = [target_acc]

    for acc in target_accounts:
        background_tasks.add_task(
            run_flashsale_task,
            acc["id"],
            request.discount_percent,
            request.stock_per_item,
            request.target_product_count,
            request.selected_products
        )
    return {"status": "success", "message": f"Đã khởi chạy Flash Sale cho {len(target_accounts)} Shop."}


# ==========================================
# MODULE 6: AI SALES CHATBOT (TƯ VẤN 24/7) - ĐA SHOP ĐỒNG THỜI
# ==========================================

class ShopChatState:
    def __init__(self, account_id: str, agent: AISalesConsultant):
        self.account_id = account_id
        self.agent_instance = agent
        self.is_running = True
        self.task: Optional[asyncio.Task] = None

active_chat_agents: Dict[str, ShopChatState] = {}

@app.post("/api/chat/toggle")
async def toggle_ai_chat(request: AIChatToggleRequest):
    accounts = load_accounts()
    settings = load_settings()
    api_key = request.api_key or settings.get("gemini_api_key", "")
    
    if request.action == "start":
        target_accounts = []
        if request.account_id == "all":
            target_accounts = accounts
        else:
            target_acc = next((a for a in accounts if a["id"] == request.account_id), None)
            if target_acc:
                target_accounts = [target_acc]

        if not target_accounts:
            raise HTTPException(status_code=404, detail="Không tìm thấy Shop.")

        started = 0
        for acc in target_accounts:
            aid = acc["id"]
            if aid in active_chat_agents and active_chat_agents[aid].is_running:
                continue
            
            profile_dir = acc.get("profile_dir")
            chat_agent = AISalesConsultant(profile_dir=profile_dir, shop_name=acc.get("name", "Shop"), api_key=api_key)
            cstate = ShopChatState(aid, chat_agent)
            active_chat_agents[aid] = cstate
            task = asyncio.create_task(chat_agent.start_listening_loop(log_callback=log_to_ui))
            cstate.task = task
            started += 1

        return {"status": "success", "message": f"Đã bật AI Sales Consultant 24/7 cho {started} Shop song song."}
    else:
        target_ids = list(active_chat_agents.keys()) if request.account_id == "all" else [request.account_id]
        stopped = 0
        for aid in target_ids:
            cstate = active_chat_agents.get(aid)
            if cstate:
                cstate.is_running = False
                if cstate.agent_instance:
                    cstate.agent_instance.stop()
                if cstate.task and not cstate.task.done():
                    cstate.task.cancel()
                del active_chat_agents[aid]
                stopped += 1
        return {"status": "success", "message": f"Đã tắt AI Sales Consultant cho {stopped} Shop."}

@app.get("/api/chat/status")
def get_chat_status():
    running = [aid for aid, c in active_chat_agents.items() if c.is_running]
    return {
        "is_running": len(running) > 0,
        "running_count": len(running),
        "running_accounts": running,
        "current_account_id": running[0] if running else ""
    }

@app.get("/api/chat/history")
def get_chat_history():
    return chat_history_records

@app.post("/api/chat/test")
async def test_ai_chat_reply(request: AIChatTestRequest):
    accounts = load_accounts()
    account = next((a for a in accounts if a["id"] == request.account_id), None)
    shop_name = account.get("name", "Shop Demo") if account else "Shop Demo"
    
    settings = load_settings()
    api_key = request.api_key or settings.get("gemini_api_key", "")
    
    agent = AISalesConsultant(profile_dir="temp", shop_name=shop_name, api_key=api_key)
    reply = await agent.generate_reply(request.customer_message)
    
    # Ghi vào lịch sử để hiển thị ngay trên bảng
    add_chat_record(
        shop_name=shop_name,
        customer_msg=request.customer_message,
        ai_reply=reply,
        status="Test Thành Công"
    )
    
    await log_to_ui(f"🧪 [Test Chat {shop_name}] Khách: '{request.customer_message}' ➡️ AI: '{reply[:60]}...'")
    return {"status": "success", "shop_name": shop_name, "customer_message": request.customer_message, "reply": reply}

@app.post("/api/chat/open")
async def open_chat_portal_endpoint(request: InstantBoostRequest, background_tasks: BackgroundTasks):
    accounts = load_accounts()
    account = next((a for a in accounts if a["id"] == request.account_id), None)
    if not account: raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    profile_dir = account.get("profile_dir")
    lock = get_profile_lock(profile_dir)
    
    async def _open():
        async with lock:
            agent = AISalesConsultant(profile_dir=profile_dir, shop_name=account.get("name", "Shop"))
            await agent.open_chat_portal(log_callback=log_to_ui)
            
    background_tasks.add_task(_open)
    return {"status": "success", "message": f"Đang mở Kênh Chat Shopee cho {account.get('name')}..."}

@app.post("/api/shop/open")
async def open_shop_portal_endpoint(request: InstantBoostRequest, background_tasks: BackgroundTasks):
    accounts = load_accounts()
    account = next((a for a in accounts if a["id"] == request.account_id), None)
    if not account: raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    profile_dir = account.get("profile_dir")
    lock = get_profile_lock(profile_dir)
    
    async def _open():
        async with lock:
            booster = ShopeeProductBooster(profile_dir=profile_dir)
            await booster.open_seller_portal(log_callback=log_to_ui)
            
    background_tasks.add_task(_open)
    return {"status": "success", "message": f"Đang mở Kênh Người Bán cho {account.get('name')}..."}


# ==========================================
# MODULE 7: AI REWRITER (CHỐNG TRÙNG LẶP CLONE)
# ==========================================

@app.post("/api/ai/rewrite")
async def rewrite_product_ai(request: AIRewriteRequest):
    settings = load_settings()
    api_key = request.api_key or settings.get("gemini_api_key", "")
    res = await AIProductRewriter.rewrite_product(
        title=request.title,
        description=request.description,
        api_key=api_key,
        log_callback=log_to_ui
    )
    return {"status": "success", "data": res}


# ==========================================
# MODULE 8: ĐÓNG KHUNG ẢNH SẢN PHẨM (IMAGE STYLER)
# ==========================================

@app.post("/api/image/frame")
async def frame_image_endpoint(request: ImageFrameRequest):
    img_path = request.image_url_or_path
    if img_path.startswith("/downloads/"):
        img_path = os.path.join(DOWNLOAD_DIR, img_path.replace("/downloads/", ""))
    
    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file ảnh.")
        
    out_dir = os.path.dirname(img_path)
    filename = os.path.basename(img_path)
    out_path = os.path.join(out_dir, f"framed_{filename}")
    
    success = ImageStyler.apply_frame_and_watermark(
        image_path=img_path,
        output_path=out_path,
        frame_type=request.frame_type,
        badge_text=request.badge_text,
        discount_tag=request.discount_tag
    )
    if success:
        rel_path = f"/downloads/{os.path.basename(out_dir)}/framed_{filename}"
        await log_to_ui(f"✅ Đã tạo ảnh đóng khung tỷ lệ 1:1: framed_{filename}")
        return {"status": "success", "framed_url": rel_path}
    else:
        raise HTTPException(status_code=500, detail="Lỗi xử lý đóng khung ảnh.")


# ==========================================
# MODULE 9: LÊN LỊCH KHUNG GIỜ VÀNG (CRON SCHEDULER)
# ==========================================

async def handle_scheduled_task(task_type: str, account_id: str, payload: dict):
    if task_type == "boost":
        await run_boost_pipeline(account_id, mode=payload.get("mode", "smart"), product_ids=payload.get("product_ids"))
    elif task_type == "flashsale":
        await run_flashsale_task(
            account_id,
            discount_percent=payload.get("discount_percent", 10),
            stock_per_item=payload.get("stock_per_item", 10),
            target_product_count=payload.get("target_product_count", 10)
        )
    elif task_type == "video":
        await run_upload_pipeline([account_id])

@app.get("/api/schedules")
def get_schedules():
    return cron_scheduler.get_schedules()

@app.post("/api/schedules/add")
def add_schedule(request: ScheduleAddRequest):
    cron_scheduler.add_schedule(
        task_type=request.task_type,
        account_id=request.account_id,
        target_time=request.target_time,
        payload=request.payload
    )
    return {"status": "success", "message": f"Đã lên lịch {request.task_type} lúc {request.target_time}."}

@app.delete("/api/schedules/{sched_id}")
def delete_schedule(sched_id: str):
    cron_scheduler.remove_schedule(sched_id)
    return {"status": "success", "message": "Đã xóa lịch hẹn."}

@app.post("/api/schedules/toggle")
def toggle_scheduler(active: bool, background_tasks: BackgroundTasks):
    if active:
        if not cron_scheduler.is_running:
            background_tasks.add_task(cron_scheduler.start_loop, handle_scheduled_task, log_to_ui)
        return {"status": "success", "message": "Đã kích hoạt Bộ hẹn giờ Khung Giờ Vàng."}
    else:
        cron_scheduler.stop()
        return {"status": "success", "message": "Đã tạm dừng Bộ hẹn giờ."}


# ==========================================
# SYSTEM ROUTES
# ==========================================

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        for log in logs_buffer[-50:]:
            await websocket.send_text(log)
        while True:
            await websocket.receive_text()
    except Exception:
        ws_manager.disconnect(websocket)

app.mount("/downloads", StaticFiles(directory=DOWNLOAD_DIR), name="downloads")
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
