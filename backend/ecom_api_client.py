import hmac
import hashlib
import time
import json
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger("EcomAPIClient")

class ShopeeOpenAPI:
    """Shopee Open Platform API v2 Client"""
    BASE_URL = "https://partner.shopeemobile.com"
    TEST_URL = "https://partner.test-stable.shopeemobile.com"

    def __init__(
        self,
        partner_id: int,
        partner_key: str,
        shop_id: int,
        access_token: str,
        is_test: bool = False
    ):
        self.partner_id = int(partner_id)
        self.partner_key = str(partner_key).strip()
        self.shop_id = int(shop_id)
        self.access_token = str(access_token).strip()
        self.host = self.TEST_URL if is_test else self.BASE_URL

    def _generate_sign(self, path: str, timestamp: int) -> str:
        """Tạo chữ ký HMAC-SHA256 cho Shopee Open API v2"""
        base_str = f"{self.partner_id}{path}{timestamp}{self.access_token}{self.shop_id}"
        sign = hmac.new(
            self.partner_key.encode("utf-8"),
            base_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return sign

    def get_products(self, page_size: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Lấy danh sách sản phẩm chính thức từ Shopee Open API"""
        timestamp = int(time.time())
        path = "/api/v2/product/get_item_list"
        sign = self._generate_sign(path, timestamp)

        url = f"{self.host}{path}?partner_id={self.partner_id}&timestamp={timestamp}&access_token={self.access_token}&shop_id={self.shop_id}&sign={sign}&page_size={page_size}&offset={offset}&item_status=NORMAL"

        try:
            res = requests.get(url, timeout=15)
            data = res.json()
            if data.get("error"):
                logger.error(f"Shopee API Error get_item_list: {data.get('message')}")
                return []

            item_list = data.get("response", {}).get("item", [])
            if not item_list:
                return []

            item_ids = [it.get("item_id") for it in item_list]
            return self.get_items_detail(item_ids)
        except Exception as e:
            logger.error(f"Lỗi gọi Shopee get_item_list: {e}")
            return []

    def get_items_detail(self, item_ids: List[int]) -> List[Dict[str, Any]]:
        """Lấy thông tin chi tiết tên, ảnh, giá, tồn kho của sản phẩm"""
        if not item_ids:
            return []

        timestamp = int(time.time())
        path = "/api/v2/product/get_item_base_info"
        sign = self._generate_sign(path, timestamp)

        item_id_list_str = ",".join(str(i) for i in item_ids[:50])
        url = f"{self.host}{path}?partner_id={self.partner_id}&timestamp={timestamp}&access_token={self.access_token}&shop_id={self.shop_id}&sign={sign}&item_id_list={item_id_list_str}"

        products = []
        try:
            res = requests.get(url, timeout=20)
            data = res.json()
            items_info = data.get("response", {}).get("item_list", [])

            for it in items_info:
                name = it.get("item_name", "")
                image_info = it.get("image", {})
                img_list = image_info.get("image_url_list", []) or []
                img_url = img_list[0] if img_list else ""
                
                price_info = it.get("price_info", [{}])[0]
                price = price_info.get("current_price", 0)
                
                stock_info = it.get("stock_info_v2", {}).get("summary_info", {})
                total_stock = stock_info.get("total_available_stock", 0)

                products.append({
                    "id": str(it.get("item_id")),
                    "name": name,
                    "image": img_url,
                    "price": f"{float(price):,.0f} đ" if price > 1000 else str(price),
                    "stock": str(total_stock),
                    "is_boosted": False,
                    "boost_status": "Sẵn sàng (Official API)"
                })
            return products
        except Exception as e:
            logger.error(f"Lỗi gọi Shopee get_item_base_info: {e}")
            return []

    def boost_product(self, item_id_list: List[int]) -> Dict[str, Any]:
        """Đẩy sản phẩm chính thức qua Shopee Open API"""
        timestamp = int(time.time())
        path = "/api/v2/product/boost_item"
        sign = self._generate_sign(path, timestamp)

        url = f"{self.host}{path}?partner_id={self.partner_id}&timestamp={timestamp}&access_token={self.access_token}&shop_id={self.shop_id}&sign={sign}"
        payload = {"item_id_list": item_id_list[:5]}

        try:
            res = requests.post(url, json=payload, timeout=15)
            return res.json()
        except Exception as e:
            return {"error": "request_failed", "message": str(e)}


class TikTokShopAPI:
    """TikTok Shop Open API Client"""
    BASE_URL = "https://open-api.tiktokglobalshop.com"

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        access_token: str,
        shop_cipher: str
    ):
        self.app_key = str(app_key).strip()
        self.app_secret = str(app_secret).strip()
        self.access_token = str(access_token).strip()
        self.shop_cipher = str(shop_cipher).strip()

    def _generate_sign(self, path: str, timestamp: int, params: dict) -> str:
        """Tạo chữ ký SHA256 cho TikTok Shop API"""
        sorted_params = sorted([(k, v) for k, v in params.items() if k != "sign"])
        param_str = "".join([f"{k}{v}" for k, v in sorted_params])
        sign_base = f"{self.app_secret}{path}{param_str}{self.app_secret}"
        return hmac.new(self.app_secret.encode(), sign_base.encode(), hashlib.sha256).hexdigest()

    def get_products(self, page_size: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách sản phẩm từ TikTok Shop API"""
        timestamp = int(time.time())
        path = "/product/202309/products/search"
        params = {
            "app_key": self.app_key,
            "timestamp": timestamp,
            "shop_cipher": self.shop_cipher,
            "page_size": page_size
        }
        sign = self._generate_sign(path, timestamp, params)
        params["sign"] = sign

        headers = {
            "x-tts-access-token": self.access_token,
            "Content-Type": "application/json"
        }

        try:
            res = requests.post(f"{self.BASE_URL}{path}", params=params, headers=headers, json={}, timeout=15)
            data = res.json()
            products_list = data.get("data", {}).get("products", []) or []
            
            result = []
            for p in products_list:
                name = p.get("title", "")
                main_img = (p.get("main_images", [{}])[0]).get("url_list", [""])[0] if p.get("main_images") else ""
                skus = p.get("skus", [])
                price = skus[0].get("price", {}).get("original_price", "0") if skus else "0"
                stock = sum(int(s.get("stock_infos", [{}])[0].get("available_stock", 0)) for s in skus if s.get("stock_infos"))

                result.append({
                    "id": str(p.get("id")),
                    "name": name,
                    "image": main_img,
                    "price": f"{float(price):,.0f} đ" if str(price).replace('.','').isdigit() and float(price) > 1000 else str(price),
                    "stock": str(stock),
                    "is_boosted": False,
                    "boost_status": "TikTok Shop"
                })
            return result
        except Exception as e:
            logger.error(f"Lỗi gọi TikTok Shop API: {e}")
            return []


class MCPClientBridge:
    """Kết nối với MCP Server (Model Context Protocol) để tương tác sàn TMĐT"""
    def __init__(self, mcp_url: str = "http://127.0.0.1:7777/hub/mcp", auth_token: str = ""):
        self.mcp_url = mcp_url
        self.auth_token = auth_token

    def call_tool(self, tool_name: str, arguments: dict) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        try:
            res = requests.post(self.mcp_url, json=payload, headers=headers, timeout=20)
            return res.json().get("result")
        except Exception as e:
            logger.error(f"Lỗi gọi MCP Tool {tool_name}: {e}")
            return None
