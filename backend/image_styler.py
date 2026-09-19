import os
import io
import logging
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("ImageStyler")

class ImageStyler:
    @staticmethod
    def apply_frame_and_watermark(
        image_path: str,
        output_path: str,
        frame_type: str = "flashsale", # "flashsale", "freeship", "voucher"
        badge_text: str = "FREESHIP EXTRA",
        discount_tag: str = "-50%"
    ) -> bool:
        """Đóng khung tỷ lệ 1:1 và chèn nhãn sale bắt mắt cho ảnh sản phẩm."""
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGBA")
                
                # Chuẩn hóa về tỷ lệ vuông 1000x1000
                size = (1000, 1000)
                img = img.resize(size, Image.Resampling.LANCZOS)
                
                # Tạo lớp overlay để vẽ khung
                overlay = Image.new("RGBA", size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(overlay)
                
                border_width = 16
                if frame_type == "flashsale":
                    border_color = (238, 77, 45, 255) # Đỏ cam Shopee
                elif frame_type == "freeship":
                    border_color = (0, 182, 149, 255) # Xanh lá Freeship
                else:
                    border_color = (255, 180, 0, 255) # Vàng rực rỡ
                
                # 1. Vẽ 4 cạnh viền ngoài
                for i in range(border_width):
                    draw.rectangle([i, i, size[0] - 1 - i, size[1] - 1 - i], outline=border_color)
                
                # 2. Vẽ Banner trên đầu (Header Tag)
                banner_height = 65
                draw.rectangle([0, 0, size[0], banner_height], fill=border_color)
                
                # Vẽ text trên banner (fallback font mặc định)
                try:
                    font = ImageFont.load_default()
                except Exception:
                    font = None
                    
                draw.text((30, 20), f"🔥 {badge_text.upper()} 🔥", fill=(255, 255, 255, 255), font=font)
                
                # 3. Vẽ Tag Giảm giá góc phải
                if discount_tag:
                    tag_box = [size[0] - 160, 0, size[0], 90]
                    draw.rectangle(tag_box, fill=(255, 212, 36, 255))
                    draw.text((size[0] - 130, 30), f"GIẢM\n{discount_tag}", fill=(208, 1, 27, 255), font=font)
                
                # Ghép ảnh gốc và overlay
                final_img = Image.alpha_composite(img, overlay).convert("RGB")
                
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                final_img.save(output_path, "JPEG", quality=90)
                return True
        except Exception as e:
            logger.error(f"Lỗi đóng khung ảnh: {e}")
            return False

    @staticmethod
    def batch_process_folder(folder_path: str, frame_type: str = "flashsale", badge_text: str = "CHÍNH HÃNG 100%") -> int:
        """Đóng khung hàng loạt ảnh trong thư mục."""
        count = 0
        if not os.path.exists(folder_path):
            return 0
        files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        for f in files:
            in_file = os.path.join(folder_path, f)
            out_file = os.path.join(folder_path, f"framed_{f}")
            if ImageStyler.apply_frame_and_watermark(in_file, out_file, frame_type, badge_text):
                count += 1
        return count
