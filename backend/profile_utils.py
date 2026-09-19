import os
import logging
from typing import List

logger = logging.getLogger("ProfileUtils")

def resolve_profile_path(profile_dir: str) -> str:
    """
    Tìm kiếm và trả về đường dẫn thư mục profile Chrome/Playwright chính xác.
    Kiểm tra tuần tự:
    1. Đường dẫn tuyệt đối (nếu tồn tại)
    2. '03. ShopeeVideoAutoPoster/<profile_dir>'
    3. 'ShopeeVideoAutoPoster/<profile_dir>'
    4. '07. EcomOmniTool/browser_profiles/shopee/<profile_dir>'
    5. '07. EcomOmniTool/browser_profiles/tiktok/<profile_dir>'
    6. '07. EcomOmniTool/<profile_dir>'
    """
    if not profile_dir:
        return ""
        
    if os.path.isabs(profile_dir) and os.path.exists(profile_dir):
        return profile_dir

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_workspace = os.path.abspath(os.path.join(backend_dir, "..", ".."))
    ecom_dir = os.path.abspath(os.path.join(backend_dir, ".."))

    candidate_paths = [
        os.path.join(root_workspace, "03. ShopeeVideoAutoPoster", profile_dir),
        os.path.join(root_workspace, "ShopeeVideoAutoPoster", profile_dir),
        os.path.join(ecom_dir, "browser_profiles", "shopee", profile_dir),
        os.path.join(ecom_dir, "browser_profiles", "tiktok", profile_dir),
        os.path.join(ecom_dir, profile_dir),
        os.path.abspath(profile_dir)
    ]

    for p in candidate_paths:
        if os.path.exists(p):
            return p

    # Nếu chưa tồn tại, ưu tiên tạo trong 03. ShopeeVideoAutoPoster nếu thư mục đó tồn tại, nếu không thì tạo trong browser_profiles
    poster_dir = os.path.join(root_workspace, "03. ShopeeVideoAutoPoster")
    if os.path.exists(poster_dir):
        return os.path.join(poster_dir, profile_dir)
        
    return os.path.join(ecom_dir, "browser_profiles", "shopee", profile_dir)

def get_shared_config_dir() -> str:
    """Trả về thư mục cấu hình dùng chung (ưu tiên 03. ShopeeVideoAutoPoster/config hoặc 07. EcomOmniTool/config)."""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_workspace = os.path.abspath(os.path.join(backend_dir, "..", ".."))
    ecom_dir = os.path.abspath(os.path.join(backend_dir, ".."))

    candidates = [
        os.path.join(root_workspace, "03. ShopeeVideoAutoPoster", "config"),
        os.path.join(root_workspace, "ShopeeVideoAutoPoster", "config"),
        os.path.join(ecom_dir, "config")
    ]

    for c in candidates:
        if os.path.exists(c):
            return c

    default_dir = os.path.join(ecom_dir, "config")
    os.makedirs(default_dir, exist_ok=True)
    return default_dir
